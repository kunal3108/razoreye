# Razoreye

**Competitive AEO Intelligence — Monitor → Detect → Compare → Recommend → Act**

Razoreye is a competitive-intelligence agent for Answer Engine Optimization (AEO). It monitors competitors' AI-facing content, detects and versions changes, compares those changes with a brand's existing coverage, produces **ACT**, **WATCH**, or **NO ACTION** recommendations, and routes actionable intelligence to Slack.

## Problem

AI-facing product and documentation surfaces can change without an obvious announcement. Teams need to know what changed, whether it creates a meaningful coverage gap, and what action is justified—not just whether their own site passes an AEO checklist.

> **Traditional AEO readiness tools:** “How AI-ready is my website?”  
> **Razoreye:** “What are my competitors changing, does it create a gap for us, and what should we do about it?”

## What Razoreye Does

- Monitors configured `llms.txt` sources on a schedule or on demand.
- Uses SHA-256 hashes to detect content changes.
- Stores versions and readable line-level diffs.
- Uses an LLM to analyze the competitive signal against stored brand coverage.
- Falls back to deterministic analysis if LLM analysis is unavailable.
- Classifies recommendations as **ACT**, **WATCH**, or **NO ACTION**.
- Sends daily summaries and change analysis to Slack.

`llms.txt` is an emerging convention for publishing AI-facing site guidance. Razoreye treats it as a useful monitoring surface, not as a proven ranking factor or evidence of causality in AI answer engines.

## Architecture

```text
Competitor AI-facing content
        ↓
      Monitor
        ↓
SHA-256 Change Detection
        ↓
   Version / Diff
        ↓
   LLM Analysis
        ↓
Brand Coverage Comparison
        ↓
ACT / WATCH / NO ACTION
        ↓
      Slack
```

## Current MVP

The MVP monitors `llms.txt` content and has monitors for **Razorpay, Stripe, Cashfree**, and the included **DemoPay sandbox**. It supports:

- Adding, pausing, resuming, checking, and deleting monitors.
- Scheduled checks with configurable intervals.
- HTTP status and error tracking.
- Baseline capture, SHA-256 change detection, and version history.
- Unified line-level diffs.
- Evidence-focused OpenAI analysis with structured output.
- Deterministic fallback recommendations.
- Daily Slack summaries with threaded change analysis.
- A DemoPay simulation for demonstrating a detected competitive change.

## Example Workflow

1. Razoreye fetches a competitor's latest `llms.txt`.
2. A SHA-256 comparison identifies whether the content changed.
3. Razoreye stores the new version and generates a line-level diff.
4. The analyzer retrieves relevant evidence from the competitor and Razorpay content.
5. The change receives an impact assessment and **ACT**, **WATCH**, or **NO ACTION** recommendation.
6. The result appears in the dashboard and the daily Slack alert.

## AEO Signals We Can Monitor Next

- `robots.txt` rules and AI crawler access
- XML sitemaps and URL inventory changes
- Schema.org and other structured data
- Product, pricing, and documentation changes
- API documentation and changelogs
- MCP and agent-discovery surfaces
- Brand and entity signals
- AI answer-engine mentions and citations
- Competitive share of voice
- Eventual GA4 and Google Search Console correlation for business-impact analysis

These signals can support investigation and prioritization; they should not be presented as proof of ranking impact or causality.

## Tech Stack

- Python 3.12
- Flask and Jinja templates
- SQLite
- APScheduler
- Requests
- OpenAI Python SDK
- Gunicorn
- Server-rendered HTML, CSS, and vanilla JavaScript
- `uv` for Python dependency management

## Running Locally

Prerequisites: Python 3.12 and `uv`.

```bash
uv sync
uv run python artifacts/api-server/razoreye.py
```

The application listens on port `8080` by default. For a production-style local server:

```bash
PORT=8080 uv run gunicorn \
  --chdir artifacts/api-server \
  --bind 0.0.0.0:$PORT \
  --workers 1 \
  --threads 4 \
  razoreye:app
```

## Environment Variables

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `SLACK_BOT_TOKEN`
- `RAZOREYE_SLACK_CHANNEL`
- `RAZOREYE_SLACK_CONTACT`
- `SESSION_SECRET`
- `RAZOREYE_DB`
- `PORT`

Store credentials in Replit Secrets or your local environment. Never commit them.

## Future Roadmap

- Expand monitoring beyond `llms.txt` to the AEO signals listed above.
- Add cross-competitor trend and share-of-voice views.
- Track citations and mentions across answer engines.
- Correlate detected changes with GA4 and Search Console outcomes.
- Move persistence and scheduling to infrastructure suited for durable, always-on production workloads.
- Add configurable brands, analysis policies, alert destinations, and team workflows.