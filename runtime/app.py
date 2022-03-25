import json
import sys
from decimal import Decimal
from typing import Any, Dict

from aws_lambda_powertools.event_handler.api_gateway import ApiGatewayResolver, ProxyEventType, Response
from aws_lambda_powertools.utilities.data_classes import EventBridgeEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
from botocore.exceptions import ClientError
from pydantic import BaseModel

from limits import utils
from limits.manager import LimitManagementError, PerCustomerLimit


class FundTransfer(BaseModel):
    transaction_id: str

    debit_customer_id: str
    debit_account_id: str
    debit_prev_balance: Decimal
    debit_prev_avail_balance: Decimal
    debit_balance: Decimal
    debit_avail_balance: Decimal

    credit_customer_id: str
    credit_account_id: str
    credit_prev_balance: Decimal
    credit_prev_avail_balance: Decimal
    credit_balance: Decimal
    credit_avail_balance: Decimal

    transfer_amount: Decimal
    currency: str
    memo: str
    transaction_date: str
    status: str

    limits_req_id: str


# handles serializatino of Decimal
class JSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        return json.JSONEncoder.default(self, obj)


logger, metrics, tracer = utils.init_monitoring()
app = ApiGatewayResolver(proxy_type=ProxyEventType.APIGatewayProxyEvent)


def response(status_code: int, body: Dict[str, Any]) -> Response:
    return Response(status_code, "application/json", json.dumps(body, cls=JSONEncoder))


@app.post("/customers/<customer_id>/limits")
@tracer.capture_method
def new_request(customer_id):
    if not app.current_event.body:
        return response(400, {"error": "invalid input parameters"})

    body = app.current_event.json_body
    req_amount = body["req_amount"]

    logger.info(f"new_request for {customer_id} of amount {req_amount}")
    req_id = PerCustomerLimit(customer_id).request(Decimal(str(req_amount)))
    return response(
        201,
        {
            "customer_id": customer_id,
            "action": "create",
            "req_id": req_id,
            "req_amount": req_amount,
        },
    )


@app.post("/customers/<customer_id>/limits/<req_id>/confirm")
@tracer.capture_method
def request_confirm(customer_id, req_id):
    req_amount = PerCustomerLimit(customer_id).confirm(req_id)
    return response(200, {"custome_id": customer_id, "action": "confirm", "req_amount": req_amount})


@app.delete("/customers/<customer_id>/limits/<req_id>")
@tracer.capture_method
def request_delete(customer_id, req_id):
    req_amount = PerCustomerLimit(customer_id).release(req_id)
    return response(200, {"custome_id": customer_id, "action": "release", "req_amount": req_amount})


@app.get("/customers/<customer_id>/limits")
def get_current_limits(customer_id):
    customer = PerCustomerLimit.load(customer_id)
    payload = {
        "custome_id": customer_id,
        "avail_amount": customer.avail_amount,
        "max_amount": customer.max_amount,
    }
    return response(200, payload)


@tracer.capture_method
def handle_event(transfer: FundTransfer) -> bool:
    # to prevent eventbridge from retrying requests
    # unneccessarily, we need to handle exceptions thrown
    # from processing logic
    try:
        customer_id = transfer.debit_customer_id
        req_id = transfer.limits_req_id
        request_confirm(customer_id, req_id)
        return True
    except KeyError:
        logger.info("event does not have req_id attribute set %s", transfer)
    except LimitManagementError as e:
        logger.info("exception during processing: %s", e)
    except ClientError as e:
        logger.info("AWS API exception during processing: %s", e)
    except:  # noqa
        logger.warning("Unexpected error:", sys.exc_info()[0])

    return False


def lambda_handler(event: Dict[str, Any], context: LambdaContext):
    logger.info(event)
    if "requestContext" in event:
        # treat this as an event from ApiGateway
        return app.resolve(event, context)
    else:
        # treat this event as an event from event bridge
        eb_event = EventBridgeEvent(event)
        transfer = FundTransfer(**eb_event.detail)
        return handle_event(transfer)
