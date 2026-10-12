import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { TicketPanel } from "@app/TicketPanel";
import { apply, newTicket, type Ticket } from "@app/ticketMachine";

const BASE = Date.UTC(2026, 5, 1, 9, 0);

function fixtures(): Ticket[] {
  const t1 = newTicket("T1", "Tent pole snapped", BASE);
  let t2 = newTicket("T2", "Wrong size socks", BASE - 60_000);
  t2 = apply(t2, { type: "triage", priority: "high", at: BASE });
  t2 = apply(t2, { type: "assign", agent: "Jane Doe", at: BASE });
  t2 = apply(t2, { type: "resolve", at: BASE });
  let t3 = newTicket("T3", "Stove will not light", BASE - 120_000);
  t3 = apply(t3, { type: "triage", priority: "urgent", at: BASE });
  t3 = apply(t3, { type: "assign", agent: "Sam Lee", at: BASE });
  t3 = apply(t3, { type: "resolve", at: BASE });
  t3 = apply(t3, { type: "close", at: BASE });
  return [t1, t2, t3];
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(BASE);
});

afterEach(() => {
  vi.useRealTimers();
});

function listIds() {
  return within(screen.getByRole("list", { name: "Tickets" }))
    .getAllByRole("button")
    .map((b) => b.getAttribute("data-testid")!.replace("ticket-", ""));
}

test("counts tickets that still need work", () => {
  render(<TicketPanel initialTickets={fixtures()} agent="Me" />);
  expect(screen.getByTestId("open-count")).toHaveTextContent("1 open");
});

test("list is sorted urgent first and filter is case insensitive", () => {
  render(<TicketPanel initialTickets={fixtures()} agent="Me" />);
  expect(listIds()).toEqual(["T3", "T2", "T1"]);
  fireEvent.change(screen.getByLabelText("Filter tickets"), { target: { value: "JANE" } });
  expect(listIds()).toEqual(["T2"]);
  fireEvent.change(screen.getByLabelText("Filter tickets"), { target: { value: "" } });
  expect(listIds()).toHaveLength(3);
});

test("actions follow the state machine and the detail view updates", () => {
  render(<TicketPanel initialTickets={fixtures()} agent="Me" />);
  fireEvent.click(screen.getByTestId("ticket-T1"));
  expect(screen.getByTestId("status")).toHaveTextContent("open");
  expect(screen.getByRole("button", { name: "Resolve" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Assign to me" })).toBeDisabled();

  fireEvent.click(screen.getByRole("button", { name: "Triage as high" }));
  expect(screen.getByTestId("status")).toHaveTextContent("triaged");
  fireEvent.click(screen.getByRole("button", { name: "Assign to me" }));
  expect(screen.getByTestId("status")).toHaveTextContent("in_progress");
  expect(screen.getByRole("button", { name: "Close" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Resolve" }));
  expect(screen.getByTestId("status")).toHaveTextContent("resolved");
  expect(screen.getByTestId("open-count")).toHaveTextContent("0 open");
  fireEvent.click(screen.getByRole("button", { name: "Close" }));
  expect(screen.getByTestId("status")).toHaveTextContent("closed");
  expect(screen.getByRole("button", { name: "Reopen" })).toBeDisabled();
});

test("SLA countdown keeps ticking", () => {
  render(<TicketPanel initialTickets={fixtures()} agent="Me" />);
  expect(screen.getByTestId("sla-T1")).toHaveTextContent("24h 00m");
  act(() => {
    vi.advanceTimersByTime(61 * 60_000);
  });
  expect(screen.getByTestId("sla-T1")).toHaveTextContent("22h 59m");
  act(() => {
    vi.advanceTimersByTime(60 * 60_000);
  });
  expect(screen.getByTestId("sla-T1")).toHaveTextContent("21h 59m");
});
