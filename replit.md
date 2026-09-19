# Razoreye

Razoreye monitors competitors' llms.txt files and keeps a readable history of every content change.

## Run & Operate

- `uv run python artifacts/api-server/razoreye.py` — run Razoreye locally
- `uv run gunicorn --bind 0.0.0.0:$PORT artifacts.api-server.razoreye:app` — production server
- Optional env: `RAZOREYE_DB` — custom SQLite database path

## Stack

- Python 3.12, Flask, Gunicorn
- SQLite
- APScheduler for periodic checks
- Server-rendered HTML, CSS, and vanilla JavaScript

## Where things live

- `artifacts/api-server/razoreye.py` — Flask app, SQLite schema, monitoring logic, scheduler
- `artifacts/api-server/templates/` — server-rendered pages
- `artifacts/api-server/static/` — CSS and JavaScript

## Architecture decisions

- A first successful fetch establishes the baseline and is not counted as a change.
- Website roots are normalized to `/llms.txt`; explicit file URLs are preserved.
- Monitoring runs in the web process and checks due targets once per minute.

## Product

- Add, pause, resume, manually check, and delete competitor monitors.
- Track HTTP health and the latest successful content.
- Review a timestamped history with unified line-level diffs.

## User preferences

- Use Python, Flask, SQLite, HTML, CSS, and JavaScript. Do not use React.

## Gotchas

_Populate as you build — sharp edges, "always run X before Y" rules._

## Pointers

- See the `pnpm-workspace` skill for workspace structure, TypeScript setup, and package details
