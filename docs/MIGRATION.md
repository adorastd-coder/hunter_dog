# Migration Report

This report covers the visible project files in `../dog/` and `../business-leads-ai-automation/`.

Generated or external artifacts are not migration sources: `.git/`, `.venv/`, `node_modules/`, `__pycache__/`, `output/`, and empty runtime log files.

Required Hunter Dog architecture files were not present in the workspace at the time of this report: `docs/MASTER_RULES.md` and `docs/ARCHITECTURE.md`.

## Label Legend

- `PORT`: Logic gets reused in Hunter Dog.
- `DISCARD`: Not used in Hunter Dog.
- `REWRITE`: Concept is kept, but implementation changes.

## `../dog/`

| File | Label | Summary |
| --- | --- | --- |
| `config.py` | REWRITE | Stores hard-coded placeholders for Google Places, Groq, Gmail SMTP, and Gmail OAuth credential paths. Keep the configuration concept, but move to Hunter Dog's finalized secrets/config approach. |
| `emailer.py` | PORT | Calls Groq chat completions to generate short cold email copy from lead name, city, country, and gap reason. Port the Groq outreach generation behavior. |
| `leads.py` | DISCARD | Uses Google Places Text Search and Place Details APIs to collect dental clinic leads and save them to `leads.xlsx`. Discard because billing-gated APIs are not allowed. |
| `requirements.txt` | REWRITE | Lists legacy Python dependencies for requests, OpenPyXL, Playwright, and Gmail APIs. Recreate dependencies from Hunter Dog's actual modules. |
| `run_pipeline.py` | REWRITE | Orchestrates Excel-based enrichment, scraping, HOT/WARM/COLD scoring, and Groq email drafting. Keep the pipeline concept only; Hunter Dog implementation must use the finalized architecture and ported 0-100 scoring. |
| `scorer.py` | DISCARD | Scores leads into HOT/WARM/COLD using simple website, email, social, copyright, rating, and review rules. Discard because Hunter Dog uses the ported 0-100 JavaScript scoring model. |
| `scraper.py` | PORT | Uses Playwright to normalize websites, scan home/contact pages, extract email, WhatsApp, Instagram, Facebook, LinkedIn, and copyright year. Port this website contact and social extraction logic. |
| `sender.py` | PORT | Sends pending Excel leads through Gmail SMTP with daily caps, sent flags, sent dates, randomized delays, and required column creation. Port SMTP sending behavior. |
| `tracker.py` | PORT | Uses Gmail API OAuth to detect replies, mark replied leads, and send scheduled follow-ups at 3, 6, and 10 days through the sender module. Port Gmail reply checking and follow-up behavior. |

## `../business-leads-ai-automation/`

