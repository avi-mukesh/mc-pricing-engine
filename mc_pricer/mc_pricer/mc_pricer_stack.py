from aws_cdk import (
    # Duration,
    Stack,
    CfnOutput,
    RemovalPolicy,
    aws_s3 as s3,
    aws_ecr as ecr
)
from constructs import Construct

class McPricerStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # The code that defines your stack goes here

        bucket = s3.Bucket(
            self,
            "ResultsBucket",
            bucket_name="mc-pricer-bucket",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )
        
        repository = ecr.Repository(
            self,
            "PricerImageRepository",
            repository_name="mc-pricer",
            removal_policy=RemovalPolicy.DESTROY,
            empty_on_delete=True,
            lifecycle_rules=[ecr.LifecycleRule(
                description="Keep only the the 5 most recent images",
                max_image_count=5
            )]
        )
        
        # TODO - use this in deploy.sh
        CfnOutput(self, "McPricerImage", value=repository.repository_uri)
        CfnOutput(self, "BucketName", value=bucket.bucket_name)