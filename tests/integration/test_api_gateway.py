import requests
import requests_aws_iam_auth


def test_new_request(api_base_url):
    auth = requests_aws_iam_auth.ApiGateway()
    response = requests.post(f"{api_base_url}customers/11223344/limits", json={"req_amount": 1000}, auth=auth)

    assert response.status_code == 201
    assert response.json()["req_id"]
