# Newsletter Skill v3 — JSON Schemas

All artefacts produced by the newsletter workflow conform to these schemas.

---

## config.json

```json
{
  "newsletter_name": "string",
  "frequency": "once_daily | twice_daily | every_N_hours | weekly",
  "delivery_time": ["HH:MM"],     // array; 1 item for once_daily, 2 for twice_daily
  "every_N_hours": 6,             // only used when frequency == "every_N_hours"
  "rolling_window": 3,            // days to plan ahead (1–7)
  "depth": "beginner | intermediate | advanced",
  "email": "string | null",
  "created_at": "ISO8601",
  "updated_at": "ISO8601"
}
```

---

## vault/inbox.json (append-only intake log)

Stored at `newsletter-workspace/vault/inbox.json`. Records raw intake items from user interactions.

```json
[
  {
    "id": "uuid",
    "type": "topic | followup | config_change",
    "content": "string",              // raw user input
    "timestamp": "ISO8601",
    "processed": false                // set to true by Vault Manager
  }
]
```

---

## plan.json

```json
{
  "window_days": 3,               // from settings.md rolling_window_days
  "slots_per_day": 3,             // from settings.md sends_per_day / len(slot_times)
  "generated_at": "ISO8601",
  "days": [
    {
      "day": 1,
      "date": "YYYY-MM-DD",
      "slots": [
        {
          "slot_time": "08:00",
          "status": "scheduled | ready | delivered | empty",
          "theme": "string",
          "headline": "string",
          "topic_source": "string",
          "template_type": "learning | case-study | creative | newsletter | custom",
          "learning_objectives": ["string"],
          "research_brief": "string",
          "part": "1/2 | null",           // set when a topic is split across slots
          "moved_from": "YYYY-MM-DD 13:00 | null",
          "follow_up_slot": {
            "followup_id": "string",
            "question": "string",
            "priority": "urgent | soon"
          }
        }
      ]
    }
  ],
  "backlog": [
    {
      "theme": "string",
      "headline": "string",
      "learning_objectives": ["string"],
      "demoted_at": "ISO8601",
      "reason": "window_full"
    }
  ]
}
```

`follow_up_slot` is `null` when no follow-up is injected for that slot.
`moved_from` records where a slot's content was displaced from (audit trail for
ultimate-priority new-topic insertion). `backlog` mirrors the Backlog section of
`content_plan.md`.

### plan.json → chunks[] (v3.1 — chunk-based planning)

```json
"chunks": [
  {
    "chunk_id": "chunk-1",
    "title": "string",
    "learning_objectives": ["string"],
    "word_estimate": 2400,
    "estimated_reading_minutes": 11,
    "standalone": true,
    "depends_on": [],
    "slot_ref": "day-1/08:00"
  }
],
"plan_eval": {
  "verdict": "pass | revise | pass_with_warnings",
  "revision_cycle": 0,
  "eval_file": "eval/plan-eval.json"
}
```

## eval/plan-eval.json (v3.1 — Plan Evaluator output)

```json
{
  "evaluated_at": "ISO8601",
  "verdict": "pass | revise | pass_with_warnings",
  "revision_cycle": 0,
  "chunk_verdicts": [
    {
      "chunk_id": "chunk-1",
      "reading_time_ok": true,
      "necessary": true,
      "notes": "string"
    }
  ],
  "contiguity_check": {
    "passed": true,
    "interleaved_empty_slots": [],    // list of empty slots that occur before scheduled slots
    "notes": "string"
  },
  "pacing_check": {
    "mode": "dense | spaced",
    "passed": true,
    "notes": "string"
  },
  "revision_instructions": [
    "string"
  ],
  "warnings": ["string | null"]
}
```

## content_plan.md (mirror of plan.json, human-readable)

Statuses: `DELIVERED | SCHEDULED | EMPTY` per slot; a `Backlog (unscheduled)` section
lists demoted topics. The output agent reads this file to decide what to send.

---

## research/<date>-slot-<HHMM>.json

```json
{
  "date": "YYYY-MM-DD",
  "slot_time": "08:00",
  "theme": "string",
  "follow_up_research": {
    "question": "string",
    "sources": [{"url": "string", "title": "string", "key_facts": ["string"]}],
    "answer_summary": "string"
  },
  "sources": [
    {
      "url": "string",
      "title": "string",
      "key_facts": ["string"],
      "retrieved_at": "ISO8601"
    }
  ],
  "featured_image": {
    "url": "https://example.com/image.jpg | null",
    "alt": "string",
    "caption": "string",
    "source_credit": "string",
    "context_placement": "intro | section_1 | section_2"
  },
  "visual_data": {
    "process_stages": [
      {"step": 1, "title": "string", "desc": "string"}
    ],
    "metric_comparisons": [
      {"label": "string", "value": "string", "pct": 75}
    ],
    "matrix_quadrants": [
      {"quadrant": "string", "title": "string", "desc": "string"}
    ],
    "timeline_milestones": [
      {"date": "string", "event": "string"}
    ]
  },
  "definitions": {
    "term": "plain-English definition"
  },
  "examples": ["string"],
  "insight": "string",
  "coverage_check": {
    "objective_1": true,
    "objective_2": true,
    "objective_3": false
  }
}
```

