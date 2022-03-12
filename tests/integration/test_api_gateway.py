import requests


def test_new_request(api_auth, api_base_url):
    response = requests.post(f"{api_base_url}customers/11223344/limits", json={"req_amount": 1000}, auth=api_auth)

    assert response.status_code == 201
    assert response.json()["req_id"]

    response = requests.get(f"{api_base_url}customers/11223344/limits", json={"req_amount": 1000}, auth=api_auth)
    assert response.status_code == 200
