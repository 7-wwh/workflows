# Tavily Research Integration

Tavily is the **primary online research source** for the newsletter skill.
The Researcher agent must check for and prefer Tavily before falling back to
generic web search.

Read this file when:
- The Researcher agent is about to run any search
- The user says "use Tavily", "search with Tavily", "Tavily lookup"
- `config.json → research_rules.primary_source == "tavily"` (the default)

---

## Why Tavily First

Tavily is purpose-built for AI agent research: it returns clean, pre-extracted
content rather than raw HTML, ranks results by relevance, and supports
advanced filters (recency, domain, content type). This means the Researcher
spends fewer tool calls cleaning up results and more time synthesising insights.

---

## Tool Detection

Before calling Tavily, verify it is available as an MCP connector:

```javascript
// Check if tavily_search or tavily tool is in the current tool list
const tavilyAvailable = tools.some(t =>
  t.name.toLowerCase().includes("tavily") ||
  t.description?.toLowerCase().includes("tavily")
);
```

| Result | Action |
|--------|--------|
| Tavily tool found | Use it as the primary search (see Query Patterns below) |
| Not found, MCP registry searchable | Search registry for "tavily" and call `suggest_connectors` |
| Not found, registry unavailable | Fall back to `web_search`; log `"tavily_unavailable": true` in `research/day-N.json` |

**Never block the pipeline** waiting for Tavily. If unavailable, fall through to the
fallback sources defined in `config.json → research_rules.fallback_sources`.

---

## Query Patterns for Tavily

The Researcher uses these query patterns with Tavily, in this order:

### Query 1 — Overview & Images (always run)

```json
{
  "query": "{theme} explained introduction overview",
  "search_depth": "basic",
  "max_results": 5,
  "include_answer": true,
  "include_images": true
}
```

Use `include_answer: true` and `include_images: true` — Tavily returns relevant direct image URLs that can be used for the featured illustration/diagram in the newsletter.

### Query 2 — Depth / Mechanism (always run)

```json
{
  "query": "{theme} how it works examples implementation architecture diagram",
  "search_depth": "advanced",
  "max_results": 5,
  "include_images": true
}
```

Use `search_depth: "advanced"` and `include_images: true` here to get deeper sub-page content and technical diagrams.

### Query 3 — Insight / Counter-Intuitive (always run)

```json
{
  "query": "{theme} surprising misconception counterintuitive non-obvious",
  "search_depth": "basic",
  "max_results": 3
}
```

### Query 4 — Follow-Up Resolution (only when `follow_up_slot` is present)

```json
{
  "query": "{follow_up_question} explanation {theme}",
  "search_depth": "advanced",
  "max_results": 4,
  "include_raw_content": true
}
```

Use `include_raw_content: true` to get the full article body — follow-up answers
often require more nuance than a snippet provides.

### Query 5 — Recency Check (conditional)

Only run if `config.json → research_rules.require_recency_days` is set:

```json
{
  "query": "{theme} 2025 2026 latest developments",
  "search_depth": "basic",
  "max_results": 3,
  "days": {require_recency_days}
}
```

---

## Domain Filtering

Apply the domain rules from `config.json → research_rules` to every Tavily call:

```json
{
  "exclude_domains": ["reddit.com", "quora.com"],
  "include_domains": []   // only set if prefer_domains is non-empty
}
```

> Note: `include_domains` acts as an allowlist. Only use it when the user has
> explicitly set `prefer_domains` — otherwise leave it empty so Tavily returns
> the broadest relevant results.

---

## Credibility Tiers

Map `minimum_source_credibility` to Tavily result filtering:

| Config Value | Filtering Behaviour |
|-------------|---------------------|
| `"low"` | Accept all returned results |
| `"medium"` | Skip results where Tavily score < 0.5 (if score field present) |
| `"high"` | Skip results where Tavily score < 0.75; also skip personal blogs without bylines |

When credibility filtering drops results below 2 sources, relax the threshold by
one tier and log a warning in `research/day-N.json → tavily_notes`.

---

## Extracting Facts from Tavily Results

For each Tavily result, extract:

```json
{
  "url": "...",
  "title": "...",
  "published_date": "...",     // use if available for recency check
  "tavily_score": 0.87,        // relevance score from Tavily (if present)
  "key_facts": [
    "Paraphrased fact 1 (≤25 words)",
    "Paraphrased fact 2 (≤25 words)"
  ],
  "jargon_terms": {
    "term": "plain-English definition (1 sentence)"
  },
  "example": "One concrete real-world example if present"
}
```

Rules:
- **Never copy-paste** verbatim text from results (copyright; see SKILL.md guidance).
- Paraphrase every fact into the Researcher's own words.
- If Tavily returns a synthesised `answer` field, use it as a starting point but
  always verify against the source URLs.

---

## Fallback Chain

If Tavily fails or returns fewer than 2 relevant results for a query:

```
Tavily → web_search (Claude built-in) → web_fetch (direct URL if known)
```

Log the fallback in `research/day-N.json`:

```json
"source_chain": {
  "query_1": "tavily",
  "query_2": "tavily",
  "query_3": "web_search (tavily_score_too_low)"
}
```

This lets the Evaluator flag low-confidence research days.

---

## Recording Tavily Usage in Research Output

Every `research/day-N.json` should include a `tavily_metadata` block:

```json
"tavily_metadata": {
  "available": true,
  "queries_run": 3,
  "results_used": 4,
  "results_filtered_out": 1,
  "fallback_used": false,
  "tavily_notes": ""
}
```

This block is read by the Evaluator for accuracy scoring and by the Vault Manager
when updating source provenance in `knowledge-map.json`.

---

## Connecting Tavily (First-Time Setup)

If the user has not yet connected Tavily and the skill needs it:

1. Search the MCP registry: `search_mcp_registry(["tavily", "web search", "research"])`
2. If a Tavily connector appears, call `suggest_connectors` with its UUID.
3. Tell the user:
   > "Tavily is your configured primary research source, but it isn't connected yet.
   > Connecting it gives the Researcher cleaner, more relevant results. You can also
   > continue with the built-in web search as a fallback — just say 'skip for now'."
4. If the user skips: set `config.json → research_rules.primary_source: "web_search"`
   temporarily and log a note that Tavily was requested but not available.
