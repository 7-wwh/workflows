---
name: newsletter
description: >
  Personalised, vault-aware learning newsletter with configurable delivery frequency,
  3-day rolling content plans, Tavily-powered research, automated cron scheduling,
  and a follow-up Q&A loop that rewires future editions.
  Trigger on /newsletter, /vault, /followup, /plan-newsletter, /send-newsletter,
  /cron-setup, /rules, /frequency, /install-cron, /update-rules,
  or whenever the user mentions newsletter, daily digest, learning email, 3-day plan,
  content calendar, Tavily research, cron schedule, or asks to research and write about
  topics they want to learn. Also trigger when the user asks a follow-up question about
  a past newsletter edition ("what is X?", "I didn't understand Y", "tell me more about Z"),
  or when they want to automate, schedule, or update frequency/writing/research rules.
---

# Newsletter Skill (v3 — Vault-Aware, Adaptive, Cron-Scheduled, Tavily-Powered)

A multi-agent workflow that turns the user's learning interests into a personalised,
adaptive newsletter — planned against a persistent knowledge vault, researched, written,
refined by a directly-editing evaluator, and delivered on a configurable schedule.

---

## Architecture Overview

```
SETTINGS (settings.md - authoritative) -----------------------------------------+
  sends_per_day, slot_times, batch_time (INTERMEDIATE AGENT cron),
  delivery_days, timezone (IANA id), rolling_window_days,
  new_topic_priority, allow_topic_split

INPUT AGENT (foreground, user-triggered) — requirements & planning ONLY ----------+
[1] INTAKE        -> Collect topics, follow-up Qs, settings changes
[2] VAULT MANAGER -> Update vault; flag brand-new topics (is_new_topic)
[3] PLANNER       -> Plan in CONTENT CHUNKS (10-20 min read each); arrange chunks
                     into slots (ULTIMATE priority for new topics)
[3.5] PLAN EVAL   -> FRESH-SUBAGENT gate: consolidation bias + 10-20 min reading-time
                     gate (references/plan-evaluator-agent.md)
  Output: a GATED content plan. The Input Agent NEVER researches, writes, or sends.

CONTENT PLAN (content_plan.md) - slot grid: N days x sends_per_day slots
  statuses: DELIVERED | READY | SCHEDULED | EMPTY  +  Backlog section

INTERMEDIATE AGENT (background — cron fires ONCE at settings.md batch_time) ------+
[4] RESEARCHERS   -> PARALLEL Tavily deep-dive for ALL scheduled slots of today (concurrent fan-out)
[5] WRITERS       -> Draft modular content JSON per slot (2,250–3,500 words) + assemble_edition.py
[6] EVALUATORS    -> Score + JSON patches; Assembler handoff -> final HTML
  Writes ALL finished editions to outbox/YYYY-MM-DD/slot-HHMM-final.html
  Marks each slot READY in content_plan.md. Produces runs/batch-<date>.json.
  NEVER sends and NEVER touches planned topics/slots.

SENDER AGENT (background — cron fires at EACH settings.md slot_time) --------------+
[7] SENDER        -> Retrieve the READY edition from outbox, verify eval pass,
                     send/present, mark DELIVERED, write editions.json record.
                     Zero production work — no writing delay at send time. ----+
```
## Path Resolution & Installation (read first)

- **Skill root** = the directory containing this `SKILL.md`. Every relative path in
  this document and in every `references/*.md` file resolves from the skill root.
  Never search the filesystem for these files; if a referenced file is missing from
  the skill root, report the missing path and stop.
- On install, if `newsletter-workspace/` does not exist under the skill root,
  create the scaffold: `settings.md` (defaults per Step 0), `config.json`,
  empty `content_plan.md`, and directories `vault/ research/ html/ content/ eval/ cron/ runs/`.
- **Data-safety rule**: `newsletter-workspace/` is user data, not skill-package data.
  On install or update NEVER overwrite or delete an existing `newsletter-workspace/`;
  only `SKILL.md`, `references/`, and `assets/` are replaced on update.
- Canonical templates live in `assets/templates/` only. Any copies of template HTML
  found inside a profile's `html/` are non-canonical and must not be used as a base.

