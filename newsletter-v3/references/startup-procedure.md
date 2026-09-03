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

### Phase 2 — High-Priority Profile Calibration & Diagnostic Intake

> [!IMPORTANT]
> **CRITICAL PRIORITY & NON-NEGOTIABLE GATE**:
> Gathering rich, precise, high-fidelity details about the user's profession, field of study, native domain fluency, and intellectual curiosity triggers is of **THE HIGHEST IMPORTANCE AND PRIORITY**.
> Generic user profiles produce generic newsletters. The agent must invest the necessary effort to ask the **right precision questions** and probe deeper to extract the nuances of the user's background, current expertise depth, and intellectual interests.

#### The 6 Precision Diagnostic Questions (The Right Questions to Ask)

When conducting the profile intake interview, present these focused questions:

```
To ensure every edition is calibrated to your exact background, explains concepts with the right depth, and surfaces unexpected ideas that spark your curiosity:

1. 💼 Profession, Current Role & Daily Mechanics:
   What is your exact job title, profession, or daily work focus? What specific systems, problems, workflows, or methodologies do you engage with every day?
   (e.g., "Staff Distributed Systems Engineer building high-throughput streaming pipelines", "Cardiologist running clinical drug trials and imaging", "Macroeconomic Quantitative Analyst")

2. 🎓 Field of Study & Academic/Technical Discipline:
   What is your primary educational, academic, or technical discipline, and what core sub-specializations did you train in?
   (e.g., "Computer Science with focus on Compiler Design & Distributed State", "Cardiovascular Physiology & Pharmacokinetics", "Applied Mathematics & Econometrics")

3. 🧠 Depth of Study & Native Fluency (The "Zero-101s" Invariant):
   What foundational concepts, jargon, theories, and mental models do you know inside out, where you NEVER want introductory or 101 explanations?
   (e.g., "Raft consensus, memory barriers, lockless data structures", "Hemodynamics, receptor affinity, ischemia", "Stochastic calculus, Black-Scholes, options greeks")

4. 🎯 Target Learning Horizons & Specific Topics:
   What specific domains, technologies, or subjects do you want this newsletter to teach you, and what specific mechanics do you want demystified?
   (e.g., "Quantum Computing (qubit coherence and gate algorithms)", "Bio-mechanics and prosthetic engineering", "High-performance Rust async runtimes")

5. 💡 Interdisciplinary Curiosity & Spark Triggers:
   What unexpected, adjacent, or cross-disciplinary intersections spark your curiosity or fascination?
   (e.g., "Applying biological immune systems to network security", "Physics models applied to financial markets", "Biomimicry in aerospace engineering")

6. 🌉 Pedagogical, Analogy & Depth Calibration:
   Would you like concepts outside your field explained using metaphors and analogies drawn from your primary field of study? What information density and style do you prefer?
   (e.g., "Explain complex physics or financial concepts using software architecture / distributed systems analogies where possible; prefer high technical density over superficial fluff")
```

---

#### The Adaptive Probing Protocol (Follow-Up to Get the Best Information)

If the user gives brief, generic, or underspecified answers (e.g., *"I'm a developer and want to learn AI"* or *"I'm in finance"*), the agent **MUST NOT immediately proceed to Phase 3**. The agent must ask smart, targeted follow-up probing questions:

- **If profession/role is vague**:
  - *"To help us tailor the technical depth: What specific tools, languages, or architectural challenges do you work on most frequently? Are you more focused on infrastructure, algorithms, or product architecture?"*
- **If field of study / depth is vague**:
  - *"What are 2 or 3 technical concepts in your field that you consider second nature? That will help us set the baseline so we never bore you with basics in those areas."*
- **If target topics are broad**:
  - *"For [Domain]: Are you looking to explore it from an applied practitioner lens, a theoretical first-principles perspective, or an architecture/case-study angle?"*

Only when the agent has collected concrete, actionable answers should it proceed to persist the profile in Phase 3.

---

### Phase 3 — Persisting the User Profile (vault/user.md & vault/user-profile.json)

Once the user responds, extract structured metadata and write **BOTH** `vault/user.md` (human-readable authoritative profile) and `vault/user-profile.json`:

#### 1. Write `vault/user.md`:

