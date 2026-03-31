# Analytics SaaS — Mainlayer

[![CI](https://github.com/mainlayer/analytics-saas-mainlayer/actions/workflows/ci.yml/badge.svg)](https://github.com/mainlayer/analytics-saas-mainlayer/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Production-ready privacy-friendly analytics platform (Plausible-like) monetized with [Mainlayer](https://mainlayer.fr) subscription billing.

Perfect for teams that need:
- Privacy-focused event tracking (no third-party tracking)
- Subscription billing with metered usage
- Real-time analytics dashboards
- Per-site billing and entitlement management

## Features

- **Event ingestion** — track pageviews, custom events, user properties
- **Subscription plans** — pro (5 sites, 1M events/mo) or business (25 sites, 10M/mo)
- **Per-site subscriptions** — control billing per customer
- **Real-time analytics** — live visitor counts for the past 5 minutes
- **Dashboard stats** — pageviews, unique visitors, top pages, referrers by period
- **Privacy-first** — visitor IPs are one-way hashed, no tracking pixels
- **FastAPI** — async, production-ready, supports high throughput

## Quick Start

### Installation

```bash
pip install -e ".[dev]"
```

### Run Demo

```bash
export MAINLAYER_API_KEY=mlk_your_api_key
uvicorn src.main:app --reload
```

Then test via [http://localhost:8000/docs](http://localhost:8000/docs)

## API Reference

### Register Site

```
POST /sites
```

Request:
```json
{
  "domain": "example.com",
  "name": "My App",
  "owner_email": "owner@example.com"
}
```

Response (201):
```json
{
  "site_id": "a1b2c3d4",
  "domain": "example.com",
  "name": "My App",
  "created_at": "2024-01-01T00:00:00Z"
}
```

### Track Event

```
POST /track
Header: X-Mainlayer-Token: {token}
```

Request:
```json
{
  "site_id": "a1b2c3d4",
  "name": "pageview",
  "url": "https://example.com/page",
  "referrer": "https://google.com",
  "props": {
    "plan": "pro",
    "account_id": "12345"
  }
}
```

Response (201):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "site_id": "a1b2c3d4",
  "name": "pageview",
  "url": "https://example.com/page",
  "timestamp": "2024-01-01T12:34:56Z"
}
```

When token invalid (402):
```json
{
  "error": "payment_required",
  "info": "mainlayer.fr"
}
```

### Subscribe to Plan

```
POST /subscribe
```

Request:
```json
{
  "site_id": "a1b2c3d4",
  "plan": "pro",
  "api_key": "mlk_your_mainlayer_key"
}
```

Response (200):
```json
{
  "site_id": "a1b2c3d4",
  "plan": "pro",
  "status": "active",
  "payment_id": "pay_abc123",
  "amount": 2900,
  "currency": "USD",
  "message": "Subscription activated. Enjoy your pro plan!"
}
```

### Get Dashboard Stats

```
GET /stats/{site_id}?period=7d
```

Response:
```json
{
  "site_id": "a1b2c3d4",
  "period": "7d",
  "total_pageviews": 12543,
  "unique_visitors": 2104,
  "bounce_rate": 35.2,
  "avg_session_duration_seconds": 142,
  "top_pages": [
    {
      "path": "/",
      "pageviews": 5000,
      "visitors": 1200
    }
  ],
  "top_referrers": [
    {
      "referrer": "google.com",
      "visits": 4500
    }
  ]
}
```

### Get Real-Time Visitors

```
GET /realtime/{site_id}
```

Response:
```json
{
  "site_id": "a1b2c3d4",
  "active_visitors": 47,
  "window_minutes": 5,
  "timestamp": "2024-01-01T12:34:56Z"
}
```

### Check Subscription Status

```
GET /subscription/{site_id}
```

Response:
```json
{
  "site_id": "a1b2c3d4",
  "plan": "pro",
  "active": true,
  "valid_until": "2024-02-01T00:00:00Z"
}
```

## Subscription Plans

| Feature | Pro | Business |
|---------|-----|----------|
| **Monthly price** | $29 | $99 |
| **Sites** | 5 | 25 |
| **Events/month** | 1,000,000 | 10,000,000 |
| **Days history** | 365 | 365 |
| **Real-time** | Yes | Yes |
| **Custom events** | Yes | Yes |
| **API access** | Yes | Yes |

## Environment Variables

```bash
# Required
MAINLAYER_API_KEY=mlk_your_api_key              # Your Mainlayer API key
MAINLAYER_TRACK_RESOURCE_ID=res_track_id        # Resource ID for event tracking billing
MAINLAYER_STATS_RESOURCE_ID=res_stats_id        # Resource ID for dashboard access

# Optional
MAINLAYER_BASE_URL=https://api.mainlayer.fr     # API base URL (default)
DB_PATH=/data/analytics.db                       # SQLite database path
PORT=8000                                        # HTTP port
HOST=0.0.0.0                                     # Bind address
CORS_ORIGINS=*                                   # CORS allowed origins
LOG_LEVEL=INFO                                   # Logging level
```

## Architecture

```
src/
├── main.py               # FastAPI application and routes
├── billing.py            # Mainlayer subscription helpers
├── models.py             # Pydantic data models
└── backend/
    ├── mainlayer.py      # Mainlayer API client
    ├── analytics_db.py   # Analytics event storage
    └── models.py         # Database models
```

### How It Works

1. **Register site** — create `site_id`, database entry
2. **Subscribe** — user pays via Mainlayer, subscription stored
3. **Track events** — POST /track records analytics events
4. **Check entitlement** — verify active subscription before serving dashboard
5. **Aggregate stats** — query event database for dashboard data
6. **Real-time** — query recent events for live visitor count

### Data Storage

Events are stored in SQLite with these fields:
- `event_id` — unique event identifier
- `site_id` — which site this event belongs to
- `name` — event name (pageview, custom_event, etc)
- `url` — page URL or resource identifier
- `referrer` — referring page/source
- `visitor_id` — hashed visitor identifier (derived from IP)
- `timestamp` — when event occurred
- `props` — JSON custom properties

## Testing

```bash
pytest tests/ -v -s
```

## Production Deployment Checklist

- [ ] Set MAINLAYER_API_KEY securely (use secrets manager)
- [ ] Set MAINLAYER_TRACK_RESOURCE_ID and MAINLAYER_STATS_RESOURCE_ID
- [ ] Replace SQLite with PostgreSQL or similar for durability
- [ ] Set up database backups
- [ ] Deploy behind reverse proxy with TLS
- [ ] Enable CORS for your domain(s) only
- [ ] Set LOG_LEVEL=INFO in production
- [ ] Monitor API error rates and latency
- [ ] Set up alerting for failed Mainlayer API calls
- [ ] Test subscription validation failure modes
- [ ] Implement rate limiting for /track endpoint
- [ ] Add request signing verification for webhooks
- [ ] Monitor database query performance
- [ ] Implement data retention policy (GDPR compliance)

## Performance Tuning

- **Event ingestion** — 5,000+ events/second possible with async processing
- **Dashboard queries** — <100ms for 7-day stats (with proper DB indexing)
- **Real-time queries** — <50ms for last 5 minutes
- **Subscription checks** — cached at 5-minute TTL to reduce API calls

## Security Notes

- Visitor IPs are one-way hashed (SHA-256), never stored plaintext
- Events endpoint requires valid Mainlayer token
- Dashboard access requires active subscription
- All Mainlayer API calls use HTTPS
- Rate limiting recommended on /track endpoint

## Privacy

- No third-party tracking pixels
- No user profiling across sites
- No cookie consent required (GDPR compliant)
- Visitor data not sold to third parties
- See PRIVACY.md for full privacy policy

## Examples

See `/examples` for:
- Site registration and subscription
- Event tracking from web and server
- Dashboard data retrieval
- Plan upgrade flows

## Troubleshooting

### Getting 402 Payment Required?
- Site has no active subscription
- Call `POST /subscribe` to activate plan
- Check Mainlayer token is valid
- Verify MAINLAYER_API_KEY is configured

### Events not recorded?
- Check X-Mainlayer-Token header is valid
- Verify site_id exists
- Check database connectivity
- Review server logs for errors

### Dashboard returning no data?
- Verify subscription is active
- Check site_id matches events
- Ensure events were recorded recently
- Check database has proper indexes

## Support

- Documentation: [mainlayer.fr/docs](https://mainlayer.fr/docs)
- GitHub: [github.com/mainlayer/analytics-saas-mainlayer](https://github.com/mainlayer/analytics-saas-mainlayer)
- Issues: [github.com/mainlayer/analytics-saas-mainlayer/issues](https://github.com/mainlayer/analytics-saas-mainlayer/issues)