`follow_up_research` is `null` when the slot has no follow-up question.

---

## eval/<date>-slot-<HHMM>-eval.json

```json
{
  "date": "YYYY-MM-DD",
  "slot_time": "08:00",
  "edition_file": "html/YYYY-MM-DD-slot-0800.html",
  "scores": {
    "readability": 0,
    "depth": 0,
    "accuracy": 0,
    "narrative_quality": 0,
    "html_quality": 0
  },
  "overall": 0,
  "pass": false,
  "follow_up_missing": false,
  "fix_list": [
    {
      "dimension": "string",
      "issue": "string",
      "suggested_fix": "string"
    }
  ],
  "edits_made": [
    {
      "location": "string",
      "dimension": "string",
      "original": "string",
      "replacement": "string",
      "reason": "string"
    }
  ],
  "patches": {
    "field_name": "refined string or object content applied directly by assemble_edition.py"
  },
  "revision_cycle": 0,
  "manual_review_note": "string | null"
}
```

---

## content/<date>-slot-<HHMM>.json (Writer Structured Narrative)

```json
{
  "theme": "string",
  "headline": "string",
  "deck": "string",
  "template_type": "case-study | learning | creative | newsletter",
  "glance_items": ["string", "string", "string", "string"],
  "intro_paragraphs": "<p>...</p><p>...</p>",
  "what_happened_header": "string",
  "what_happened_body": "<p>...</p>",
  "timeline_dates": ["string"],
  "timeline_events": ["string"],
  "mistakes": [
    {"title": "string", "body": "string"}
  ],
  "lessons": [
    {
      "title": "string",
      "body": "string",
      "takeaways": ["string", "string"],
      "playbook": [
        {"action": "string", "detail": "string"}
      ]
    }
  ],
  "insight_text": "<p>...</p>",
  "try_this_text": "string",
  "custom_sign_off": "string",
  "featured_image": {
    "url": "https://... | null",
    "alt": "string",
    "caption": "string",
    "source_credit": "string"
  }
}
```

---

## vault/state.json

Authoritative tracker for runtime delivery states and dynamic issue numbering:

```json
{
  "last_run": "ISO8601",
  "last_edition_id": "string",
  "next_due": "ISO8601",
  "run_count": 0,
  "total_editions_delivered": 0
}
```

> **Dynamic Issue Number Resolution**:
> When generating a new edition, the Writer computes:
> `issue_number = state.total_editions_delivered + 1` (zero-padded as `#001`, `#042`).

---

## vault/inbox.json

See `intake.json` above — same schema, same file (inbox IS the append-only intake log).

---

## vault/user-profile.json (User Background & Domain Mastery)

Stored at `newsletter-workspace/vault/user-profile.json`. Initialized during the startup procedure (`references/startup-procedure.md`).

```json
{
  "name": "string",
  "occupation": "string",
  "daily_focus": "string",
  "core_expertise_domains": ["string"],
  "target_learning_domains": ["string"],
  "domain_mastery": {
    "domain_slug": "beginner | intermediate | advanced | expert"
  },
  "preferred_analogy_domains": ["string"],
  "scaffolding_preference": "adaptive | foundational | technical",
  "created_at": "ISO8601",
  "updated_at": "ISO8601"
}
```

---

## vault/learning-profile.md (Human-Readable Knowledge Frontier)

Rewritten by Vault Manager on every run:

```markdown
# Learning Profile & Background
Last updated: [ISO8601]

## User Background & Core Expertise
- **Role / Occupation**: [string]
- **Active Focus**: [string]
- **Core Expertise**: [domains marked expert/advanced]

## Domain Scaffolding & Analogy Rules
- **Domain Mismatch Rules**: [e.g. For physics, use medical/biological bridge analogies and first principles]
- **Native Domains**: [skip elementary definitions]

## Domain Familiarity Matrix
| Domain | Familiarity Tier | Delivered Editions | Mastery Notes |
|---|---|---|---|
| Physics | Beginner -> Intermediate | 3 | Understood basic thermodynamics; ready for wave mechanics |

## What You've Covered
- [Delivered topics, grouped by theme]

## Knowledge Gaps to Address
- [Gaps from knowledge-map.json]
```

---

## vault/knowledge-map.json

