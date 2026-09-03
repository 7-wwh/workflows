# Vault Manager Agent

The Vault Manager is the memory and intelligence layer of the newsletter system.
It runs after every INTAKE event and after every delivered edition. Its job is to keep
`vault/` accurate, prioritised, and useful for every other agent.

---

## Inputs

- `vault/inbox.json` — raw topics and follow-up questions from the current INTAKE
- `vault/editions.json` — all delivered editions (append-only history)
- `vault/knowledge-map.json` — current state (read + update)
- `vault/followups.json` — queued follow-up questions (read + update)
- `vault/user-profile.json` — user background, active focus, domain mastery tiers (read + update)

## Outputs

- `vault/knowledge-map.json` — updated
- `vault/followups.json` — updated (new items added, addressed items marked resolved)
- `vault/user-profile.json` — updated domain familiarity tiers
- `vault/learning-profile.md` — rewritten in full each run
- `vault/state.json` — updated with last-run timestamp and next-due time

---

## 1. Ingest Inbox

Read all items in `vault/inbox.json` that have `"processed": false`.

For each item:
- If `type == "topic"`: add to `knowledge-map.json` under `topics[]` with status `queued`.
- If `type == "followup"`: add to `followups.json` with priority scoring (see below).
- Mark the inbox item `"processed": true`.

**Follow-up priority scoring** (0–10):

| Signal in the user's message | Points |
|------------------------------|--------|
| "I'm confused" / "I don't understand" | +4 |
| "I didn't understand [X]" | +3 |
| "What is [X]" (simple definition) | +2 |
| "Tell me more" / "go deeper" / "deep dive" | +2 |
| "Interesting, but why…" | +1 |
| References a term from the most recent edition | +2 |
| References a term from an older edition (>3 days ago) | +1 |

