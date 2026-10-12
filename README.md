# debug-dojo

Practice for the debugging round: an unfamiliar, medium sized codebase, a pile of bug
tickets, a clock. You read, hypothesise, reproduce, fix, verify, and explain out loud.

The codebase is a support agent for a fictional outdoor store (Alpine Supply Co.): a
conversation state machine, an order lifecycle state machine, a refund policy flowchart
with customer tiers, promo codes with Pacific time windows, a retrying API client, and a
tool calling agent loop. Pure Python, no dependencies beyond pytest, everything offline.

## Quick start

```bash
python -m venv .venv && . .venv/bin/activate && pip install -e .
(cd ts && npm install)                        # only needed for level 09
python dojo.py list
python dojo.py start 05-conversation-machine   # plants the bugs into workspace/ and starts the clock
cat levels/05-conversation-machine/BRIEF.md   # the tickets
python dojo.py demo refund-chat               # reproduce a ticket against your workspace copy
# ... edit workspace/supportdesk/*.py ...
python dojo.py check                          # how many tests still fail, per module
python dojo.py solution                       # every planted bug and the fix (end of session only)
```

`workspace/` is a throwaway copy; `reference/` is the clean implementation. Do not read
`reference/` or `levels/*/_solution.py` while a level is running; that is the answer key.

## Levels

| level | what it drills | bugs | time |
|---|---|---|---|
| 01-strings-and-loops | normalisation, sort direction, off by one in loops and slices | 5 | 20m |
| 02-refund-flowchart | paper flowchart to code: inclusive windows, tier comparisons, branch guards, rounding, thresholds | 5 | 30m |
| 03-promo-clock | timezone conversion vs relabelling, exclusive ends, side effect ordering, clamps | 5 | 30m |
| 04-order-lifecycle | transition table drift, idempotency, check before update, two code paths disagreeing | 5 | 30m |
| 05-conversation-machine | slot contamination, counters that never reset, >= vs >, cleanup on timeout, partial rollback | 6 | 40m |
| 06-flaky-api | retry classification, attempt caps, pagination loop order, idempotency keys, jitter | 5 | 30m |
| 07-agent-loop | loop bounds, exceptions as observations, history trimming, memory merge, early exit, grounding | 6 | 40m |
| 08-release-triage | one bug per module, tickets do not say where. Closest to the real thing | 6 | 60m |
| 09-react-ticket-panel | TypeScript/React: reducer state machine, sort comparator, case handling, stale closure, props vs state | 7 | 45m |

Each level folder has a `BRIEF.md` written as tickets (what a user or on call saw), not as
"the bug is in function X". The specs in `docs/specs/` are the ground truth the code is
supposed to match; in the refund level the spec is literally the flowchart.

## How to run a session so it feels like the interview

1. Start the clock with `dojo.py start`. Do not open the tests first.
2. Spend the first five minutes reading. Read the spec for the module, then the module top
   to bottom. Say what each function is for in one sentence.
3. For each ticket: form a concrete hypothesis ("the tier is compared as a string"), then
   pick the smallest experiment that would confirm or kill it (a REPL call, a print,
   `dojo.py demo`). Only then edit.
4. Make the minimal fix. Then ask: where else does this same class of bug live? Planted bugs
   come in classes (two `>=` vs `>` bugs in one file is deliberate).
5. `dojo.py check` is the grader. Use `--names` only when you are stuck; `-v` is a last resort.
   Hints cost you: `dojo.py solution` prints how many you used.
6. Narrate. The interviewer is grading the hypothesis loop as much as the fix.
7. After the session, read `dojo.py solution` and `dojo.py diff`. For every bug you missed,
   write down which experiment would have found it.

Scoring that I would use: all bugs found inside the time box with no hints is the bar; one
hint or one missed bug is fine; two misses or editing tests to make them pass is a fail.

## What the research says about Sierra's round

