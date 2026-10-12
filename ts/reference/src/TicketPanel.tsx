import { useEffect, useMemo, useReducer, useState } from "react";
import { formatDuration, initials, matchesQuery, sortTickets, truncate } from "./formatters";
import { apply, canApply, isBreached, slaRemainingMs, type Ticket, type TicketEvent } from "./ticketMachine";

interface Props {
  initialTickets: Ticket[];
  agent: string;
  now?: () => number;
}

type Action = { ticketId: string; event: TicketEvent };

function reducer(tickets: Ticket[], action: Action): Ticket[] {
  return tickets.map((t) => (t.id === action.ticketId ? apply(t, action.event) : t));
}

export function TicketPanel({ initialTickets, agent, now = Date.now }: Props) {
  const [tickets, dispatch] = useReducer(reducer, initialTickets);
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(initialTickets[0]?.id ?? null);
  const [clock, setClock] = useState(now());

  useEffect(() => {
    const id = setInterval(() => setClock(now()), 1000);
    return () => clearInterval(id);
  }, [now]);

  const visible = useMemo(() => sortTickets(tickets.filter((t) => matchesQuery(t, query))), [tickets, query]);
  const selected = tickets.find((t) => t.id === selectedId) ?? null;
  const openCount = tickets.filter((t) => t.status !== "closed" && t.status !== "resolved").length;

  const send = (event: TicketEvent) => {
    if (!selected) return;
    dispatch({ ticketId: selected.id, event });
  };

  return (
    <div className="panel">
      <header>
        <input aria-label="Filter tickets" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="filter" />
        <span data-testid="open-count">{openCount} open</span>
      </header>
      <ul aria-label="Tickets">
        {visible.map((t) => (
          <li key={t.id}>
            <button
              aria-pressed={t.id === selectedId}
              onClick={() => setSelectedId(t.id)}
              data-testid={`ticket-${t.id}`}
              className={isBreached(t, clock) ? "breached" : ""}
            >
              <span className="prio">{t.priority}</span> {t.id} {truncate(t.subject, 24)}
              <span className="assignee">{t.assignee ? initials(t.assignee) : "--"}</span>
              <span className="sla" data-testid={`sla-${t.id}`}>
                {formatDuration(slaRemainingMs(t, clock))}
              </span>
            </button>
          </li>
        ))}
      </ul>
      {selected && (
        <section aria-label="Selected ticket">
          <h2>
            {selected.id} <small data-testid="status">{selected.status}</small>
          </h2>
          <div className="actions">
            <button disabled={!canApply(selected, "triage")} onClick={() => send({ type: "triage", priority: "high", at: now() })}>
              Triage as high
            </button>
            <button disabled={!canApply(selected, "assign")} onClick={() => send({ type: "assign", agent, at: now() })}>
              Assign to me
            </button>
            <button
              disabled={!canApply(selected, "ask_customer")}
              onClick={() => send({ type: "ask_customer", text: "Could you share a photo?", at: now() })}
            >
              Ask customer
            </button>
            <button
              disabled={!canApply(selected, "customer_replied")}
              onClick={() => send({ type: "customer_replied", text: "Here you go", at: now() })}
            >
              Simulate reply
            </button>
            <button disabled={!canApply(selected, "resolve")} onClick={() => send({ type: "resolve", at: now() })}>
              Resolve
            </button>
            <button disabled={!canApply(selected, "reopen")} onClick={() => send({ type: "reopen", at: now() })}>
              Reopen
            </button>
            <button disabled={!canApply(selected, "close")} onClick={() => send({ type: "close", at: now() })}>
              Close
            </button>
            <button disabled={!canApply(selected, "escalate")} onClick={() => send({ type: "escalate", at: now() })}>
              Escalate
            </button>
          </div>
          <ol aria-label="Messages">
            {selected.messages.map((m, i) => (
              <li key={`${m.at}-${i}`}>
                <b>{m.from}:</b> {m.text}
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  );
}