| File | Label | Summary |
| --- | --- | --- |
| `.env.example` | REWRITE | Documents legacy OpenAI/Groq, campaign, scraper, output, scoring, and marketing settings. Keep the environment-template concept, but rewrite for Hunter Dog's Python/Streamlit/GitHub Actions architecture. |
| `.github/FUNDING.yml` | DISCARD | Repository sponsorship metadata. Not relevant to Hunter Dog runtime or migration logic. |
| `.gitignore` | REWRITE | Ignores Node outputs, `.env`, CSVs, and generated profile files. Rewrite ignore rules for Hunter Dog's actual Python outputs and secrets. |
| `config.py` | DISCARD | Python config for Google Places API discovery, CSV columns, Playwright timing, and search queries. Discard because it centers on billing-gated Places APIs and legacy CSV flow. |
| `CONTRIBUTING.md` | DISCARD | Legacy contribution guide and ethical-use notes for the old Node project. Not used in Hunter Dog implementation. |
| `DISCLAIMER.md` | DISCARD | Legacy legal/ethical disclaimer focused on scraping, APIs, and marketing compliance. Not a Hunter Dog migration source. |
| `docs/USER_GUIDE.md` | DISCARD | User guide for the legacy Node web dashboard, setup wizard, campaign UI, and exports. Discard because Hunter Dog uses Streamlit and GitHub Actions. |
| `index.js` | DISCARD | Thin redirect to `src/cli.js` and legacy scraper export. Discard with the legacy CLI structure. |
| `leads.py` | DISCARD | Python Google Places API lead discovery and CSV export. Discard because no billing-gated APIs are allowed. |
| `nodemon.json` | DISCARD | Node development reload configuration. Not used by Hunter Dog. |
| `package.json` | DISCARD | Node package metadata, scripts, and dependencies for Puppeteer, Express, OpenAI, SQLite, and ExcelJS. Discard because Hunter Dog is not keeping the Node app. |
| `package-lock.json` | DISCARD | Locked Node dependency tree. Discard with the Node implementation. |
| `README.md` | DISCARD | Legacy project documentation for Node scraping, campaigns, setup, and dashboard usage. Not used in Hunter Dog implementation. |
| `requirements.txt` | REWRITE | Python dependency list for the legacy sidecar scripts. Rewrite based on Hunter Dog's actual Python dependencies. |
| `scraper.py` | PORT | Python Playwright website enrichment over CSV rows: extracts email, phone, Facebook, Instagram, copyright year, contact/about pages, and scrape status. Port useful enrichment concepts alongside `dog/scraper.py`. |
| `scripts/build_master_lead_workbooks.js` | DISCARD | Aggregates legacy JSON campaign outputs into styled Excel master workbooks, deduplicates leads, and splits local/international sheets. Discard unless Hunter Dog later defines an Excel export requirement. |
| `scripts/generate_intelligence_pdf.py` | DISCARD | Generates ReportLab PDF intelligence reports from legacy JSON with ad, competitor, reputation, and sales strategy sections. Discard because report generation is not part of the finalized task mapping. |
| `scripts/requirements.txt` | DISCARD | ReportLab dependency list for the discarded PDF script. Not used. |
| `src/adIntelligence.js` | REWRITE | Uses Puppeteer to inspect Meta Ads Library pages and Google Ads Transparency pages, then summarizes active ad platforms. Rewrite to use Meta Ad Library API only and drop Google Ad Transparency scraping. |
| `src/businessProfile.js` | REWRITE | Loads, validates, defaults, saves, and flattens `business-profile.json` for AI prompts. Keep the profile concept only if needed by Hunter Dog settings, but rewrite in Python. |
| `src/campaign.js` | DISCARD | Interactive Node campaign builder that scrapes Maps, scores leads, generates content, exports files, and optionally runs intelligence reports. Discard in favor of Streamlit and GitHub Actions. |
| `src/cli.js` | DISCARD | Parses Node CLI flags, runs Google Maps scraping, saves files, and optionally generates marketing content. Discard because Hunter Dog replaces CLI flow. |
| `src/competitorFinder.js` | DISCARD | Uses Maps-style searches, competitor scoring, and ad intelligence to find nearby competitors and opportunity reasons. Not in Hunter Dog's finalized migration scope. |
| `src/fileUtils.js` | REWRITE | Saves and loads legacy CSV/JSON lead files, logs activity, and normalizes phone values. Keep file persistence/export concepts only if needed, but rewrite for Hunter Dog data models. |
| `src/intelligenceOrchestrator.js` | DISCARD | Coordinates ad intelligence, competitor analysis, 0-100 scoring, JSON output, and PDF generation. Discard because Hunter Dog scope only ports scoring and rewrites ad checks. |
| `src/leadIntelligence.js` | PORT | Implements 0-100 weighted lead scoring using data completeness, business quality, digital presence, location value, industry potential, and contactability. Port this scoring model to Python. |
| `src/marketing.js` | DISCARD | OpenAI-powered marketing automation for email and WhatsApp content using business profile prompts. Discard because Hunter Dog ports Groq email generation from Python instead. |
| `src/marketingAI.js` | DISCARD | Industry-specific AI outreach templates, multi-touch generation, and campaign-style prompt logic for dental/private school niches. Not part of Hunter Dog's finalized migration mapping. |
| `src/openaiClient.js` | DISCARD | Creates and caches an OpenAI-compatible client from environment variables. Discard because Hunter Dog ports Groq behavior from `dog/emailer.py`. |
| `src/scraper.js` | PORT | Puppeteer Google Maps discovery with search URL creation, result scrolling, card extraction, detail-page enrichment, website enrichment, market filtering, and legacy Yellow Pages/email search helpers. Port the Maps search and scroll discovery logic to Python Playwright. |
| `src/setup.js` | DISCARD | Interactive Node setup wizard for API keys, business profile, owner info, preferences, industries, and sample campaigns. Discard with the legacy Node app. |
| `src/web/public/css/components.css` | DISCARD | Legacy dashboard component styling for cards, tables, modals, notifications, progress UI, and exports. Discard because dashboard UI is replaced by Streamlit. |
| `src/web/public/css/dashboard.css` | DISCARD | Legacy dashboard layout, navigation, campaign, analytics, and responsive CSS. Discard because dashboard UI is replaced by Streamlit. |
| `src/web/public/index.html` | DISCARD | Legacy Express-served dashboard shell for campaigns, leads, analytics, settings, modals, and script loading. Discard because dashboard UI is replaced by Streamlit. |
| `src/web/public/js/api.js` | DISCARD | Browser API wrapper for legacy Express endpoints, formatting helpers, downloads, scoring display, and error handling. Discard with the Express dashboard. |
| `src/web/public/js/components.js` | DISCARD | Legacy browser UI components for notifications, modals, charts, data tables, and campaign progress. Discard with the dashboard HTML/CSS. |
| `src/web/public/js/dashboard.js` | DISCARD | Legacy client-side dashboard controller for campaigns, leads, analytics, SSE progress, exports, outreach editing, and send queue dry runs. Discard because Streamlit replaces the dashboard. |
| `src/web/server.js` | DISCARD | Express API and static server for dashboard data, campaigns, exports, vCards, SSE, settings, sending, and intelligence endpoints. Discard because Hunter Dog uses Streamlit and GitHub Actions. |
| `test.js` | DISCARD | Legacy Node test/demo script for scraper, file utilities, marketing automation, CLI commands, error handling, and environment checks. Discard with the Node app. |
| `vrixo_pipeline.py` | REWRITE | Monolithic Python campaign pipeline using Google Places APIs, website enrichment, public Meta page checks, grading, Groq drafting, SMTP sending, exports, and CLI commands. Keep selected concepts only where they match finalized architecture; rewrite to avoid billing-gated APIs and align with Hunter Dog modules. |

## Ground Truth Migration Decisions

- `dog/scraper.py`: `PORT` for website email, social, WhatsApp, LinkedIn, contact-page, and copyright extraction.
- `dog/scorer.py`: `DISCARD` because scoring is replaced by ported 0-100 JavaScript scoring.
- `dog/emailer.py`, `dog/sender.py`, `dog/tracker.py`: `PORT` for Groq email generation, SMTP sending, and Gmail API reply checks.
- `dog/leads.py`: `DISCARD` because Google Places API usage is billing-gated.
- `business-leads-ai-automation/src/scraper.js`: `PORT` for Google Maps search and scroll logic, to become Python Playwright discovery.
- `business-leads-ai-automation/src/leadIntelligence.js`: `PORT` for 0-100 weighted scoring, to be ported to Python.
- `business-leads-ai-automation/src/adIntelligence.js`: `REWRITE` using Meta Ad Library API only; Google Ad Transparency scraping is dropped.
- `business-leads-ai-automation/src/web/server.js`, `business-leads-ai-automation/src/cli.js`, and dashboard HTML/CSS/JS: `DISCARD` because Hunter Dog uses Streamlit and GitHub Actions.
