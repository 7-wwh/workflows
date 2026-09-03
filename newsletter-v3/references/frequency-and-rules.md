# Frequency & Rules Configuration

This document governs how the user updates:
1. **Delivery settings** — `newsletter-workspace/settings.md` (authoritative): sends_per_day,
   slot_times, delivery_days, timezone, rolling_window_days
2. **Research rules** — how the Researcher agent behaves (sources, depth, breadth)
3. **Writing rules** — style, structure, and length constraints for the Writer agent
4. **Generation rules** — how the Planner selects and sequences topics

## 0 — settings.md (authoritative settings file)

`newsletter-workspace/settings.md` is the single source of truth for scheduling and
delivery. All agents (Planner, Sender, cron output agent) read it before every run.
If `config.json` disagrees with `settings.md`, **settings.md wins** and the agent warns
the user. Timezone values must be IANA location identifiers (`Asia/Kuala_Lumpur`,
`Europe/Berlin`) — never UTC offsets. `auto` is a placeholder resolved once by
`/cron-setup` into a real IANA zone and written back.

```markdown
sends_per_day: 3
slot_times: ["08:00", "13:00", "18:00"]
batch_time: "03:00"        # Intermediate Agent cron: compile & write all editions for the day
delivery_days: ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
email: null
timezone: auto
rolling_window_days: 3
new_topic_priority: ultimate
allow_topic_split: true
topic_pacing: dense        # dense (pack same-topic chunks into consecutive slots) | spaced (max 1 chunk per topic per day, remaining daily slots filled with distinct topics)
artifact_retention_days: 7  # auto-delete transient artifacts (html, outbox, research, eval, runs) after N days (0 = keep forever)
html_expiry_days: 7        # legacy alias for artifact_retention_days
```

Field reference:

| Field | Options | Effect |
|-------|---------|--------|
| `sends_per_day` | integer 1–6 | Delivery slots per day (must match len(slot_times)) |
| `slot_times` | array of "HH:MM" | The actual delivery times for Sender Agent instant retrieval |
| `batch_time` | "HH:MM" (e.g. "03:00") | Time for Intermediate Agent nightly batch production (compile/write/eval) |
| `delivery_days` | array of mon…sun | Days the newsletter runs |
| `timezone` | IANA location id | Used by cron, Sender timestamps, and `next_due` |
| `rolling_window_days` | integer 1–7 | Planner never schedules beyond today + N days |
| `new_topic_priority` | `ultimate \| queue_order` | `ultimate`: brand-new user topics take the earliest slot and displace planned content |
| `allow_topic_split` | true/false | Planner may split a topic across slots/days when reshuffling |
| `topic_pacing` | `dense \| spaced` | `dense`: pack chunks of the same topic into consecutive available slots. `spaced`: max 1 chunk per topic per day; remaining daily slots MUST be filled with distinct topics/gaps (no empty holes) |
| `artifact_retention_days` | integer ≥ 0 | Delete transient pipeline artifacts (`html/`, `outbox/`, `research/`, `eval/`, `runs/`) N days after generation (0 = keep forever). Vault history (`vault/`) is never deleted |
| `html_expiry_days` | integer ≥ 0 | Legacy alias for `artifact_retention_days` |

When the user changes `sends_per_day` / `slot_times` / `batch_time` / `delivery_days` / `timezone`,
mirror the equivalent values into `config.json` (legacy fields) and **immediately and automatically update the Hermes Cron schedule**.
The agent never asks the user to manually run `/cron-setup` — the agent executes the update itself.

Read this file whenever the user says any of:
- "change my frequency", "send it more often", "only send weekly"
- "update my newsletter rules", "change how it writes", "change how it researches"
- "/rules", "/frequency", "/update-rules", `/config frequency=...`
- "make it shorter", "use a different tone", "focus on fewer topics"
- "always use Tavily for research", "prioritise academic sources"

---

## 1 — Delivery Frequency

### Supported Frequency Values

| User Says | Config Value | Meaning |
|-----------|-------------|---------|
| "once a day" / "daily" | `once_daily` | One edition at `delivery_time[0]` |
| "twice a day" / "morning and evening" | `twice_daily` | Two editions at `delivery_time[0]` and `delivery_time[1]` |
| "every N hours" (e.g. "every 6 hours") | `every_N_hours` | Pipeline runs every N hours; `every_N_hours: N` set in config |
| "weekly" / "once a week" | `weekly` | One edition per week; defaults to Monday at `delivery_time[0]` |
| "weekdays only" | `weekdays` | `once_daily` Mon–Fri; Saturday and Sunday skipped |
| "pause" / "stop" | `paused` | Pipeline will not auto-run; user must invoke manually |

