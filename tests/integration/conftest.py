import os
from typing import List

import boto3
import pytest
from botocore.exceptions import ClientError
from requests_aws4auth import AWS4Auth

from limits.manager import PerCustomerLimit

_stack_outputs_: List[str] = []


def stack_outputs_for_key(key: str) -> List[str]:
    """
    helper funciton to get output values from a Cloudformation stack
    can be used by a fixture to retrieve output values and inject
    into tests

    e.g.

    # in conftest.py
    @pytest.fixture(scope="session")
    def api_base_url() -> str:
        return _stack_outputs__for_key("RestApiEndpoint")[0]

    # in tests
    import requests
    def test_restapi(api_base_url):
        response = requests.get(f"{api_base_url}/ping")
        assert response.status_code == 200

    """

    global _stack_outputs_

    region = os.environ.get("TESTING_REGION", "us-west-2")
    stack_name = os.environ.get("TESTING_STACK_NAME", "LimitsStack")
    client = boto3.client("cloudformation", region_name=region)

    if not _stack_outputs_:
        try:
            response = client.describe_stacks(StackName=stack_name)
            _stack_outputs_ = response["Stacks"][0]["Outputs"]
        except ClientError as e:
            raise Exception(f"Cannot find stack {stack_name} in region {region}") from e

    output_values = [item["OutputValue"] for item in _stack_outputs_ if key in item["OutputKey"]]  # type: ignore
    if not output_values:
        raise Exception(f"There is no output with key {key} in stack {stack_name} in region {region}")

    return output_values


@pytest.fixture(scope="session", autouse=True)
def ddb_table() -> None:
    ddb = boto3.resource("dynamodb")
    table_name = stack_outputs_for_key("LimitsTableName")[0]
    PerCustomerLimit.__table__ = ddb.Table(table_name)


@pytest.fixture(scope="session", autouse=True)
def api_base_url() -> str:
    return stack_outputs_for_key("RestApiEndpoint")[0]


@pytest.fixture(scope="session")
def api_auth() -> AWS4Auth:
    session = boto3.Session()
    credentials = session.get_credentials()
    return AWS4Auth(
        credentials.access_key,
        credentials.secret_key,
        session.region_name,
        "execute-api",
    )