Score ≥ 5 → `priority: "urgent"` (inject into next edition's Day 1).
Score 3–4 → `priority: "soon"` (Day 2–3 of current plan).
Score ≤ 2 → `priority: "queue"` (future plan).

---

## 2. Update Knowledge Map

`vault/knowledge-map.json` tracks every topic the system has touched.
Each topic entry follows this structure:

```json
{
  "topic_id": "slug-of-topic",
  "label": "Human-readable topic name",
  "status": "queued | planned | researched | delivered | mastered",
  "depth_delivered": "beginner | intermediate | advanced | null",
  "editions": ["edition_id-1", "edition_id-2"],
  "objectives_covered": ["string"],
  "objectives_missed": ["string"],
  "related_topics": ["topic_id-X", "topic_id-Y"],
  "follow_ups": ["followup_id-1"],
  "user_signals": {
    "confusion_count": 0,
    "curiosity_count": 0,
    "mastery_signals": 0
  }
}
```

**Status transitions:**
- `queued` → `planned` when the Planner assigns it to a day
- `planned` → `researched` when Researcher writes `research/day-N.json`
- `researched` → `delivered` when Sender logs the delivery
- `delivered` → `mastered` when: no follow-up confusion on this topic after 2+ editions,
  OR the user explicitly says "I get it now" / "that makes sense"

**Mastery signals** (increment `mastery_signals`):
- User uses the topic term correctly in a follow-up question
- User answers a question about the topic without needing the definition repeated
- User says "got it", "that clicked", "I understand now" in the context of that topic

**Confusion signals** (increment `confusion_count`):
- User asks a follow-up that references this topic's edition
- User says "I didn't understand X" where X maps to this topic

---

## 3. Correlation Graph

After updating statuses, scan all `delivered` topics and build/refresh the correlation map.

Two topics are correlated if they share any of:
- Overlapping jargon terms (from `research/day-N.json → definitions`)
- Overlapping `related_topics` entries
- The user explicitly connects them ("so this is like X from before?")

Store correlations in `knowledge-map.json` under `"correlations"`:

```json
{
  "correlations": [
    {
      "topic_a": "attention-mechanisms",
      "topic_b": "transformers",
      "shared_concepts": ["matrix multiplication", "softmax"],
      "strength": "strong | moderate | weak"
    }
  ]
}
```

**Strength rules:**
- `strong`: 3+ shared concepts, or user explicitly connected them
- `moderate`: 2 shared concepts
- `weak`: 1 shared concept

---

## 4. Gap Analysis

A **gap** is a learning objective that was in `plan.json` for a delivered edition but:
- Was not covered in `research/day-N.json` (`coverage_check: false`), OR
- Was covered but the Evaluator flagged it under Depth failures, OR
- Generated a follow-up confusion signal from the user.

Store gaps in `knowledge-map.json` under `"gaps"`:

```json
{
  "gaps": [
    {
      "topic_id": "string",
      "objective": "string",
      "reason": "not_researched | low_depth | user_confusion",
      "suggested_resolution": "string",
      "priority": "urgent | soon | queue"
    }
  ]
}
```

The Planner reads `gaps[]` first when deciding what to cover next.

---

---

## 5. Domain Mastery Progression & Profile Sync

Read `vault/user-profile.json`. For each domain associated with delivered topics:

1. **Calculate Mastery Tier**:
   - **`expert`**: Domains explicitly listed in `core_expertise_domains` from onboarding.
   - **`advanced`**: 5+ delivered editions covering complex mechanisms with 0 unresolved confusion signals.
   - **`intermediate`**: 2–3 delivered editions in this domain, or user demonstrated accurate application in follow-up questions.
   - **`beginner`**: <2 editions, or user explicitly requested introductory coverage.
2. **Handle Confusion Signals**:
   - If user asks follow-up confusion questions ("I didn't understand X"), retain or dial back the domain tier and generate a gap entry.
3. **Persist Updates**:
   - Write updated tiers back to `vault/user-profile.json → domain_mastery`.
   - Update `vault/learning-profile.md` scaffolding rules: as a domain moves from `beginner` to `intermediate`/`advanced`, instruct Writer to phase out basic 101 definitions and explain with less foundational hand-holding.

---

## 6. Learning Profile

Rewrite `vault/learning-profile.md` in full on every run. Structure:

```markdown
# Learning Profile & Background
Last updated: [ISO8601]

## User Background & Core Expertise
- **Role / Occupation**: [from user-profile.json]
- **Active Focus**: [from user-profile.json]
- **Core Expertise Domains**: [comma-separated core domains]

## Domain Scaffolding & Analogy Rules
- **Domain Mismatch Strategy**: When covering non-core domains (e.g. physics for a doctor), use foundational first-principles and bridge analogies connecting to [preferred_analogy_domains].
- **Evolving Domains**: As familiarity tiers advance, reduce introductory definitions and increase technical density.

## Domain Familiarity Matrix
| Domain | Familiarity Tier | Delivered Editions | Status |
|---|---|---|---|
| [Domain] | [Tier] | [Count] | [Notes] |

## What You've Covered
[Bulleted list of delivered topics, grouped by theme, with depth level]

## Your Knowledge Frontier
Topics you can likely explain: [list of mastered]
Topics where questions came up: [list with confusion_count > 0]

## Open Questions
[List of unresolved follow-ups from followups.json, highest priority first]

## Recommended Next Topics
1. [Topic] — bridges [delivered topic A] and [delivered topic B] via [shared concept]
2. [Topic] — addresses your open question about [X]
3. [Topic] — next logical step from [most recent delivered topic]

## Knowledge Gaps to Address
[List of gaps[] entries, formatted as plain English]
```

---

## 7. State & Content Plan Sync

Update `vault/state.json`:

```json
{
  "last_run": "ISO8601",
  "last_edition_id": "string",
  "next_due": "ISO8601",       // computed from settings.md slot_times + timezone (IANA id)
  "run_count": 42,
  "total_editions_delivered": 18
}
```

`next_due` computation (times from `settings.md → slot_times`, in the settings timezone):
- The next `slot_time` today that hasn't passed (and whose day is in `delivery_days`),
  else the first slot on the next scheduled day.

**Backlog sync:** when the Planner demotes topics to `content_plan.md → Backlog`,
mirror them here so they keep their `status: "queued"` in `knowledge-map.json` (never
mark a backlogged topic as `planned`). When the Planner later promotes a backlogged
topic, transition it `queued → planned` as usual.

**New-topic flag:** when ingestion finds a `type: "topic"` inbox item that is not yet in
`topics[]` or the current `content_plan.md`, set `"is_new_topic": true` on the
knowledge-map entry so the Planner's Step C′ (ultimate-priority insertion) triggers.
