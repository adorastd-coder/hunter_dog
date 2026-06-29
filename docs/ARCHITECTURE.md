# Hunter Dog Architecture

Hunter Dog is organized as an independent, retryable, idempotent pipeline. Google Sheets is the single source of truth for all lead records and runtime configuration.

## Source Of Truth

The main Google Sheets leads tab stores every lead and its current `status`. Each pipeline module reads the full tab once, processes eligible rows, and writes back once with a batch update.

Runtime parameters come only from the Google Sheets `CONFIG` tab. Modules must not hardcode runtime values.

Failures are written to the `RUN_LOG` tab. Modules must not fail silently.

## Pipeline Order

1. Discovery
2. Enrichment
3. Scoring
4. Email Writer
5. Sender
6. Tracker

## Lead Status Flow

Each lead advances through this status sequence:

1. `SCRAPED`
2. `ENRICHED`
3. `SCORED`
4. `EMAIL_READY`
5. `SENT`
6. `REPLIED`

## Stage Responsibilities

### Discovery

Discovery scrapes Google Maps search results directly with Playwright, ported from `business-leads-ai-automation/scraper.js`. If Maps returns zero results or raises, Yellow Pages is the fallback source.

Discovery writes newly found leads to Google Sheets with `status = SCRAPED`.

### Enrichment

Enrichment visits each lead's own website only, ported from `dog/scraper.py`. It extracts email addresses, social links, and contact-page data.

Enrichment must not scrape Google Maps place pages and must not run live Google search scraping.

Enriched leads move to `status = ENRICHED`.

### Scoring

Scoring ports the 0-100 weighted algorithm from `leadIntelligence.js`. It folds local Lighthouse page-speed results and Meta ads-running signal into the score as additional signal bonuses.

Bucket assignment remains `A+` through `E`.

Scored leads move to `status = SCORED`.

### Email Writer

Email Writer creates outreach copy for scored leads using credentials from environment variables and runtime parameters from the `CONFIG` tab.

Leads with completed outreach move to `status = EMAIL_READY`.

### Sender

Sender uses Gmail SMTP only. It applies the warm-up ramp using `RAMP_STEP` from the `CONFIG` tab.

Sent leads move to `status = SENT`.

### Tracker

Tracker checks Gmail replies and updates lead records when replies are found.

Replied leads move to `status = REPLIED`.
