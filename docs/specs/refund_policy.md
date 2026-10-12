# Refund policy (the flowchart)

Inputs: the order, the customer (with tier), and the request (sku, quantity, reason, requested_at).
Outputs: `outcome` in `approved | denied | needs_review`, `amount_cents`, `restocking_fee_cents`,
`shipping_refund_cents`, and a list of `reasons`.

Walk the boxes in order. The first denial wins.

1. Reason must be one of `changed_mind`, `defective`, `wrong_item`, `late`. Otherwise deny.
2. Order status must be `delivered`, `return_requested` or `returned`. Otherwise deny.
3. The SKU must be on the order. Otherwise deny.
4. Quantity must be between 1 and the quantity ordered, inclusive. Otherwise deny.
5. `defective` means reason is `defective` or `wrong_item`.
6. Window, measured from `delivered_at` to `requested_at`, inclusive of the last day:
   - defective: 90 days for every tier
   - otherwise by tier: basic 14, silver 30, premium 60
   Outside the window: deny.
7. Final sale items are only refundable when defective. Otherwise deny.
8. `base = unit_price * quantity`.
9. Restocking fee, only when not defective: basic 10%, silver 5%, premium 0%, rounded half up to the cent.
10. Shipping is refunded only when the request covers the whole order (single line item, full quantity) and
    either the item is defective or the customer is premium.
11. `amount = base - fee + shipping_refund`, capped at `order.total - order.refunded` (add a reason when capped).
12. Basic tier amounts strictly over $500.00 are `needs_review`. Everything else that reached this box is `approved`.

| tier    | window | fee | shipping back on whole order |
|---------|--------|-----|------------------------------|
| basic   | 14 d   | 10% | only if defective            |
| silver  | 30 d   | 5%  | only if defective            |
| premium | 60 d   | 0%  | always                       |
