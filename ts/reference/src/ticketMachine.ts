// Support ticket lifecycle. Spec: ../../docs/specs/ticket_machine.md

export type Status = "open" | "triaged" | "in_progress" | "waiting_on_customer" | "resolved" | "closed";
export type Priority = "low" | "normal" | "high" | "urgent";

export interface Message {
  from: "customer" | "agent";
  text: string;
  at: number;
}

export interface Ticket {
  id: string;
  subject: string;
  status: Status;
  priority: Priority;
  assignee: string | null;
  messages: Message[];
  reopenCount: number;
  createdAt: number;
  updatedAt: number;
}

export type TicketEvent =
  | { type: "triage"; priority: Priority; at: number }
  | { type: "assign"; agent: string; at: number }
  | { type: "ask_customer"; text: string; at: number }
  | { type: "customer_replied"; text: string; at: number }
  | { type: "resolve"; at: number }
  | { type: "close"; at: number }
  | { type: "reopen"; at: number }
  | { type: "escalate"; at: number };

export const MAX_REOPENS = 2;
export const TERMINAL: ReadonlySet<Status> = new Set(["closed"]);

export const SLA_MINUTES: Record<Priority, number> = { low: 2880, normal: 1440, high: 240, urgent: 60 };
export const PRIORITY_RANK: Record<Priority, number> = { urgent: 0, high: 1, normal: 2, low: 3 };

const TRANSITIONS: Record<string, Status> = {
  "open:triage": "triaged",
  "triaged:assign": "in_progress",
  "in_progress:ask_customer": "waiting_on_customer",
  "waiting_on_customer:customer_replied": "in_progress",
  "in_progress:resolve": "resolved",
  "resolved:close": "closed",
  "resolved:reopen": "in_progress",
};

export class IllegalTransition extends Error {}

export function canApply(ticket: Ticket, type: TicketEvent["type"]): boolean {
  if (TERMINAL.has(ticket.status)) return false;
  if (type === "escalate") return true;
  return `${ticket.status}:${type}` in TRANSITIONS;
}

export function newTicket(id: string, subject: string, at: number): Ticket {
  return {
    id,
    subject,
    status: "open",
    priority: "normal",
    assignee: null,
    messages: [],
    reopenCount: 0,
    createdAt: at,
    updatedAt: at,
  };
}

/** Pure reducer: returns a new ticket, never mutates the input. */
export function apply(ticket: Ticket, event: TicketEvent): Ticket {
  if (TERMINAL.has(ticket.status)) {
    throw new IllegalTransition(`${ticket.id} is ${ticket.status}; no further events allowed`);
  }
  if (event.type === "escalate") {
    return { ...ticket, priority: "urgent", assignee: null, status: "triaged", updatedAt: event.at };
  }
  const next = TRANSITIONS[`${ticket.status}:${event.type}`];
  if (next === undefined) {
    throw new IllegalTransition(`cannot ${event.type} a ticket that is ${ticket.status}`);
  }
  const updated: Ticket = { ...ticket, status: next, updatedAt: event.at, messages: [...ticket.messages] };
  switch (event.type) {
    case "triage":
      updated.priority = event.priority;
      break;
    case "assign":
      updated.assignee = event.agent;
      break;
    case "ask_customer":
      updated.messages.push({ from: "agent", text: event.text, at: event.at });
      break;
    case "customer_replied":
      updated.messages.push({ from: "customer", text: event.text, at: event.at });
      break;
    case "reopen":
      updated.reopenCount = ticket.reopenCount + 1;
      if (updated.reopenCount > MAX_REOPENS) {
        // too many reopens: escalate instead of bouncing back to the same agent
        return { ...updated, priority: "urgent", assignee: null, status: "triaged" };
      }
      break;
  }
  return updated;
}

/** Milliseconds until the SLA is breached (negative once breached). Measured from creation. */
export function slaRemainingMs(ticket: Ticket, now: number): number {
  return ticket.createdAt + SLA_MINUTES[ticket.priority] * 60_000 - now;
}

export function isBreached(ticket: Ticket, now: number): boolean {
  return !TERMINAL.has(ticket.status) && ticket.status !== "resolved" && slaRemainingMs(ticket, now) < 0;
}
