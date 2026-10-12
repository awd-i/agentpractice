# Conversation state machine

```
GREETING -> TRIAGE
TRIAGE   -> TRIAGE (unclear, up to MAX_CLARIFICATIONS times) | IDENTIFYING (refund / status) | RESOLVING (product) | ESCALATED (human, or too many unclear) | CLOSED (bye)
IDENTIFYING -> IDENTIFYING (still missing a slot) | VERIFYING (email + order id known) | ESCALATED (human)
VERIFYING   -> LOOKUP (ok) | IDENTIFYING (not ok, attempts left) | ESCALATED (MAX_VERIFY_ATTEMPTS failures)
LOOKUP      -> RESOLVING (refund intent) | TRIAGE (status intent) | ESCALATED (order not found)
RESOLVING   -> CONFIRMING (refund approved) | TRIAGE (denied, search results, refund issued) | ESCALATED (needs_review)
CONFIRMING  -> RESOLVING (yes -> issue_refund) | TRIAGE (no) | CONFIRMING (unclear)
timeout     -> CLOSED from any non terminal state
ESCALATED, CLOSED: terminal, every further event raises InvalidTransition
```

Events: `user_message(text)`, `tool_result(tool, result)`, `timeout`.
Actions: `reply(text)`, `tool_call(tool, args)`, `handoff(text)`.

Rules:

- `handle()` is all or nothing: if a handler raises, both `state` and `context` are restored.
- `_go()` only allows edges listed in `ALLOWED_TRANSITIONS`.
- Slots (`email`, `order_id`) accumulate across messages; a message that only has one of them never erases the other.
- `MAX_VERIFY_ATTEMPTS = 3`: the third failed verification escalates. A successful verification resets the counter.
  A failed verification drops only the `order_id` slot and asks for the order number again.
- `MAX_CLARIFICATIONS = 2`: two unclear messages are tolerated in TRIAGE; the third escalates.
- An approved refund is stored in `context["pending_refund"]` and must be confirmed with a yes/no.
  Yes issues it, no clears it, timeout clears it and closes the chat. No money moves without a yes.
- Order status replies read `Order W1001 is return requested.` (underscores become spaces).
