"""Catalog helpers: normalising identifiers and searching products.

Spec: docs/specs/catalog.md
"""
from __future__ import annotations

import re
from collections.abc import Iterable

from .models import Product

ORDER_ID_RE = re.compile(r"^#?([A-Za-z])0*(\d+)$")


def normalize_order_id(raw: str) -> str:
    """"#w1001", "W1001", " w01001 " all become "W1001".

    Raises ValueError for anything that is not a letter followed by digits.
    """
    match = ORDER_ID_RE.match((raw or "").strip())
    if not match:
        raise ValueError(f"not an order id: {raw!r}")
    prefix, digits = match.groups()
    return f"{prefix.upper()}{int(digits)}"


def normalize_sku(raw: str) -> str:
    """SKUs are upper case, dash separated: "ap-tent-02" -> "AP-TENT-02"."""
    cleaned = re.sub(r"[\s_]+", "-", (raw or "").strip())
    return cleaned.upper()


def find_product(products: Iterable[Product], sku: str) -> Product | None:
    wanted = normalize_sku(sku)
    for product in products:
        if product.sku == wanted:
            return product
    return None


def search_products(
    products: Iterable[Product],
    query: str,
    *,
    in_stock_only: bool = True,
    limit: int = 5,
) -> list[Product]:
    """Rank products by how many query words hit the name or tags.

    Ties keep catalog order. Products with zero hits are never returned.
    """
    words = [w for w in re.split(r"\W+", query.lower()) if w]
    scored: list[tuple[int, int, Product]] = []
    for position, product in enumerate(products):
        if in_stock_only and product.in_stock <= 0:
            continue
        haystack = {product.name.lower(), *[t.lower() for t in product.tags]}
        name_words = set(re.split(r"\W+", product.name.lower()))
        score = 0
        for word in words:
            if word in name_words or word in haystack:
                score += 1
        if score > 0:
            scored.append((-score, position, product))
    scored.sort(key=lambda entry: (entry[0], entry[1]))
    return [product for _, _, product in scored[:limit]]


def similar_products(
    products: Iterable[Product],
    sku: str,
    *,
    limit: int = 3,
) -> list[Product]:
    """Fallback recommendations: in-stock products sharing the most tags."""
    catalog = list(products)
    anchor = find_product(catalog, sku)
    if anchor is None:
        return []
    anchor_tags = set(anchor.tags)
    ranked: list[tuple[int, int, Product]] = []
    for position, product in enumerate(catalog):
        if product.sku == anchor.sku or product.in_stock <= 0:
            continue
        overlap = len(anchor_tags & set(product.tags))
        if overlap:
            ranked.append((-overlap, position, product))
    ranked.sort(key=lambda entry: (entry[0], entry[1]))
    return [product for _, _, product in ranked[:limit]]


def chunk(items: list, size: int) -> list[list]:
    """Split a list into consecutive chunks of at most `size`."""
    if size <= 0:
        raise ValueError("size must be positive")
    return [items[i : i + size] for i in range(0, len(items), size)]


def mask_email(email: str) -> str:
    """"alice.jones@example.com" -> "a*********s@example.com"."""
    local, _, domain = email.partition("@")
    if len(local) <= 2:
        masked = local[0] + "*" * (len(local) - 1) if local else ""
    else:
        masked = local[0] + "*" * (len(local) - 2) + local[-1]
    return f"{masked}@{domain}"
