# Order lifecycle

```
PLACED --pay--> PAID --fulfill--> FULFILLING --ship--> SHIPPED --deliver--> DELIVERED
  |              |                  |                                          |
  cancel         cancel             cancel                              request_return
  v              v                  v                                          v
CANCELLED     CANCELLED          CANCELLED                            RETURN_REQUESTED
                                                                      /            \
                                                        cancel_return              receive_return
                                                           v                            v
                                                       DELIVERED                     RETURNED

DELIVERED or RETURNED --refund (remaining reaches 0)--> REFUNDED
```

- Terminal states: `REFUNDED`, `CANCELLED`. No event is accepted in a terminal state (`IllegalTransition`).
- `apply(event, at)` follows the table above or raises `IllegalTransition`; the state does not change on failure.
- Cancelling a `PAID` order refunds it in full (`refunded_cents = total_cents`, note `auto refund on cancel`).
  Cancelling before payment refunds nothing. Cancel is not allowed once shipped.
- `refund(refund_id, amount, at)`:
  - idempotent: a `refund_id` seen before is a no-op and returns the current state
  - only from `DELIVERED` or `RETURNED`
  - amount must be positive and must not exceed `remaining_cents` (`ValueError`)
  - partial refunds keep the state; when `remaining_cents` reaches 0 the order becomes `REFUNDED`
- `can(event)` must agree with what `apply`/`refund` would accept.
- Every successful transition appends a `HistoryEntry`.
