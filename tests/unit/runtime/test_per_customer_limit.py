from decimal import Decimal

import pytest

import ulid
from limits import utils
from limits.manager import LimitManagementError, PerCustomerLimit


def test_cust_id():
    return ulid.new().str


@pytest.fixture
def limit():
    return PerCustomerLimit(customer_id=test_cust_id(), max_amount=Decimal(1000000))


def test_ctor(limit) -> None:
    cust_id = test_cust_id()
    max_amount = Decimal(1000000)

    # customer_id is required field
    with pytest.raises(LimitManagementError):
        PerCustomerLimit()

    # rand cust should not exist in database
    with pytest.raises(LimitManagementError):
        PerCustomerLimit.load(cust_id)

    # default max_amount is set
    limit = PerCustomerLimit(customer_id=cust_id)
    assert limit.customer_id == cust_id
    assert limit.max_amount

    # max_amount can be passed to ctor
    limit = PerCustomerLimit(customer_id=cust_id, max_amount=max_amount)
    assert limit.customer_id == cust_id
    assert limit.max_amount == max_amount


def test_request(limit) -> None:
    # successiful requests are saved in the DB
    req_amount = Decimal(1000)
    req_id_1 = limit.request(req_amount)
    req_id_2 = limit.request(req_amount * 2)
    assert req_id_1 and req_id_2
    assert limit, PerCustomerLimit.load(limit.customer_id)


def test_request_over_limit(limit) -> None:
    # requests for over the avail_amount will have no effect
    assert limit.request(Decimal(1000))
    limit_before = PerCustomerLimit.load(limit.customer_id)
    with pytest.raises(LimitManagementError):
        limit.request(limit.max_amount)
    limit_after = PerCustomerLimit.load(limit.customer_id)
    assert limit_before == limit_after


def test_request_invalid(limit) -> None:
    # cannot request for amount of 0 or less
    with pytest.raises(LimitManagementError):
        limit.request(Decimal(0))

    # cannot request for more than max_amount in one go
    with pytest.raises(LimitManagementError):
        limit.request(limit.max_amount + Decimal(1))


def test_release(limit) -> None:
    req_id = limit.request(Decimal(1000))
    assert req_id

    limit.release(req_id)
    actual_limit = PerCustomerLimit.load(limit.customer_id)
    assert limit == actual_limit
    assert actual_limit.avail_amount == actual_limit.max_amount


def test_release_invalid(limit) -> None:
    req_id = limit.request(Decimal(1000))
    bad_req_id = req_id[:-1]
    with pytest.raises(LimitManagementError):
        limit.release(bad_req_id)


def test_confirm(limit) -> None:
    """requests get deleted after confirmation"""
    now = utils.iso_timestamp(100000)

    req_id = limit.request(Decimal(1000))
    assert req_id

    limit.confirm(req_id)
    reqs_after = limit._requests_prior(now)
    assert reqs_after == []


def test_confirm_invalid(limit) -> None:
    """invalid confirm gets an exception"""
    req_id = limit.request(Decimal(1000))
    assert req_id

    bad_req_id = req_id[:-1]
    with pytest.raises(LimitManagementError):
        limit.confirm(bad_req_id)


def test_reclaim_requests(limit) -> None:
    # create 3 requsts, results will be returned by requests_since
    now = utils.iso_timestamp(100000)
    req_amount = Decimal(1000)
    req_id_1 = limit.request(req_amount)
    req_id_2 = limit.request(req_amount * 2)
    req_id_3 = limit.request(req_amount * 3)
    reqs_before = set(limit._requests_prior(now))
    assert reqs_before == {req_id_1, req_id_2, req_id_3}

    limit.reclaim_requests(now)
    reqs_after = limit._requests_prior(now)
    assert reqs_after == []
