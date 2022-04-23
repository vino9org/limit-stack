from os.path import abspath, dirname

from aws_cdk import CfnOutput, RemovalPolicy, Stack
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_events as events
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_logs as logs
from aws_cdk import aws_sam as sam
from aws_solutions_constructs.aws_apigateway_lambda import ApiGatewayToLambda
from aws_solutions_constructs.aws_eventbridge_lambda import EventbridgeToLambda
from aws_solutions_constructs.aws_lambda_dynamodb import LambdaToDynamoDB
from constructs import Construct


class LimitsStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

    def build(self):
        cons1 = self.lamdba_with_restapi()
        cons2 = self.dynamodb_table_for_lambda(cons1.lambda_function)
        self.event_bridge_trigger_for_lambda(cons1.lambda_function)

        CfnOutput(self, "LimitsTableName", value=cons2.dynamo_table.table_name)

        return self

    def lamdba_with_restapi(self) -> ApiGatewayToLambda:
        src_dir = abspath(dirname(abspath(__file__)) + "/../runtime")
        name = f"{self.stack_name}-restapi"
        return ApiGatewayToLambda(
            self,
            name,
            api_gateway_props=apigateway.RestApiProps(
                rest_api_name=name,
                default_method_options=apigateway.MethodOptions(
                    api_key_required=True,
                    authorization_type=apigateway.AuthorizationType.NONE,
                ),
                endpoint_configuration=apigateway.EndpointConfiguration(
                    types=[apigateway.EndpointType.REGIONAL],
                ),
            ),
            lambda_function_props=_lambda.FunctionProps(
                runtime=_lambda.Runtime.PYTHON_3_9,
                handler="app.lambda_handler",
                code=_lambda.Code.from_asset(src_dir),
                layers=[self.powertools_layer("1.24.2")],
                memory_size=512,
                architecture=_lambda.Architecture.ARM_64,
                log_retention=logs.RetentionDays.ONE_WEEK,
            ),
            log_group_props=logs.LogGroupProps(
                retention=logs.RetentionDays.ONE_WEEK,
            ),
        )

    def dynamodb_table_for_lambda(self, lambda_func: _lambda.Function) -> LambdaToDynamoDB:
        return LambdaToDynamoDB(
            self,
            f"{self.stack_name}-ddb",
            existing_lambda_obj=lambda_func,
            dynamo_table_props=dynamodb.TableProps(
                partition_key=dynamodb.Attribute(name="customer_id", type=dynamodb.AttributeType.STRING),
                sort_key=dynamodb.Attribute(name="request_id", type=dynamodb.AttributeType.STRING),
                billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
                removal_policy=RemovalPolicy.DESTROY,
            ),
        )

    def event_bridge_trigger_for_lambda(self, lambda_func: _lambda.Function) -> EventbridgeToLambda:
        return EventbridgeToLambda(
            self,
            f"{self.stack_name}-trigger",
            existing_lambda_obj=lambda_func,
            event_rule_props=events.RuleProps(
                enabled=True,
                event_pattern=events.EventPattern(
                    source=["service.fund_transfer"], detail_type=["transfer"], detail={"status": ["completed"]}
                ),
                rule_name=f"{self.stack_name}-limits-trigger",
            ),
        )

    def powertools_layer(self, version: str) -> _lambda.ILayerVersion:
        # Launches SAR App as CloudFormation nested stack and return Lambda Layer
        POWERTOOLS_BASE_NAME = "AWSLambdaPowertools"
        powertools_app = sam.CfnApplication(
            self,
            f"{POWERTOOLS_BASE_NAME}Application",
            location={  # type: ignore
                "applicationId": "arn:aws:serverlessrepo:eu-west-1:057560766410:applications/aws-lambda-powertools-python-layer-extras",  # noqa
                "semanticVersion": version,
            },
        )
        powertools_layer_arn = powertools_app.get_att("Outputs.LayerVersionArn").to_string()
        return _lambda.LayerVersion.from_layer_version_arn(self, f"{POWERTOOLS_BASE_NAME}", powertools_layer_arn)
