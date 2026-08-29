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

To test one source at a time:

```powershell
python scripts\discover_topics.py --source "Enable Holidays"
```

Source-specific runs create their own timestamped run folder but do not update the top-level latest snapshot files by default. This prevents a debug run for one source from making `data/output/opportunities/source-pages.csv` look like the full crawl lost other sources.

If you intentionally want a source-specific run to become the latest snapshot, add:

```powershell
python scripts\discover_topics.py --source "Enable Holidays" --update-latest
```

The crawler respects `robots.txt`, uses a descriptive User-Agent, applies conservative delays, limits crawl depth and pages per domain, and marks sources as JavaScript-required when useful content is unavailable through normal HTTP requests.

Some sites, including Enable Holidays, return a JavaScript app shell for normal page requests. For those sites, the crawler now tries the public sitemap as a fallback and records sitemap-derived topic leads rather than pretending it extracted full article HTML. These rows will usually have `category` set to `sitemap_candidate` in the processed JSON.

Enable Holidays is configured with `discovery_strategy: sitemap_first` because its blog listing uses on-page buttons for pagination without changing the URL. A normal crawler cannot follow those buttons as separate pages. The sitemap-first strategy uses the public sitemap to discover likely blog/topic URLs instead.

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
data/output/opportunities/runs/<RUN_ID>/source-statuses.csv
data/output/opportunities/runs/<RUN_ID>/destinations.csv
data/output/opportunities/runs/<RUN_ID>/accessibility-topics.csv
data/output/opportunities/runs/<RUN_ID>/topic-combinations.csv
```

Latest snapshot files are also written here for convenience:

```text
data/output/opportunities/source-pages.csv
data/output/opportunities/source-statuses.csv
data/output/opportunities/destinations.csv
data/output/opportunities/accessibility-topics.csv
data/output/opportunities/topic-combinations.csv
```

Raw and normalised JSON outputs are saved under:

```text
data/raw/research/
data/processed/research/
```

### Which Result Files To Open

After a real crawl, start with the newest folder under:

```text
data/output/opportunities/runs/
```

The newest folder has the latest timestamp-style name, for example:

```text
data/output/opportunities/runs/20260829T180911Z/
```

Open these files in this order:

```text
source-statuses.csv
source-pages.csv
topic-combinations.csv
destinations.csv
accessibility-topics.csv
```

What each file means:

- `source-statuses.csv` tells you what happened for each configured source: crawled successfully, blocked by `robots.txt`, JavaScript-required, or no relevant pages found.
- `source-pages.csv` is the main list of discovered pages and topics. This is usually the first useful research file.
- `topic-combinations.csv` aggregates combinations such as `UK + wheelchair + hotels`.
- `destinations.csv` aggregates destination mentions found from the configured vocabulary.
- `accessibility-topics.csv` aggregates accessibility-topic mentions found from the configured vocabulary.

The `data/raw/research/runs/<RUN_ID>/` folder is for crawler diagnostics and raw research JSON.

The `data/processed/research/runs/<RUN_ID>/` folder is the normalised JSON version of discovered pages.

The `data/output/opportunities/runs/<RUN_ID>/` folder is the folder intended for day-to-day review in Excel, Google Sheets or another spreadsheet tool.

The files directly under `data/output/opportunities/` are latest snapshots. They are overwritten by real full crawls. Dry runs and source-specific runs do not overwrite them unless you add `--update-latest`. The files inside `data/output/opportunities/runs/<RUN_ID>/` are preserved for that specific run.

If a source you expect to be rich has few or no rows, check `source-statuses.csv`. For example, Enable Holidays may appear as `sitemap_first` because its blog page is rendered by JavaScript and its pagination buttons do not expose separate crawlable URLs. That means the crawler used sitemap URLs as research leads while avoiding JavaScript crawling or anti-bot workarounds.

### Validate The Workflow

Run the dependency-free tests:

```powershell
python -m unittest discover -s tests
```

Run a Python syntax check:

```powershell
python -m compileall app research scripts tests
```

## Starting The App

Create a virtual environment:

```powershell
python -m venv .venv
```

Activate it on Windows:

```powershell
.venv\Scripts\activate
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

### Install Ollama And Download Gemma

The article generator uses Ollama locally to run Gemma.

Install Ollama for Windows:

```powershell
irm https://ollama.com/install.ps1 | iex
```

Alternatively, download the Windows installer from:

```text
https://ollama.com/download/windows
```

After installing Ollama, close and reopen your terminal. Confirm Windows can find Ollama:

```powershell
ollama --version
```

Download the configured Gemma model:

```powershell
ollama pull gemma4:12b
```

Confirm the model is installed:

```powershell
ollama list
```

If Windows says `'ollama' is not recognized as an internal or external command`, Ollama is not installed or the terminal was opened before installation finished. Close the terminal, open a new one, and try `ollama --version` again.

Ollama for Windows normally runs its API in the background at:

```text
http://localhost:11434
```

If needed, start Ollama manually:

```powershell
ollama serve
```

To use a different local model later, pull that model and change `OLLAMA_MODEL` in `.env`.

