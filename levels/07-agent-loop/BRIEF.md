# Level 07: the agent loop

Module: `workspace/supportdesk/agent.py`. Spec: `docs/specs/agent.md`.

Tickets from the agent platform team:

1. "max_steps=3 but the model was called 4 times before we gave up."
2. "A tool threw a RuntimeError and the whole request 500'd. Tool failures are supposed
   to be fed back to the model as observations."
3. "Long conversations lose the system prompt after trimming. The model starts
   answering as a generic assistant."
4. "Memory of what the customer ordered only remembers the last order we looked up."
5. "When the model calls handoff alongside another tool, the handoff is ignored and the
   model keeps going."
6. "The agent refuses to quote $180.00 even though decide_refund returned 18000 cents.
   It says it needs to double check with a teammate."

Fix the code so the tickets are resolved. Do not change the tests.
