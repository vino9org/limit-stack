import json

import boto3


def test_confirm_rquest_event():
    client = boto3.client("events")
    response = client.put_events(
        Entries=[
            {
                "Source": "service.fund_transfer",
                "DetailType": "transfer",
                "Detail": json.dumps({"customer_id": "11223344", "req_id": "11111111", "status": "completed"}),
            },
        ]
    )
    assert response["ResponseMetadata"]["HTTPStatusCode"] == 200
