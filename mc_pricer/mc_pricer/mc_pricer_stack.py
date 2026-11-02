from aws_cdk import (
    # Duration,
    Stack,
    CfnOutput,
    RemovalPolicy,
    aws_s3 as s3,
    aws_ecr as ecr,
    aws_iam as iam,
    aws_ec2 as ec2,
    
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
                description="Keep only the the 5 most recent images",
                max_image_count=5
            )]
        )
        
        worker_job_role = iam.Role(
            self, "McWorkerJobRole",
            assumed_by=iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
            role_name="mc-worker-job-role"
        )
        bucket.grant_write(worker_job_role)
        
        aggregator_job_role = iam.Role(
            self, "McAggregatorJobRole",
            assumed_by=iam.ServicePrincipal('ecs-tasks.amazonaws.com'),
            role_name="mc-aggregator-job-role"
        )
        bucket.grant_read_write(aggregator_job_role)
        
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
        
        # TODO - use this in deploy.sh
        CfnOutput(self, "McPricerImage", value=repository.repository_uri)
        CfnOutput(self, "BucketName", value=bucket.bucket_name)
        