---

## Multi-Profile Architecture (v5)

The workspace supports **multiple isolated profiles** — one per recipient email, each
with its own settings, schedule, vault, followups, content plan, and outbox.

```
newsletter-workspace/
├── profiles/
│   ├── registry.json               ← canonical profile list ({ "profiles": [{ "id", "enabled" }] })
│   └── <profile-id>/               ← 100% SELF-CONTAINED workspace per recipient
│       ├── settings.md             ← email, slot_times, batch_time, timezone, rules
│       ├── config.json  content_plan.md  plan.json
│       ├── vault/                  ← state.json, inbox.json, followups.json,
│       │                              knowledge-map.json, learning-profile.md, editions.json
│       ├── outbox/  research/  eval/  html/  content/  runs/
├── shared/                         ← read-only shared layer (scripts/assemble_edition.py)
└── cron/                           ← profile-aware runners + logs/ + locks/
```

### Boundary rules (MANDATORY for every agent)

1. **A profile workspace is the agent's entire world.** All internal agents (Input,
   Vault Manager, Planner, Researcher, Writer, Evaluator) operate with the profile
   directory as their working root and NEVER read or write outside it. Followups,
   state, inbox, and knowledge live and die inside the individual profile.
2. **The Sender is the only agent that crosses a profile boundary**, and it does the
   minimum: retrieve `outbox/<date>/slot-<HHMM>-final.html` from ITS profile, send to
   the `email` in ITS profile's `settings.md`, mark DELIVERED, append the delivery
   record (with `profile` and `sent_to` fields), exit. Zero production work.
3. **Recipient resolution**: the runner script (`run-sender.sh`) reads the recipient
   from the profile's `settings.md` and INJECTS it into the sender prompt. The agent
   never guesses an address. If `email` is missing, the script hard-fails.
4. **Registry validation**: every runner validates `--profile` against
   `profiles/registry.json` before launching an agent. Unregistered IDs fail fast —
   a typo can never silently spawn a rogue workspace.
5. **`shared/` is read-only** (templates/assembler). No state is ever shared between
   profiles.
6. **Per-profile locks and logs**: `cron/locks/<profile>-<task>.lock`,
   `cron/logs/<profile>.log`.

### Runner CLI (v5)

```
cron/run-batch.sh   --profile <id> [--dry-run]   # Intermediate Agent batch for one profile
cron/run-sender.sh  --profile <id> [--dry-run]   # Sender delivery for one profile
cron/run-newsletter.sh --profile <id> --batch|--send
cron/purge-expired.sh [--profile <id>]           # one profile, or sweep all
cron/run-vault-maintenance.sh [--profile <id>]   # one profile, or sweep all
```

`--profile` may be omitted only when exactly one profile is registered.

### Adding a profile

1. `mkdir -p profiles/<id>` with the full scaffold (copy settings.md defaults,
   empty `content_plan.md`, `vault/`, `outbox/`, `research/`, `eval/`, `html/`,
   `content/`, `runs/`).
2. Register it in `profiles/registry.json` (`enabled: true`).
3. Install its cron entries per `references/cron-setup.md` (tagged
   `# newsletter-skill:<profile-id>` so one profile's cron never clobbers another's).
4. Set its `email`, `slot_times`, `batch_time`, `timezone`, and rules in
   `profiles/<id>/settings.md`.

Commands like `/newsletter`, `/settings`, `/plan`, `/followup` operate on the
**active profile**; when multiple profiles exist, the agent must first ask the user
which profile (or accept an explicit `/profile <id>` prefix) before touching state.

---

## Execution Runbook (MANDATORY — role-scoped, follow in order, no skipping)

Every invocation of this skill MUST first determine its **role**, then follow only
that role's checklist. The runbook is enforced by a **run manifest**: before starting
step N, the manifest must show steps 1..N-1 complete.

### Role determination (every invocation, no exceptions)

