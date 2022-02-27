import boto3
import pytest
import requests
from requests_aws4auth import AWS4Auth


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


def test_new_request(api_auth, api_base_url):
    response = requests.post(f"{api_base_url}customers/11223344/limits", json={"req_amount": 1000}, auth=api_auth)

    assert response.status_code == 201
    assert response.json()["req_id"]
