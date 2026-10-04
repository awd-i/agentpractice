"""Sierra drill: trim conversation history to a token budget.

Message: {"id": int, "role": "system"|"user"|"assistant"|"tool",
          "tokens": int, "pinned": bool (optional), "tool_call_id": str (optional)}

Part 1 (15m): keep messages[0] (system) always. Then keep the NEWEST messages
  that fit, contiguous: stop at the first one that doesn't fit (don't skip it
  to grab smaller older ones). Return in original order.
  Raise ValueError if the system message alone exceeds budget.
Part 2 (10m): pinned messages are always kept. Fill the rest newest-first, contiguous.
Part 3 (10m): assistant + tool messages sharing a tool_call_id are kept or dropped together.
Part 4 (10m, talk it out): if anything was dropped, insert a 20-token summary right
  after system listing dropped ids (it counts toward budget). How do you avoid
  O(n) work every turn in a long chat?
"""


def trim(messages, budget):
    # TODO
    raise NotImplementedError
