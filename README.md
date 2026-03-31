# Analytics SaaS — Mainlayer

Privacy-friendly analytics platform (Plausible-like) monetised with [Mainlayer](https://mainlayer.fr).

Sites subscribe via Mainlayer to unlock their dashboard. Event ingestion is billed per-event.

## Features

- **POST /track** — ingest pageviews and custom events (requires Mainlayer token)
- **GET /stats/{site_id}** — full dashboard: pageviews, unique visitors, top pages, referrers (subscription required)
- **GET /realtime/{site_id}** — live visitor count for the past 5 minutes (subscription required)
- **POST /sites** — register a site and receive a `site_id`
- **POST /subscribe** — activate a Pro or Business plan via Mainlayer

## Quick start

```bash
pip install -e ".[dev]"
MAINLAYER_API_KEY=sk_... uvicorn src.main:app --reload
```

Open [http://localhost:8000/docs](http://localhost:8000/docs) for the interactive API explorer.

## Plans

| Plan | Price | Sites | Events/month |
|------|-------|-------|--------------|
| Pro | $29/mo | 5 | 1,000,000 |
| Business | $99/mo | 25 | 10,000,000 |

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `MAINLAYER_API_KEY` | `demo` | Your Mainlayer API key |
| `DB_PATH` | `/data/analytics.db` | SQLite database path |
| `PORT` | `8000` | HTTP port |

## Running tests

```bash
pytest tests/ -v
```
