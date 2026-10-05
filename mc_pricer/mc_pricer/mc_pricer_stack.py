from aws_cdk import (
    # Duration,
    Stack,
    CfnOutput,
    RemovalPolicy,
    aws_s3 as s3
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
        
        CfnOutput(self, "BucketName", value=bucket.bucket_name)