### Updating Frequency

1. Write the new schedule values to `newsletter-workspace/profiles/<profile>/settings.md` (authoritative) and mirror to `config.json`.
2. Write the change to `vault/state.json → rule_change_log` with a timestamp.
3. **Automatically Edit Hermes Cron (MANDATORY)**:
   The agent MUST immediately update the Hermes scheduled task:
   - In interactive Hermes session: call `cronjob(action="update", job_id="newsletter:<profile>-send", schedule="<new_cron>")` (and update batch job if `batch_time` changed).
   - Or run shell runner: `bash newsletter-workspace/cron/sync-cron.sh --profile <profile>`.
   - Update `vault/state.json` (`cron_synced_at`).
4. Confirm the change to the user in plain language, including confirmation of the updated scheduler:
   > "Done — your newsletter schedule and Hermes Cron have been automatically updated:
   > • 🌙 Batch Writing: every day at `03:00`
   > • 📬 Deliveries: every day at `08:00` and `18:00` (Etc/UTC)."

### Timezone

Always store and display times in the user's local timezone (read from
`config.json → timezone`, set during `/cron-setup`). When the timezone is unknown,
show times as UTC and ask the user to confirm their timezone.

---

## 2 — Research Rules

Research rules are stored in `newsletter-workspace/config.json → research_rules`.
The Researcher agent reads this block before every search session.

### Default Research Rules Block

```json
"research_rules": {
  "primary_source": "tavily",
  "fallback_sources": ["web_search", "brave"],
  "source_diversity": "high",
  "max_sources_per_day": 4,
  "avoid_domains": ["reddit.com", "quora.com"],
  "prefer_domains": [],
  "require_recency_days": null,
  "academic_weight": "normal",
  "minimum_source_credibility": "medium",
  "search_depth": "standard"
}
```

### Field Reference

| Field | Options | Effect |
|-------|---------|--------|
| `primary_source` | `"tavily"` · `"web_search"` · `"brave"` | Which tool the Researcher calls first |
| `fallback_sources` | array of source names | Used if primary returns < 2 relevant results |
| `source_diversity` | `"low"` · `"normal"` · `"high"` | How hard the Researcher tries to mix source types |
| `max_sources_per_day` | integer 2–8 | Hard cap on sources fetched per day's research |
| `avoid_domains` | array of domain strings | Never fetch from these; skip if returned |
| `prefer_domains` | array of domain strings | Prioritise results from these domains |
| `require_recency_days` | integer or `null` | If set, only use sources published within N days |
| `academic_weight` | `"low"` · `"normal"` · `"high"` | `"high"` → prefer arXiv, PubMed, Google Scholar results |
| `minimum_source_credibility` | `"low"` · `"medium"` · `"high"` | Filter out sources below this credibility tier |
| `search_depth` | `"standard"` · `"deep"` | `"deep"` → Researcher runs 2 extra follow-up queries |

### Updating Research Rules

Parse the user's intent and update the matching field(s) in `config.json`.

Example mappings:

| User Says | Config Change |
|-----------|--------------|
| "use Tavily for all research" | `primary_source: "tavily"` |
| "focus on recent articles only" | `require_recency_days: 30` |
| "avoid social media sources" | `avoid_domains: ["reddit.com","twitter.com","x.com","quora.com","facebook.com"]` |
| "use more academic sources" | `academic_weight: "high"` |
| "go deeper on research" | `search_depth: "deep"` |
| "use at most 3 sources" | `max_sources_per_day: 3` |
| "prefer Harvard Business Review" | `prefer_domains: ["hbr.org"]` |

Always echo back the change in plain language before saving.

---

## 3 — Writing Rules

Writing rules are stored in `newsletter-workspace/config.json → writing_rules`.
The Writer agent reads this block before generating each edition.

### Default Writing Rules Block

