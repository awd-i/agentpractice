# Agent loop

`AgentLoop(model, tools, max_steps=6, max_history=12).run(history, user_message)`

- Messages sent to the model are `[system prompt, *history, user message, *tool exchanges]`.
- Trimming keeps the system prompt plus the most recent `max_history` messages.
- The model is called at most `max_steps` times. If it never produces a final text, the result is an
  escalation (`escalated=True`) with `steps == max_steps`.
- A turn with text and no tool calls ends the loop.
- Tool calls run in order. The result (or an `{"error": ...}` observation) is appended as a `tool` message.
  Tool failures of any kind become observations; they never crash the loop.
- Argument validation: missing required arguments -> error observation; arguments with a declared type are
  coerced (`"2"` -> `2`) or rejected with `argument X must be int`.
- The `handoff` pseudo tool ends the loop immediately with `escalated=True` and the given message; later tool
  calls in the same turn are not executed.
- Memory: every `lookup_order` result's item SKUs are merged into `memory["ordered_items"]`, deduplicated, in
  first seen order.
- Grounding: every `$12.34` amount in the final text must equal a `*_cents` value found in some tool result;
  otherwise the reply is replaced by a double check message.
