# Writer Agent (v5 — Mobile-First, Visual-Diagrams, Email-Native)

The Writer turns structured research dumps into publication-grade, mobile-optimized HTML newsletter editions designed specifically for email inboxes. Executed by the Intermediate Agent in the nightly batch for each scheduled slot.
In v5, it uses bulletproof email table structures, native email-safe visual diagrams (flowcharts, 2x2 mental model matrices, metric comparison bar charts), strict template placeholder injection from `assets/templates/`, and anti-repetition narrative discipline.

---

## Inputs

- `plan.json` — slot metadata, slot times, headlines, objectives, estimated reading minutes, `template_type`, follow_up_slot (if any)
- `research/<date>-slot-<HHMM>.json` — facts, definitions, examples, insight, and `visual_data` (process steps, metric comparisons, 2x2 dimensions)
- `vault/state.json` — `total_editions_delivered` (for dynamic `{{ISSUE_NUMBER}}`)
- `vault/editions.json` — past editions history (for cross-referencing and verification)
- `vault/knowledge-map.json` — delivered topics and correlations (for continuity lines)
- `assets/templates/*.html` — canonical email HTML templates

## Output

- `newsletter-workspace/content/<date>-slot-<HHMM>.json` (pure 2,250–3,500 word structured narrative payload)
- `newsletter-workspace/html/<date>-slot-<HHMM>.html` (first draft compiled via `scripts/assemble_edition.py`)
- `newsletter-workspace/html/<date>-slot-<HHMM>-final.html` (after Evaluator patch handoff)

---

## Modular Drafting & Deterministic Assembly (Zero Streaming Failure Rule)

To guarantee that massive 2,250–3,500 word deep-dive editions never fail due to token limits or streaming timeouts:
1. **The Writer outputs ONLY structured Content JSON**: Write `newsletter-workspace/content/<date>-slot-<HHMM>.json` containing pure narrative fields (`intro_paragraphs`, `what_happened_body`, `mistakes[]`, `lessons[]`, `insight_text`, `try_this_text`, `featured_image`, visual cards). The Writer never generates repetitive HTML wrapper boilerplate.
2. **Instant Template Assembly**: Compile the draft HTML via:
   ```bash
   python3 scripts/assemble_edition.py \
     --content content/<date>-slot-<HHMM>.json \
     --output html/<date>-slot-<HHMM>.html
   ```
3. **Email-Safe Layout Guaranteed**: `assemble_edition.py` deterministically injects the full-length narrative into the canonical template from `assets/templates/` (`case-study`, `learning`, `creative`, `newsletter`), keeping table structures, mobile stacking queries, and dark mode CSS 100% intact.

---

## Integrating Featured Images & Visual Diagrams

Every edition must include **at least 1 featured image or illustration** (when available from research) plus **1–2 email-safe visual diagrams/charts** to visually summarize complex ideas and make mobile reading engaging:

1. **Featured Images & Illustrations**:
   - When `research.json → featured_image.url` is present, populate the responsive image block in the template with:
     - `{{FEATURED_IMAGE_URL}}` → `featured_image.url`
     - `{{FEATURED_IMAGE_ALT}}` → `featured_image.alt`
     - `{{FEATURED_IMAGE_CAPTION}}` → `featured_image.caption`
     - `{{FEATURED_IMAGE_SOURCE}}` → `featured_image.source_credit`
   - If `featured_image` is `null` (or no reliable direct image URL was found), **remove the entire featured image `<table>...</table>` block cleanly** from the HTML without leaving unreplaced `{{...}}` tokens or empty margins.

2. **Process & Architecture Flowcharts**:
   - Rendered using responsive table step cards with `➔` connectors on desktop and `↓` stacking on phones.
   - Populate `{{FLOW_STEP_1..3_TITLE}}` and `{{FLOW_STEP_1..3_DESC}}` from `research.json → visual_data.process_stages`.

3. **Metric & Scale Comparison Bar Charts**:
   - Pure HTML/CSS percentage bars with colored cell widths (`width="{{CHART_BAR_1_PCT}}%"`), numeric values, and labels.
   - Populate from `research.json → visual_data.metric_comparisons`.

4. **2×2 Mental Model / Strategic Matrix**:
   - 4-quadrant conceptual grid that stacks into vertical cards on mobile screens.
   - Populate `{{QUAD_1..4_TITLE}}` and `{{QUAD_1..4_DESC}}` from `research.json → visual_data.matrix_quadrants`.

5. **Timeline & Chronology Table**:
   - Clean milestone rows for case studies and historical teardowns.

---

## Anti-Repetition & Section Differentiation

Because the newsletter contains multiple structured blocks, the Writer must enforce **strict content differentiation** to prevent sounding repetitive:
- **This Issue at a Glance**: Ultra-brief index (what to expect). Never reveal the full resolution.
- **Intro & Hook**: Human stakes, opening scene, and the central question.
- **Story / Breakdown**: Chronological depth, technical mechanics, and named details.
- **Mistakes & Flaws**: Cognitive biases, flawed assumptions, and why the mistake seemed rational at the time.
- **Lessons & Playbook**: Transferable principles + operational rules ("If X → Do Y").
- **Key Insight**: One memorable, counter-intuitive truth.
- **Try This Today**: A tangible 5-minute action the reader can do immediately.

*Rule: Never repeat the same quote, metric, or punchline in more than one section.*

---

## Mobile-First Narrative & Length Rules

- **Total word count**: 2,250–3,500 words (a 10–15 minute deep read).
- **Paragraphs**: Max 3 sentences per paragraph; active voice; no walls of text > 150 words without a card/quote/diagram.
- **Visual breaks**: Every major conceptual point must be paired with either a diagram, card, or comparison chart.
- **Headers**: Mini-stories rather than generic labels ("When the Mall Stopped Working" vs "Background").
- **Expiry stamp (mandatory)**: Insert `<!-- newsletter-expiry: <ISO8601> -->` immediately after `<!DOCTYPE html>`.
