"""HTTP-ish client for the orders service, with retries and idempotency.

Spec: docs/specs/api_client.md
"""
from __future__ import annotations

import random
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from .models import Order, OrderItem


class ApiError(Exception):
    def __init__(self, status: int, message: str = ""):
        super().__init__(f"{status}: {message}")
        self.status = status


class ApiTimeout(ApiError):
    def __init__(self, message: str = "timed out"):
        super().__init__(0, message)


RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 4
    base_delay: float = 0.2
    max_delay: float = 3.0
    budget_seconds: float = 10.0


def is_retryable(error: Exception) -> bool:
    if isinstance(error, ApiTimeout):
        return True
    if isinstance(error, ApiError):
        return error.status in RETRYABLE_STATUSES
    return False


def backoff_delay(policy: RetryPolicy, attempt: int, rng: random.Random) -> float:
    """Exponential backoff with +/-50% jitter. attempt is 1-based."""
    raw = policy.base_delay * (2 ** (attempt - 1))
    capped = min(raw, policy.max_delay)
    return capped * rng.uniform(0.5, 1.5)


def with_retry(
    fn: Callable[[], Any],
    policy: RetryPolicy = RetryPolicy(),
    *,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    rng: random.Random | None = None,
) -> Any:
    """Call fn until it succeeds, the attempts run out, or the time budget is spent."""
    rng = rng or random.Random()
    started = clock()
    attempt = 0
    while True:
        attempt += 1
        try:
            return fn()
        except Exception as error:
            if not is_retryable(error):
                raise
            if attempt >= policy.max_attempts:
                raise
            delay = backoff_delay(policy, attempt, rng)
            if clock() - started + delay > policy.budget_seconds:
                raise
            sleep(delay)


@dataclass
class Response:
    status: int
    body: Any = None
    headers: dict = field(default_factory=dict)


class FakeTransport:
    """Scripted transport. Each (method, path) has a queue of responses.

    A response can be a Response, an Exception instance (raised), or a
    callable taking the request body and returning either.
    """

    def __init__(self) -> None:
        self.scripts: dict[tuple[str, str], list] = {}
        self.calls: list[tuple[str, str, Any, dict]] = []
        self.refunds: dict[str, dict] = {}

    def script(self, method: str, path: str, *responses) -> None:
        self.scripts.setdefault((method, path), []).extend(responses)

    def request(self, method: str, path: str, body: Any = None, headers: dict | None = None) -> Response:
        headers = headers or {}
        self.calls.append((method, path, body, headers))
        queue = self.scripts.get((method, path))
        if not queue:
            raise ApiError(404, f"no script for {method} {path}")
        step = queue.pop(0) if len(queue) > 1 else queue[0]
        if callable(step) and not isinstance(step, Exception):
            step = step(body, headers)
        if isinstance(step, Exception):
            raise step
        return step


class OrdersAPI:
    def __init__(self, transport: FakeTransport, policy: RetryPolicy = RetryPolicy(), **retry_kwargs):
        self.transport = transport
        self.policy = policy
        self.retry_kwargs = retry_kwargs

    def _once(self, method: str, path: str, body: Any = None, headers: dict | None = None) -> Any:
        response = self.transport.request(method, path, body, headers)
        if response.status >= 400:
            raise ApiError(response.status, str(response.body))
        return response.body

    def _call(self, method: str, path: str, body: Any = None, headers: dict | None = None) -> Any:
        return with_retry(lambda: self._once(method, path, body, headers), self.policy, **self.retry_kwargs)

    def get_order(self, order_id: str) -> Order:
        payload = self._call("GET", f"/orders/{order_id}")
        return parse_order(payload)

    def list_orders(self, customer_id: str) -> list[dict]:
        """Follow `next_cursor` until the server says there is no more."""
        orders: list[dict] = []
        cursor: str | None = None
        while True:
            path = f"/customers/{customer_id}/orders"
            if cursor:
                path += f"?cursor={cursor}"
            page = self._call("GET", path)
            orders.extend(page["orders"])
            if not page.get("has_more"):
                break
            cursor = page["next_cursor"]
        return orders

    def issue_refund(self, order_id: str, amount_cents: int, idempotency_key: str | None = None) -> dict:
        """POST a refund. One key per logical refund, reused across retries."""
        key = idempotency_key or str(uuid.uuid4())
        body = {"order_id": order_id, "amount_cents": amount_cents}
        return self._call("POST", f"/orders/{order_id}/refunds", body, {"Idempotency-Key": key})


def parse_datetime(raw: str) -> datetime:
    """ISO 8601, 'Z' allowed. Naive timestamps are treated as UTC."""
    value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value


def parse_order(payload: dict) -> Order:
    items = [
        OrderItem(
            sku=item["sku"],
            quantity=int(item["quantity"]),
            unit_price_cents=int(item["unit_price_cents"]),
            final_sale=bool(item.get("final_sale", False)),
        )
        for item in payload["items"]
    ]
    delivered = payload.get("delivered_at")
    return Order(
        order_id=payload["order_id"],
        customer_id=payload["customer_id"],
        items=items,
        shipping_cents=int(payload.get("shipping_cents", 0)),
        placed_at=parse_datetime(payload["placed_at"]),
        delivered_at=parse_datetime(delivered) if delivered else None,
        status=payload.get("status", "placed"),
        refunded_cents=int(payload.get("refunded_cents", 0)),
    )
