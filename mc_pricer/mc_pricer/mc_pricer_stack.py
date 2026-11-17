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

        # a run as a state machine: the worker array job, then the aggregator once every worker
        # has succeeded. The execution input is a config like config/base.json
        # the execution name is unique per run, so it doubles as the run_id
        run_id = sfn.JsonPath.execution_name

        # the env vars main.py reads, copied from the config. Batch only takes string values,
        # and States.Format turns the config's numbers into strings
        config_keys = ["S0", "K", "T", "t", "rf", "sigma",
                       "num_workers", "num_simulations", "iterations", "root_seed"]
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
            definition_body=sfn.DefinitionBody.from_chainable(run_workers.next(run_aggregator)),
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
            # cron in UTC would shift by an hour with daylight saving, so pin the time zone
            schedule=scheduler.ScheduleExpression.cron(
                hour="22", minute="0", time_zone=TimeZone.EUROPE_LONDON
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
        