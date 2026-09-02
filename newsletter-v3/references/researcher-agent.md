# Researcher Agent (v5 — Slot-Scoped, Parallel Concurrent Execution, Tavily-First)

During the Intermediate Agent nightly batch, **parallel Researcher subagent instances are dispatched concurrently** for ALL scheduled slots of today. Each instance deep-dives its assigned slot topic independently and produces a structured, high-density research dump for the Writer, including **relevant direct image URLs**, quantifiable data, and process steps for visual diagrams and charts.

### Parallel Execution Invariant
Because each slot has its own distinct file destination (`research/<date>-slot-<HHMM>.json`) and reads only its isolated slice from `plan.json`, parallel execution runs with zero file locking or race conditions, reducing total research wall-clock time by ~70%.

---

## Inputs

- One `slots[M]` slice from `plan.json` (theme, headline, objectives, research_brief, depth)
- `vault/knowledge-map.json` (to avoid re-explaining mastered concepts)
- `config.json → research_rules` (Tavily configuration, domain allow/block lists, search depth)

## Output

- `newsletter-workspace/research/<date>-slot-<HHMM>.json` (see `schemas.md`)

---

## Search Strategy

### Queries to run (in order)

1. **Overview & Images query**: `"{theme}" introduction explained` (pass `include_images: true`) → foundational explainer + direct imagery
2. **Mechanism & Diagram query**: `"{theme}" architecture diagram how it works step by step` (pass `include_images: true`) → technical flow + schematic visuals
3. **Data & Metrics query**: `"{theme}" statistics benchmarks comparison market share numbers` → numbers for comparison bar charts
4. **Insight & Misconception query**: `"{theme}" surprising counterintuitive misconception failure mode` → memorable non-obvious angle
5. **Source variety**: Aim for 3–5 diverse, reputable sources (official documentation, Wikimedia Commons, engineering teardowns, academic summaries, industry case studies).

---

## Image Discovery & Extraction (To Prevent Boring Newsletters)

To make newsletters visually captivating and prevent text fatigue, the Researcher must actively discover and verify **at least 1 high-quality relevant image / illustration / diagram**:

### Where to Find Images
- **Tavily Image Results (Primary)**: Extract top direct image URLs (`.jpg`, `.png`, `.webp`) returned when `include_images: true`.
- **Wikimedia Commons / Wikipedia (Primary Fallback)**: When Tavily is unavailable, use `web_search` (`"{theme}" site:wikipedia.org` or `site:commons.wikimedia.org`) and extract the direct Wikimedia upload URL (`https://upload.wikimedia.org/wikipedia/commons/...`).
- **Official Documentation / Press Archives**: High-res schematics, architecture charts, product renders from reputable sources.

### Structured Output in `research.json`
Populate the `featured_image` object (the key must ALWAYS exist):

```json
"featured_image": {
  "url": "https://upload.wikimedia.org/.../example.jpg",
  "alt": "Descriptive accessibility text for email clients",
  "caption": "Contextual caption explaining what the reader is seeing.",
  "source_credit": "Wikimedia Commons / Apple Inc.",
  "context_placement": "intro | section_1 | section_2"
}
```

*Note: If no reliable direct image URL can be discovered after fallback search, set `"featured_image": null`. Never omit the `"featured_image"` property.*

---

## Visual Data Extraction (For Mobile Diagrams & Charts)

The Researcher must actively structure findings into a `visual_data` object inside `research/<date>-slot-<HHMM>.json`:

1. **Process Flow Steps** (for architecture/workflow diagrams):
   - 3–4 sequential phases (`step_1`, `step_2`, `step_3`, `step_4`) with a punchy title (≤4 words) and a crisp 1-sentence description.
2. **Metric & Scale Comparisons** (for bar charts):
   - 2–3 comparison metrics with exact labels, formatted values, and estimated percentage weights (`pct` 10–100%) for visual bar rendering.
3. **2×2 Matrix Dimensions** (for mental model grids):
   - 4 quadrants with title and 1–2 sentence operational definition (e.g. High/Low Impact vs. High/Low Effort, Consumer vs. Pro).
4. **Timeline Milestones** (for case studies):
   - 3–4 key dates and consequential milestone events.

---

## The Insight

The insight is the single most memorable, non-obvious truth the reader will walk away with:
- Contradicts a common assumption or reveals hidden leverage.
- 1–2 sentences max.
- Traceable to source material.

---

## Depth Calibration

| Depth        | Jargon tolerance | Mechanism detail | Examples & Visuals required |
|--------------|-----------------|-----------------|-----------------------------|
| Beginner     | Zero — define every term | "what" only | 1 everyday analogy + 1 simple flow diagram + 1 featured image |
| Intermediate | Minimal — define on first use | "what + why" | 1 real-world case + 1 comparison bar chart / flow + 1 featured image |
| Advanced     | Accepted — glossary provided | "what + why + how" | 2+ concrete teardowns + 2x2 matrix, metric bars & schematics |

---

## Output Rules

- All facts must be traceable to a `sources[]` entry.
- Paraphrase every fact into clear, analytical prose (never copy-paste raw paragraphs).
- Provide concrete numbers and verifiable data to prevent the Writer from generalizing.
- Always populate `featured_image` and `visual_data` blocks with valid inputs.
