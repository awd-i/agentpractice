import pytest

from helpers import customer, order, request
from supportdesk.models import OrderItem, Tier
from supportdesk.refund_policy import decide_refund


def test_basic_changed_mind_inside_window_pays_restocking_fee():
    d = decide_refund(order(), customer(Tier.BASIC), request(days=10))
    assert d.outcome == "approved"
    assert d.restocking_fee_cents == 2000
    assert d.shipping_refund_cents == 0
    assert d.amount_cents == 18000


@pytest.mark.parametrize("tier, last_ok_day", [(Tier.BASIC, 14), (Tier.SILVER, 30), (Tier.PREMIUM, 60)])
def test_window_is_inclusive_of_the_last_day(tier, last_ok_day):
    assert decide_refund(order(), customer(tier), request(days=last_ok_day)).outcome == "approved"
    denied = decide_refund(order(), customer(tier), request(days=last_ok_day + 1))
    assert denied.outcome == "denied"
    assert any("window" in r for r in denied.reasons)


def test_silver_fee_is_five_percent():
    d = decide_refund(order(), customer(Tier.SILVER), request(days=20))
    assert (d.restocking_fee_cents, d.amount_cents) == (1000, 19000)


def test_premium_pays_no_fee_and_gets_shipping_back_on_whole_order():
    d = decide_refund(order(), customer(Tier.PREMIUM), request(days=45))
    assert d.outcome == "approved"
    assert (d.restocking_fee_cents, d.shipping_refund_cents, d.amount_cents) == (0, 1500, 21500)


def test_defective_gets_full_refund_and_shipping_for_any_tier_within_90_days():
    d = decide_refund(order(), customer(Tier.BASIC), request(days=80, reason="defective"))
    assert (d.outcome, d.amount_cents) == ("approved", 21500)
    assert decide_refund(order(), customer(Tier.BASIC), request(days=91, reason="defective")).outcome == "denied"


def test_wrong_item_counts_as_defective():
    d = decide_refund(order(), customer(Tier.BASIC), request(days=40, reason="wrong_item"))
    assert (d.outcome, d.restocking_fee_cents) == ("approved", 0)


def test_final_sale_only_refundable_when_defective():
    items = [OrderItem(sku="AP-TENT-02", quantity=1, unit_price_cents=20000, final_sale=True)]
    assert decide_refund(order(items), customer(Tier.PREMIUM), request(days=3)).outcome == "denied"
    assert decide_refund(order(items), customer(Tier.BASIC), request(days=3, reason="defective")).outcome == "approved"


def test_basic_refund_over_500_dollars_needs_manager():
    items = [OrderItem(sku="AP-TENT-02", quantity=1, unit_price_cents=60000)]
    basic = decide_refund(order(items), customer(Tier.BASIC), request(days=3))
    assert (basic.outcome, basic.amount_cents) == ("needs_review", 54000)
    silver = decide_refund(order(items), customer(Tier.SILVER), request(days=3))
    assert (silver.outcome, silver.amount_cents) == ("approved", 57000)


def test_basic_refund_of_exactly_500_dollars_is_approved():
    items = [OrderItem(sku="AP-TENT-02", quantity=1, unit_price_cents=50000)]
    d = decide_refund(order(items), customer(Tier.BASIC), request(days=3, reason="defective"), )
    # defective: no fee, shipping refunded -> 51500 which is over the line
    assert d.outcome == "needs_review"
    d = decide_refund(order(items, shipping=0), customer(Tier.BASIC), request(days=3, reason="defective"))
    assert (d.outcome, d.amount_cents) == ("approved", 50000)


def test_partial_quantity_refund_has_no_shipping():
    items = [OrderItem(sku="AP-SOCK-M", quantity=3, unit_price_cents=1000)]
    d = decide_refund(order(items), customer(Tier.PREMIUM), request(days=3, sku="AP-SOCK-M", qty=2))
    assert (d.amount_cents, d.shipping_refund_cents) == (2000, 0)
    d = decide_refund(order(items), customer(Tier.BASIC), request(days=3, sku="AP-SOCK-M", qty=2))
    assert (d.amount_cents, d.restocking_fee_cents) == (1800, 200)


def test_quantity_bounds():
    items = [OrderItem(sku="AP-SOCK-M", quantity=3, unit_price_cents=1000)]
    assert decide_refund(order(items), customer(), request(days=3, sku="AP-SOCK-M", qty=0)).outcome == "denied"
    assert decide_refund(order(items), customer(), request(days=3, sku="AP-SOCK-M", qty=4)).outcome == "denied"
    assert decide_refund(order(items), customer(), request(days=3, sku="AP-SOCK-M", qty=3)).outcome == "approved"


def test_refund_is_capped_at_amount_still_refundable():
    d = decide_refund(order(refunded=20000), customer(Tier.BASIC), request(days=3, reason="defective"))
    assert (d.outcome, d.amount_cents) == ("approved", 1500)
    assert any("capped" in r for r in d.reasons)


@pytest.mark.parametrize("status", ["placed", "paid", "shipped", "cancelled"])
def test_only_delivered_orders_are_refundable(status):
    assert decide_refund(order(status=status), customer(), request(days=1)).outcome == "denied"


def test_unknown_reason_and_unknown_sku_are_denied():
    assert decide_refund(order(), customer(), request(reason="bored")).outcome == "denied"
    assert decide_refund(order(), customer(), request(sku="AP-NOPE")).outcome == "denied"


def test_fee_rounds_half_up_to_the_cent():
    items = [OrderItem(sku="AP-SOCK-M", quantity=1, unit_price_cents=1005)]
    basic = decide_refund(order(items), customer(Tier.BASIC), request(days=1, sku="AP-SOCK-M"))
    assert (basic.restocking_fee_cents, basic.amount_cents) == (101, 904)
    silver = decide_refund(order(items), customer(Tier.SILVER), request(days=1, sku="AP-SOCK-M"))
    assert (silver.restocking_fee_cents, silver.amount_cents) == (50, 955)
