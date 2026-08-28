# Limitless Travel Content Engine

## Project purpose

The project will eventually help Limitless Travel identify, research, generate and optimise accessible-travel content designed to provide useful information and generate qualified enquiries.

## Architecture

The system separates editorial guidance, website understanding, research, scoring, AI-assisted drafting and article lifecycle storage.

```text
content-guidelines
    |
Defines HOW Limitless communicates

crawler
    |
Understands WHAT already exists

research
    |
Understands WHAT people search for and WHAT performs

content
    |
Understands gaps, duplication and internal structure

scoring
    |
Prioritises opportunities and checks quality

ai
    |
Creates and reviews content using all available context

articles
    |
Stores briefs, drafts and approved content
```

The AI layer is intentionally model-independent so future integrations can support Gemma, Gemini or other language models without renaming the whole system around one provider.

## Development phases

```text
Phase 1 - Editorial guidelines
Phase 2 - Website crawler
Phase 3 - Existing content inventory
Phase 4 - Search Console / analytics
Phase 5 - Topic opportunity system
Phase 6 - AI brief generation
Phase 7 - AI article generation
Phase 8 - Editorial / CRO / accessibility QA
Phase 9 - Performance feedback loop
```

Phase 1 is already present in `content-guidelines/`. The remaining phases are represented only as project skeleton placeholders and are not implemented yet.
