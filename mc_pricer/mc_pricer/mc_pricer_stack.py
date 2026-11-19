import json
from pathlib import Path

from aws_cdk import (
    Duration,
    Stack,
    TimeZone,
    CfnOutput,
    RemovalPolicy,
    Size,
    aws_s3 as s3,
    aws_ecr as ecr,
    aws_iam as iam,
    aws_ec2 as ec2,
    aws_batch as batch,
    aws_ecs as ecs,
    aws_logs as logs,
    aws_lambda as lambda_,
    aws_ssm as ssm,
    aws_stepfunctions as sfn,
    aws_stepfunctions_tasks as tasks,
    aws_scheduler as scheduler,
    aws_scheduler_targets as scheduler_targets,
)
from constructs import Construct

class McPricerStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The code that defines your stack goes here

        bucket = s3.Bucket(
            self, "ResultsBucket",
            bucket_name="mc-pricer-bucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )
        
        repository = ecr.Repository(
            self, "PricerImageRepository",
            repository_name="mc-pricer",
            removal_policy=RemovalPolicy.DESTROY,
            empty_on_delete=True,
            lifecycle_rules=[ecr.LifecycleRule(
                description="Keep only the 5 most recent images",
                max_image_count=5
            )]
        )
        
        worker_job_role = iam.Role(
            self, "McWorkerJobRole",
            assumed_by=iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
            role_name="mc-worker-job-role"
        )
        bucket.grant_put(worker_job_role)
        
        aggregator_job_role = iam.Role(
            self, "McAggregatorJobRole",
            assumed_by=iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
            role_name="mc-aggregator-job-role"
        )
        bucket.grant_read(aggregator_job_role)
        bucket.grant_put(aggregator_job_role)
        
        execution_role = iam.Role(
            self, "ExecutionRole",
            assumed_by=iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
            role_name="mc-execution-role",
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name('service-role/AmazonECSTaskExecutionRolePolicy')
            ]
        )
        
        vpc = ec2.Vpc(
            self, "McVPC",
            ip_addresses=ec2.IpAddresses.cidr("10.0.0.0/16"),
            nat_gateways=0,
            max_azs=2,
            subnet_configuration=[
                ec2.SubnetConfiguration(
                    name="public",
                    subnet_type=ec2.SubnetType.PUBLIC,
                    cidr_mask=24,
                )
            ],
        )
        
        security_group = ec2.SecurityGroup(
            self, "McWorkerSecurityGroup",
            vpc=vpc,
            description="Batch workers: outbound only",
            allow_all_outbound=True
        )

        compute_environment = batch.FargateComputeEnvironment(
            self, "McComputeEnvironment",
            compute_environment_name="mc-pricer-compute-env",
            vpc=vpc,
            vpc_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PUBLIC),
            security_groups=[security_group],
            maxv_cpus=128
        )

        job_queue = batch.JobQueue(
            self, "McJobQueue",
            job_queue_name="mc-pricer-job-queue",
            compute_environments=[batch.OrderedComputeEnvironment(
                compute_environment=compute_environment,
                order=1
            )]
        )

        # worker and aggregator share one image, deploy.sh pushes it as :latest
        image = ecs.ContainerImage.from_ecr_repository(repository, "latest")

        # DESTROY because log groups default to RETAIN and would outlive cdk destroy
        job_logs = logs.LogGroup(
            self, "McJobLogs",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY
        )

        worker_job_definition = batch.EcsJobDefinition(
            self, "McWorkerJobDefinition",
            job_definition_name="mc-pricer-job-definition",
            container=batch.EcsFargateContainerDefinition(
                self, "McWorkerContainer",
                image=image,
                cpu=0.5,
                memory=Size.mebibytes(1024),
                assign_public_ip=True,
                job_role=worker_job_role,
                execution_role=execution_role,
                environment={"s3_bucket": bucket.bucket_name},
                logging=ecs.LogDriver.aws_logs(stream_prefix="worker", log_group=job_logs)
            )
        )

        aggregator_job_definition = batch.EcsJobDefinition(
            self, "McAggregatorJobDefinition",
            job_definition_name="mc-pricer-aggregator-job-definition",
            container=batch.EcsFargateContainerDefinition(
                self, "McAggregatorContainer",
                image=image,
                command=["python3", "aggregate.py"],
                cpu=0.25,
                memory=Size.mebibytes(1024),
                assign_public_ip=True,
                job_role=aggregator_job_role,
                execution_role=execution_role,
                environment={"s3_bucket": bucket.bucket_name},
                logging=ecs.LogDriver.aws_logs(stream_prefix="aggregator", log_group=job_logs)
            )
        )

        # FetchMarketData: fetches the ticker's prices from Tiingo, writes a dated snapshot to S3
        # and returns the config with real S0 and sigma - the first state of the run
        # the key is created by hand (CloudFormation can't create SecureStrings), so import it by name
        tiingo_api_key = ssm.StringParameter.from_secure_string_parameter_attributes(
            self, "TiingoApiKey",
            parameter_name="/mc-pricer/tiingo-api-key"
        )
        market_data_logs = logs.LogGroup(
            self, "FetchMarketDataLogs",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY
        )
        fetch_market_data = lambda_.Function(
            self, "FetchMarketData",
            function_name="mc-pricer-fetch-market-data",
            runtime=lambda_.Runtime.PYTHON_3_12,
            # only the handler goes in the zip - it needs nothing beyond what the runtime provides
            code=lambda_.Code.from_asset(
                str(Path(__file__).parents[2] / "market_data"),
                exclude=["__pycache__"]
            ),
            handler="handler.handler",
            timeout=Duration.seconds(30),
            environment={
                "s3_bucket": bucket.bucket_name,
                "api_key_parameter": tiingo_api_key.parameter_name,
            },
            log_group=market_data_logs
        )
        # read just this parameter - the default aws/ssm key decrypts for any caller SSM allows
        tiingo_api_key.grant_read(fetch_market_data)
        # write snapshots, but no reading or deleting run results
        bucket.grant_put(fetch_market_data)

        # a run as a state machine: fetch market data, then the worker array job, then the
        # aggregator once every worker has succeeded. The execution input is a config like
        # config/base.json
        run_fetch = tasks.LambdaInvoke(
            self, "FetchMarketDataTask",
            lambda_function=fetch_market_data,
            # the state's output is just what the handler returns - the config with S0, sigma
            # and market_as_of added - instead of a wrapper with it under Payload
            payload_response_only=True
        )
        # Tiingo being down or slow is worth waiting out. Errors are named after the Python
        # exception, and ValueError (too little history) or KeyError (no ticker) aren't retried
        # because trying again won't fix them
        run_fetch.add_retry(
            errors=["HTTPError", "URLError", "TimeoutError"],
            interval=Duration.seconds(30),
            max_attempts=3,
            backoff_rate=2
        )

        # the execution name is unique per run, so it doubles as the run_id
        run_id = sfn.JsonPath.execution_name

        # the env vars main.py reads, copied from the config. Batch only takes string values,
        # and States.Format turns the config's numbers into strings
        config_keys = ["S0", "K", "T", "t", "rf", "sigma",
                       "num_workers", "num_simulations", "iterations", "root_seed",
                       "ticker", "market_as_of"]
        worker_environment = {key: sfn.JsonPath.format("{}", sfn.JsonPath.string_at(f"$.{key}"))
                              for key in config_keys}
        worker_environment["run_id"] = run_id

        # BatchSubmitJob defaults to the .sync integration, so each step waits for its job to
        # finish and fails if the job fails
        run_workers = tasks.BatchSubmitJob(
            self, "RunWorkers",
            job_name="mc-pricer-job",
            job_queue_arn=job_queue.job_queue_arn,
            job_definition_arn=worker_job_definition.job_definition_arn,
            array_size=sfn.JsonPath.number_at("$.num_workers"),
            container_overrides=tasks.BatchContainerOverrides(environment=worker_environment),
            # keep the config as the state's data rather than replacing it with Batch's response
            result_path=sfn.JsonPath.DISCARD
        )

        run_aggregator = tasks.BatchSubmitJob(
            self, "RunAggregator",
            job_name="mc-pricer-aggregate-job",
            job_queue_arn=job_queue.job_queue_arn,
            job_definition_arn=aggregator_job_definition.job_definition_arn,
            container_overrides=tasks.BatchContainerOverrides(environment={"run_id": run_id}),
            result_path=sfn.JsonPath.DISCARD
        )

        state_machine = sfn.StateMachine(
            self, "McRunStateMachine",
            state_machine_name="mc-pricer-run",
            definition_body=sfn.DefinitionBody.from_chainable(
                run_fetch.next(run_workers).next(run_aggregator)
            ),
            # Batch jobs have no timeout of their own, so stop a stuck run from waiting forever
            timeout=Duration.hours(3)
        )
        # when an execution is stopped or times out, Step Functions tries to terminate the
        # Batch job it's waiting on - without this, stopped runs leave their jobs running
        state_machine.add_to_role_policy(iam.PolicyStatement(
            actions=["batch:TerminateJob"],
            resources=[self.format_arn(service="batch", resource="job", resource_name="*")]
        ))

        # nightly run with config/base.json, read at synth time so the file stays the one
        # source of truth - edit it and cdk deploy, and the next night uses the new values
        base_config = json.loads((Path(__file__).parents[2] / "config" / "base.json").read_text())
        scheduler.Schedule(
            self, "NightlyRunSchedule",
            description="Nightly VaR run with config/base.json",
            # 06:00 London is hours after the US close (21:00 London) so Tiingo has published it.
            # Tuesday to Saturday covers the Monday to Friday closes - Sunday and Monday mornings
            # would only re-price Friday's close.
            # cron in UTC would shift by an hour with daylight saving, so pin the time zone
            schedule=scheduler.ScheduleExpression.cron(
                hour="6", minute="0", week_day="TUE-SAT", time_zone=TimeZone.EUROPE_LONDON
            ),
            target=scheduler_targets.StepFunctionsStartExecution(
                state_machine,
                input=scheduler.ScheduleTargetInput.from_object(base_config)
            )
        )

        # cdk deploy writes these to stack-outputs.json (outputsFile in cdk.json) for the shell scripts
        CfnOutput(self, "McPricerImage", value=repository.repository_uri)
        CfnOutput(self, "BucketName", value=bucket.bucket_name)
        CfnOutput(self, "JobQueueName", value=job_queue.job_queue_name)
        CfnOutput(self, "WorkerJobDefinitionArn", value=worker_job_definition.job_definition_arn)
        CfnOutput(self, "AggregatorJobDefinitionArn", value=aggregator_job_definition.job_definition_arn)
        CfnOutput(self, "StateMachineArn", value=state_machine.state_machine_arn)
        