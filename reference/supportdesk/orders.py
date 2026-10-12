"""Order lifecycle state machine.

Spec and diagram: docs/specs/orders.md
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class OrderState(str, Enum):
    PLACED = "placed"
    PAID = "paid"
    FULFILLING = "fulfilling"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    RETURN_REQUESTED = "return_requested"
    RETURNED = "returned"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


TERMINAL = {OrderState.REFUNDED, OrderState.CANCELLED}

TRANSITIONS: dict[tuple[OrderState, str], OrderState] = {
    (OrderState.PLACED, "pay"): OrderState.PAID,
    (OrderState.PAID, "fulfill"): OrderState.FULFILLING,
    (OrderState.FULFILLING, "ship"): OrderState.SHIPPED,
    (OrderState.SHIPPED, "deliver"): OrderState.DELIVERED,
    (OrderState.DELIVERED, "request_return"): OrderState.RETURN_REQUESTED,
    (OrderState.RETURN_REQUESTED, "receive_return"): OrderState.RETURNED,
    (OrderState.RETURN_REQUESTED, "cancel_return"): OrderState.DELIVERED,
    (OrderState.PLACED, "cancel"): OrderState.CANCELLED,
    (OrderState.PAID, "cancel"): OrderState.CANCELLED,
    (OrderState.FULFILLING, "cancel"): OrderState.CANCELLED,
}

REFUNDABLE_FROM = {OrderState.DELIVERED, OrderState.RETURNED}


class IllegalTransition(Exception):
    pass


@dataclass
class HistoryEntry:
    at: datetime
    event: str
    from_state: OrderState
    to_state: OrderState
    note: str = ""


@dataclass
class OrderLifecycle:
    order_id: str
    total_cents: int
    state: OrderState = OrderState.PLACED
    refunded_cents: int = 0
    refund_ids: set[str] = field(default_factory=set)
    history: list[HistoryEntry] = field(default_factory=list)

    @property
    def remaining_cents(self) -> int:
        return self.total_cents - self.refunded_cents

    def can(self, event: str) -> bool:
        if event == "refund":
            return self.state in REFUNDABLE_FROM and self.remaining_cents > 0
        return (self.state, event) in TRANSITIONS

    def apply(self, event: str, at: datetime, *, note: str = "") -> OrderState:
        if self.state in TERMINAL:
            raise IllegalTransition(f"{self.order_id} is {self.state.value}; no further events allowed")
        target = TRANSITIONS.get((self.state, event))
        if target is None:
            raise IllegalTransition(f"cannot {event} an order that is {self.state.value}")
        previous = self.state
        if event == "cancel" and previous == OrderState.PAID:
            # cancelling a paid order refunds it in full
            self.refunded_cents = self.total_cents
            note = note or "auto refund on cancel"
        self.state = target
        self.history.append(HistoryEntry(at, event, previous, target, note))
        return target

    def refund(self, refund_id: str, amount_cents: int, at: datetime) -> OrderState:
        """Record a refund. Same refund_id twice is a no-op (idempotent)."""
        if refund_id in self.refund_ids:
            return self.state
        if self.state not in REFUNDABLE_FROM:
            raise IllegalTransition(f"cannot refund an order that is {self.state.value}")
        if amount_cents <= 0:
            raise ValueError("refund amount must be positive")
        if amount_cents > self.remaining_cents:
            raise ValueError(
                f"refund of {amount_cents} exceeds remaining {self.remaining_cents} on {self.order_id}"
            )
        previous = self.state
        self.refunded_cents += amount_cents
        self.refund_ids.add(refund_id)
        if self.remaining_cents == 0:
            self.state = OrderState.REFUNDED
        self.history.append(HistoryEntry(at, "refund", previous, self.state, f"{refund_id}:{amount_cents}"))
        return self.state

    def replay(self, events: list[tuple[str, datetime]]) -> OrderState:
        for event, at in events:
            self.apply(event, at)
        return self.state


def latest_transition(lifecycle: OrderLifecycle, event: str) -> HistoryEntry | None:
    for entry in reversed(lifecycle.history):
        if entry.event == event:
            return entry
    return None
