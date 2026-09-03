# Newsletter Settings

> This file is the **authoritative settings source**. Agents read this before every
> planning or delivery run. Values here take precedence over `config.json`; if the
> two disagree, agents must warn the user and use this file.
>
> **Timezone format: IANA location identifiers only** (e.g. `Asia/Kuala_Lumpur`,
> `Europe/Berlin`, `America/New_York`). Do NOT use UTC offsets (they break with DST)
> and do NOT leave `auto` for production use — `auto` is a placeholder that
> `/cron-setup` resolves once into a real IANA zone and writes back here.

sends_per_day: 3
slot_times: ["08:00", "13:00", "18:00"]
batch_time: "03:00"        # INTERMEDIATE AGENT cron: batch-research/write/evaluate ALL of today's editions
delivery_days: ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
email: null
timezone: auto
rolling_window_days: 3
new_topic_priority: ultimate
allow_topic_split: true
topic_pacing: dense        # dense (pack same-topic chunks into consecutive slots) | spaced (max 1 chunk per topic per day, remaining daily slots filled with distinct topics)
artifact_retention_days: 7  # auto-delete transient pipeline artifacts (html, outbox, research, eval, runs) after N days; 0 = keep forever (vault/ is never deleted)
html_expiry_days: 7        # legacy alias for artifact_retention_days
