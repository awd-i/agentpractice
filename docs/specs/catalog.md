# Catalog helpers

`normalize_order_id(raw)`
: Accepts `#W1001`, `w1001`, ` W01001 `. Strips whitespace and a leading `#`, upper cases the prefix letter, drops leading zeros from the number. Returns `W1001`. Anything that is not one letter followed by digits raises `ValueError`.

`normalize_sku(raw)`
: SKUs are upper case and dash separated. Whitespace and underscores are separators: `ap_tent_02` and `ap tent 02` both become `AP-TENT-02`.

`find_product(products, sku)`
: Exact match on the normalised SKU, or `None`.

`search_products(products, query, in_stock_only=True, limit=5)`
: Score each product by how many distinct query words appear in its name or tags. Products with zero hits are never returned. Highest score first; ties keep catalog order. Out of stock products are skipped unless `in_stock_only=False`.

`similar_products(products, sku, limit=3)`
: In stock products that share the most tags with the anchor, most overlap first, ties in catalog order. The anchor itself is never returned. Unknown anchor returns `[]`.

`chunk(items, size)`
: Consecutive chunks of at most `size`; the last chunk may be shorter. `size <= 0` raises `ValueError`.

`mask_email(email)`
: Keep the first and last character of the local part, star out the middle: `alice.jones@example.com` -> `a*********s@example.com`. Local parts of one or two characters keep the first character only.
