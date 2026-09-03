# Planner Agent (v2 — Vault-Aware)

The Planner builds a rolling 3-day content calendar that is personalised to the user's
vault state: what they've covered, what confused them, and what topics correlate.

---

## Inputs

- `vault/knowledge-map.json` — topic statuses, gaps, correlations
- `vault/followups.json` — prioritised follow-up questions
- `vault/learning-profile.md` — user's knowledge frontier
- `vault/user.md` — user profession, field of study, domain depth tiers, and curiosity sparks
- `newsletter-workspace/settings.md` — **authoritative settings**: sends_per_day,
  slot_times, delivery_days, rolling_window_days, new_topic_priority, allow_topic_split, topic_pacing
- `newsletter-workspace/content_plan.md` — the current forward-looking plan (may be empty)
- `newsletter-workspace/config.json` — depth level (settings.md wins on any conflict)

## Outputs

- `newsletter-workspace/plan.json` (schema in `schemas.md` — slots per day)
- `newsletter-workspace/content_plan.md` (rewritten in full every replan)

---

## Planning Logic (in order)

### Step 0 — Plan in CHUNKS, not slots (v3.1 — mandatory)

Do **not** assign topic-parts directly to slots. Two phases:

**Phase 1 — Chunk decomposition.** Decompose the topic into **content chunks**:
self-contained, individually deliverable units of learning. For each chunk record
(in `plan.json → chunks[]`): `chunk_id`, `title`, `learning_objectives`,
`word_estimate`, `estimated_reading_minutes` (word_estimate ÷ 225, round up),
`standalone` (can it be read alone?), and `depends_on` (earlier chunk ids, if any).
Chunk boundaries must follow natural narrative or conceptual boundaries — never
split mechanically just because a topic is large.

**Phase 2 — Slot arrangement & Contiguous Packing.** Only after chunking, arrange chunks into the slot
grid. One chunk per slot.

**Contiguous Slot Packing & Zero-Interleaving Invariant (MANDATORY)**:
- Slots must be populated in strict chronological, contiguous order: `Day 1 [Slot 0] → Day 1 [Slot 1] → ... → Day N [Slot M]`.
- **NEVER leave internal `EMPTY` slots between scheduled slots.** An earlier slot may NEVER be marked `EMPTY` if any later slot in the rolling window is `SCHEDULED`.
- Respect `settings.md → topic_pacing`:
  - **`dense`** (default): Chunks of the same multi-part topic are assigned to **consecutive delivery slots** (e.g. Part 1 at Day 1 08:00, Part 2 at Day 1 13:00, Part 3 at Day 1 18:00).
  - **`spaced`**: At most 1 chunk per topic per day (e.g. Part 1 at Day 1 08:00, Part 2 at Day 2 08:00, Part 3 at Day 3 08:00). When `spaced` is active, the intermediate daily slots (e.g. 13:00 and 18:00) **MUST NOT** be left empty; they must be filled with distinct topics from the priority hierarchy (gaps, queued topics, or correlation branches).
- Trailing slots at the tail end of the rolling window may remain `EMPTY` only if all queues, gaps, and correlation candidates are completely exhausted, but active slots must never be separated by empty gaps.

**Chunk constraints (hard):**
- Every chunk: **10–20 minutes reading time** (~2,250–4,500 words).
  Under 10 → merge or densify. Over 20 → split.
- Prefer the **fewest chunks** that satisfy the constraints. A chunk must earn
  its independence.

**Phase 3 — Plan Eval gate.** Submit `plan.json` to the **Plan Evaluator** (a fresh
subagent — see `references/plan-evaluator-agent.md`). On `verdict: "revise"`, apply
its `revision_instructions[]` (merge, densify, or replace chunks) and resubmit.
Max 2 revision cycles, then proceed `pass_with_warnings`. Do not run Researcher
until the gate passes.

### Step A — Resolve urgent follow-ups

Check `vault/followups.json` for items with `priority: "urgent"`.
If any exist:
- Day 1 of the plan gets a `follow_up_slot` entry (see schema).
- The `research_brief` for Day 1 starts with: "PRIORITY: Answer the user's question
  '[question text]' before covering the main topic."

