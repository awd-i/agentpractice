# Level 02: the refund flowchart

Module: `workspace/supportdesk/refund_policy.py`. Spec: `docs/specs/refund_policy.md`
(this is the flowchart; the code is supposed to implement it exactly).

Finance and support both filed tickets after the Friday deploy:

1. "A basic customer asked for a refund on the 14th day after delivery and was denied.
   Policy says 14 days inclusive."
2. "Silver customers are getting their shipping refunded on whole order returns.
   Only premium customers (and defective items) get shipping back."
3. "A defective final sale item was denied. Defective items are always refundable."
4. "Restocking fees are coming out one cent low on odd prices. Finance wants half up rounding."
5. "A basic tier refund of exactly $500.00 was routed to a manager. The threshold is
   strictly over $500."

Fix the code so the tickets are resolved. Do not change the tests.
