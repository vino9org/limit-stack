import json
import os.path

import app

events_path = os.path.abspath(os.path.dirname(__file__) + "/../../events")


def test_handler_for_apigateway(lambda_context):
    with open(f"{events_path}/event1.json", "r") as f:
        event = json.load(f)
        ret = app.lambda_handler(event, lambda_context)
        assert ret["statusCode"] == 201


def test_handler_for_eventbridge(lambda_context):
    with open(f"{events_path}/event2.json", "r") as f:
        event = json.load(f)
        ret = app.lambda_handler(event, lambda_context)
        assert ret is False