### Step B — Fill gaps first

Check `vault/knowledge-map.json → gaps[]` for items with `priority: "urgent"` or `"soon"`.
These take precedence over new topics. A gap resolution day has:
- Theme: "Revisiting [original topic]: [gap objective]"
- Headline: phrased as an answer to the missed objective
- Research brief notes: "This revisits a gap from a previous edition. Do not re-cover
  content already in [edition_id]. Focus only on [gap objective]."

### Step C′ — Insert brand-new user topics (ULTIMATE priority)

This step runs **before** gap filling competes for slots and **before** any queued
topic is placed. It exists to handle: *"the user says 'I want to learn ABC' while
other topics are already scheduled in the rolling window."*

A **new topic** is any inbox item with `type: "topic"` that is not already present in
`knowledge-map.json → topics[]` or in the current `content_plan.md`.

When `settings.md → new_topic_priority == "ultimate"` (the default):

1. The new topic **must occupy the earliest available slot** in the window — ahead of
   every already-planned topic, including topics scheduled for today.
2. **Re-evaluate the existing plan**: load `content_plan.md` and, for every topic that
   now conflicts with the new topic's target slot, apply (in order of preference):
   - **Push forward** — move the displaced topic to the next free slot within the window.
   - **Split** — if `settings.md → allow_topic_split == true` and the displaced topic has
     2+ learning objectives, split it into parts ("Pydantic Day 2: Validators" →
     "Validators (Part 1)" slot today 18:00 + "Settings & pydantic-core (Part 2)" slot
     tomorrow 08:00). Each part gets its own research brief and objectives.
   - **Backlog** — if the window (`today + rolling_window_days`, default 3 days) is full,
     demote the displaced topic to the `Backlog` section of `content_plan.md` with its
     original objectives intact. Backlogged topics are re-promoted by Step C as slots free up.
3. A topic that was already **delivered** is never moved or split; only
   `scheduled`/`planned` items are candidates for displacement.
4. Multi-chunk topic distribution:
   - When `settings.md → topic_pacing == "dense"` (default): assign all chunks of the topic to **consecutive upcoming delivery slots** across `slot_times` (e.g., today 08:00, 13:00, 18:00). Do not space them across separate calendar days if slots are available today.
   - When `settings.md → topic_pacing == "spaced"`: assign at most 1 chunk per calendar day, and immediately fill the remaining daily delivery slots with distinct topics, gaps, or correlation bridges. Under no circumstances may intermediate daily slots be left `EMPTY`.

### Step C — Fill remaining slots & Spark Curiosity

From `knowledge-map.json → topics[]` where `status == "queued"` (plus the Backlog
section of `content_plan.md`, oldest first), fill slots that remain after Step C′.
Pick topics that:
1. Have not been `delivered` at the current depth level.
2. Correlate with recently delivered topics (prefer `strength: strong` bridges).
3. Were recommended in `learning-profile.md → Recommended Next Topics` or **`vault/user.md § 4 (Curiosity Sparks)`** to bridge the user's field of study with novel interdisciplinary horizons and ignite curiosity.

Prioritise correlation bridging: if a new topic shares concepts with the most recent
delivered topic or connects to the user's field of study in `vault/user.md`, note the bridge in `research_brief`.

### Step D — Distribute across the slot grid

Read `sends_per_day`, `slot_times`, `delivery_days`, and `rolling_window_days` from
`settings.md`. The plan is a **slot grid**: `delivery_days ∩ [today, today + rolling_window_days]`
× `slot_times` (e.g. 3 sends/day × 3 days = 9 slots).