```json
{
  "topics": [
    {
      "topic_id": "slug",
      "label": "string",
      "status": "queued | planned | researched | delivered | mastered",
      "depth_delivered": "beginner | intermediate | advanced | null",
      "editions": ["edition_id"],
      "objectives_covered": ["string"],
      "objectives_missed": ["string"],
      "related_topics": ["topic_id"],
      "follow_ups": ["followup_id"],
      "user_signals": {
        "confusion_count": 0,
        "curiosity_count": 0,
        "mastery_signals": 0
      }
    }
  ],
  "correlations": [
    {
      "topic_a": "string",
      "topic_b": "string",
      "shared_concepts": ["string"],
      "strength": "strong | moderate | weak"
    }
  ],
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

---

## vault/followups.json

```json
[
  {
    "followup_id": "uuid",
    "question": "string",
    "related_topic_id": "string | null",
    "related_edition_id": "string | null",
    "priority": "urgent | soon | queue",
    "priority_score": 0,
    "status": "queued | planned | addressed",
    "created_at": "ISO8601",
    "addressed_in_edition": "string | null"
  }
]
```

---

## vault/editions.json (append-only)

```json
[
  {
    "edition_id": "YYYY-MM-DD-0800",
    "issue_number": 1,
    "profile": "profile-id",            // v5: which profile delivered this edition
    "sent_to": "recipient@example.com", // v5: audit trail — injected recipient
    "date": "YYYY-MM-DD",
    "slot_time": "08:00",
    "headline": "string",
    "theme": "string",
    "topics_covered": ["topic_id"],
    "follow_ups_addressed": ["followup_id"],
    "delivered_at": "ISO8601",
    "eval_score": 0,
    "file": "html/day-1-final.html"
  }
]
```

## runs/run-<timestamp>.json (v3.1 — Run Manifest / enforcement log)

```json
{
  "run_id": "run-YYYYMMDD-HHMMSS",
  "profile": "profile-id",       // v5: profile this run belongs to
  "trigger": "input | batch | send",
  "started_at": "ISO8601",
  "closed_at": "ISO8601 | null",
  "steps": [
    {
      "step_id": 1,
      "name": "intake | vault_manager | planner | plan_eval_gate | researcher | writer | evaluator | writer_final | sender | vault_sync",
      "status": "in_progress | complete | failed | skipped",
      "output_file": "path relative to skill root | null",
      "notes": "string | null",
      "completed_at": "ISO8601"
    }
  ]
}
```

Rule: before starting step N, steps 1..N-1 must be `complete` (or `skipped` with a
note). Read-only triggers do not open a manifest.

## runs/batch-<YYYY-MM-DD>.json (v4 — Intermediate Agent batch report)

```json
{
  "batch_date": "YYYY-MM-DD",
  "started_at": "ISO8601",
  "finished_at": "ISO8601 | null",
  "slots": [
    {
      "slot_time": "08:00",
      "chunk_id": "chunk-1",
      "research_file": "research/YYYY-MM-DD-slot-0800.json",
      "draft_file": "html/YYYY-MM-DD-slot-0800.html",
      "eval_file": "eval/YYYY-MM-DD-slot-0800-eval.json",
      "final_file": "outbox/YYYY-MM-DD/slot-0800-final.html",
      "eval_score": 0,
      "eval_pass": true,
      "slot_status_after": "ready | failed"
    }
  ],
  "failures": ["string | null"]
}
```

## Outbox (v4 — Intermediate Agent output, Sender input)

`newsletter-workspace/outbox/YYYY-MM-DD/slot-HHMM-final.html` — one finished,
eval-passed (or warning-banner-flagged) edition per scheduled slot, written entirely
during the `batch_time` run. The Sender only ever reads from here; it never produces.

---

## cron/cron-summary.json (v5 — Real-time Delivery Queue & Cron Status Summary)

```json
{
  "generated_at": "ISO8601",
  "summary": {
    "total_profiles": 1,
    "active_profiles": 1,
    "disabled_profiles": 0,
    "next_recipient_profile": "string | null",
    "next_recipient_email": "string | null",
    "next_sending_schedule": "ISO8601 | null",
    "time_until_next_send": "string | null",
    "failing_profiles_count": 0
  },
  "cron_summary": [
    {
      "profile_id": "string",
      "user_email": "string",
      "is_active": true,
      "next_sending_schedule": "ISO8601 | N/A (disabled)",
      "next_sending_slot": "HH:MM",
      "time_until_next_send": "string",
      "next_batch_schedule": "ISO8601 | N/A (disabled)",
      "previous_sent": "ISO8601 | Never",
      "status": "success | fail | ready | scheduled | paused",
      "error_encountered": "N/A | error message string",
      "delivery_days": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"],
      "slot_times": ["08:00", "13:00", "18:00"],
      "timezone": "string",
      "crontab_status": "in_sync | drift | missing",
      "details": {
        "outbox_ready": false,
        "latest_edition_id": "string | null",
        "total_editions_delivered": 0,
        "last_run_timestamp": "ISO8601 | null"
      }
    }
  ]
}
```

