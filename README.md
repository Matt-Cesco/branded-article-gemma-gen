# Travel Content Engine

## Project purpose

The project will help to identify, research, generate and optimise content designed to provide useful information and generate qualified enquiries.

## Architecture

The system separates editorial guidance, website understanding, research, scoring, AI-assisted drafting and article lifecycle storage.

```text
content-guidelines
    |
Defines HOW the brand communicates

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

## Topic Discovery Crawler

The first research workflow discovers publicly available accessible-travel topic ideas from the curated external sources in `config/sources.yaml`.

It is research-only:

- It does not crawl the L Travel website.
- It does not generate articles.
- It does not connect to Gemma, Gemini or any other AI model.
- It does not query search engines or invent search-demand values.

### Configuration

Source websites are configured in:

```text
config/sources.yaml
```

Destination vocabulary is configured in:

```text
config/destinations.yaml
```

Accessibility-topic vocabulary is configured in:

```text
config/accessibility-topics.yaml
```

Expand these YAML files when you want the crawler to recognise more sources, destinations, countries or accessibility requirements.

### Run A Dry Check

Use this to confirm the configuration and output folders without requesting any websites:

```powershell
cd C:\Users\Matteo\Desktop\gemmaContentEngine
python scripts\discover_topics.py --no-crawl
```

### Launch The Crawler

Run the crawler from the project root:

```powershell
cd C:\Users\Matteo\Desktop\gemmaContentEngine
python scripts\discover_topics.py
```

Optional crawl controls:

```powershell
python scripts\discover_topics.py --max-depth 2 --max-pages-per-domain 40 --delay-seconds 2
```

The crawler respects `robots.txt`, uses a descriptive User-Agent, applies conservative delays, limits crawl depth and pages per domain, and marks sources as JavaScript-required when useful content is unavailable through normal HTTP requests.

### Where Results Are Saved

Every launch creates a new timestamped run folder, for example:

```text
data/raw/research/runs/20260829T180208Z/
data/processed/research/runs/20260829T180208Z/
data/output/opportunities/runs/20260829T180208Z/
```

The main CSV files for each run are:

```text
data/output/opportunities/runs/<RUN_ID>/source-pages.csv
data/output/opportunities/runs/<RUN_ID>/destinations.csv
data/output/opportunities/runs/<RUN_ID>/accessibility-topics.csv
data/output/opportunities/runs/<RUN_ID>/topic-combinations.csv
```

Latest snapshot files are also written here for convenience:

```text
data/output/opportunities/source-pages.csv
data/output/opportunities/destinations.csv
data/output/opportunities/accessibility-topics.csv
data/output/opportunities/topic-combinations.csv
```

Raw and normalised JSON outputs are saved under:

```text
data/raw/research/
data/processed/research/
```

### Validate The Workflow

Run the dependency-free tests:

```powershell
python -m unittest discover -s tests
```

Run a Python syntax check:

```powershell
python -m compileall research scripts tests
```