```
0. ROLE + STATE CHECK
   a. Determine the ACTIVE PROFILE: from an explicit user command prefix
      (/profile <id>), the cron runner's --profile argument, or — only when
      exactly one profile is registered — that sole profile in
      profiles/registry.json. With multiple profiles and no explicit choice,
      ASK the user before touching state.
   b. All paths below are relative to profiles/<active-profile>/.
   c. Read settings.md
   d. Determine role:
        - fired by the batch_time cron (or user says "run the batch")        -> INTERMEDIATE AGENT
        - fired by a slot_time cron (or user says "send the newsletter")     -> SENDER AGENT
        - otherwise (user-triggered foreground)                              -> INPUT AGENT
   e. Read vault/state.json and content_plan.md
   f. Derive: which slots are SCHEDULED for today? Gate verdict in eval/plan-eval.json?
      Unprocessed inbox items? Unsent READY slots?
   g. Open/continue the role's run manifest (runs/run-<timestamp>.json, with
      "profile": "<active-profile>").
```

### INPUT AGENT checklist (requirements & planning ONLY)

| # | Step | Output (must exist before next step) | Exit condition |
|---|------|--------------------------------------|----------------|
| 1 | INTAKE (Step 1) | item(s) appended to `vault/inbox.json` | inbox updated |
| 2 | VAULT MANAGER (Step 2) | `vault/knowledge-map.json`, `learning-profile.md`, `state.json` updated | inbox items `processed: true` |
| 3 | PLANNER chunking (Step 3) | `plan.json` (with `chunks[]`) + `content_plan.md` rewritten | chunks all >=10 and <=20 min |
| 4 | **PLAN EVAL GATE** (Step 3.5, fresh subagent) | `eval/plan-eval.json` | verdict = pass / pass_with_warnings; <=2 revision cycles, then ask user |

Then: present plan summary to user (interactive) and STOP. **The Input Agent NEVER
researches, writes, evaluates, sends, or writes to outbox/.** If the user asks for
immediate production, tell them production happens at `batch_time` (or run the
batch explicitly per its checklist).

### INTERMEDIATE AGENT checklist (background batch — ALL production for the day)

```
B1. STATE CHECK (role = batch). If slot status for today is not SCHEDULED -> nothing to do, log, stop.
B2. Verify plan gate: eval/plan-eval.json verdict pass / pass_with_warnings for the current plan. Else ABORT batch, log.
B3. Open batch manifest (trigger: batch) + runs/batch-<date>.json report file.
B4. PARALLEL RESEARCH FAN-OUT (Step 4):
    Spawn parallel Researcher subagents simultaneously for ALL slots of today with status SCHEDULED.
    Each subagent writes research/<date>-slot-<HHMM>.json concurrently (coverage_check all true).
    Wait for all slot research dumps to complete.
B5. MODULAR PRODUCTION & ASSEMBLY (Steps 5–6, per scheduled slot in slot_time order):
    a. WRITER (Step 5)     -> content/<date>-slot-<HHMM>.json + scripts/assemble_edition.py -> html/<date>-slot-<HHMM>.html (expiry stamp; 2,250–3,500 words)
    b. EVALUATOR (Step 6, fresh subagent) -> eval/<date>-slot-<HHMM>-eval.json (+ patches block if edited)
    c. ASSEMBLER final (Step 6 handoff) -> scripts/assemble_edition.py --patch -> html/<date>-slot-<HHMM>-final.html
    d. Copy final -> outbox/<date>/slot-<HHMM>-final.html
    e. Mark slot READY in content_plan.md (eval pass) or FAILED (2 revision cycles
       exhausted -> still export with visible warning banner; record in batch failures)
    f. Vault: topic status -> researched
B6. Write runs/batch-<date>.json (finished_at, per-slot records, failures[]).
B7. Close manifest. NEVER send. NEVER modify planned topics/slots. NEVER touch outbox after B6.
```

Re-run semantics: if the batch is re-invoked (crash/retry), process only slots still
SCHEDULED — never redo READY/DELIVERED slots.

### SENDER AGENT checklist (delivery ONLY — zero production)

