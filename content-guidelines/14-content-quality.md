---
document: content_quality_scoring
brand: Limitless Travel
priority: high
applies_to:
  - editorial_review
  - blog
  - seo_content
language: en-GB
status_on_threshold_failure: REVISION REQUIRED
---

# Content Quality Scoring

Use this framework to score article drafts. These are internal editorial scores, not Google ranking factors.

```yaml
scores:
  search_intent: 0
  usefulness: 0
  accessibility_accuracy: 0
  factual_accuracy: 0
  clarity: 0
  tone_of_voice: 0
  empathy: 0
  reassurance: 0
  trust: 0
  conversion: 0
  seo: 0
```

Mandatory thresholds:

```yaml
minimum_scores:
  accessibility_accuracy: 95
  factual_accuracy: 95
  search_intent: 90
  usefulness: 90
  clarity: 85
  tone_of_voice: 85
```

If mandatory thresholds are not achieved:

```text
STATUS: REVISION REQUIRED
```

The model should explain why and rewrite problematic sections.

## How To Judge Each Score

Search intent: Does the article answer the query the reader actually searched? A high score requires an answer near the start, correct format and no mismatch between keyword and content angle.

Usefulness: Does the article give practical, decision-supporting information? A high score requires specific guidance, examples, checks and clear next steps.

Accessibility accuracy: Are accessibility claims verified, caveated and individualised? A high score requires no invented features, no blanket suitability claims and clear uncertainty handling.

Factual accuracy: Are travel, destination, service and process statements accurate or flagged for checking? A high score requires no unsupported claims and appropriate source caution.

Clarity: Is the article easy to read, scan and understand? A high score requires descriptive headings, short paragraphs and plain English.

Tone of voice: Does the article sound clear, empathetic, warm and reassuring? A high score avoids jargon, hard selling and exaggerated claims.

Empathy: Does the article acknowledge real concerns respectfully? A high score recognises uncertainty without pity or drama.

Reassurance: Does the article reduce uncertainty through practical information? A high score avoids empty reassurance and explains what can be checked.

Trust: Does the article show expertise and honesty? A high score uses verified evidence, transparent caveats and realistic expectations.

Conversion: Does the article create a natural reason to call? A high score places CTAs at the right time, uses helpful phone framing and avoids pressure.

SEO: Does the article use metadata, headings, keywords and internal links naturally? A high score satisfies intent without keyword stuffing.

## Revision Requirements

If a section scores low:

- Identify the weak section.
- Explain the issue in one sentence.
- Rewrite the section.
- Re-score the affected categories.

Do not approve an article with unresolved factual or accessibility uncertainty.