```json
"writing_rules": {
  "tone": "friendly-professional",
  "style": "narrative",
  "max_words_per_edition": 3500,
  "min_words_per_edition": 2250,
  "max_sentences_per_paragraph": 3,
  "wall_of_text_limit_words": 150,
  "section_count": "2-3",
  "include_visual_diagrams": true,
  "diagram_style": "email-native-charts",
  "mobile_layout": "responsive-stacking",
  "include_glance_box": true,
  "include_mistakes_section": true,
  "include_lessons_section": true,
  "include_takeaways_playbook": true,
  "include_insight_box": true,
  "include_try_this": true,
  "include_definitions_box": true,
  "include_follow_up_section": true,
  "continuity_lines": true,
  "reading_level": "auto",
  "language": "en",
  "emoji_style": "structural-headers",
  "custom_sign_off": ""
}
```

### Field Reference

| Field | Options | Effect |
|-------|---------|--------|
| `tone` | `"friendly-professional"` · `"academic"` · `"casual"` · `"motivational"` | Overall voice of the Writer |
| `style` | `"narrative"` · `"report"` | `"narrative"` (default) = story arc: hook → story → mistakes → lessons → action; `"report"` = classic explainer sections |
| `max_words_per_edition` | integer | Writer must stay under this word count |
| `min_words_per_edition` | integer | Writer must exceed this word count |
| `include_visual_diagrams` | boolean | Toggle email-safe visual process flows, 2x2 matrices, and bar charts |
| `diagram_style` | `"email-native-charts"` · `"infographic-images"` | Choose between pure HTML/CSS table-based diagrams or rendered image diagrams |
| `mobile_layout` | `"responsive-stacking"` · `"fixed"` | Ensures multi-column cards stack vertically on smartphones |
| `max_sentences_per_paragraph` | integer 2–5 | Hard cap on paragraph length |
| `wall_of_text_limit_words` | integer | Max unbroken prose before a list/quote/callout break is required |
| `section_count` | `"1"` · `"2"` · `"2-3"` · `"3"` | How many story sections per edition |
| `include_glance_box` | boolean | Toggle the "This Issue at a Glance" index box |
| `include_mistakes_section` | boolean | Toggle numbered mistake blocks |
| `include_lessons_section` | boolean | Toggle lessons with takeaways/playbook |
| `include_takeaways_playbook` | boolean | Toggle the Key Takeaways + Operator Playbook boxes per lesson |
| `include_insight_box` | boolean | Toggle the non-obvious insight callout |
| `include_try_this` | boolean | Toggle the 5-minute action box |
| `include_definitions_box` | boolean | Toggle the glossary box |
| `include_follow_up_section` | boolean | Toggle follow-up Q&A blocks |
| `continuity_lines` | boolean | Toggle cross-edition reference sentences |
| `reading_level` | `"auto"` · `"grade-8"` · `"grade-12"` · `"college"` | Target reading complexity |
| `language` | BCP-47 code e.g. `"en"`, `"ms"`, `"zh-Hant"` | Output language |
| `emoji_style` | `"structural-headers"` · `"none"` | `"structural-headers"` = emoji in headers/glance box per Writer Emoji Rules; `"none"` = no emoji |
| `custom_sign_off` | string or `""` | Appended to every footer; `""` uses default |

### Updating Writing Rules

Example mappings:

| User Says | Config Change |
|-----------|--------------|
| "make it shorter" | `max_words_per_edition: 500` |
| "I want a more casual tone" | `tone: "casual"` |
| "remove the try this section" | `include_try_this: false` |
| "write it in Malay" | `language: "ms"` |
| "add emojis to headings" | `emoji_style: "structural-headers"` |
| "keep it simple" | `reading_level: "grade-8"` |
| "sign off with 'Stay curious'" | `custom_sign_off: "Stay curious 🔍"` |

---

## 4 — Generation Rules

Generation rules govern how the Planner selects, sequences, and prioritises topics.
Stored in `newsletter-workspace/config.json → generation_rules`.

### Default Generation Rules Block

```json
"generation_rules": {
  "rolling_window": 3,
  "avoid_repeat_days": 14,
  "topic_selection_strategy": "correlation-first",
  "max_new_topics_per_run": 1,
  "gap_resolution_priority": "high",
  "follow_up_priority": "urgent-first",
  "depth_progression": "auto",
  "forbidden_topics": [],
  "pinned_topics": [],
  "topic_variety": "moderate"
}
```

