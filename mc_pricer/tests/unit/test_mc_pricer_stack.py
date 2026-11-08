from fnmatch import fnmatch

import aws_cdk as cdk
import pytest
from aws_cdk.assertions import Template
import json

from mc_pricer.mc_pricer_stack import McPricerStack


# synthesize once and share across every test in this file
@pytest.fixture(scope="module")
def template():
    app = cdk.App()
    stack = McPricerStack(app, "TestStack")
    return Template.from_stack(stack)


def actions_for_role(template, role_name):
    # find the role's logical id by its physical name, then collect every action
    # in the IAM policies attached to it
    roles = template.find_resources("AWS::IAM::Role", {"Properties": {"RoleName": role_name}})
    assert len(roles) == 1, f"expected one role named {role_name}"
    role_id = next(iter(roles))

    actions = []
    for policy in template.find_resources("AWS::IAM::Policy").values():
        if {"Ref": role_id} not in policy["Properties"].get("Roles", []):
            continue
        for statement in policy["Properties"]["PolicyDocument"]["Statement"]:
            action = statement["Action"]
            actions += action if isinstance(action, list) else [action]
    return actions


def allows(actions, needed):
    # granted actions can be wildcards like s3:GetObject*, so match them like IAM does
    return any(fnmatch(needed, granted) for granted in actions)


def test_worker_role_can_write_but_not_read_s3(template):
    actions = actions_for_role(template, "mc-worker-job-role")

    # what main.py calls: upload_file and put_object
    assert allows(actions, "s3:PutObject")
    # workers must not be able to read other workers' pnl or the summary
    assert not allows(actions, "s3:GetObject")
    assert not allows(actions, "s3:ListBucket")
    # or delete them
    assert not allows(actions, "s3:DeleteObject")


def test_aggregator_can_read_and_write_s3(template):
    actions = actions_for_role(template, "mc-aggregator-job-role")

    # what aggregate.py calls: list_objects_v2, get_object and put_object
    assert allows(actions, "s3:ListBucket")
    assert allows(actions, "s3:GetObject")
    assert allows(actions, "s3:PutObject")
    # it never deletes, so it shouldn't be able to wipe a run's pnl arrays
    assert not allows(actions, "s3:DeleteObject")


def job_definitions(template):
    defs = template.find_resources("AWS::Batch::JobDefinition")
    assert len(defs) == 2, "expected a worker and an aggregator job definition"
    return [d["Properties"] for d in defs.values()]


def test_vpc_has_no_nat_gateway(template):
    # a NAT gateway costs ~$32/month even when idle - tasks use public IPs instead
    template.resource_count_is("AWS::EC2::NatGateway", 0)


def test_job_definitions_assign_public_ip(template):
    # without a NAT gateway, tasks need a public IP to pull from ECR and reach S3
    for props in job_definitions(template):
        assert props["ContainerProperties"]["NetworkConfiguration"]["AssignPublicIp"] == "ENABLED"


def test_job_definitions_pass_the_stack_bucket(template):
    # main.py and aggregate.py read the bucket from s3_bucket, so it must be this stack's bucket
    bucket_id = next(iter(template.find_resources("AWS::S3::Bucket")))
    for props in job_definitions(template):
        env = {e["Name"]: e["Value"] for e in props["ContainerProperties"]["Environment"]}
        assert env["s3_bucket"] == {"Ref": bucket_id}


def test_outputs_the_scripts_read_exist(template):
    # stack-outputs.sh looks these up by name, so renaming one breaks deploy.sh and the submit scripts
    outputs = template.find_outputs("*")
    for key in ["McPricerImage", "JobQueueName", "WorkerJobDefinitionArn", "AggregatorJobDefinitionArn"]:
        assert key in outputs, f"missing output {key}"