```
S1. STATE CHECK (role = send). Identify the slot matching the firing slot_time.
S2. Slot status READY? -> continue. SCHEDULED (batch not finished/failed) -> log
    "not ready", skip send, DO NOT block; surface to user at next input interaction.
    DELIVERED/EMPTY -> log, stop.
S3. Retrieve outbox/<date>/slot-<HHMM>-final.html. Missing -> log + skip (never write it).
S4. Verify matching eval file pass: true (or warning-banner flag recorded). Else skip + log.
S5. Send (email per settings) or present the file (no email configured). Mode A/B per sender-agent.md.
S6. Re-stamp expiry marker (now + html_expiry_days); run cron/purge-expired.sh.
S7. Mark slot DELIVERED in content_plan.md; append record to vault/editions.json;
    vault topic status -> delivered; update state.json; close manifest.
```

### Hard gates & stop rules (never violate)

1. ROLE SEPARATION: the Input Agent never produces/sends; the Intermediate Agent
   never sends and never modifies planned topics/slots; the Sender never produces —
   it only retrieves from outbox/ and delivers.
2. The batch NEVER runs unless `eval/plan-eval.json` verdict is pass /
   pass_with_warnings for the current plan.
3. NO SLOT DELIVERED without: an outbox final HTML + matching eval `pass: true`
   (or recorded warning-banner failure). Missing/failed -> skip + log, never fabricate.
4. NEVER re-run a slot marked DELIVERED. Ambiguous due slot -> STOP and ask.
5. Revision loops: plan gate <=2 cycles; edition eval <=2 cycles -> export with
   warning banner (batch marks slot FAILED-for-warning), never block silently.
6. Fresh-subagent rule: PLAN EVAL (Step 3.5) and EVALUATOR (Step 6) must each run
   as a fresh subagent with no access to the producing agent's reasoning.
7. Production happens ONLY inside the batch run (batch_time). At slot_time the
   system must be able to send instantly — if it needs to write, that is a violation.

### Run Manifest (enforcement)

Maintain `newsletter-workspace/runs/run-<timestamp>.json` (schema in
`references/schemas.md`; trigger: input | batch | send). Append one entry per
completed step with its `output_file`. Before starting step N, steps 1..N-1 must be
`complete` in the manifest. Read-only triggers (`/vault`, `/plan`, settings edits)
do not open a manifest.

The **content plan** (`newsletter-workspace/content_plan.md`) is the forward-looking
plan of record: a slot grid (e.g. 3 days x 3 slots = 9 slots) with statuses
`DELIVERED | SCHEDULED | EMPTY` plus a Backlog section. The input agent (user-facing:
intake, vault, planning) maintains it; the output agent (cron-triggered) reads it to
decide what to research, write, evaluate, and send at each scheduled slot.

The **vault** (`newsletter-workspace/vault/`) persists everything: topics, editions,
follow-up questions, coverage maps, and knowledge-gap analysis. Every agent reads from
and writes back to it.

Three configuration layers govern the whole pipeline:
- **`settings.md`** — authoritative delivery settings (slots, timezone as an IANA id,
  priorities). If `config.json` disagrees, `settings.md` wins.
- **`config.json → research_rules`** — Tavily as primary source, fallback chain, domain filters
- **`config.json → writing_rules`** — tone, length, structure of each edition
- **`config.json → generation_rules`** — how the Planner picks and sequences topics
- **`cron/`** — OS-level scheduler jobs: ONE entry for `batch_time` (Intermediate
  Agent, nightly production) + ONE entry per `slot_times` value (Sender Agent,
  instant delivery from outbox) for fully automated operation

---

## Step 0 — CONFIG (first run only, or on /config)

On first run, collect or confirm the **delivery settings** and write them to
`newsletter-workspace/settings.md` (the authoritative file — see
`references/frequency-and-rules.md § 0`):

```
sends_per_day: 3
slot_times: ["08:00", "13:00", "18:00"]
batch_time: "03:00"
delivery_days: ["mon","tue","wed","thu","fri","sat","sun"]
email: string | null
timezone: IANA location id (e.g. "Asia/Kuala_Lumpur"); "auto" is resolved once by /cron-setup
rolling_window_days: 3
new_topic_priority: ultimate
allow_topic_split: true
artifact_retention_days: 7
html_expiry_days: 7
```

Plus agent-behavior rules in `newsletter-workspace/config.json`:

```json
{
  "newsletter_name": "string",
  "depth": "beginner | intermediate | advanced",
  "research_rules": { /* see references/frequency-and-rules.md § 2 */ },
  "writing_rules":  { /* see references/frequency-and-rules.md § 3 */ },
  "generation_rules": { /* see references/frequency-and-rules.md § 4 */ }
}
```

- For **schedule / delivery changes**: edit `settings.md` (per frequency-and-rules.md § 0),
  then regenerate cron via `/cron-setup`.
- For **research / writing / generation rule changes**: read `references/frequency-and-rules.md`.
- For **cron / automation setup**: read `references/cron-setup.md`.
- For **Tavily configuration**: read `references/tavily-research.md`.

**Frequency runtime note**: Claude.ai does not run background tasks. With the three
role split, a foreground `/newsletter` invocation acts ONLY as the Input Agent
(config/intake/vault/plan + gate). Production happens in the INTERMEDIATE AGENT
batch at `batch_time` (or manually via `/batch`), and delivery in the SENDER AGENT
at each `slot_time` (or manually via "send the newsletter"). If a due slot is not
READY at send time, report it and offer to run the batch now.

After first-run config is complete, offer to install cron jobs:
> "Want me to set up an automatic schedule so your newsletter runs without you having to
> trigger it? I can install a cron job for your system. Just say '/cron-setup'."

---

## Step 1 — INTAKE

Accept input in any of these forms:

| Trigger | Meaning |
|---------|---------|
| `/newsletter [topic ideas]` | Add new topics to the vault and run the pipeline |
| `/followup [question]` | Log a follow-up question; re-plan if needed |
| `/vault` | Show vault summary: what's been learned, gaps, upcoming plan |
| `/settings [key=value]` | Read/edit `settings.md` (sends_per_day, slot_times, timezone, ...) |
| `/plan` | Show `content_plan.md` — planned content moving forward + backlog |
| `/config [key=value]` | Update agent-behavior rules in config.json |
| Free text follow-up | Detect follow-up intent (see Follow-Up Detection below) |

Collect and store raw input in `vault/inbox.json` (append, never overwrite).

### New-Topic Insertion (important)

When the user names a topic they want to learn that is **not already queued or
scheduled**, it receives **ultimate priority** (default `new_topic_priority: ultimate`):
the Planner re-evaluates the existing `content_plan.md` and slots the new topic into
the **earliest available slot**, pushing later, splitting, or backlogging previously
planned content within the `rolling_window_days` window — never dropping delivered
content. See `references/planner-agent.md → Step C′`.

### Follow-Up Detection

If the user's message (not a `/` command) contains any of:
- "what is [term from a past edition]"
- "I didn't understand [X]"
- "tell me more about [X]"
- "can you go deeper on [X]"
- "why does [X] work"
- questions that reference a headline or theme from `vault/editions.json`

→ Treat as a follow-up. Log it to `vault/followups.json` and proceed to Step 2.
The Planner will inject a follow-up resolution slot into the next edition.

---

## Step 2 — VAULT MANAGER

Read `references/vault-manager-agent.md` for full instructions.

The Vault Manager runs after every INTAKE and after every delivered edition. It:

