import os

import aws_cdk as cdk

from limits_stack import LimitsStack

stack_name = os.environ.get("TESTING_STACK_NAME", "LimitsStack")
app = cdk.App()
LimitsStack(app, stack_name).build()
app.synth()
