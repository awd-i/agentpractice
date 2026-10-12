# Level 06: the flaky orders API

Module: `workspace/supportdesk/api_client.py`. Spec: `docs/specs/api_client.md`.

On-call notes from last night:

1. "A 404 on GET /orders/W9 was retried four times with backoff. 4xx should fail fast."
2. "The policy says 4 attempts. Logs show 5 requests for one call."
3. "Customers with more than one page of orders are missing their most recent orders.
   The last page never makes it into the list."
4. "The payments team sees a fresh Idempotency-Key on every retry of a refund POST,
   so a timed-out refund was issued twice."
5. "All our retries hit the server at the same instant (thundering herd). Backoff is
   supposed to be jittered."

Fix the code so the tickets are resolved. Do not change the tests.
