import { formatDuration, initials, matchesQuery, sortTickets, truncate } from "@app/formatters";
import { newTicket, type Priority, type Ticket } from "@app/ticketMachine";

test.each([
  [3_900_000, "1h 05m"],
  [-3_900_000, "-1h 05m"],
  [59_000, "0h 00m"],
  [0, "0h 00m"],
  [25 * 3_600_000, "25h 00m"],
])("formatDuration(%i) -> %s", (ms, expected) => {
  expect(formatDuration(ms)).toBe(expected);
});

test("initials", () => {
  expect(initials("Jane Q. Doe")).toBe("JD");
  expect(initials("  plato ")).toBe("PL");
  expect(initials("")).toBe("");
});

test("truncate never exceeds max", () => {
  expect(truncate("hello world", 5)).toBe("hell…");
  expect(truncate("hello world", 5)).toHaveLength(5);
  expect(truncate("hi", 5)).toBe("hi");
  expect(truncate("hello", 5)).toBe("hello");
});

function ticket(id: string, priority: Priority, createdAt: number, assignee: string | null = null): Ticket {
  return { ...newTicket(id, `Subject ${id}`, createdAt), priority, assignee };
}

test("sortTickets puts urgent first then oldest first, without mutating", () => {
  const input = [ticket("A", "low", 3), ticket("B", "urgent", 2), ticket("C", "normal", 1), ticket("D", "high", 4), ticket("E", "urgent", 1)];
  const copy = [...input];
  expect(sortTickets(input).map((t) => t.id)).toEqual(["E", "B", "D", "C", "A"]);
  expect(input).toEqual(copy);
});

test("matchesQuery is case insensitive across id, subject and assignee", () => {
  const t = ticket("T7", "normal", 0, "Jane Doe");
  expect(matchesQuery(t, "")).toBe(true);
  expect(matchesQuery(t, "   ")).toBe(true);
  expect(matchesQuery(t, "t7")).toBe(true);
  expect(matchesQuery(t, "JANE")).toBe(true);
  expect(matchesQuery(t, "subject t7")).toBe(true);
  expect(matchesQuery(t, "zzz")).toBe(false);
  expect(matchesQuery({ ...t, assignee: null }, "jane")).toBe(false);
});
