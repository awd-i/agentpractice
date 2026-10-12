import pytest

from supportdesk.catalog import (
    chunk,
    find_product,
    mask_email,
    normalize_order_id,
    normalize_sku,
    search_products,
    similar_products,
)
from supportdesk.models import Product

CATALOG = [
    Product("AP-TENT-02", "Ridgeline 2P Tent", 20000, ("tent", "camping", "shelter"), in_stock=4),
    Product("AP-TENT-04", "Ridgeline 4P Tent", 32000, ("tent", "camping", "shelter", "family"), in_stock=0),
    Product("AP-BAG-20", "Summit 20F Sleeping Bag", 15000, ("sleeping", "camping", "bag"), in_stock=7),
    Product("AP-STOVE-1", "Ember Canister Stove", 6000, ("stove", "camping", "cooking"), in_stock=2),
    Product("AP-SOCK-M", "Merino Trail Socks", 1800, ("socks", "hiking", "apparel"), in_stock=50),
    Product("AP-TARP-1", "Ultralight Tarp", 9000, ("tarp", "shelter", "camping"), in_stock=1),
]


@pytest.mark.parametrize(
    "raw, expected",
    [("#W1001", "W1001"), ("w1001", "W1001"), (" W01001 ", "W1001"), ("#a7", "A7")],
)
def test_normalize_order_id(raw, expected):
    assert normalize_order_id(raw) == expected


@pytest.mark.parametrize("raw", ["", "1001", "WX1001", "W", "W-1001"])
def test_normalize_order_id_rejects_garbage(raw):
    with pytest.raises(ValueError):
        normalize_order_id(raw)


def test_normalize_sku():
    assert normalize_sku("ap-tent-02") == "AP-TENT-02"
    assert normalize_sku(" ap tent 02 ") == "AP-TENT-02"
    assert normalize_sku("ap_tent_02") == "AP-TENT-02"


def test_find_product_is_case_insensitive():
    assert find_product(CATALOG, "ap-stove-1").name == "Ember Canister Stove"
    assert find_product(CATALOG, "AP-NOPE") is None


def test_search_ranks_by_hits_and_keeps_catalog_order_on_ties():
    names = [p.name for p in search_products(CATALOG, "camping tent")]
    assert names[0] == "Ridgeline 2P Tent"
    assert "Ridgeline 4P Tent" not in names  # out of stock
    assert names[1:] == ["Summit 20F Sleeping Bag", "Ember Canister Stove", "Ultralight Tarp"]


def test_search_can_include_out_of_stock_and_respects_limit():
    results = search_products(CATALOG, "tent", in_stock_only=False, limit=1)
    assert [p.sku for p in results] == ["AP-TENT-02"]
    results = search_products(CATALOG, "tent", in_stock_only=False)
    assert [p.sku for p in results] == ["AP-TENT-02", "AP-TENT-04"]


def test_search_returns_nothing_for_no_hits():
    assert search_products(CATALOG, "kayak") == []


def test_similar_products_shares_tags_and_skips_anchor_and_out_of_stock():
    skus = [p.sku for p in similar_products(CATALOG, "AP-TENT-02")]
    assert skus == ["AP-TARP-1", "AP-BAG-20", "AP-STOVE-1"]
    assert similar_products(CATALOG, "AP-NOPE") == []


def test_chunk():
    assert chunk([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]
    assert chunk([], 3) == []
    assert chunk([1, 2], 5) == [[1, 2]]
    with pytest.raises(ValueError):
        chunk([1], 0)


def test_mask_email():
    assert mask_email("alice.jones@example.com") == "a*********s@example.com"
    assert mask_email("al@example.com") == "a*@example.com"
    assert mask_email("a@example.com") == "a@example.com"
