# Ticket panel (TypeScript / React)

Code: `ts/reference/src/`. Tests: `ts/tests/`.

```
open --triage--> triaged --assign--> in_progress --ask_customer--> waiting_on_customer
                                        ^                                |
                                        +--------customer_replied--------+
in_progress --resolve--> resolved --close--> closed (terminal)
resolved --reopen--> in_progress            (reopenCount + 1; the reopen after MAX_REOPENS=2 escalates instead)
any live state --escalate--> triaged, priority urgent, assignee cleared
```

- `apply(ticket, event)` is a pure reducer: it returns a new ticket and never mutates the input.
  Unknown edges and events in `closed` throw `IllegalTransition`. `canApply` must agree with `apply`.
- SLA minutes by priority: low 2880, normal 1440, high 240, urgent 60. `slaRemainingMs` is measured from
  `createdAt`. Resolved and closed tickets are never "breached".
- `formatDuration(3_900_000) === "1h 05m"`, negative durations get a leading `-`.
- `sortTickets`: urgent, high, normal, low; ties oldest first; input not mutated.
- `matchesQuery`: case insensitive on id, subject, assignee; empty query matches everything.
- `TicketPanel`: shows `N open` (anything not resolved or closed), the sorted and filtered list with a live
  SLA countdown that ticks every second, and a detail view whose buttons are enabled exactly when the
  machine allows the event. The detail view reflects the current ticket state after every action.
