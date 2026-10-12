# Promotions

A `Promotion` has a `kind` (`percent`, `fixed`, `free_shipping`), a `value`, and optional gates:
`min_subtotal_cents` (inclusive), `min_tier` (this tier or above), `starts`/`ends` (aware datetimes,
start inclusive, end exclusive), `daily_window` (Pacific local time, `[start, end)`), `max_discount_cents`,
and `single_use` (once per customer).

All time checks are evaluated in America/Los_Angeles. `now` must be timezone aware; convert it,
do not relabel it. A naive `now` raises `ValueError`.

`apply_promotions(cart, now, store)` evaluates codes in the order given:

1. Unknown code: rejected `unknown code`.
2. Ineligible (closed window, subtotal too low, tier too low, already redeemed): rejected with the reason.
3. At most one money code (`percent` or `fixed`) and at most one `free_shipping` code. A second code of the
   same kind is rejected (`only one discount code per order` / `only one shipping code per order`).
4. Discount: percent of the subtotal rounded half up, or the fixed amount. Apply `max_discount_cents`, then
   never exceed the subtotal.
5. Shipping is zero when a shipping code applied.
6. `total = subtotal - discount + shipping`.
7. Only codes that actually applied are marked redeemed, and only if `single_use`.
