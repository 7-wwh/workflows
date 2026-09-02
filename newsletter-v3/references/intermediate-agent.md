# Intermediate Agent (v4 — Nightly Batch Producer)

The Intermediate Agent runs ONCE per day, triggered by cron at
`settings.md → batch_time` (default 03:00, settings timezone). It performs **all
production** — research, writing, evaluation — for EVERY scheduled slot of the day,
so that at each `slot_time` the Sender can deliver instantly with zero writing delay.

## Hard boundaries

- NEVER sends anything (no email, no presentation to the user as delivery).
- NEVER modifies planned topics/slots (that is the Input Agent's job) — it only
  flips slot **statuses** (`SCHEDULED → READY` / `FAILED`).
- NEVER runs unless `eval/plan-eval.json → verdict` is `pass` / `pass_with_warnings`
  for the current plan.
- All artifacts are slot-scoped, keyed by date + slot time (supersedes the legacy
  `day-N` naming in `references/researcher-agent.md` / `writer-agent.md` /
  `evaluator-agent.md`):
  - Research: `research/<date>-slot-<HHMM>.json`
  - Draft:    `html/<date>-slot-<HHMM>.html`
  - Eval:     `eval/<date>-slot-<HHMM>-eval.json` (+ `-eval1.html` if edited)
  - Final:    `html/<date>-slot-<HHMM>-final.html`
  - Export:   `outbox/<date>/slot-<HHMM>-final.html`

## Batch procedure (in order)

1. **STATE CHECK** (role = batch): read settings.md, state.json, content_plan.md.
   List today's slots with status `SCHEDULED`. None → log + stop.
2. **Gate check**: `eval/plan-eval.json` verdict for the current plan must be
   pass / pass_with_warnings. Otherwise abort and log. Open the run manifest
   (`runs/run-<timestamp>.json`, trigger `batch`) and `runs/batch-<date>.json`.
3. **Parallel Research Fan-Out (Step 4)**:
   - Identify all slots of today with status `SCHEDULED`.
   - Dispatch **parallel Researcher subagents concurrently** (one per scheduled slot).
   - Each subagent runs Tavily-first search and writes its designated `research/<date>-slot-<HHMM>.json` file simultaneously without race conditions.
   - Wait for all slot research dumps to be written (`coverage_check` all true).
4. **Modular Production & Assembly (Steps 5–6, per scheduled slot in slot_time order)**:
   a. Writer (`references/writer-agent.md`) → `content/<date>-slot-<HHMM>.json` + `scripts/assemble_edition.py` → `html/<date>-slot-<HHMM>.html` (expiry stamp; 2,250–3,500 words)
   b. Evaluator (`references/evaluator-agent.md`, **fresh subagent**) → `eval/<date>-slot-<HHMM>-eval.json` (+ `patches` block when < 80)
   c. Assembler patch compilation → `scripts/assemble_edition.py --patch` → `html/<date>-slot-<HHMM>-final.html`
   d. Copy final → `outbox/<date>/slot-<HHMM>-final.html`
   e. Flip the slot's status in `content_plan.md`:
      - eval pass → `READY`
      - still failing after 2 revision cycles → export anyway WITH a visible warning
        banner, mark the slot `READY` but record `eval_pass: false` in the batch
        report (the Sender will skip-and-log it)
   f. Vault: topic status → `researched`
5. **Batch report**: complete `runs/batch-<date>.json` (per-slot files, scores, failures[]).
6. Close the run manifest.

## Re-run / crash semantics

- Re-invocation processes only slots still `SCHEDULED`; never redoes
  `READY`/`DELIVERED` slots.
- If the batch aborts mid-run, already-READY slots stay deliverable; remaining
  slots stay `SCHEDULED` and will be picked up by a retry (`/batch`).

## What it must NOT do

- No email, no "present as delivered", no `editions.json` writes (Sender's job).
- No plan.json/content_plan.md content edits, no intake, no vault profile rewrites.