1. **Ingests** new topics and follow-up questions from `vault/inbox.json`.
2. **Updates** `vault/knowledge-map.json`:
   - Marks topics as `planned`, `researched`, `delivered`, or `mastered`.
   - Identifies **gaps**: learning objectives that were in a plan but not fully covered.
   - Identifies **correlations**: topics that share underlying concepts (e.g. "attention
     mechanisms" and "transformers" both touch "matrix multiplication").
3. **Prioritises** the follow-up queue: urgent questions (user said "I'm confused") get
   promoted to the next edition; curiosity questions ("tell me more") get queued for day 2–3.
4. **Writes** a human-readable learning profile to `vault/learning-profile.md`:
   - What the user has covered
   - Their apparent knowledge frontier (what they can explain vs. what confused them)
   - Top 3 recommended next topics based on correlation graph

Output files: `vault/knowledge-map.json`, `vault/followups.json`, `vault/learning-profile.md`.

---

## Step 3 — PLANNER

Read `references/planner-agent.md` for full instructions. **Enhanced from v1.**

The Planner reads `vault/knowledge-map.json`, `vault/learning-profile.md`,
`settings.md`, and the current `content_plan.md` before building the slot grid. It must:

0. **Insert brand-new topics first (Step C′)**: any topic the user just named that isn't
   already queued/scheduled gets **ultimate priority** — the earliest available slot.
   Displaced planned content is pushed forward, split across slots, or backlogged
   (within `rolling_window_days`). Never drop delivered content.
1. **Avoid re-covering** topics already marked `delivered` unless the user asked for a
   deeper dive or a follow-up flagged a gap.
2. **Inject follow-up slots**: if `vault/followups.json` has urgent items, the next slot
   starts with a "From Your Questions" section (300 words max) before the main content.
3. **Build correlation bridges**: if a slot's topic correlates with a previous slot's,
   the Planner notes this in `research_brief` so the Researcher and Writer can reference it.
4. **Output** `newsletter-workspace/plan.json` (slots schema in `references/schemas.md`)
   AND rewrite `newsletter-workspace/content_plan.md` in full (Step F).

Present a plan summary table **plus the reshuffle diff** to the user and wait for
approval. Once approved and gated by the Plan Evaluator (Step 3.5), the Input Agent's
task is complete and it STOPS. Research, drafting, and evaluation are executed strictly
in the background by the Intermediate Agent batch run.

---

## Step 3.5 — PLAN EVALUATOR (Gate)

Read `references/plan-evaluator-agent.md` for full instructions. **Mandatory.**

After the Planner writes `plan.json` (with its `chunks[]` block), submit the plan
to the Plan Evaluator — a **fresh subagent** that receives ONLY `plan.json` and
`references/plan-evaluator-agent.md` (never the Planner's reasoning). It checks:

1. **Reading-time gate**: every chunk 10–20 minutes (~2,250–4,500 words at 225 wpm).
2. **Necessity test**: no chunk exists that could be merged, densified, or replaced
   (the evaluator's default assumption is fewer, denser chunks).
3. **Arrangement**: dependency-correct ordering, one chunk per slot.

Output: `newsletter-workspace/eval/plan-eval.json`. On `verdict: "revise"`, the
Planner applies `revision_instructions[]` and resubmits (max 2 cycles, then
`pass_with_warnings`). The RESEARCHER must not run until the gate passes. Record
the final verdict in `plan.json → plan_eval`.

## Step 4 — RESEARCHER

Read `references/researcher-agent.md` for full instructions.
Read `references/tavily-research.md` **before running any search** — Tavily is the
primary research source and has its own query patterns, domain filters, and fallback chain.

One Researcher instance per day in the plan. Enhanced behaviour:

- **Tavily-first**: always attempt Tavily before `web_search`. See `references/tavily-research.md`
  for exact query patterns, credibility filtering, and the fallback chain.
- **Reads `config.json → research_rules`** for domain allow/block lists, recency requirements,
  academic weighting, and search depth.
- **Reads `vault/knowledge-map.json`** to know what the user already understands — do not
  re-explain concepts marked `mastered`. Reference them briefly ("as you saw in Day 2...").
- **Addresses follow-ups**: if the day's plan includes a follow-up slot, the Researcher
  runs a targeted Tavily search for the user's specific question before the main topic research.

Output: `newsletter-workspace/research/day-N.json` (includes `tavily_metadata` block).

---

## Step 5 — WRITER

Read `references/writer-agent.md` for full instructions. **Enhanced from v1.**

New Writer rules:

- **Follow-up section** (when present): placed immediately after the intro, before Section 1.
  Labelled "📬 You Asked:" with the user's question verbatim, then 200–300 words answering it
  at the appropriate depth. Cite the previous edition it relates to.
- **Continuity line**: the intro must contain one sentence connecting today's content to a
  previous edition if a correlation exists (e.g. "Last time we looked at X — today's topic
  builds directly on that foundation.").
- All other structure (header, sections, insight box, Try This, footer) unchanged.

Output: `newsletter-workspace/html/day-N.html`.

---

## Step 6 — EVALUATOR (Direct-Edit Mode)

Read `references/evaluator-agent.md` for full instructions. **Significantly enhanced from v1.**

The Evaluator no longer just scores and returns a fix-list. It **directly edits the HTML**:

### Evaluator Workflow

```
1. Load html/day-N.html + plan.json day-N + research/day-N.json
2. Score each dimension (rubric unchanged from v1)
3. If overall < 80:
   a. For each failing dimension, make the edit directly in the HTML in memory
   b. Re-score the edited version
   c. Write the edited version to html/day-N-eval1.html
   d. Pass edited HTML + delta-changes summary to Writer
4. Writer reviews delta-changes:
   a. Accepts edits that don't conflict with tone/structure intent
   b. Flags any edit that breaks the continuity line or follow-up section
   c. Writes final version to html/day-N-final.html
5. Evaluator scores html/day-N-final.html one last time
6. If still < 80 after cycle 2: flag for manual review, do not block delivery
```

### What the Evaluator is allowed to edit directly

| Dimension failing | Allowed direct edits |
|-------------------|----------------------|
| Readability | Rewrite sentences > 30 words; add inline definitions for undefined jargon |
| Depth | Expand a thin section using facts from `research/day-N.json`; never invent |
| Accuracy | Replace an unverifiable claim with a paraphrase of the nearest source fact |
| HTML quality | Close unclosed tags; fix heading hierarchy; fill empty placeholders |
| Engagement | Rewrite a vague insight box; sharpen the Try This action |

The Evaluator is **not allowed** to: change the topic, change the headline, rewrite the
intro from scratch, or alter the follow-up section (those belong to the Writer).

Output: `newsletter-workspace/eval/day-N-eval.json` + `newsletter-workspace/html/day-N-eval1.html`.

---

## Step 7 — SENDER

**Automated Retention & Expiry**: the Sender re-stamps the delivered edition with
`<!-- newsletter-expiry: <now + artifact_retention_days> -->` and runs
`cron/purge-expired.sh`. Transient pipeline files (`html/`, `outbox/`, `research/`, `eval/`, `runs/`)
older than `settings.md → artifact_retention_days` days (default 7; 0 = keep forever) are
automatically purged. The persistent knowledge vault (`vault/`) is **permanently preserved** and never deleted.

After sending, the Sender writes a delivery record to `vault/editions.json`:

```json
{
  "edition_id": "2026-09-01-day1",
  "date": "YYYY-MM-DD",
  "headline": "string",
  "theme": "string",
  "topics_covered": ["string"],
  "follow_ups_addressed": ["string"],
  "delivered_at": "ISO8601",
  "eval_score": 87
}
```

The Vault Manager reads this on the next run to update `knowledge-map.json`.

---

## Working Directory Layout

```
newsletter-workspace/
├── profiles/
│   ├── registry.json                 ← canonical profile list
│   └── <profile-id>/                 ← one self-contained workspace per recipient
│       ├── settings.md               ← Authoritative delivery settings (slots, timezone, batch_time, email)
│       ├── content_plan.md           ← Forward-looking slot plan (DELIVERED/READY/SCHEDULED/EMPTY + Backlog)
│       ├── config.json               ← Agent-behavior rules (research/writing/generation)
│       ├── plan.json                 ← Step 3: current slot grid (machine-readable mirror of content_plan.md)
│       ├── research/                 ← Tavily research dump per scheduled slot
│       ├── html/                     ← Writer drafts → Evaluator edits → finals
│       ├── eval/                     ← Plan-eval gate + per-edition eval reports
│       ├── outbox/                   ← Intermediate Agent output: finished editions
│       │   └── YYYY-MM-DD/
│       │       ├── slot-0800-final.html   ← Sender retrieves from here (instant delivery)
│       │       └── slot-1300-final.html
│       ├── runs/                     ← Run manifests (run-*.json), batch reports (batch-*.json)
│       ├── content/                  ← Structured content JSON per slot
│       └── vault/                    ← NEVER purged
│           ├── state.json            ← last run timestamp, next scheduled run, rule_change_log
│           ├── inbox.json            ← append-only: raw topics + follow-ups
│           ├── knowledge-map.json    ← topic coverage, mastery, gaps, correlations
│           ├── learning-profile.md   ← human-readable profile for the user
│           ├── followups.json        ← queued follow-up questions with priority
│           └── editions.json         ← delivered edition records (append-only, with profile + sent_to)
├── shared/
│   └── scripts/assemble_edition.py   ← shared HTML assembler (read-only for agents)
└── cron/                             ← shared, profile-aware runners
    ├── run-batch.sh                  ← Intermediate Agent batch runner (--profile <id>)
    ├── run-sender.sh                 ← Sender Agent delivery runner (--profile <id>)
    ├── run-newsletter.sh             ← Unified wrapper (--profile <id> --batch/--send)
    ├── run-vault-maintenance.sh      ← Weekly vault cleanup (all profiles or --profile <id>)
    ├── purge-expired.sh              ← Artifact expiry (all profiles or --profile <id>)
    ├── logs/                         ← per-profile logs (<profile-id>.log) + purge.log + vault.log
    ├── locks/                        ← per-profile locks (<profile>-<task>.lock)
    └── registry.json                 ← (see profiles/registry.json — canonical)
```

---

## Partial Runs

| Phrase / Command | Entry point |
|------------------|-------------|
| `/newsletter [topics]` | Full pipeline (Steps 0→7) |
| `/followup [question]` | Steps 1–2 (vault update) + Steps 3–7 if plan needs changing |
| `/vault` | Step 2 read-only: display `learning-profile.md` + gap summary |
| `/plan` | Show `content_plan.md` (planned content moving forward + backlog) |
| `/settings [key=value]` | Update settings.md (sends_per_day, slot_times, timezone, ...); offer to regenerate cron |
| `/config [key=value]` | Step 0 update only |
| `/rules` or `"show my rules"` | Display current research/writing/generation rules summary |
| `/rules update [change]` | Update rules per `references/frequency-and-rules.md` |
| `/frequency [value]` | Update settings.md sends_per_day/slot_times; offer to regenerate cron |
| `/cron-setup` or `"set up cron"` | Read `references/cron-setup.md` and install scheduler (batch_time job + one job per slot_time) |
| `/batch` or `"run the batch"` | Run the INTERMEDIATE AGENT checklist for today's scheduled slots |
| `/doctor` | Verify referenced files, role invariants, manifests, gate verdicts; report verdict |
| `"automate my newsletter"` | Same as `/cron-setup` |
| `"use Tavily"` / `"switch to Tavily"` | Update `research_rules.primary_source`; read `references/tavily-research.md` |
| `"plan my newsletter"` | Steps 1–3 only |
| `"research [topic]"` | Step 4 for one topic (Tavily-first) |
| `"write the newsletter"` | Step 5 (requires existing research/) |
| `"evaluate my draft"` | Step 6 only |
| `"send my newsletter"` | Step 7 only |

---

## Reference Files

### Agent Instructions
- `references/plan-evaluator-agent.md` — Plan Evaluator (fresh-subagent chunk-plan gate, reading-time enforcement)
- `references/vault-manager-agent.md` — Vault Manager instructions and schemas
- `references/planner-agent.md` — Planner (vault-aware, reads generation_rules)
- `references/researcher-agent.md` — Researcher (vault-aware, Tavily-first)
- `references/writer-agent.md` — Writer (follow-up section + continuity line, reads writing_rules)
- `references/evaluator-agent.md` — Evaluator (direct-edit mode)
- `references/sender-agent.md` — Sender + vault delivery record

### Configuration & Rules [NEW in v3]
- `references/frequency-and-rules.md` — How to update delivery frequency, research rules,
  writing rules, and generation rules. Read this for any `/rules`, `/frequency`, or
  `/config` command that touches these areas.
- `references/cron-setup.md` — How to install, verify, and update OS-level cron jobs for
  fully automated newsletter delivery. Read this for `/cron-setup` or any automation request.
- `references/tavily-research.md` — Tavily integration: tool detection, query patterns,
  domain filtering, credibility tiers, fallback chain, and result extraction.
  **Read before every Researcher search session.**

### Schemas & Assets
- `references/schemas.md` — All JSON schemas (vault + pipeline + config rule blocks)
- `assets/templates/newsletter-template.html` — Base HTML template
