import base64
import json
import os

import boto3
import pytest
from botocore.exceptions import ClientError
from pycognito import Cognito


@pytest.fixture(scope="session", autouse=True)
def api_base_url() -> str:
    region = os.environ.get("TESTING_REGION", "us-west-2")
    stack = os.environ.get("TESTING_STACK_NAME", "LimitsStack")
    client = boto3.client("cloudformation", region_name=region)

    try:
        response = client.describe_stacks(StackName=stack)
    except ClientError as e:
        raise Exception(f"Cannot find stack {stack} in region {region}") from e

    stack_outputs = response["Stacks"][0]["Outputs"]
    api_outputs = [item for item in stack_outputs if "ApiGatewayToLambdaLambdaRestApiEndpoint" in item["OutputKey"]]
    return api_outputs[0]["OutputValue"]


@pytest.fixture
def cognito_access_token() -> str:
    """
    get an access token from AWS Cognito and then use it call HttpApi
    with JWT authorizer

    the authorizer needs the following setup in order to work:
    1. the issuer URL should match the iss attribute in the token
    2. the audience should match the scope in the token
    """
    pool_id = os.environ.get("COGNITO_POOL_ID", "")
    client_id = os.environ.get("COGNITO_CLIENT_ID", "")
    client_secret = os.environ.get("COGNITO_CLIENT_SECRET", "")
    credential = os.environ.get("COGNITO_LOGIN_CREDENTIAL", "")
    if not all([credential, client_id, client_secret, pool_id]):
        raise Exception("please specifcy set Cognito parameters in environment variables")

    cred_dict = json.loads(credential)
    user = Cognito(pool_id, client_id, client_secret=client_secret, username=cred_dict["username"])
    user.authenticate(password=cred_dict["password"])
    access_token = user.access_token

    jwt = base64.standard_b64decode(access_token.split(".")[1])
    print(f"{json.dumps(json.loads(jwt), indent=4)}")

    return access_token
