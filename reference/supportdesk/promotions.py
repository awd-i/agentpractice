"""Promotion eligibility and application.

Spec: docs/specs/promotions.md
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, time
from zoneinfo import ZoneInfo

from .models import TIER_RANK, Tier

PACIFIC = ZoneInfo("America/Los_Angeles")


@dataclass(frozen=True)
class Promotion:
    code: str
    kind: str  # "percent" | "fixed" | "free_shipping"
    value: int = 0  # percent (0-100) or cents
    min_subtotal_cents: int = 0
    min_tier: Tier | None = None
    starts: datetime | None = None  # aware datetimes
    ends: datetime | None = None
    daily_window: tuple[time, time] | None = None  # Pacific local time, [start, end)
    max_discount_cents: int | None = None
    single_use: bool = False


@dataclass
class Cart:
    subtotal_cents: int
    shipping_cents: int
    tier: Tier
    customer_id: str
    codes: list[str] = field(default_factory=list)


@dataclass
class PromoResult:
    applied: list[str] = field(default_factory=list)
    rejected: dict[str, str] = field(default_factory=dict)
    discount_cents: int = 0
    shipping_cents: int = 0
    total_cents: int = 0


class PromotionStore:
    def __init__(self, promotions: list[Promotion]):
        self._by_code = {p.code.upper(): p for p in promotions}
        self._redeemed: set[tuple[str, str]] = set()

    def get(self, code: str) -> Promotion | None:
        return self._by_code.get((code or "").strip().upper())

    def already_redeemed(self, customer_id: str, code: str) -> bool:
        return (customer_id, code.upper()) in self._redeemed

    def mark_redeemed(self, customer_id: str, code: str) -> None:
        self._redeemed.add((customer_id, code.upper()))


def window_open(promo: Promotion, now: datetime) -> bool:
    """Date range and daily window checks, both evaluated in Pacific time."""
    if now.tzinfo is None:
        raise ValueError("now must be timezone aware")
    local = now.astimezone(PACIFIC)
    if promo.starts is not None and local < promo.starts.astimezone(PACIFIC):
        return False
    if promo.ends is not None and local >= promo.ends.astimezone(PACIFIC):
        return False
    if promo.daily_window is not None:
        start, end = promo.daily_window
        if not (start <= local.time() < end):
            return False
    return True


def check_eligibility(promo: Promotion, cart: Cart, now: datetime, store: PromotionStore) -> str | None:
    """Return a rejection reason, or None when the code can be applied."""
    if not window_open(promo, now):
        return "not active right now"
    if cart.subtotal_cents < promo.min_subtotal_cents:
        return f"needs a subtotal of at least {promo.min_subtotal_cents} cents"
    if promo.min_tier is not None and TIER_RANK[cart.tier] < TIER_RANK[promo.min_tier]:
        return f"requires {promo.min_tier.value} tier or above"
    if promo.single_use and store.already_redeemed(cart.customer_id, promo.code):
        return "already redeemed"
    return None


def apply_promotions(cart: Cart, now: datetime, store: PromotionStore) -> PromoResult:
    """Apply the codes on the cart.

    Rules (see spec): at most one percent/fixed code and at most one free
    shipping code; percent discounts are computed on the subtotal before
    fixed discounts; the discount never exceeds the subtotal; codes are
    evaluated in the order given and later duplicates of a kind are rejected.
    """
    result = PromoResult()
    money_code: Promotion | None = None
    shipping_code: Promotion | None = None

    for raw in cart.codes:
        promo = store.get(raw)
        if promo is None:
            result.rejected[raw] = "unknown code"
            continue
        reason = check_eligibility(promo, cart, now, store)
        if reason is not None:
            result.rejected[raw] = reason
            continue
        if promo.kind == "free_shipping":
            if shipping_code is not None:
                result.rejected[raw] = "only one shipping code per order"
                continue
            shipping_code = promo
        else:
            if money_code is not None:
                result.rejected[raw] = "only one discount code per order"
                continue
            money_code = promo
        result.applied.append(promo.code)

    discount = 0
    if money_code is not None:
        if money_code.kind == "percent":
            discount = (cart.subtotal_cents * money_code.value + 50) // 100
        elif money_code.kind == "fixed":
            discount = money_code.value
        if money_code.max_discount_cents is not None:
            discount = min(discount, money_code.max_discount_cents)
        discount = min(discount, cart.subtotal_cents)

    shipping = 0 if shipping_code is not None else cart.shipping_cents

    result.discount_cents = discount
    result.shipping_cents = shipping
    result.total_cents = cart.subtotal_cents - discount + shipping

    for code in result.applied:
        promo = store.get(code)
        if promo is not None and promo.single_use:
            store.mark_redeemed(cart.customer_id, code)
    return result
