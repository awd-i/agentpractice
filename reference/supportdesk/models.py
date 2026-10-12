from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Tier(str, Enum):
    BASIC = "basic"
    SILVER = "silver"
    PREMIUM = "premium"


TIER_RANK = {Tier.BASIC: 0, Tier.SILVER: 1, Tier.PREMIUM: 2}


def parse_tier(raw: str) -> Tier:
    """Accept any casing / surrounding whitespace ("  Premium ")."""
    value = (raw or "").strip().lower()
    for tier in Tier:
        if tier.value == value:
            return tier
    raise ValueError(f"unknown tier: {raw!r}")


@dataclass(frozen=True)
class Customer:
    customer_id: str
    email: str
    name: str
    tier: Tier


@dataclass(frozen=True)
class Product:
    sku: str
    name: str
    price_cents: int
    tags: tuple[str, ...] = ()
    final_sale: bool = False
    in_stock: int = 0


@dataclass(frozen=True)
class OrderItem:
    sku: str
    quantity: int
    unit_price_cents: int
    final_sale: bool = False

    @property
    def line_total_cents(self) -> int:
        return self.quantity * self.unit_price_cents


@dataclass
class Order:
    order_id: str
    customer_id: str
    items: list[OrderItem]
    shipping_cents: int
    placed_at: datetime
    delivered_at: datetime | None = None
    status: str = "placed"
    refunded_cents: int = 0

    @property
    def subtotal_cents(self) -> int:
        return sum(item.line_total_cents for item in self.items)

    @property
    def total_cents(self) -> int:
        return self.subtotal_cents + self.shipping_cents

    def item(self, sku: str) -> OrderItem:
        for item in self.items:
            if item.sku == sku:
                return item
        raise KeyError(sku)


@dataclass(frozen=True)
class RefundRequest:
    order_id: str
    sku: str
    quantity: int
    reason: str  # "changed_mind" | "defective" | "wrong_item" | "late"
    requested_at: datetime


@dataclass
class RefundDecision:
    outcome: str  # "approved" | "denied" | "needs_review"
    amount_cents: int = 0
    restocking_fee_cents: int = 0
    shipping_refund_cents: int = 0
    reasons: list[str] = field(default_factory=list)


def format_cents(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    return f"{sign}${cents // 100}.{cents % 100:02d}"
