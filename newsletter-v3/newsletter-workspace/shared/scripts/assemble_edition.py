#!/usr/bin/env python3
"""
assemble_edition.py — Deterministic Template Assembler for Newsletter v3

Decouples full-length 2,250–3,500 word narrative drafting from HTML boilerplate rendering.
Hydrates structured Content JSON into canonical email templates in assets/templates/
with zero LLM token overhead, instant execution (<20ms), and 100% email client safety.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

def resolve_paths(script_path):
    scripts_dir = os.path.dirname(os.path.abspath(script_path))
    workspace_dir = os.path.dirname(scripts_dir)
    skill_root = os.path.dirname(workspace_dir)
    templates_dir = os.path.join(skill_root, "assets", "templates")
    return workspace_dir, skill_root, templates_dir

def load_template(templates_dir, template_type):
    mapping = {
        "case-study": "case-study-template.html",
        "learning": "learning-template.html",
        "creative": "creative-template.html",
        "newsletter": "newsletter-template.html",
        "custom": "learning-template.html"
    }
    filename = mapping.get(template_type, "case-study-template.html")
    path = os.path.join(templates_dir, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Template not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return f.read(), filename

def apply_patch(content, patch_data):
    """Recursively or key-wise update content dict with patch dictionary."""
    if isinstance(patch_data, dict):
        for k, v in patch_data.items():
            if isinstance(v, dict) and isinstance(content.get(k), dict):
                content[k].update(v)
            else:
                content[k] = v
    return content

def assemble_html(content, template_html, expiry_days=7):
    html = template_html

    # 1. Insert/Update Expiry Stamp
    expiry_date = (datetime.now(timezone.utc) + timedelta(days=expiry_days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    expiry_tag = f"<!-- newsletter-expiry: {expiry_date} -->\n"
    if "<!DOCTYPE html>" in html:
        html = re.sub(r'(<!DOCTYPE html>\s*)', r'\1' + expiry_tag, html, count=1)
    else:
        html = expiry_tag + html

    # 2. Handle Featured Image Block
    feat_img = content.get("featured_image")
    if feat_img and feat_img.get("url"):
        html = html.replace("{{FEATURED_IMAGE_URL}}", str(feat_img.get("url", "")))
        html = html.replace("{{FEATURED_IMAGE_ALT}}", str(feat_img.get("alt", "")))
        html = html.replace("{{FEATURED_IMAGE_CAPTION}}", str(feat_img.get("caption", "")))
        html = html.replace("{{FEATURED_IMAGE_SOURCE}}", str(feat_img.get("source_credit", "Source")))
    else:
        # Cleanly remove the entire featured image table block if null
        html = re.sub(
            r'<!-- ─── FEATURED (?:IMAGE|DIAGRAM|ILLUSTRATION) [^─]*─── -->\s*<table width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation"[^>]*>.*?</table>',
            '',
            html,
            flags=re.DOTALL
        )

    # 3. Dynamic token mapping dictionary
    flat_tokens = {}

    # Header & Issue Metadata
    flat_tokens["{{NEWSLETTER_NAME}}"] = content.get("newsletter_name", "Intellego Newsletter")
    issue_num = content.get("issue_number", 1)
    flat_tokens["{{ISSUE_NUMBER}}"] = f"{int(issue_num):03d}" if str(issue_num).isdigit() else str(issue_num)
    flat_tokens["{{DAY_OF_WEEK}}"] = content.get("day_of_week", datetime.now().strftime("%A"))
    flat_tokens["{{FULL_DATE}}"] = content.get("full_date", content.get("date", datetime.now().strftime("%B %d, %Y")))
    flat_tokens["{{SLOT_TIME}}"] = content.get("slot_time", "08:00")
    flat_tokens["{{READING_TIME}}"] = content.get("reading_time", f"{content.get('reading_time_minutes', 12)} min")
    flat_tokens["{{THEME}}"] = content.get("theme", "")
    flat_tokens["{{HEADLINE}}"] = content.get("headline", "")
    flat_tokens["{{DECK}}"] = content.get("deck", "")
    flat_tokens["{{CUSTOM_SIGN_OFF}}"] = content.get("custom_sign_off", content.get("sign_off", "Understand deeply."))
    flat_tokens["{{EMAIL_ADDRESS}}"] = content.get("email_address", "lamweiheng124@gmail.com")

    # Glance Items
    glance = content.get("glance_items", [])
    for i in range(1, 5):
        val = glance[i-1] if len(glance) >= i else ""
        flat_tokens["{{" + f"GLANCE_ITEM_{i}" + "}}"] = val

    # Intro
    flat_tokens["{{INTRO_PARAGRAPHS}}"] = content.get("intro_paragraphs", content.get("intro", ""))

    # Insight & Try This
    if "insight_text" in content:
        insight_val = content["insight_text"]
    elif "insight" in content:
        insight_val = content["insight"]
    elif "insight_p1" in content:
        p1 = content.get("insight_p1", "")
        p2 = content.get("insight_p2", "")
        insight_val = f"<p>{p1}</p>" + (f"<p>{p2}</p>" if p2 else "")
    else:
        insight_val = ""

    if isinstance(insight_val, list):
        insight_val = "".join(f"<p>{p}</p>" if not p.startswith("<p>") else p for p in insight_val)
    flat_tokens["{{INSIGHT_TEXT}}"] = str(insight_val)
    flat_tokens["{{TRY_THIS_TEXT}}"] = content.get("try_this_text", content.get("try_this_action", content.get("try_this", "")))

    # Case Study specific mappings
    flat_tokens["{{WHAT_HAPPENED_HEADER}}"] = content.get("what_happened_header", "What Happened")
    flat_tokens["{{WHAT_HAPPENED_BODY}}"] = content.get("what_happened_body", "")
    flat_tokens["{{TURNING_POINT_HEADER}}"] = content.get("turning_point_header", "The Turning Point")
    flat_tokens["{{TURNING_POINT_BODY}}"] = content.get("turning_point_body", "")
    flat_tokens["{{MISTAKES_HEADER}}"] = content.get("mistakes_header", "The Fatal Flaws & Missteps")
    flat_tokens["{{LESSONS_HEADER}}"] = content.get("lessons_header", "Core Lessons & Operator Playbook")
    flat_tokens["{{PULL_QUOTE_TEXT}}"] = content.get("pull_quote_text", content.get("quote_text", ""))
    flat_tokens["{{PULL_QUOTE_ATTRIB}}"] = content.get("pull_quote_attrib", content.get("quote_attrib", ""))

    # Timeline mappings
    t_dates = content.get("timeline_dates", [])
    t_events = content.get("timeline_events", [])
    for i in range(1, 4):
        d_val = t_dates[i-1] if len(t_dates) >= i else ""
        e_val = t_events[i-1] if len(t_events) >= i else ""
        flat_tokens["{{" + f"TIMELINE_DATE_{i}" + "}}"] = d_val
        flat_tokens["{{" + f"TIMELINE_EVENT_{i}" + "}}"] = e_val

    # Mistakes / Myths mappings
    mistakes = content.get("mistakes", content.get("myths", content.get("misconceptions", [])))
    for i in range(1, 3):
        m = mistakes[i-1] if len(mistakes) >= i else {}
        flat_tokens["{{" + f"MISTAKE_{i}_TITLE" + "}}"] = m.get("title", "")
        flat_tokens["{{" + f"MISTAKE_{i}_BODY" + "}}"] = m.get("body", m.get("desc", ""))
        flat_tokens["{{" + f"MYTH_{i}_TITLE" + "}}"] = m.get("title", "")
        flat_tokens["{{" + f"MYTH_{i}_BODY" + "}}"] = m.get("body", m.get("desc", ""))

    # Lessons / Principles mappings
    lessons = content.get("lessons", content.get("principles", []))
    if lessons:
        l1 = lessons[0]
        flat_tokens["{{LESSON_1_TITLE}}"] = l1.get("title", "")
        flat_tokens["{{LESSON_1_BODY}}"] = l1.get("body", "")
        flat_tokens["{{PRINCIPLE_1_TITLE}}"] = l1.get("title", "")
        flat_tokens["{{PRINCIPLE_1_BODY}}"] = l1.get("body", "")
        takeaways = l1.get("takeaways", [l1.get("takeaway", ""), ""])
        flat_tokens["{{LESSON_1_TAKEAWAY_1}}"] = takeaways[0] if len(takeaways) > 0 else ""
        flat_tokens["{{LESSON_1_TAKEAWAY_2}}"] = takeaways[1] if len(takeaways) > 1 else ""
        flat_tokens["{{PRINCIPLE_1_TAKEAWAY_1}}"] = takeaways[0] if len(takeaways) > 0 else ""
        flat_tokens["{{PRINCIPLE_1_TAKEAWAY_2}}"] = takeaways[1] if len(takeaways) > 1 else ""
        plays = l1.get("playbook", [{"action": l1.get("playbook_rule", ""), "detail": ""}])
        for p_idx in range(1, 3):
            p = plays[p_idx-1] if len(plays) >= p_idx else {}
            flat_tokens["{{" + f"LESSON_1_PLAY_{p_idx}_ACTION" + "}}"] = p.get("action", "")
            flat_tokens["{{" + f"LESSON_1_PLAY_{p_idx}_DETAIL" + "}}"] = p.get("detail", "")

    # Learning template specific mappings
    flat_tokens["{{CONCEPT_HEADER}}"] = content.get("concept_header", "Core Architecture")
    flat_tokens["{{CONCEPT_BODY}}"] = content.get("concept_body", "")
    flat_tokens["{{DEEP_DIVE_HEADER}}"] = content.get("deep_dive_header", "Deep Dive")
    flat_tokens["{{DEEP_DIVE_BODY}}"] = content.get("deep_dive_body", "")
    flat_tokens["{{MATRIX_TITLE}}"] = content.get("matrix_title", "Strategic 2x2 Matrix")
    flat_tokens["{{MISCONCEPTIONS_HEADER}}"] = content.get("misconceptions_header", "Common Misconceptions")
    flat_tokens["{{EXAMPLE_CONTEXT}}"] = content.get("example_context", "")
    flat_tokens["{{EXAMPLE_TEXT}}"] = content.get("example_text", "")

    # Flow Steps
    flow = content.get("flow_steps", content.get("process_stages", []))
    for i in range(1, 4):
        st = flow[i-1] if len(flow) >= i else {}
        flat_tokens["{{" + f"FLOW_STEP_{i}_TITLE" + "}}"] = st.get("title", "")
        flat_tokens["{{" + f"FLOW_STEP_{i}_DESC" + "}}"] = st.get("desc", "")

    # 2x2 Matrix Quadrants
    quads = content.get("matrix_quadrants", content.get("quadrants", []))
    for i in range(1, 5):
        q = quads[i-1] if len(quads) >= i else {}
        flat_tokens["{{" + f"QUAD_{i}_TITLE" + "}}"] = q.get("title", "")
        flat_tokens["{{" + f"QUAD_{i}_DESC" + "}}"] = q.get("desc", "")

    # Bar Charts
    charts = content.get("metric_comparisons", content.get("chart_bars", []))
    flat_tokens["{{CHART_TITLE}}"] = content.get("chart_title", "Metric Comparison")
    for i in range(1, 3):
        cb = charts[i-1] if len(charts) >= i else {}
        pct = cb.get("pct", 50)
        flat_tokens["{{" + f"CHART_BAR_{i}_LABEL" + "}}"] = cb.get("label", "")
        flat_tokens["{{" + f"CHART_BAR_{i}_VAL" + "}}"] = str(cb.get("value", ""))
        flat_tokens["{{" + f"CHART_BAR_{i}_PCT" + "}}"] = str(pct)
        flat_tokens["{{" + f"CHART_BAR_{i}_REMAIN" + "}}"] = str(max(0, 100 - int(pct)))

    # Creative / Story Template mappings
    flat_tokens["{{SETTING_HEADER}}"] = content.get("setting_header", "Setting the Scene")
    flat_tokens["{{SETTING_BODY}}"] = content.get("setting_body", "")
    flat_tokens["{{CONFLICT_HEADER}}"] = content.get("conflict_header", "The Conflict")
    flat_tokens["{{CONFLICT_BODY}}"] = content.get("conflict_body", "")
    flat_tokens["{{RESOLUTION_HEADER}}"] = content.get("resolution_header", "The Resolution")
    flat_tokens["{{RESOLUTION_BODY}}"] = content.get("resolution_body", "")
    # Narrative Arc mapping
    arc = content.get("narrative_arc", content.get("arc_steps", []))
    for i in range(1, 4):
        a_val = ""
        if isinstance(arc, list):
            a_val = arc[i-1] if len(arc) >= i else ""
        elif isinstance(arc, dict):
            a_val = arc.get(f"step_{i}", arc.get(f"arc_step_{i}", ""))
        if isinstance(a_val, dict):
            a_val = a_val.get("desc", a_val.get("title", ""))
        flat_tokens["{{" + f"ARC_STEP_{i}_DESC" + "}}"] = str(a_val)

    # Stats cards
    stats = content.get("stat_cards", content.get("stats", []))
    for i in range(1, 4):
        s = stats[i-1] if len(stats) >= i else {}
        flat_tokens["{{" + f"STAT_{i}_NUMBER" + "}}"] = str(s.get("num", s.get("number", "")))
        flat_tokens["{{" + f"STAT_{i}_LABEL" + "}}"] = str(s.get("label", ""))

    # Newsletter sections
    flat_tokens["{{SECTION_1_HEADER}}"] = content.get("section_1_header", "Deep Dive")
    flat_tokens["{{SECTION_1_BODY}}"] = content.get("section_1_body", "")
    flat_tokens["{{SECTION_2_HEADER}}"] = content.get("section_2_header", "Strategic Breakdown")
    flat_tokens["{{SECTION_2_BODY}}"] = content.get("section_2_body", "")

    # Replace all tokens in HTML
    for token, val in flat_tokens.items():
        html = html.replace(token, str(val))

    # Clean up any leftover undefined optional row blocks
    html = html.replace("{{DEFINITIONS_ROWS}}", "")

    return html

def main():
    parser = argparse.ArgumentParser(description="Assemble modular newsletter content into full-length HTML.")
    parser.add_argument("--content", required=True, help="Path to content JSON file")
    parser.add_argument("--patch", help="Path to optional JSON patch file to apply on content before assembly")
    parser.add_argument("--output", required=True, help="Path to write compiled HTML draft/final")
    parser.add_argument("--outbox", help="Optional outbox destination path to copy final HTML")
    parser.add_argument("--template-type", help="Override template type (case-study | learning | creative | newsletter)")
    parser.add_argument("--expiry-days", type=int, default=7, help="HTML expiry retention days (default 7)")

    args = parser.parse_args()

    workspace_dir, skill_root, templates_dir = resolve_paths(__file__)

    with open(args.content, "r", encoding="utf-8") as f:
        content_data = json.load(f)

    if args.patch and os.path.exists(args.patch):
        with open(args.patch, "r", encoding="utf-8") as f:
            patch_data = json.load(f)
            if "patches" in patch_data:
                patch_data = patch_data["patches"]
            content_data = apply_patch(content_data, patch_data)

    template_type = args.template_type or content_data.get("template_type", "case-study")
    template_html, template_file = load_template(templates_dir, template_type)

    compiled_html = assemble_html(content_data, template_html, expiry_days=args.expiry_days)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(compiled_html)

    print(f"[OK] Successfully assembled {len(compiled_html)} bytes -> {args.output} (Template: {template_file})")

    if args.outbox:
        os.makedirs(os.path.dirname(os.path.abspath(args.outbox)), exist_ok=True)
        with open(args.outbox, "w", encoding="utf-8") as f:
            f.write(compiled_html)
        print(f"[OK] Exported outbox deliverable -> {args.outbox}")

if __name__ == "__main__":
    main()
