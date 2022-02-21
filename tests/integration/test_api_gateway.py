import requests


def test_new_request(api_base_url, cognito_access_token):
    print(
        f"""
    {api_base_url}
    {cognito_access_token}
    """
    )

    headers = {"Authorization": f"Bearer {cognito_access_token}"}
    url = f"{api_base_url}/customers/11223344/limits"
    response = requests.post(url, json={"req_amount": 1000}, headers=headers)

    assert response.status_code == 201
    assert response.json()["req_id"]
