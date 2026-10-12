import random
from datetime import UTC, datetime

import pytest

from supportdesk.api_client import (
    ApiError,
    ApiTimeout,
    FakeTransport,
    OrdersAPI,
    Response,
    RetryPolicy,
    backoff_delay,
    is_retryable,
    parse_datetime,
    parse_order,
    with_retry,
)


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def flaky(failures, result="ok"):
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if calls["n"] <= len(failures):
            raise failures[calls["n"] - 1]
        return result

    fn.calls = calls
    return fn


POLICY = RetryPolicy(max_attempts=4, base_delay=0.1, max_delay=1.0, budget_seconds=10.0)


def test_retries_server_errors_then_succeeds():
    clock = Clock()
    fn = flaky([ApiError(503), ApiError(500)])
    assert with_retry(fn, POLICY, sleep=clock.sleep, clock=clock, rng=random.Random(1)) == "ok"
    assert fn.calls["n"] == 3


def test_timeouts_and_429_are_retried():
    assert is_retryable(ApiTimeout())
    assert is_retryable(ApiError(429))
    clock = Clock()
    fn = flaky([ApiTimeout()])
    assert with_retry(fn, POLICY, sleep=clock.sleep, clock=clock, rng=random.Random(1)) == "ok"


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
def test_client_errors_are_not_retried(status):
    clock = Clock()
    fn = flaky([ApiError(status)])
    with pytest.raises(ApiError) as info:
        with_retry(fn, POLICY, sleep=clock.sleep, clock=clock)
    assert info.value.status == status
    assert fn.calls["n"] == 1


def test_gives_up_after_max_attempts_with_last_error():
    clock = Clock()
    fn = flaky([ApiError(500), ApiError(502), ApiError(503), ApiError(504), ApiError(500)])
    with pytest.raises(ApiError) as info:
        with_retry(fn, POLICY, sleep=clock.sleep, clock=clock, rng=random.Random(1))
    assert info.value.status == 504
    assert fn.calls["n"] == 4


def test_backoff_is_exponential_with_jitter_and_cap():
    rng = random.Random(7)
    delays = [backoff_delay(POLICY, attempt, rng) for attempt in (1, 2, 3, 4, 5, 6)]
    for attempt, delay in zip((1, 2, 3, 4), delays[:4], strict=True):
        nominal = 0.1 * 2 ** (attempt - 1)
        assert 0.5 * nominal <= delay <= 1.5 * nominal
    assert delays[5] <= 1.5 * 1.0
    many = {round(backoff_delay(POLICY, 1, rng), 6) for _ in range(20)}
    assert len(many) > 1  # jitter actually varies


def test_sleeps_between_attempts_not_after_last():
    clock = Clock()
    sleeps = []

    def sleep(s):
        sleeps.append(s)
        clock.sleep(s)

    fn = flaky([ApiError(500), ApiError(500), ApiError(500), ApiError(500)])
    with pytest.raises(ApiError):
        with_retry(fn, POLICY, sleep=sleep, clock=clock, rng=random.Random(3))
    assert len(sleeps) == 3


def test_time_budget_stops_retrying():
    clock = Clock()
    policy = RetryPolicy(max_attempts=10, base_delay=1.0, max_delay=1.0, budget_seconds=2.5)
    fn = flaky([ApiError(500)] * 9)
    with pytest.raises(ApiError):
        with_retry(fn, policy, sleep=clock.sleep, clock=clock, rng=random.Random(0))
    assert fn.calls["n"] <= 3
    assert clock.now <= policy.budget_seconds  # never sleep past the budget


@pytest.fixture
def api():
    transport = FakeTransport()
    clock = Clock()
    return OrdersAPI(transport, POLICY, sleep=clock.sleep, clock=clock, rng=random.Random(1)), transport


def test_list_orders_follows_cursor_to_the_end(api):
    client, transport = api
    first = Response(200, {"orders": [{"id": 1}, {"id": 2}], "has_more": True, "next_cursor": "p2"})
    transport.script("GET", "/customers/C1/orders", first)
    transport.script("GET", "/customers/C1/orders?cursor=p2", Response(200, {"orders": [{"id": 3}], "has_more": True, "next_cursor": "p3"}))
    transport.script("GET", "/customers/C1/orders?cursor=p3", Response(200, {"orders": [{"id": 4}], "has_more": False}))
    assert [o["id"] for o in client.list_orders("C1")] == [1, 2, 3, 4]
    assert len(transport.calls) == 3


def test_list_orders_single_page(api):
    client, transport = api
    transport.script("GET", "/customers/C1/orders", Response(200, {"orders": [], "has_more": False}))
    assert client.list_orders("C1") == []


def test_refund_retry_reuses_the_same_idempotency_key(api):
    client, transport = api
    seen = []

    def accept(body, headers):
        seen.append(headers["Idempotency-Key"])
        return Response(200, {"refund_id": "r1", "amount_cents": body["amount_cents"]})

    transport.script("POST", "/orders/W1/refunds", Response(503, "busy"), ApiTimeout(), accept)
    result = client.issue_refund("W1", 1800)
    assert result["amount_cents"] == 1800
    keys = {headers["Idempotency-Key"] for _, _, _, headers in transport.calls}
    assert len(keys) == 1
    assert seen == [keys.pop()]


def test_refund_uses_caller_key_when_given(api):
    client, transport = api
    transport.script("POST", "/orders/W1/refunds", Response(200, {"refund_id": "r1", "amount_cents": 5}))
    client.issue_refund("W1", 5, idempotency_key="abc")
    assert transport.calls[0][3]["Idempotency-Key"] == "abc"


def test_get_order_raises_on_404_without_retry(api):
    client, transport = api
    transport.script("GET", "/orders/W9", Response(404, "missing"))
    with pytest.raises(ApiError) as info:
        client.get_order("W9")
    assert info.value.status == 404
    assert len(transport.calls) == 1


def test_parse_datetime_handles_z_and_naive():
    assert parse_datetime("2026-05-01T12:00:00Z") == datetime(2026, 5, 1, 12, tzinfo=UTC)
    assert parse_datetime("2026-05-01T12:00:00") == datetime(2026, 5, 1, 12, tzinfo=UTC)
    assert parse_datetime("2026-05-01T05:00:00-07:00") == datetime(2026, 5, 1, 12, tzinfo=UTC)


def test_parse_order_coerces_types():
    order = parse_order(
        {
            "order_id": "W1",
            "customer_id": "C1",
            "items": [{"sku": "A", "quantity": "2", "unit_price_cents": "1500", "final_sale": 1}],
            "shipping_cents": "800",
            "placed_at": "2026-04-27T00:00:00Z",
            "delivered_at": "2026-05-01T00:00:00Z",
            "status": "delivered",
        }
    )
    assert order.items[0].quantity == 2 and order.items[0].final_sale is True
    assert order.subtotal_cents == 3000 and order.total_cents == 3800
    assert order.delivered_at.tzinfo is not None
    bare = parse_order({"order_id": "W2", "customer_id": "C1", "items": [], "placed_at": "2026-04-27T00:00:00Z"})
    assert bare.delivered_at is None
