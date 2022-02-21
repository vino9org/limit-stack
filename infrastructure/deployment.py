import aws_cdk as cdk

from limits_stack import LimitsStack

app = cdk.App()
LimitsStack(app, "LimitsStack").build()
app.synth()
