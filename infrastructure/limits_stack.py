from os.path import abspath, dirname

from aws_cdk import Stack
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as _lambda
from aws_solutions_constructs.aws_apigateway_lambda import ApiGatewayToLambda
from aws_solutions_constructs.aws_lambda_dynamodb import LambdaToDynamoDB
from constructs import Construct


class LimitsStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

    def build(self):
        construct1 = self.lamdba_with_restapi()
        self.dynamodb_table_for_lambda(construct1.lambda_function)
        return self

    def lamdba_with_restapi(self) -> ApiGatewayToLambda:
        src_dir = abspath(dirname(abspath(__file__)) + "/../runtime")
        return ApiGatewayToLambda(
            self,
            f"{self.stack_name}-ApiGatewayToLambda",
            api_gateway_props=apigateway.RestApiProps(
                endpoint_configuration=apigateway.EndpointConfiguration(
                    types=[apigateway.EndpointType.REGIONAL],
                ),
            ),
            lambda_function_props=_lambda.FunctionProps(
                runtime=_lambda.Runtime.PYTHON_3_9,
                handler="app.lambda_handler",
                code=_lambda.Code.from_asset(src_dir),
                layers=[
                    _lambda.LayerVersion.from_layer_version_arn(
                        self,
                        "lambda-powertools-layer",
                        f"arn:aws:lambda:{Stack.of(self).region}:017000801446:layer:AWSLambdaPowertoolsPython:10",
                    )
                ],
                memory_size=512,
                architecture=_lambda.Architecture.ARM_64,
            ),
        )

    def dynamodb_table_for_lambda(self, lambda_func: _lambda.Function) -> LambdaToDynamoDB:
        return LambdaToDynamoDB(
            self,
            f"{self.stack_name}-LambdaToDynamoDB",
            existing_lambda_obj=lambda_func,
            dynamo_table_props=dynamodb.TableProps(
                partition_key=dynamodb.Attribute(name="customer_id", type=dynamodb.AttributeType.STRING),
                sort_key=dynamodb.Attribute(name="request_id", type=dynamodb.AttributeType.STRING),
                billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            ),
        )
