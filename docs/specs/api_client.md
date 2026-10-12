# Orders API client

`RetryPolicy(max_attempts=4, base_delay=0.2, max_delay=3.0, budget_seconds=10.0)`

`with_retry(fn, policy, sleep, clock, rng)`:

- Retry only `ApiTimeout`, HTTP 429, and 5xx. Any other error is raised immediately.
- At most `max_attempts` calls to `fn`; the last error is re-raised.
- Backoff before attempt n+1 is `min(base * 2^(n-1), max_delay)` scaled by uniform jitter in `[0.5, 1.5]`.
- Never sleep past the budget: if `elapsed + delay > budget_seconds`, raise instead of sleeping.
- No sleep after the final attempt.

`OrdersAPI`:

- `get_order(id)`: GET `/orders/{id}` and parse.
- `list_orders(customer_id)`: GET `/customers/{id}/orders`, then follow `next_cursor` (`?cursor=...`) while
  `has_more` is true. Every page's `orders` are included, including the last one.
- `issue_refund(order_id, amount_cents, idempotency_key=None)`: POST `/orders/{id}/refunds` with an
  `Idempotency-Key` header. One key per logical refund, generated once and reused on every retry.

Parsing: ISO 8601 timestamps, `Z` allowed, naive values are UTC. Numeric fields may arrive as strings.