Ollama settings can be changed in `.env`:

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=gemma4:12b
OLLAMA_TIMEOUT=180
MAX_RESEARCH_RECORDS=20
MAX_RESEARCH_CONTEXT_CHARS=20000
```

`MAX_RESEARCH_RECORDS` and `MAX_RESEARCH_CONTEXT_CHARS` limit how much crawler output is included when `Use crawler/research data` is enabled. The app still keeps the crawler files on disk, but only the most relevant matching rows are sent into the article prompt.

Do not commit `.env`.

### Run The FastAPI App

In another terminal, run FastAPI from the project root:

```powershell
cd C:\Users\Matteo\Desktop\gemmaContentEngine
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8010
```

Open:

```text
http://127.0.0.1:8010
```

If Windows shows `[WinError 10013] An attempt was made to access a socket in a way forbidden by its access permissions`, the default port is blocked or reserved. Change only the port number, for example:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8020
```

If the app says `Ollama is not running or cannot be reached at the configured URL`, check that Ollama is installed and reachable:

```powershell
ollama list
```

Then confirm the Gemma model is listed. If it is missing, run:

```powershell
ollama pull gemma4:12b
```

Routes:

```text
/
```

Article generator. This always loads the Markdown files in `content-guidelines/` in filename order.

```text
/suggestions
```

Research-driven topic/title suggestions. This uses local crawler output from `data/` and never fabricates search volume.

The article form includes a checkbox:

```text
Use crawler/research data
```

If unchecked, the article prompt uses only the user brief plus mandatory `content-guidelines/`. If checked, the app searches supported local research files and includes only relevant rows. The generated article is saved to:

```text
articles/drafts/
```

## Testing Article Quality

Use this workflow to manually compare Gemma output with and without crawler/research context. This is not automatic A/B testing; it is a controlled manual review.

Recommended first test brief:

```text
Working title:
Wheelchair Accessible Holidays in Tenerife

Primary keyword:
wheelchair accessible holidays Tenerife

Secondary keywords:
accessible holidays Tenerife
disabled holidays Tenerife
wheelchair friendly Tenerife
accessible hotels Tenerife

Article type:
Destination guide

Search intent:
Commercial Research

Funnel stage:
Consideration

Primary reader need:
The reader wants to understand whether Tenerife could be suitable for their accessibility requirements and what they should consider before choosing a holiday.

Main concerns:
Accessible accommodation
Wheelchair-friendly transport
Airport assistance
Accessible excursions
Mobility scooters
Bathroom suitability

Destination:
Tenerife

Country:
Spain

Target length:
1500

Primary conversion:
Phone enquiry

CTA strength:
Automatic based on intent
```

Only add verified Limitless information when it is genuinely known. Do not use the form to invent factual accessibility claims.

### Test A

Run the article with:

```text
Use crawler/research data = OFF
Show prompt/debug details = ON
```

Review:

- search-intent satisfaction
- tone
- accessibility language
- CRO flow
- CTA timing
- factual caution
- readability
- repetition
- adherence to Limitless guidelines

### Test B

Run the exact same brief with:

```text
Use crawler/research data = ON
Show prompt/debug details = ON
```

Compare against Test A.

Research should ideally improve:

- topic coverage
- headings
- questions considered
- destination context
- article depth

Research must not:

- introduce unsupported Limitless claims
- make competitor accessibility claims sound verified
- copy competitor wording
- significantly damage tone
- create irrelevant sections
- overwhelm the article brief

### Debug Review

When `Show prompt/debug details` is enabled, the result page shows a collapsed developer section with:

- model configuration without secrets
- guideline files loaded in the order sent to Gemma
- combined guideline character count
- approximate guideline token count
- structured article brief
- whether research data was requested
- selected research records and files consulted
- whether research context was truncated
- system prompt and user prompt shown separately
- available Ollama metrics
- generation start time, finish time and duration

The complete assembled prompt is displayed only in the debug UI. It is not saved into article drafts.

### Manual Review Checklist

Search intent:

- Does the article answer the actual query quickly?
- Does it avoid a generic travel introduction?

Tone:

- Clear?
- Warm?
- Empathetic?
- Reassuring?
- Human?
- UK English?
- Not patronising?

Accessibility:

- Any blanket accessibility claims?
- Any unsupported hotel, transport or equipment claims?
- Does it recognise individual requirements?

CRO progression:

```text
Useful answer
Practical information
Accessibility considerations
Reassurance
Trust
Relevant Limitless solution
Reason to talk to an advisor
Phone CTA
```

- Does the CTA feel earned?
- Is there a genuine reason to call?
- Does it avoid aggressive urgency?

SEO:

- Does the primary keyword occur naturally?
- Are headings descriptive?
- Are related questions answered?
- Is there keyword stuffing?
- Is there filler?

AI-writing quality:

Watch for excessive phrases such as:

```text
Whether you're...
It's important to note...
Embark on...
Vibrant destination...
Look no further...
When it comes to...
```

Also watch for:

- repetitive conclusions
- formulaic H2 sections
- unnecessary bullet lists
- excessive reassurance
- repeated CTA wording
- generic travel descriptions

The editorial score generated by Gemma can remain in the article output, but do not treat a model grading its own article as objective evidence. Manual evaluation comes first.
