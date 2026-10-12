from datetime import UTC, datetime, time

import pytest

from supportdesk.models import Tier
from supportdesk.promotions import PACIFIC, Cart, Promotion, PromotionStore, apply_promotions, window_open

PROMOS = [
    Promotion("SAVE10", "percent", 10, min_subtotal_cents=5000),
    Promotion("FREESHIP", "free_shipping"),
    Promotion("VIP20", "percent", 20, min_tier=Tier.SILVER, max_discount_cents=3000),
    Promotion("FLAT5", "fixed", 500, single_use=True),
    Promotion("EARLY", "percent", 10, daily_window=(time(8, 0), time(10, 0))),
    Promotion(
        "SUMMER",
        "percent",
        15,
        starts=datetime(2026, 6, 1, 0, 0, tzinfo=PACIFIC),
        ends=datetime(2026, 7, 1, 0, 0, tzinfo=PACIFIC),
    ),
]
NOW = datetime(2026, 6, 15, 9, 0, tzinfo=PACIFIC)


def cart(codes, subtotal=10000, shipping=800, tier=Tier.BASIC, customer_id="C1"):
    return Cart(subtotal_cents=subtotal, shipping_cents=shipping, tier=tier, customer_id=customer_id, codes=list(codes))


@pytest.fixture
def store():
    return PromotionStore(PROMOS)


def test_percent_code_is_case_insensitive(store):
    r = apply_promotions(cart(["save10"]), NOW, store)
    assert r.applied == ["SAVE10"]
    assert (r.discount_cents, r.shipping_cents, r.total_cents) == (1000, 800, 9800)


def test_unknown_code_is_rejected(store):
    r = apply_promotions(cart(["NOPE"]), NOW, store)
    assert r.rejected == {"NOPE": "unknown code"}
    assert r.total_cents == 10800


def test_minimum_subtotal_boundary(store):
    assert "SAVE10" in apply_promotions(cart(["SAVE10"], subtotal=4999), NOW, store).rejected
    assert apply_promotions(cart(["SAVE10"], subtotal=5000), NOW, store).applied == ["SAVE10"]


def test_tier_gate_and_single_discount_code(store):
    basic = apply_promotions(cart(["SAVE10", "VIP20"]), NOW, store)
    assert basic.applied == ["SAVE10"]
    assert basic.rejected["VIP20"] == "requires silver tier or above"
    silver = apply_promotions(cart(["SAVE10", "VIP20"], tier=Tier.SILVER), NOW, store)
    assert silver.applied == ["SAVE10"]
    assert silver.rejected["VIP20"] == "only one discount code per order"
    premium = apply_promotions(cart(["VIP20"], tier=Tier.PREMIUM), NOW, store)
    assert premium.applied == ["VIP20"]


def test_max_discount_cap(store):
    r = apply_promotions(cart(["VIP20"], subtotal=20000, tier=Tier.SILVER), NOW, store)
    assert r.discount_cents == 3000


def test_free_shipping_stacks_with_a_discount_but_not_with_itself(store):
    r = apply_promotions(cart(["FREESHIP", "SAVE10"]), NOW, store)
    assert r.applied == ["FREESHIP", "SAVE10"]
    assert (r.discount_cents, r.shipping_cents, r.total_cents) == (1000, 0, 9000)
    r = apply_promotions(cart(["FREESHIP", "FREESHIP"]), NOW, store)
    assert r.applied == ["FREESHIP"]
    assert r.rejected["FREESHIP"] == "only one shipping code per order"


def test_single_use_code_is_per_customer(store):
    assert apply_promotions(cart(["FLAT5"]), NOW, store).applied == ["FLAT5"]
    second = apply_promotions(cart(["FLAT5"]), NOW, store)
    assert second.rejected["FLAT5"] == "already redeemed"
    assert apply_promotions(cart(["FLAT5"], customer_id="C2"), NOW, store).applied == ["FLAT5"]


def test_rejected_codes_are_not_marked_redeemed(store):
    r = apply_promotions(cart(["SAVE10", "FLAT5"]), NOW, store)
    assert r.rejected["FLAT5"] == "only one discount code per order"
    assert not store.already_redeemed("C1", "FLAT5")
    assert apply_promotions(cart(["FLAT5"]), NOW, store).applied == ["FLAT5"]
    assert store.already_redeemed("C1", "FLAT5")


def test_fixed_discount_never_exceeds_subtotal(store):
    r = apply_promotions(cart(["FLAT5"], subtotal=300), NOW, store)
    assert (r.discount_cents, r.total_cents) == (300, 800)


def test_percent_rounds_half_up(store):
    r = apply_promotions(cart(["SAVE10"], subtotal=5005), NOW, store)
    assert r.discount_cents == 501


@pytest.mark.parametrize(
    "now, expected",
    [
        (datetime(2026, 6, 15, 8, 0, tzinfo=PACIFIC), True),
        (datetime(2026, 6, 15, 9, 59, tzinfo=PACIFIC), True),
        (datetime(2026, 6, 15, 10, 0, tzinfo=PACIFIC), False),
        (datetime(2026, 6, 15, 7, 59, tzinfo=PACIFIC), False),
        (datetime(2026, 6, 15, 16, 30, tzinfo=UTC), True),  # 09:30 Pacific
        (datetime(2026, 6, 15, 9, 30, tzinfo=UTC), False),  # 02:30 Pacific
    ],
)
def test_daily_window_is_evaluated_in_pacific_time(now, expected):
    assert window_open(PROMOS[4], now) is expected


def test_date_range_end_is_exclusive():
    summer = PROMOS[5]
    assert window_open(summer, datetime(2026, 6, 30, 23, 59, tzinfo=PACIFIC)) is True
    assert window_open(summer, datetime(2026, 7, 1, 0, 0, tzinfo=PACIFIC)) is False
    assert window_open(summer, datetime(2026, 5, 31, 23, 59, tzinfo=PACIFIC)) is False


def test_naive_now_is_rejected():
    with pytest.raises(ValueError):
        window_open(PROMOS[4], datetime(2026, 6, 15, 9, 0))
