RUNTIME = "ts"
TITLE = "The ticket panel (TypeScript / React)"
MINUTES = 45
HINTS = [
    "Tickets 1 to 4 are in ticketMachine.ts and formatters.ts; 5 to 7 are React. Split your time accordingly.",
    "Ticket 6: a closure inside setInterval sees the values from the render that created it. What does the effect depend on?",
    "Ticket 7: two arrays of tickets exist in the component. Which one is the detail view reading?",
]
DEMO = []
MUTATIONS = [
    dict(
        file="ticketMachine.ts",
        kind="transition table (extra edge)",
        why="An in_progress -> closed edge lets agents skip the resolve step.",
        old='  "resolved:close": "closed",\n',
        new='  "resolved:close": "closed",\n  "in_progress:close": "closed",\n',
    ),
    dict(
        file="ticketMachine.ts",
        kind="off by one (>= vs >)",
        why="MAX_REOPENS reopens are allowed; only the one after that escalates.",
        old="      if (updated.reopenCount > MAX_REOPENS) {",
        new="      if (updated.reopenCount >= MAX_REOPENS) {",
    ),
    dict(
        file="ticketMachine.ts",
        kind="wrong anchor timestamp",
        why="The SLA clock starts at creation; using updatedAt resets it on every event.",
        old="  return ticket.createdAt + SLA_MINUTES[ticket.priority] * 60_000 - now;",
        new="  return ticket.updatedAt + SLA_MINUTES[ticket.priority] * 60_000 - now;",
    ),
    dict(
        file="formatters.ts",
        kind="sort direction",
        why="Rank 0 is urgent, so the comparator must be a - b to put it first.",
        old="    const byPriority = PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority];",
        new="    const byPriority = PRIORITY_RANK[b.priority] - PRIORITY_RANK[a.priority];",
    ),
    dict(
        file="formatters.ts",
        kind="case handling",
        why="The query is lower cased but the fields are not, so upper case queries never match.",
        old="  return [ticket.id, ticket.subject, ticket.assignee ?? \"\"].some((field) => field.toLowerCase().includes(q));",
        new="  return [ticket.id, ticket.subject, ticket.assignee ?? \"\"].some((field) => field.includes(q));",
    ),
    dict(
        file="TicketPanel.tsx",
        kind="stale closure in an effect",
        why="The interval captured `clock` from the first render, so it keeps setting the same value.",
        old="    const id = setInterval(() => setClock(now()), 1000);\n    return () => clearInterval(id);\n  }, [now]);",
        new="    const id = setInterval(() => setClock(clock + 1000), 1000);\n    return () => clearInterval(id);\n  }, []);",
    ),
    dict(
        file="TicketPanel.tsx",
        kind="reading props instead of state",
        why="The detail view must read from the reducer state; initialTickets never changes.",
        old="  const selected = tickets.find((t) => t.id === selectedId) ?? null;",
        new="  const selected = initialTickets.find((t) => t.id === selectedId) ?? null;",
    ),
]
