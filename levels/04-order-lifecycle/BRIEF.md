# Level 04: the order lifecycle

Module: `workspace/supportdesk/orders.py`. Spec and diagram: `docs/specs/orders.md`.

Ops found these in the audit log:

1. "Order W2201 was cancelled after it had shipped. The warehouse cannot pull back
   a shipped parcel; cancel must stop being allowed once we ship."
2. "A paid order that was cancelled shows refunded_cents = 0, while an order cancelled
   before payment shows a full refund. Backwards."
3. "Payment provider retried the refund webhook for r-77 and we recorded the refund twice."
4. "Orders that have been refunded in full are still sitting in DELIVERED instead of REFUNDED."
5. "The UI offers the Refund button on shipped orders. `can('refund')` is saying yes."

Fix the code so the tickets are resolved. Do not change the tests.
