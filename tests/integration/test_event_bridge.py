import json
import uuid
from datetime import datetime
from time import sleep
from typing import Any, Dict, Tuple

import boto3
import requests
from requests_aws4auth import AWS4Auth

import limits.utils as utils
from limits.manager import PerCustomerLimit

TEST_CUSTOMER_ID = uuid.uuid1().hex.upper()


def gen_test_event(req_id: str) -> Tuple[str, Dict[Any, Any]]:
    trx_id = uuid.uuid1().hex
    detail = json.dumps(
        {
            "customer_id": TEST_CUSTOMER_ID,
            "account_id": "RANDOM_ACCOUNT_ID",
            "transaction_id": trx_id,
            "transfer_amount": 1234.56,
            "prev_balance": 10000.00,
            "prev_avail_balance": 10000.00,
            "new_balance": 11234.56,
            "new_avail_balance": 11234.56,
            "currency": "SGD",
            "memo": "to some random account",
            "transaction_date": "2022-03-11",
            "status": "completed",
            "limits_req_id": req_id,
        }
    )

    event = {
        "Time": datetime.now(),
        "Source": "service.fund_transfer",
        "DetailType": "transfer",
        "EventBusName": "default",
        "Detail": detail,
    }

    return trx_id, event


def send_fund_transfer_event(req_id: str) -> str:
    trx_id, rand_event = gen_test_event(req_id)

    client = boto3.client("events")
    response = client.put_events(Entries=[rand_event])

    assert response["FailedEntryCount"] == 0

    return trx_id


def test_confirm_rquest_event(api_auth: AWS4Auth, api_base_url: str) -> None:
    manager = PerCustomerLimit(TEST_CUSTOMER_ID)
    cutoff_time = utils.iso_timestamp(offset=30)

    response = requests.post(
        f"{api_base_url}customers/{TEST_CUSTOMER_ID}/limits", json={"req_amount": 1000}, auth=api_auth
    )
    assert response.status_code == 201

    limit_req_id = response.json()["req_id"]

    outstanding_reqs = manager._requests_prior(cutoff_time)
    assert limit_req_id in outstanding_reqs

    trx_id = send_fund_transfer_event(limit_req_id)

    # try n times with gradual delay backoff
    for i in range(6):
        sleep(5 * i)
        outstanding_reqs = manager._requests_prior(cutoff_time)
        if limit_req_id not in outstanding_reqs:
            return
        else:
            print("requests returned:", outstanding_reqs)

    assert False, f"event {trx_id} not processed in time"
