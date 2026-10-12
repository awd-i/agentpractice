import { apply, canApply, IllegalTransition, isBreached, newTicket, slaRemainingMs, type Ticket } from "@app/ticketMachine";

const T0 = Date.UTC(2026, 5, 1, 9, 0);
const H = 3_600_000;

function inProgress(): Ticket {
  let t = newTicket("T1", "Tent pole snapped", T0);
  t = apply(t, { type: "triage", priority: "high", at: T0 + H });
  t = apply(t, { type: "assign", agent: "Jane Doe", at: T0 + 2 * H });
  return t;
}

test("happy path to closed", () => {
  let t = inProgress();
  t = apply(t, { type: "ask_customer", text: "Photo?", at: T0 + 3 * H });
  expect(t.status).toBe("waiting_on_customer");
  t = apply(t, { type: "customer_replied", text: "Here", at: T0 + 4 * H });
  expect(t.status).toBe("in_progress");
  t = apply(t, { type: "resolve", at: T0 + 5 * H });
  t = apply(t, { type: "close", at: T0 + 6 * H });
  expect(t.status).toBe("closed");
  expect(t.priority).toBe("high");
  expect(t.assignee).toBe("Jane Doe");
  expect(t.messages.map((m) => m.from)).toEqual(["agent", "customer"]);
  expect(t.updatedAt).toBe(T0 + 6 * H);
});

test("cannot close without resolving first", () => {
  const t = inProgress();
  expect(canApply(t, "close")).toBe(false);
  expect(() => apply(t, { type: "close", at: T0 })).toThrow(IllegalTransition);
});

test("skipping triage is illegal and leaves the ticket untouched", () => {
  const t = newTicket("T1", "x", T0);
  expect(() => apply(t, { type: "assign", agent: "Jane", at: T0 })).toThrow(IllegalTransition);
  expect(t.status).toBe("open");
});

test("two reopens are tolerated, the third escalates", () => {
  let t = apply(inProgress(), { type: "resolve", at: T0 });
  t = apply(t, { type: "reopen", at: T0 });
  expect([t.status, t.reopenCount]).toEqual(["in_progress", 1]);
  t = apply(apply(t, { type: "resolve", at: T0 }), { type: "reopen", at: T0 });
  expect([t.status, t.reopenCount, t.assignee]).toEqual(["in_progress", 2, "Jane Doe"]);
  t = apply(apply(t, { type: "resolve", at: T0 }), { type: "reopen", at: T0 });
  expect([t.status, t.priority, t.assignee, t.reopenCount]).toEqual(["triaged", "urgent", null, 3]);
});

test("closed is terminal", () => {
  const t = apply(apply(inProgress(), { type: "resolve", at: T0 }), { type: "close", at: T0 });
  for (const type of ["triage", "assign", "reopen", "escalate", "close"] as const) {
    expect(canApply(t, type)).toBe(false);
  }
  expect(() => apply(t, { type: "escalate", at: T0 })).toThrow(IllegalTransition);
});

test("escalate works from any live state", () => {
  const waiting = apply(inProgress(), { type: "ask_customer", text: "?", at: T0 });
  const t = apply(waiting, { type: "escalate", at: T0 + H });
  expect([t.status, t.priority, t.assignee]).toEqual(["triaged", "urgent", null]);
  expect(canApply(newTicket("T2", "y", T0), "escalate")).toBe(true);
});

test("apply never mutates its input", () => {
  const before = inProgress();
  const snapshot = JSON.stringify(before);
  apply(before, { type: "ask_customer", text: "Photo?", at: T0 });
  expect(JSON.stringify(before)).toBe(snapshot);
});

test("SLA counts from creation, not from the last update", () => {
  const t = inProgress(); // high priority = 240 minutes, updated at T0 + 2h
  expect(slaRemainingMs(t, T0 + 3 * H)).toBe(H);
  expect(slaRemainingMs(t, T0 + 5 * H)).toBe(-H);
  expect(isBreached(t, T0 + 5 * H)).toBe(true);
  expect(isBreached(t, T0 + 3 * H)).toBe(false);
});

test("resolved and closed tickets never count as breached", () => {
  const t = apply(inProgress(), { type: "resolve", at: T0 });
  expect(isBreached(t, T0 + 100 * H)).toBe(false);
});
