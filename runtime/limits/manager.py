from __future__ import annotations

import os
import time
from decimal import Decimal
from typing import Dict, List, Type, TypeVar, Union, cast

import boto3
import ulid
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from . import utils

logger, metrics, tracer = utils.init_monitoring()

__CUSTOMER_SORT_TKEY__ = "9" * 26  # ulid is 26 chars long

__params__: Dict[str, Union[str, int]] = {"default_customer_max_limit": 5000001, "default_request_ttl": 600}
__params__.update(utils.get_app_parameters())

"""
Table structure

TODO:
"""


class LimitManagementError(Exception):
    pass


T = TypeVar("T")


class PerCustomerLimit:
    """
    Manages per customer limit using data stored in DynamoDB.
    Table structure as follows:

    """

    __table__ = None  # dynamodb table
    avail_amount: Decimal
    max_amount: Decimal

    @classmethod
    def load(cls: Type[T], customer_id: str) -> T:
        inst = PerCustomerLimit(customer_id=customer_id)
        resp = inst._table_().get_item(Key=inst._cust_key())
        if resp["ResponseMetadata"]["HTTPStatusCode"] != 200 or "Item" not in resp:
            logger.info(f"unable to load Customer({customer_id}), received: %s", resp)
            raise LimitManagementError(f"customer {customer_id}) cannot be found")

        for key in ["avail_amount", "max_amount", "updated_at"]:
            setattr(inst, key, resp["Item"][key])

        return cast(T, inst)

    def __init__(self, customer_id: str = "", **kwargs) -> None:
        if not customer_id:
            raise LimitManagementError("customer_id is required")

        self.customer_id = customer_id
        self.avail_amount = Decimal(0)
        self.max_amount = Decimal(__params__["default_customer_max_limit"])
        for key in kwargs:
            setattr(self, key, kwargs[key])

    def request(self, req_amount: Decimal, expires_at: str = "") -> str:
        """
        Request a certain amount to be reserved from
        total limit. Usually called before a fund transfer
        is initiated
        """
        if req_amount <= 0:
            raise LimitManagementError("req_amount must be positive")
        elif req_amount > self.max_amount:
            raise LimitManagementError(f"Cannot request for more than max_amount for customer {self.customer_id}")

        if expires_at:
            expires_at = utils.iso_timestamp(int(__params__["default_request_ttl"]))

        self.avail_amount = self._upsert_customer(req_amount, self.max_amount)
        req_id = self._add_request(req_amount, expires_at)

        logger.info(f"request {req_id} created for customer {self.customer_id} for amount {str(req_amount)}")

        return req_id

    def release(self, req_id: str) -> None:
        """
        release the amount reserved by the previous request,
        typeically called when a fund transfer is unsuccessful
        """
        amount = self._del_request(req_id)
        # release means increase the avail_amount, so we pass negative req_amount
        self.avail_amount = self._upsert_customer(-1 * amount, self.max_amount)
        logger.info(f"released request {req_id} for customer {self.customer_id}")

    def confirm(self, req_id: str):
        """
        confirm the request has been consumed
        typeically called after a fund transfer is unsuccessful
        """
        amount = self._del_request(req_id)
        logger.info(f"confirm request {req_id} for customer {self.customer_id} of amount {str(amount)}")
        return amount

    def reset(self) -> None:
        """
        Reset available amount to max amount and remove all outstanding requests
        """
        raise LimitManagementError("not implemented")

    def reclaim_requests(self, cutoff_time: str = "") -> None:
        """
        delete requests from a list, and recover the requested amount
        typically used when requests are made but never
        """
        if not cutoff_time:
            cutoff_time = utils.iso_timestamp(offset=int(__params__["default_request_ttl"]))

        logger.info(f"trying to reclaim outstanding requests prior to {cutoff_time} for customer {self.customer_id}")

        req_ids = self._requests_prior(cutoff_time)
        if req_ids:
            with self._table_().batch_writer() as batch:
                for rid in req_ids:
                    batch.delete_item(Key=self._req_key(rid))

    ##
    ## private methods begin here ####
    ##

    # utlity methods to operator on DynamoDB

    @classmethod
    def _table_(cls):
        if cls.__table__ is None:
            ddb = boto3.resource("dynamodb")
            cls.__table__ = ddb.Table(os.environ.get("DDB_TABLE_NAME", ""))
        return cls.__table__

    def _upsert_customer(self, req_amount: Decimal, max_amount: Decimal, batch=None) -> Decimal:
        if batch is None:
            batch = self._table_()

        try:
            resp = batch.update_item(
                Key=self._cust_key(),
                UpdateExpression="""
                    SET updated_at = if_not_exists(updated_at, :now),
                        avail_amount = if_not_exists(avail_amount, :default_amount) - :req_amount,
                        max_amount = if_not_exists(max_amount, :default_amount)
                """,
                ConditionExpression=" attribute_not_exists(avail_amount) or avail_amount >= :req_amount",
                ExpressionAttributeValues={
                    ":now": utils.iso_timestamp(),
                    ":default_amount": max_amount,
                    ":req_amount": req_amount,
                },
                ReturnValues="ALL_NEW",
            )
            return resp["Attributes"]["avail_amount"]
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                # codnitional check fails means avail_amount is insufficient
                logger.info(
                    f"Insufficient avail_amount when requesting {str(req_amount)} for customer {self.customer_id}"
                )
                raise LimitManagementError("insufficent available amount")
            else:
                logger.info(f"Exception requesting {str(req_amount)} for customer {self.customer_id}, exception: %s", e)
                raise e

    def _add_request(self, req_amount: Decimal, expires_at: str, batch=None) -> str:
        if batch is None:
            batch = self._table_()

        req_id = str(ulid.new())
        batch.put_item(
            Item=self._req_key(req_id)
            | {
                "updated_at": utils.iso_timestamp(),
                "req_amount": req_amount,
                "expires_at": expires_at,
                "delete_at": int(time.time()) + 24 * 3600,  # DDB will delete the record automatically after 24 hours
            }
        )

        return req_id

    def _del_request(self, req_id: str, batch=None) -> Decimal:
        if batch is None:
            batch = self._table_()

        resp = self._table_().delete_item(
            Key=self._req_key(req_id),
            ReturnValues="ALL_OLD",
        )
        if resp["ResponseMetadata"]["HTTPStatusCode"] != 200 or "Attributes" not in resp:
            logger.info(f"unable to delete request {req_id}. response %s", resp)
            raise LimitManagementError("unable to delete request")

        return resp["Attributes"]["req_amount"]

    def _requests_prior(self, cutoff_time) -> List[str]:
        """return a list of req_id that have expires_at before since"""
        resp = self._table_().query(
            ProjectionExpression="request_id, req_amount",
            KeyConditionExpression=Key("customer_id").eq(self.customer_id),
            FilterExpression="expires_at < :cutoff_time",
            ExpressionAttributeValues={":cutoff_time": cutoff_time},
        )

        if "LastEvaluatedKey" in resp:
            logger.info(f"Customer({self.customer_id} requests_since {cutoff_time} returned more than 1 page")

        return [item["request_id"] for item in resp["Items"]]

    #### helper methods ####
    def _req_key(self, alloc_id: str) -> Dict[str, str]:
        return {"customer_id": self.customer_id, "request_id": alloc_id}

    def _cust_key(self) -> Dict[str, str]:
        return {"customer_id": self.customer_id, "request_id": __CUSTOMER_SORT_TKEY__}

    def __eq__(self, other) -> bool:
        return (
            self.customer_id == other.customer_id
            and self.avail_amount == other.avail_amount
            and self.max_amount == other.max_amount
        )

    def __str__(self) -> str:
        return f"PerCustomerLimit(customer_id:{self.customer_id},avail:{self.avail_amount},max:{self.max_amount})"
