# Startup Procedure Agent (First-Time Onboarding & Profile Calibration)

This document defines the **mandatory first-time setup sequence** for the newsletter skill. It runs whenever a profile is uninitialized or when the user explicitly triggers `/setup` or `/onboarding`.

---

## When to Trigger

The Input Agent **must halt all standard planning/intake** and immediately run this procedure if:
1. `vault/user-profile.json` is missing or contains unpopulated fields.
2. `settings.md` contains placeholder values (`email: null` with unconfirmed delivery, or `timezone: auto`).
3. The user explicitly requests `/setup`, `/onboarding`, `/init`, or "set up my profile".

---

## Objectives

1. **Configure Delivery & Schedule Settings**:
   - Resolve recipient email, sends per day, slot times, timezone, and topic pacing.
2. **Build the User Professional & Knowledge Profile**:
   - Capture occupation, current work/study focus, and core expertise domains.
   - Capture target learning domains and analogy/explanation preferences.
3. **Calibrate Content Scaffolding & Domain Mismatch Engine**:
   - Establish baseline domain familiarity tiers.
   - Instruct Researcher and Writer agents on how to adapt depth and bridge analogies based on the user's background.

---

## The Interactive Startup Sequence

The agent conducts an interactive, friendly onboarding conversation:

### Phase 1 — Delivery & Scheduling

Prompt the user to establish or confirm their delivery mechanics:

```
👋 Welcome to your Personal Learning Newsletter! Let's get your system dialed in.

1. Delivery Address: What email address should receive your editions?
2. Schedule: How often would you like editions delivered?
   - Default: 3 sends/day at 08:00, 13:00, and 18:00
   - You can also pick once daily, twice daily, or custom slot times.
3. Timezone: What is your city/timezone? (e.g. Asia/Kuala_Lumpur, America/New_York, Europe/London)
4. Topic Pacing:
   - Dense (default): Multi-part topics arrive in consecutive slots (e.g. Parts 1–3 today at 08:00, 13:00, 18:00).
   - Spaced: At most 1 part per topic per day (remaining daily slots are filled with companion topics or case studies).
```

Save validated responses into `settings.md`:
- `email`: user email or `null` (present-file mode)
- `sends_per_day`: integer (e.g. 3)
- `slot_times`: array of `"HH:MM"`
- `batch_time`: `"HH:MM"` (default `"03:00"` or user-specified background writing time)
- `timezone`: valid IANA identifier
- `topic_pacing`: `"dense"` or `"spaced"`

---

### Phase 1b — Automated Hermes Cron Registration (Mandatory)

**Trigger Point**: The exact moment the agent gathers the background writing time (`batch_time`) and delivery slots (`slot_times`) in Phase 1, the agent **MUST autonomously register the scheduled tasks for itself**. Do NOT wait for the user to ask, and do NOT tell the user to manually run `/cron-setup`.

The agent executes the automated registration using either method:
1. **Interactive Hermes Session** (using the native `cronjob` tool):
   - **Intermediate Batch Job**:
     `cronjob(action="create", name="newsletter:<profile>-batch", schedule="<batch_cron>", workdir="<profile_workspace_path>", skills=["newsletter"], prompt="Execute INTERMEDIATE AGENT batch production (Steps 4–6) for all slots scheduled for today in content_plan.md...")`
   - **Sender Delivery Job**:
     `cronjob(action="create", name="newsletter:<profile>-send", schedule="<slot_times_cron>", workdir="<profile_workspace_path>", skills=["newsletter"], prompt="Role: SENDER AGENT (Step 7). Retrieve outbox READY edition, deliver instantly, mark DELIVERED in content_plan.md...")`
   - **Nightly Maintain Mode**:
     `cronjob(action="create", name="newsletter:maintain-all", schedule="30 2 * * *", workdir="<skill_root>", skills=["newsletter"], prompt="Run Nightly Maintain Mode. Check settings.md for all profiles, verify Hermes cron schedules, auto-repair drift, sweep stale locks...")`
2. **Terminal / Script Command**:
   ```bash
   bash newsletter-workspace/cron/sync-cron.sh --profile <profile-id>
   ```

**Verification**:
- Inspect registration: `cronjob(action="list")` or `hermes cron list`.
- Update `vault/state.json`: record `"cron_installed": true`, `"cron_provider": "hermes"`, `"cron_synced_at": "<ISO8601>"`.
- Immediately inform the user:
  > "✅ Automated background scheduling registered in Hermes Cron:
  > • 🌙 Nightly Batch Writing: `<batch_time>` (researches and writes all editions)
  > • 📬 Instant Delivery: `<slot_times>` (delivers instantly without writing delay)
  > • 🛡️ Nightly Maintain Mode: `02:30` (drift verification & auto-repair)"

---

### Phase 2 — Professional Background & Knowledge Profile

To personalize explanations, analogies, and pacing, ask the user about their professional and educational background:

