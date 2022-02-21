import aws_cdk as cdk
import aws_cdk.assertions as assertions
import pytest
from aws_cdk.assertions import Template

from limits_stack import LimitsStack


@pytest.fixture(scope="session")
def stack() -> Template:
    app = cdk.App()
    stack = LimitsStack(app, "LimitsStack").build()
    return assertions.Template.from_stack(stack)


def test_iam_roles_created(stack) -> None:
    assert len(stack.find_resources("AWS::IAM::Role")) == 2


def test_lambda_created(stack) -> None:
    all_funcs = stack.find_resources("AWS::Lambda::Function")
    func = list(all_funcs.values())[0]
    assert "python" in func["Properties"]["Runtime"]
