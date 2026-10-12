import { PRIORITY_RANK, type Ticket } from "./ticketMachine";

/** 3_900_000 -> "1h 05m"; negative values are shown as "-1h 05m". */
export function formatDuration(ms: number): string {
  const sign = ms < 0 ? "-" : "";
  const totalMinutes = Math.floor(Math.abs(ms) / 60_000);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return `${sign}${hours}h ${String(minutes).padStart(2, "0")}m`;
}

/** "Jane Q. Doe" -> "JD" (first and last word). Single word -> first two letters. */
export function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[words.length - 1][0]).toUpperCase();
}

/** Cut to at most `max` characters, adding an ellipsis when something was removed. */
export function truncate(text: string, max: number): string {
  if (text.length <= max) return text;
  return text.slice(0, Math.max(0, max - 1)) + "…";
}

/** Urgent first, then by age (oldest first). Does not mutate the input. */
export function sortTickets(tickets: Ticket[]): Ticket[] {
  return [...tickets].sort((a, b) => {
    const byPriority = PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority];
    if (byPriority !== 0) return byPriority;
    return a.createdAt - b.createdAt;
  });
}

/** Case insensitive match on id, subject, or assignee. Empty query matches everything. */
export function matchesQuery(ticket: Ticket, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return [ticket.id, ticket.subject, ticket.assignee ?? ""].some((field) => field.toLowerCase().includes(q));
}
