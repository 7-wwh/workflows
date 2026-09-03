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

## The Quick Onboarding Form (Concise Setup Experience)

> [!IMPORTANT]
> **CONCISE, FORM-BASED INTAKE (NO TEXT WALLS)**:
> Do not throw long walls of explanatory text at the user. Present a single, beautifully formatted, concise setup form that allows the user to quickly fill in their preferences or reply line-by-line in a few seconds.

When startup or onboarding is triggered, present this concise setup form:

```
👋 **Welcome to your Personal Learning Newsletter!**
Let's get your delivery schedule dialed in and calibrate content depth to your background. 

Please fill out or reply to this quick setup template (you can copy-paste and edit the values, or reply line-by-line):

```yaml
# ─── 📬 1. Delivery & Schedule Settings ──────────────────────────────
email: "your.email@example.com"      # Recipient address (or null for local HTML files only)
schedule: "3_daily"                  # once_daily (08:00) | twice_daily (08:00, 18:00) | 3_daily (08:00, 13:00, 18:00) | custom
timezone: "Asia/Kuala_Lumpur"        # Your IANA timezone (e.g. America/New_York, Europe/London, Etc/UTC)
topic_pacing: "dense"                # dense (consecutive slots) | spaced (max 1 part per day)

# ─── 💼 2. Profession, Field of Study & Depth ────────────────────────
profession: "..."                    # Job title & daily work focus (e.g., Staff Backend Engineer, Cardiologist)
field_of_study: "..."                # Academic or technical discipline (e.g., Computer Science, Medicine, Finance)
expert_concepts: "..."               # Mastered concepts where we NEVER need to explain 101 basics (Zero-101s)

# ─── 🎯 3. Target Learning & Curiosity Sparks ────────────────────────
target_topics: "..."                 # Domains or topics you want to learn & demystify next
spark_interests: "..."               # Adjacent or cross-disciplinary intersections that fascinate you
analogy_preference: "..."            # Bridge foreign concepts using metaphors from your field? (yes/no / custom)
```

*(Tip: You can copy-paste the template above with your answers, or reply with your choices in plain text!)*
```

---

### Phase 1b — Automated Settings & Hermes Cron Registration

As soon as the user replies with their delivery settings, the agent **immediately and autonomously**:
1. Saves validated delivery settings into `settings.md`:
   - `email`: validated email or `null`
   - `sends_per_day`: integer (e.g. 3)
   - `slot_times`: array of `"HH:MM"` (e.g. `["08:00", "13:00", "18:00"]`)
   - `batch_time`: `"HH:MM"` (default `"03:00"`)
   - `timezone`: valid IANA identifier
   - `topic_pacing`: `"dense"` or `"spaced"`
2. **Registers Hermes Cron Tasks**:
   - In interactive Hermes session: call `cronjob(action="create", ...)` for batch, send, and maintain jobs.
   - Or run shell sync: `bash newsletter-workspace/cron/sync-cron.sh --profile <profile-id>`.
   - Update `vault/state.json`: record `"cron_installed": true`, `"cron_provider": "hermes"`, `"cron_synced_at": "<ISO8601>"`.

---

### Phase 2 — Adaptive Probing (Only if Details are Underspecified)

If the user left a critical field in the profile section empty or answered with ambiguous 1-word text (e.g. *"developer / want to learn AI"*), ask **one quick, targeted follow-up question**:

- *"To make sure we hit the right technical depth: What specific tools or architecture challenges do you focus on daily, and are you learning AI from a math/research angle or an engineering/systems angle?"*

Once the answers are concrete, immediately proceed to Phase 3 persistence.

---

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
