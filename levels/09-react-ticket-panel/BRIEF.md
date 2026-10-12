# Level 09: the ticket panel (TypeScript / React)

Code: `ts/workspace/src/`. Spec: `docs/specs/ticket_machine.md`.
Run the tests with `python dojo.py check` or `cd ts && DOJO_TARGET=workspace npx vitest`.

Front end QA filed these after the sprint:

1. "An agent closed ticket T-410 straight from in progress. Close is only allowed after resolve."
2. "A ticket got escalated to urgent on its second reopen. Policy is two reopens are fine, the third escalates."
3. "SLA countdowns jump back up whenever someone touches a ticket."
4. "The queue shows low priority tickets at the top."
5. "Typing JANE in the filter finds nothing, typing jane works."
6. "The SLA countdown on screen ticks once and then freezes."
7. "After clicking Triage or Assign, the detail view still shows the old status until you reload."

Fix the code so the tickets are resolved. Do not change the tests.
