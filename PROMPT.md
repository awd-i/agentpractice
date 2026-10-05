# Context Window Management

## Background

Our agents talk to customers over long conversations. On every turn we send the
conversation history to an LLM, but the model has a fixed context window. When
the history gets too long, we need to decide what to send.

## Task

Implement `trim(messages, budget)`.

Each message looks like:

```python
{"id": 3, "role": "user", "tokens": 42}
```

`role` is one of `system`, `user`, `assistant`, `tool`. `messages` is in
chronological order. Return the list of messages to send, in their original
order, with total tokens <= `budget`.

Requirements:

1. The system prompt (`messages[0]`) must always be included.
2. Recent context matters most. Prefer the newest messages.
3. The conversation sent to the model should read coherently, without gaps in
   the recent history.

Feel free to ask clarifying questions before you start.

## Follow-ups (interviewer reveals one at a time)

1. Some messages are marked `"pinned": True` (e.g. the customer's order number).
   These must always be sent.
2. An assistant message that calls a tool and the tool's result share a
   `tool_call_id`. The model API rejects one without the other.
3. Silently dropping context confuses the model. When messages are dropped,
   insert a short summary message after the system prompt. Assume it costs 20
   tokens.
4. Conversations can run to thousands of turns, and `trim` is called on every
   one. How would you avoid recomputing from scratch each time?
