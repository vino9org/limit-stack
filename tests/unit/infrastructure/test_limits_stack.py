import aws_cdk as core
import aws_cdk.assertions as assertions

from limits_stack import LimitsStack


def test_stack_created():
    app = core.App()
    stack = LimitsStack(app, "LimitsStack")
    template = assertions.Template.from_stack(stack)
    assert template
