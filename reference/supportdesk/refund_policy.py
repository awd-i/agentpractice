"""Refund decision engine.

The flowchart this implements is in docs/specs/refund_policy.md. Read the
spec first; the code is supposed to match it exactly.
"""
from __future__ import annotations

from datetime import timedelta

from .models import (
    Customer,
    Order,
    RefundDecision,
    RefundRequest,
    Tier,
)

RETURN_WINDOW_DAYS = {Tier.BASIC: 14, Tier.SILVER: 30, Tier.PREMIUM: 60}
RESTOCKING_FEE_BPS = {Tier.BASIC: 1000, Tier.SILVER: 500, Tier.PREMIUM: 0}
DEFECTIVE_WINDOW_DAYS = 90
MANAGER_REVIEW_THRESHOLD_CENTS = 50_000
VALID_REASONS = ("changed_mind", "defective", "wrong_item", "late")


def _fee(amount_cents: int, bps: int) -> int:
    """Basis points of an amount, rounded half up to the nearest cent."""
    return (amount_cents * bps + 5_000) // 10_000


def decide_refund(order: Order, customer: Customer, request: RefundRequest) -> RefundDecision:
    decision = RefundDecision(outcome="denied")

    if request.reason not in VALID_REASONS:
        decision.reasons.append(f"unknown reason {request.reason!r}")
        return decision

    if order.status not in ("delivered", "return_requested", "returned"):
        decision.reasons.append(f"order is {order.status}, not delivered")
        return decision

    try:
        item = order.item(request.sku)
    except KeyError:
        decision.reasons.append(f"{request.sku} is not on order {order.order_id}")
        return decision

    if request.quantity < 1 or request.quantity > item.quantity:
        decision.reasons.append("quantity must be between 1 and the quantity ordered")
        return decision

    assert order.delivered_at is not None
    age = request.requested_at - order.delivered_at
    defective = request.reason in ("defective", "wrong_item")

    if defective:
        window = timedelta(days=DEFECTIVE_WINDOW_DAYS)
    else:
        window = timedelta(days=RETURN_WINDOW_DAYS[customer.tier])

    if age > window:
        decision.reasons.append(f"outside the {window.days} day window for {customer.tier.value}")
        return decision

    if item.final_sale and not defective:
        decision.reasons.append("final sale items can only be returned if defective")
        return decision

    base = item.unit_price_cents * request.quantity

    fee = 0
    if not defective:
        fee = _fee(base, RESTOCKING_FEE_BPS[customer.tier])

    shipping_refund = 0
    whole_order = request.quantity == item.quantity and len(order.items) == 1
    if whole_order and (defective or customer.tier == Tier.PREMIUM):
        shipping_refund = order.shipping_cents

    amount = base - fee + shipping_refund
    remaining = order.total_cents - order.refunded_cents
    if amount > remaining:
        decision.reasons.append("capped at the amount still refundable")
        amount = remaining

    decision.amount_cents = amount
    decision.restocking_fee_cents = fee
    decision.shipping_refund_cents = shipping_refund

    if customer.tier == Tier.BASIC and amount > MANAGER_REVIEW_THRESHOLD_CENTS:
        decision.outcome = "needs_review"
        decision.reasons.append("basic tier refunds over $500 need a manager")
        return decision

    decision.outcome = "approved"
    return decision