**Grid distribution rules**:
- Populate slots contiguously without gaps. If the primary topic does not exhaust the grid, draw from:
  1. Priority follow-up slots (`vault/followups.json`)
  2. Urgent/soon knowledge-map gaps (`vault/knowledge-map.json → gaps[]`)
  3. Queued topics & Backlog (`vault/knowledge-map.json → topics[]`)
  4. Curiosity Sparks from `vault/user.md § 4` (cross-disciplinary topics tied to user's profession)
  5. Correlated companion topics or case studies from `learning-profile.md`
- Each slot gets:
  - One main topic-part (or gap resolution)
  - One optional follow-up slot (if `priority: "soon"` items exist)
  - 2–3 learning objectives calibrated to domain depth in `vault/user.md` and `config.json`
  - A designated `template_type` assigned by matching the topic nature to available templates in `assets/templates/` (or `"custom"`)
- Trailing slots at the end of the rolling window may stay `EMPTY` only if no other topics, gaps, or correlations exist. Interleaved empty slots are strictly forbidden.

Depth calibration (vault & profession-aware):
- **Native Domain (user's field of study / expert)**: skip 101 definitions; focus directly on advanced mechanisms, architectural trade-offs, and frontier research.
- **Beginner (non-native domain)**: focus on first principles and intuitive analogies connected to `preferred_analogy_domains` from `vault/user.md`.
- **Intermediate**: include operational mechanics and practical trade-offs.
- **Advanced**: include edge cases, comparative benchmarks, and failure modes.

### Step E — Write research briefs

Each research brief (≤100 words) must include:
- Primary angle and specific question to answer
- Any correlation bridge to mention ("Day 1 covered X — connect to that when explaining Y")
- What to avoid ("save Z for Day 3")
- If the day has a follow-up slot: "Open with the follow-up answer before main content"

---

### Step F — Rewrite content_plan.md (mandatory, every replan)

After writing `plan.json`, rewrite `newsletter-workspace/content_plan.md` **in full**:

```markdown
# Content Plan
Last updated: [ISO8601]

## Today — 2026-09-01 (3 slots)
- [08:00] DELIVERED  | Pydantic Day 1: Models & validation
- [13:00] SCHEDULED  | ABC Part 1: Fundamentals (NEW — moved from backlog-free request)
- [18:00] SCHEDULED  | Pydantic Day 2: Validators (moved_from: today 13:00, split part 1/2)

## Tomorrow — 2026-09-02 (3 slots)
- [08:00] SCHEDULED | Pydantic Day 2 (Part 2): Settings & pydantic-core
- [13:00] SCHEDULED | Topic X: Architecture & Data Flow
- [18:00] SCHEDULED | Topic X: Error Handling Patterns

## Day 3 — 2026-09-03 (3 slots)
- [08:00] SCHEDULED | Topic Y ...
- [13:00] SCHEDULED | Topic Y ...
- [18:00] EMPTY     | (Trailing empty slot: backlog exhausted)

## Backlog (unscheduled)
- Topic Z — demoted 2026-09-01, original objectives intact
```

Statuses: `DELIVERED | SCHEDULED | EMPTY` for slots; Backlog lists demoted topics.
Mark every moved slot with `(moved_from: ...)` so the user can audit the reshuffle.
Slots must be contiguously populated; trailing EMPTY slots are only valid at the window's end.

## Plan Confirmation

After rewriting `content_plan.md`, present a human-readable summary **plus the diff**:

```
Day 1 | 2026-09-01 | 08:00 Pydantic D1 (delivered) | 13:00 ABC P1 (NEW) | 18:00 Pydantic D2 P1 (moved)
Day 2 | 2026-09-02 | 08:00 Pydantic D2 P2 (split)  | 13:00 Topic X            | 18:00 —
Day 3 | 2026-09-03 | ...
Backlog: Topic Y
Changes: ABC took today's 13:00 slot; Pydantic D2 moved to 18:00 and split;
         Topic Y demoted to backlog.
```

If running interactively: ask "Does this look right? Any changes?" and wait.
On user approval or edits: update `plan.json` + `content_plan.md` and pass the Plan Evaluator gate.

**Input Agent Completion**: Once the gated plan is saved with slots marked `SCHEDULED`, the Input Agent's work is complete. Stop here. The Intermediate Agent will execute all research, drafting, and evaluation in the background during the nightly batch at `batch_time`.