### Field Reference

| Field | Options | Effect |
|-------|---------|--------|
| `rolling_window` | integer 1–7 | Days planned ahead |
| `avoid_repeat_days` | integer | Don't revisit a topic within this many days |
| `topic_selection_strategy` | `"correlation-first"` · `"gap-first"` · `"queue-order"` · `"random"` | How the Planner picks from the topic queue |
| `max_new_topics_per_run` | integer 1–3 | How many brand-new topics may enter a single 3-day plan |
| `gap_resolution_priority` | `"high"` · `"normal"` · `"low"` | How urgently knowledge-map gaps are addressed |
| `follow_up_priority` | `"urgent-first"` · `"queue-order"` | Whether urgent follow-ups always go to Day 1 |
| `depth_progression` | `"auto"` · `"fixed"` | `"auto"` → depth increases as mastery grows; `"fixed"` → always use `config.depth` |
| `forbidden_topics` | array of strings | Planner will never select these topics |
| `pinned_topics` | array of strings | These always appear in the next plan (for up to 2 runs) |
| `topic_variety` | `"low"` · `"moderate"` · `"high"` | How much the Planner mixes related vs. distinct topics |
| `topic_pacing` | `"dense"` · `"spaced"` | Pacing for multi-part topics: consecutive slots vs 1 per day |

### Updating Generation Rules

| User Says | Config Change |
|-----------|--------------|
| "plan further ahead" | `rolling_window: 7` |
| "don't repeat topics for a month" | `avoid_repeat_days: 30` |
| "focus on filling gaps" | `topic_selection_strategy: "gap-first"` |
| "never cover crypto" | `forbidden_topics: ["cryptocurrency","bitcoin","blockchain"]` |
| "make sure we cover X next" | `pinned_topics: ["X"]` |
| "mix up the topics more" | `topic_variety: "high"` |
| "space out the topic", "one part per day" | `topic_pacing: "spaced"` |
| "dense packing", "learn it all today", "consecutive parts" | `topic_pacing: "dense"` |

---

## 5 — Applying a Rules Update

When any rule is changed, follow this sequence:

1. **Parse** the user's intent → identify which rule block(s) and field(s) to update.
2. **Read** the current `config.json`.
3. **Merge** the new values (do not overwrite unrelated fields).
4. **Write** the updated `config.json` (and `settings.md` if delivery settings changed) with `updated_at: <ISO8601 timestamp>`.
5. **Sync Hermes Cron**: If schedule or delivery settings changed (`sends_per_day`, `slot_times`, `batch_time`, `delivery_days`, `timezone`), immediately sync Hermes Cron:
   - Call `cronjob(action="update")` or run `bash newsletter-workspace/cron/sync-cron.sh --profile <profile>`.
6. **Log** the change to `vault/state.json → rule_change_log` (append, include timestamp + summary).
7. **Confirm** to the user in one short sentence per changed field, noting that Hermes Cron was automatically updated.
8. **Ask** whether to re-run the pipeline immediately with the new rules or wait for the next scheduled run.

### Conflict Detection

Before saving, check for logical conflicts:

| Conflict | Example | Action |
|----------|---------|--------|
| min > max words | `min: 600, max: 400` | Reject; ask user to clarify |
| Pinned topic is also forbidden | `pinned: ["X"], forbidden: ["X"]` | Warn; ask which takes precedence |
| `rolling_window < 1` | `rolling_window: 0` | Reject; enforce minimum of 1 |
| `max_sources < 2` | `max_sources_per_day: 1` | Warn; coverage may be inadequate |

---

## 6 — Showing Current Rules

When the user says "show my rules", "what are my settings", or `/rules`:

Read `config.json` and display a clean summary table:

```
📋 Your Newsletter Rules
──────────────────────────────────────────────────────
Frequency          : Once daily at 08:00 (Asia/KL)
Research source    : Tavily (primary) → Web Search (fallback)
Writing tone       : Friendly-professional
Writing style     : Narrative (hook → story → mistakes → lessons → action)
Edition length     : 2,000–3,000 words (10+ min read)
Sections per issue : 2–3
Topic strategy     : Correlation-first, rolling 3-day window
Topic pacing       : Dense (consecutive slots)
Language           : English
──────────────────────────────────────────────────────
Say "/rules update [what you want to change]" to edit any of these.
```