Official, from Sierra's own write up of their AI native interview loop
(https://sierra.ai/blog/the-ai-native-interview):

- The onsite is Plan / Build / Review. Plan: scope a product with the interviewers. Build:
  about two hours with whatever AI tooling you like. Review: demo and defend product flows,
  technical choices, data model, abstractions, extensibility, path to production, and how
  you used AI.
- They describe a debugging pilot explicitly: a medium sized codebase plus a colleague's
  draft PR that adds a cross cutting feature; the candidate reviews and improves it. Whether
  AI tools are allowed in that round was described as undecided. Level 08 here is the
  closest approximation: one release touched every module and you have to triage.

Candidate reports (Glassdoor, Blind, interview write ups; treat as noisy):

- Glassdoor lists the round as "Debugging: finding bugs in a state machine". That is level 05
  (conversation) and level 04 (order lifecycle).
- Several reports describe a refund flow handed over as a paper flowchart with customer
  tiers and several conditional branches, with about four planted bugs: wrong tier
  comparisons, refund off by ones, branch ordering. That is level 02, and the spec is the
  flowchart.
- Reports agree the bugs are mostly "incorrect strings and loops" rather than deep
  algorithmic problems: wrong case, wrong separator, off by one in a range, sort in the
  wrong direction. Level 01.
- One report describes TypeScript/React with five or six defects under time pressure. See
  `ts/` for a small variant in that stack.
- Others mention API call debugging (retries, pagination, idempotency). Level 06.

What they appear to grade: did you read before typing, did you state hypotheses, did you
reproduce before fixing, is the fix minimal, did you check for the same bug elsewhere, and
can you explain the system back. Speed matters less than not thrashing.

## Bug taxonomy used to seed the levels

State machines:

- missing or extra edges in the transition table (cancel after ship)
- guards that drift apart between two code paths (`can()` vs `apply()`)
- counters that are never reset, or compared with the wrong operator (>= vs >)
- context that is replaced instead of merged (slots, memory)
- partial rollback: state restored, context not
- cleanup skipped on timeout or on the terminal edge (pending refund survives a close)
- terminal states that still accept events
- check before update ordering (remaining checked before the refund is recorded)
- idempotency: duplicate events applied twice

Branch logic and arithmetic:

- inclusive vs exclusive boundaries (14th day, $500.00, end of a date range)
- enum compared as a string
- rounding by truncation when half up was specified
- guard missing its exemption (final sale AND NOT defective)
- clamps on the wrong side (`max(x, 0)` where `min(x, subtotal)` was needed)
- timezone relabelled (`replace(tzinfo=)`) instead of converted (`astimezone`)

Agent and API loops (these line up with the empirical study of ~1000 agent framework
issues, where API misuse and incompatibility, configuration, serialisation, memory
persistence, and concurrency confusion dominate the root causes):

- retrying non retryable errors; one attempt too many; sleeping past the budget; no jitter
- pagination that drops the last page
- idempotency key regenerated inside the retried closure
- loop bound off by one on `max_steps`
- tool exceptions escaping instead of becoming observations
- history trimming that drops the system prompt
- early exit with `break` instead of `return`
- grounding that reads the wrong field

## Layout

```
dojo.py                 the CLI (start / check / demo / hint / diff / solution / reset / verify)
reference/supportdesk/  clean implementation (the answer key)
levels/NN-slug/         BRIEF.md (tickets) and _solution.py (planted mutations, hints)
tests/                  one grader for every level; conftest points at workspace/ when it exists
docs/specs/             what the code is supposed to do, per module
ts/                     TypeScript/React variant (ticket state machine) with its own planted bugs
```

`python dojo.py verify` is the maintainer check: it plants every bug on its own and confirms
at least one test catches it, then confirms the reference passes everything.

## Adding a level

Copy a level folder, write the tickets in `BRIEF.md`, and list mutations in `_solution.py`
as `{file, old, new, why, kind}`. `old` must occur exactly once in the reference file.
Run `python dojo.py verify`.

## Also in this repo: the token budget drill

The original 45 minute drill lives at the root: fill in `trim()` in `trim.py` per `PROMPT.md`,
then `pip install -r requirements.txt && pytest -q test_trim.py`. No AI.
