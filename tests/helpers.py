from datetime import UTC, datetime, timedelta

from supportdesk.models import Customer, Order, OrderItem, RefundRequest, Tier

DELIVERED = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)


def customer(tier=Tier.BASIC, customer_id="C1"):
    return Customer(customer_id=customer_id, email="alice@example.com", name="Alice", tier=tier)


def order(items=None, shipping=1500, status="delivered", refunded=0, order_id="W1001"):
    items = items or [OrderItem(sku="AP-TENT-02", quantity=1, unit_price_cents=20000)]
    return Order(
        order_id=order_id,
        customer_id="C1",
        items=items,
        shipping_cents=shipping,
        placed_at=DELIVERED - timedelta(days=4),
        delivered_at=DELIVERED if status in ("delivered", "return_requested", "returned") else None,
        status=status,
        refunded_cents=refunded,
    )


def request(days=10, sku="AP-TENT-02", qty=1, reason="changed_mind", order_id="W1001"):
    return RefundRequest(
        order_id=order_id,
        sku=sku,
        quantity=qty,
        reason=reason,
        requested_at=DELIVERED + timedelta(days=days),
    )