```
To ensure every edition is explained at the exact right depth for you:

1. Current Role & Daily Focus: What is your occupation or what are you currently working on / studying? (e.g. "Cardiologist in clinical research", "Junior Frontend Developer", "Corporate Finance Analyst")
2. Core Expertise Domains: What fields do you already know deeply and feel comfortable with? (e.g. Medicine, Human Biology, Statistics, JavaScript, Equity Valuation)
3. Target Learning Interests: What domains do you want this newsletter to teach you? (e.g. Quantum Physics, Distributed Systems, Macroeconomics, Modern Philosophy)
4. Analogy Preferences: When explaining concepts outside your field, would you like analogies connected to your core domain? (e.g. "Explain physics or tech concepts using biological/physiological metaphors where possible")
```

---

### Phase 3 — Persisting the User Profile

Once the user responds, extract structured metadata and write to `vault/user-profile.json`:

```json
{
  "name": "User Name or Handle",
  "occupation": "Cardiologist & Clinical Researcher",
  "daily_focus": "Clinical trials, cardiology diagnostics, and patient data analytics",
  "core_expertise_domains": [
    "medicine",
    "cardiology",
    "human_biology",
    "clinical_trials",
    "pharmacology"
  ],
  "target_learning_domains": [
    "quantum_physics",
    "machine_learning",
    "options_trading"
  ],
  "domain_mastery": {
    "medicine": "expert",
    "cardiology": "expert",
    "human_biology": "expert",
    "quantum_physics": "beginner",
    "machine_learning": "beginner",
    "options_trading": "beginner"
  },
  "preferred_analogy_domains": [
    "medicine",
    "human_physiology",
    "biology"
  ],
  "scaffolding_preference": "adaptive",
  "created_at": "2026-09-03T01:40:00Z",
  "updated_at": "2026-09-03T01:40:00Z"
}
```

Then immediately generate the initial `vault/learning-profile.md` incorporating the profile and scaffolding guidelines.

---

## The Adaptive Domain-Mismatch & Scaffolding Engine

Every agent (Planner, Researcher, Writer) reads `vault/user-profile.json` and `vault/learning-profile.md` before generating content.

### 1. The Domain Mismatch Principle

| Scenario | Definition | Content Calibration Strategy |
|---|---|---|
| **High Mismatch**<br>*(e.g. Doctor learning Quantum Physics)* | Topic falls outside `core_expertise_domains` and is marked `beginner` or `unfamiliar` in `domain_mastery`. | • **Heavy Scaffolding**: Explain first principles and underlying mechanisms before technical derivations.<br>• **De-jargonize**: Define non-obvious acronyms and mathematical terms in plain English.<br>• **Bridge Analogies**: Actively use metaphors from the user's `preferred_analogy_domains` (e.g., explain electron orbital clouds like blood vessel pressure gradients or cellular membranes). |
| **Low Mismatch / Native Domain**<br>*(e.g. Doctor learning New mRNA Vaccines)* | Topic overlaps directly with `core_expertise_domains` (`expert` or `advanced`). | • **Skip Foundational Scaffolding**: Eliminate 101 definitions and basic explanations.<br>• **High Technical Density**: Dive immediately into advanced mechanisms, comparative trade-offs, and cutting-edge literature. |

---

### 2. Dynamic Progression (The Knowledge Frontier Engine)

As editions are delivered, the user's domain mastery **evolves**:

1. **Delivery & Signal Tracking**:
   - When an edition in a domain is marked `DELIVERED`, the Vault Manager records the covered objectives.
   - If the user completes editions without confusion signals (or says "got it", "makes sense", or asks advanced questions), the topic transitions to `mastered`.
2. **Mastery Threshold & Tier Upgrades**:
   - **Beginner → Intermediate**: After 2–3 delivered editions in a domain with 0 confusion signals, or when the user demonstrates understanding in a follow-up.
   - **Intermediate → Advanced**: After 5+ editions covering complex sub-mechanisms.
3. **Automatic Adjustment of Explanations**:
   - The Vault Manager updates `vault/user-profile.json → domain_mastery` and `vault/learning-profile.md`.
   - **Subsequent editions on that topic will automatically explain with less basic detail**:
     - Phasing out elementary definitions ("As we established in Edition #3...").
     - Shifting from basic analogies to native domain precision.
     - Elevating to advanced nuances, operational failure modes, and edge cases.
4. **Confusion Signal Fallback**:
   - If the user responds with "I'm confused about X" or "I didn't understand Y", the Vault Manager logs a gap, temporarily dials back the domain tier, and injects a foundational clarification slot into the next plan.

---

## Startup Completion Checklist

Before exiting the startup procedure, verify:
- [ ] `settings.md` is updated with valid email, slot times, batch time, timezone, and topic pacing.
- [ ] Automated Hermes Cron jobs (`newsletter:<profile>-batch`, `newsletter:<profile>-send`, `newsletter:maintain-all`) registered and verified.
- [ ] `vault/state.json` records `cron_installed: true` and `cron_provider: "hermes"`.
- [ ] `vault/user-profile.json` is written and populated.
- [ ] `vault/learning-profile.md` contains the user's background, core domains, and initial scaffolding rules.
- [ ] Confirm setup to the user in a clean summary and invite their first topic request:
  > "All set! Your profile and schedule are locked in. What topic would you like to explore first?"