```markdown
# User Profile & Professional Specialization

Last updated: [ISO8601]

## 1. Professional Identity & Background
- **Name / Identifier**: [User Name or Handle]
- **Primary Occupation / Profession**: Cardiologist & Clinical Researcher
- **Field of Study / Discipline**: Medicine & Cardiovascular Physiology
- **Current Role & Daily Focus**: Clinical trials, cardiology diagnostics, and patient data analytics
- **Experience Level / Seniority**: Senior Clinical Specialist (10+ years)

## 2. Core Specialty & Domain Mastery
- **Primary Field of Study**: Medicine / Cardiology (Mastery: Expert)
- **Sub-Disciplines & Specializations**:
  - Cardiovascular Diagnostics: Advanced clinical imaging and hemodynamics
  - Clinical Pharmacology: Drug trial protocols and pharmacokinetics
- **Native Concepts & Terminology** (Zero 101 explanations needed — assume high fluency):
  - Hemodynamics, cellular receptors, ischemia, clinical trial power, pharmacokinetics

## 3. Knowledge Depth & Familiarity Matrix
| Domain / Field | Category | Current Depth Tier | Evolution & Notes |
|---|---|---|---|
| Medicine / Cardiology | Native Specialty | Expert | Skip foundational basics; high technical rigor |
| Quantum Physics | Target Interest | Beginner | Needs intuitive first-principles scaffolding |
| Machine Learning | Target Interest | Beginner | Bridge with statistical clinical data models |

## 4. Learning Interests & Curiosity Spark Engine
### Active Learning Objectives
- Quantum Physics: Quantum computing principles and qubit coherence
- Machine Learning: Neural network architectures and transformer attention

### Curiosity Sparks (Cross-Disciplinary Discovery)
> Emerging, serendipitous topics identified on recurring runs connecting the user's field of study to adjacent or novel domains to spark new intellectual curiosity:
- **Bio-Quantum Sensors**: How quantum entanglement is revolutionizing molecular cardiac diagnostics.
- **Physics-Informed Neural Networks in Fluid Dynamics**: Modeling aortic blood flow with neural differential equations.

## 5. Pedagogical & Content Calibration Rules
- **Preferred Analogy Domains**: Medicine, Human Physiology, Biology
- **Scaffolding Strategy**: Heavy first-principles scaffolding for non-native domains using biological metaphors; skip basics in medical domains.
- **Tone & Narrative Style**: Friendly-professional, high information density, story-first
- **Anti-Repetition & Depth Progression**: Automatically elevate depth as editions are completed.

## 6. Profile Evolution & Discovery History
- [ISO8601]: Initial profile created during onboarding.
```

#### 2. Write `vault/user-profile.json`:

```json
{
  "name": "User Name or Handle",
  "occupation": "Cardiologist & Clinical Researcher",
  "field_of_study": "Medicine & Cardiovascular Physiology",
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
  "curiosity_sparks": [
    {
      "topic": "Bio-Quantum Sensors in Cardiac Diagnostics",
      "connection_to_profession": "Bridges quantum coherence with molecular cardiovascular imaging",
      "spark_reason": "Applies deep quantum mechanics directly to medical research"
    },
    {
      "topic": "Physics-Informed Neural Networks in Hemodynamics",
      "connection_to_profession": "Combines fluid mechanics and machine learning with vascular flow",
      "spark_reason": "High cross-disciplinary relevance to daily cardiology practice"
    }
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

Every agent (Planner, Researcher, Writer) reads `vault/user.md`, `vault/user-profile.json`, and `vault/learning-profile.md` before generating content.

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
   - The Vault Manager updates `vault/user.md`, `vault/user-profile.json → domain_mastery`, and `vault/learning-profile.md`.
   - **Subsequent editions on that topic will automatically explain with less basic detail**:
     - Phasing out elementary definitions ("As we established in Edition #3...").
     - Shifting from basic analogies to native domain precision.
     - Elevating to advanced nuances, operational failure modes, and edge cases.
4. **Recurring Curiosity Spark Discovery**:
   - On recurring runs, the Vault Manager analyzes the user's field of study and emerging concepts to generate new curiosity sparks in `vault/user.md`.
5. **Confusion Signal Fallback**:
   - If the user responds with "I'm confused about X" or "I didn't understand Y", the Vault Manager logs a gap, temporarily dials back the domain tier in `vault/user.md`, and injects a foundational clarification slot into the next plan.

---

## Startup Completion Checklist

Before exiting the startup procedure, verify:
- [ ] `settings.md` is updated with valid email, slot times, batch time, timezone, and topic pacing.
- [ ] Automated Hermes Cron jobs (`newsletter:<profile>-batch`, `newsletter:<profile>-send`, `newsletter:maintain-all`) registered and verified.
- [ ] `vault/state.json` records `cron_installed: true` and `cron_provider: "hermes"`.
- [ ] `vault/user.md` is written and populated with occupation, field of study, depth tiers, and initial curiosity sparks.
- [ ] `vault/user-profile.json` is written and populated.
- [ ] `vault/learning-profile.md` contains the user's background, core domains, and initial scaffolding rules.
- [ ] Confirm setup to the user in a clean summary and invite their first topic request:
  > "All set! Your profile, profession details, and schedule are locked in. What topic would you like to explore first?"
