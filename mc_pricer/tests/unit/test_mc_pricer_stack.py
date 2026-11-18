from fnmatch import fnmatch
from pathlib import Path

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
    # find the role's logical id by its physical name, then collect its actions
    roles = template.find_resources("AWS::IAM::Role", {"Properties": {"RoleName": role_name}})
    assert len(roles) == 1, f"expected one role named {role_name}"
    return actions_for_role_id(template, next(iter(roles)))


def actions_for_role_id(template, role_id):
    # collect every action in the IAM policies attached to the role
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


def test_job_logs_go_to_a_group_that_expires(template):
    # without a log configuration jobs fall back to /aws/batch/job, which never expires
    groups = template.find_resources("AWS::Logs::LogGroup")
    for props in job_definitions(template):
        log_config = props["ContainerProperties"].get("LogConfiguration")
        assert log_config, "job definition has no log configuration"
        group_id = log_config["Options"]["awslogs-group"]["Ref"]
        # CDK's default is two years, so check for a deliberate short retention, not just any
        retention = groups[group_id]["Properties"].get("RetentionInDays")
        assert retention is not None, "job log group never expires"
        assert retention <= 30, f"job logs kept for {retention} days"


def test_outputs_the_scripts_read_exist(template):
    # stack-outputs.sh looks these up by name, so renaming one breaks deploy.sh and the submit scripts
    outputs = template.find_outputs("*")
    for key in ["McPricerImage", "JobQueueName", "WorkerJobDefinitionArn", "AggregatorJobDefinitionArn"]:
        assert key in outputs, f"missing output {key}"



BASE_CONFIG = json.loads((Path(__file__).parents[3] / "config" / "base.json").read_text())


def state_machine_definition(template):
    machines = template.find_resources("AWS::StepFunctions::StateMachine")
    assert len(machines) == 1, "expected one state machine"
    # the definition is a Fn::Join of strings and references to other resources -
    # swap each reference for a placeholder so the result parses as JSON
    parts = next(iter(machines.values()))["Properties"]["DefinitionString"]["Fn::Join"][1]
    return json.loads("".join(p if isinstance(p, str) else "REF" for p in parts))


def test_aggregator_runs_after_workers_finish(template):
    states = state_machine_definition(template)["States"]

    assert states["RunWorkers"]["Next"] == "RunAggregator"
    # .sync makes each step wait for its Batch job and fail if the job fails,
    # so the aggregator never runs after a failed fan-out
    for name in ["RunWorkers", "RunAggregator"]:
        assert states[name]["Resource"].endswith(":states:::batch:submitJob.sync"), f"{name} doesn't wait"
    assert states["RunWorkers"]["Parameters"]["ArrayProperties"]["Size.$"] == "$.num_workers"


def test_workers_and_aggregator_share_a_run_id(template):
    # the aggregator finds the workers' arrays by run_id, so both must use the same value
    states = state_machine_definition(template)["States"]
    for name in ["RunWorkers", "RunAggregator"]:
        env = {e["Name"]: e for e in states[name]["Parameters"]["ContainerOverrides"]["Environment"]}
        assert env["run_id"]["Value.$"] == "$$.Execution.Name"


def test_workers_get_every_config_value(template):
    # the state machine lists the config keys explicitly, so a key added to base.json
    # would otherwise never reach the workers
    states = state_machine_definition(template)["States"]
    env_names = {e["Name"] for e in states["RunWorkers"]["Parameters"]["ContainerOverrides"]["Environment"]}
    missing = set(BASE_CONFIG) - env_names
    assert not missing, f"config keys not passed to the workers: {missing}"


def test_nightly_schedule_runs_base_config_in_london_time(template):
    schedules = template.find_resources("AWS::Scheduler::Schedule")
    assert len(schedules) == 1, "expected one schedule"
    props = next(iter(schedules.values()))["Properties"]

    # a cron without a time zone is UTC and would shift by an hour with daylight saving
    assert props["ScheduleExpressionTimezone"] == "Europe/London"
    assert json.loads(props["Target"]["Input"]) == BASE_CONFIG


def test_stopping_a_run_can_terminate_its_jobs(template):
    # without TerminateJob, stopping an execution (or hitting its timeout) leaves the
    # Batch jobs running - they finish and keep costing money
    machine = next(iter(template.find_resources("AWS::StepFunctions::StateMachine").values()))
    role_id = machine["Properties"]["RoleArn"]["Fn::GetAtt"][0]
    assert allows(actions_for_role_id(template, role_id), "batch:TerminateJob")


def function_role_id(template, function_name):
    functions = template.find_resources("AWS::Lambda::Function", {"Properties": {"FunctionName": function_name}})
    assert len(functions) == 1, f"expected one function named {function_name}"
    return next(iter(functions.values()))["Properties"]["Role"]["Fn::GetAtt"][0]


def test_market_data_function_reads_its_key_and_writes_snapshots_only(template):
    actions = actions_for_role_id(template, function_role_id(template, "mc-pricer-fetch-market-data"))

    # what the handler calls: ssm get_parameter and s3 put_object
    assert allows(actions, "ssm:GetParameter")
    assert allows(actions, "s3:PutObject")
    # it has no reason to read or delete run results
    assert not allows(actions, "s3:GetObject")
    assert not allows(actions, "s3:DeleteObject")


def test_market_data_function_is_told_where_its_key_and_bucket_are(template):
    functions = template.find_resources("AWS::Lambda::Function", {"Properties": {"FunctionName": "mc-pricer-fetch-market-data"}})
    env = next(iter(functions.values()))["Properties"]["Environment"]["Variables"]
    bucket_id = next(iter(template.find_resources("AWS::S3::Bucket")))
    assert env["s3_bucket"] == {"Ref": bucket_id}
    assert env["api_key_parameter"] == "/mc-pricer/tiingo-api-key"
