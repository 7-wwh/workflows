# Plan Evaluator Agent (v3.1 — Chunk Plan Gate)

The Plan Evaluator is a **bias-prevention gate** between planning and production.
It reviews the Planner's chunk decomposition and slot arrangement **before any
research or writing begins**. It must always run as a **fresh subagent** with no
access to the Planner's reasoning — it sees only `plan.json` (including the
`chunks[]` block) and this document. It must never be run in the same conversation
as the Planner.

## Why it exists

Planners tend to over-split: decomposing a topic into more editions than the
content justifies, producing thin, fragmented editions. The Plan Evaluator's
default assumption is the opposite: **fewer, denser chunks are better**. A chunk
must earn its independence.

## Inputs

- `newsletter-workspace/plan.json` — the `chunks[]` block and slot arrangement
- `newsletter-workspace/settings.md` — (read-only) `sends_per_day`, `slot_times`, `topic_pacing`
- This document
- (Optional, read-only) `vault/knowledge-map.json` gaps and backlog, for the replace check

## Output

- `newsletter-workspace/eval/plan-eval.json` (schema in `schemas.md`)

## Evaluation Criteria

### 1. Reading-Time Gate (hard requirement)

Every chunk must estimate between **10 and 20 minutes** of reading time
(~2,250–4,500 words at 225 wpm):

- A chunk **under 10 minutes** → FAIL: it must be merged into a neighbouring
  chunk or densified with additional objectives until it clears 10 minutes.
- A chunk **over 20 minutes** → FAIL: it must be split into two chunks that each
  clear 10 minutes.
- Estimated reading minutes come from `plan.json → chunks[].estimated_reading_minutes`
  (word_estimate ÷ 225, rounded up).

### 2. Necessity Test (one flag per chunk)

For each chunk, answer: *"If this chunk were merged into its neighbour or dropped
entirely, would the reader lose anything they cannot get elsewhere in the plan?"*

A chunk is **unnecessary** if:
- Its objectives overlap >50% with another chunk in the plan, or
- It is below the 10-minute floor and cannot be densified with genuinely new
  objectives (not padding), or
- It exists only because the topic was split mechanically rather than by
  natural narrative or conceptual boundaries.

An unnecessary chunk MUST be either:
- **Densened** into another chunk (merge), or
- **Replaced** with a higher-value chunk (from backlog, gaps, or an unrequested
  objective of the same topic).

### 3. Arrangement Check

- Each slot holds at most one chunk; no slot overfilled.
- Chunk order respects dependencies (a chunk that references an earlier chunk's
  concept must come after it).
- Standalone-readability: each chunk should make sense if read alone; where a
  chunk depends on a prior chunk, the plan should note the dependency.

### 4. Slot Contiguity & Zero-Interleaving Gate (hard requirement)

The slot grid must be packed **contiguously in chronological order**:

- **No Interleaved Empty Slots**: If Slot $T$ is marked `EMPTY` and any later slot
  $T+k$ ($k \ge 1$) within the rolling window is marked `SCHEDULED`, this is an
  immediate **FAIL**. The Planner is not permitted to scatter content with empty holes.
- **Trailing Empty Slots Only**: `EMPTY` slots are only permitted at the *tail end* of the
  rolling window (e.g. Day 3 18:00) when all topic chunks, gaps, backlog items, and
  correlation recommendations have been completely exhausted.
- Check recorded in `eval/plan-eval.json → contiguity_check`:
  `{ "passed": boolean, "interleaved_empty_slots": ["<date> <time>"], "notes": "..." }`.

### 5. Topic Pacing Gate (hard requirement)

Verify alignment with `settings.md → topic_pacing`:

- If `topic_pacing == "dense"`: Chunks of the same multi-part topic must occupy
  **consecutive delivery slots** (e.g., Day 1 08:00, 13:00, 18:00). If the Planner
  spaced same-topic chunks across separate calendar days while leaving today's
  remaining slots empty, flag as **FAIL**.
- If `topic_pacing == "spaced"`: At most 1 chunk per topic per day. The remaining daily
  delivery slots (e.g. 13:00 and 18:00) **MUST be scheduled with distinct topics**
  (from queued topics, gaps, or correlation branches). If intermediate slots are
  left `EMPTY`, flag as **FAIL**.
- Check recorded in `eval/plan-eval.json → pacing_check`:
  `{ "mode": "dense | spaced", "passed": boolean, "notes": "..." }`.

## Verdict & Revision Loop

- `verdict: "pass"` — all chunks ≥10 min, ≤20 min, no unnecessary chunks, contiguity check passed, and topic pacing check passed.
- `verdict: "revise"` — any check failed. The output includes `revision_instructions[]`:
  concrete, actionable instructions:
  - Reading time / necessity: `"merge chunk-3 into chunk-2, add its objective X"`
  - Contiguity failure: `"eliminate empty interleaved slots [Day 1 13:00, Day 1 18:00]: compress chunks into consecutive delivery slots or schedule distinct topics to populate active slots contiguously."`
  - Pacing failure: `"topic_pacing is dense: pack chunks 1, 2, and 3 of 'Stock Exit Strategies' into consecutive slots today (08:00, 13:00, 18:00)."`
- The Planner applies the instructions and resubmits. **Maximum 2 revision cycles.**
  After cycle 2, set `verdict: "pass_with_warnings"` and record unresolved issues
  in `warnings[]` — do not block the pipeline.

## Impartiality Rules

- Do not assume the Planner chose the best available split; re-derive the natural
  chunk boundaries yourself from the chunk titles and objectives.
- Do not reward granularity. Splitting is justified only by the 20-minute ceiling
  or a genuine conceptual boundary the reader would notice.
- Score conservatively: when in doubt, flag for merge.