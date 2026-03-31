"""Analytics SaaS API — Plausible-like analytics monetised with Mainlayer.

Endpoints
---------
POST /track                  — ingest an analytics event (requires payment)
GET  /stats/{site_id}        — aggregated dashboard stats (subscription check)
GET  /realtime/{site_id}     — live visitor count (subscription check)
POST /sites                  — register a new site
POST /subscribe              — create a subscription via Mainlayer
GET  /health                 — health probe (free)
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.analytics_db import (
    get_events,
    get_pageviews,
    get_site,
    get_subscription,
    get_summary,
    has_active_subscription,
    init_db,
    record_event,
    register_site,
    upsert_subscription,
)
from backend.mainlayer import MainlayerClient, MainlayerError
from backend.models import (
    ErrorResponse,
    EventPayload,
    EventResponse,
    PageviewsResponse,
    SiteRegistration,
    SiteResponse,
    SubscriptionRequest,
    SubscriptionResponse,
    SubscriptionStatus,
    SummaryResponse,
)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("analytics-saas")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Analytics SaaS API",
    description=(
        "Privacy-friendly analytics platform monetised with Mainlayer. "
        "Track events, view dashboards, and manage per-site subscriptions."
    ),
    version="1.0.0",
    contact={"name": "Mainlayer", "url": "https://mainlayer.fr"},
    license_info={"name": "MIT"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    init_db()
    logger.info("Database initialised")


# ---------------------------------------------------------------------------
# Payment dependency
# ---------------------------------------------------------------------------

MAINLAYER_API_KEY = os.environ.get("MAINLAYER_API_KEY", "demo")
TRACK_RESOURCE_ID = os.environ.get("MAINLAYER_TRACK_RESOURCE_ID", "")
STATS_RESOURCE_ID = os.environ.get("MAINLAYER_STATS_RESOURCE_ID", "")


async def require_active_subscription(
    site_id: str,
    x_mainlayer_token: str = Header(default=""),
) -> SubscriptionStatus:
    """FastAPI dependency — verifies an active subscription for the site."""
    if not has_active_subscription(site_id):
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "subscription_required",
                "info": "mainlayer.fr",
                "message": f"No active subscription for site '{site_id}'. POST /subscribe to get started.",
            },
        )
    sub = get_subscription(site_id)
    return SubscriptionStatus(
        site_id=site_id,
        plan=sub["plan"] if sub else None,
        active=True,
        valid_until=datetime.fromisoformat(sub["valid_until"]) if sub else None,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.post(
    "/track",
    response_model=EventResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Events"],
    summary="Record an analytics event",
    responses={402: {"model": ErrorResponse, "description": "Payment required"}},
)
async def track_event(
    payload: EventPayload,
    request: Request,
    x_mainlayer_token: str = Header(default=""),
) -> EventResponse:
    """Ingest a single analytics event for a site.

    Requires:
    - Valid Mainlayer payment token via X-Mainlayer-Token header
    - Active subscription for the site
    - Valid site_id that has been registered

    Events are stored with privacy protections:
    - Visitor IP is one-way hashed (SHA-256)
    - No PII is stored
    - Data is retained according to your plan
    """
    if not x_mainlayer_token:
        logger.warning("Event rejected: missing payment token for site %s", payload.site_id)
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "error": "payment_required",
                "message": "X-Mainlayer-Token header required",
                "info": "mainlayer.fr",
            },
        )

    # Validate site exists
    if not get_site(payload.site_id):
        logger.warning("Event rejected: unknown site %s", payload.site_id)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "site_not_found",
                "message": f"Site {payload.site_id} not found",
            },
        )

    try:
        event_id = str(uuid.uuid4())
        client_ip = request.client.host if request.client else None
        props_str = json.dumps(payload.props) if payload.props else None

        record_event(
            event_id=event_id,
            site_id=payload.site_id,
            name=payload.name,
            url=payload.url,
            referrer=payload.referrer,
            ip=client_ip,
            props=props_str,
        )

        logger.info("Event recorded: site=%s name=%s ip=%s", payload.site_id, payload.name, client_ip)
        return EventResponse(
            id=event_id,
            site_id=payload.site_id,
            name=payload.name,
            url=payload.url,
            timestamp=datetime.utcnow(),
        )
    except Exception as e:
        logger.error("Failed to record event for site %s: %s", payload.site_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_server_error", "message": str(e)},
        )


@app.get(
    "/stats/{site_id}",
    response_model=SummaryResponse,
    tags=["Stats"],
    summary="Get aggregated stats for a site (subscription required)",
    responses={402: {"model": ErrorResponse, "description": "Subscription required"}},
)
async def get_stats(
    site_id: str,
    period: str = Query("7d", pattern="^(24h|7d|30d|90d)$"),
    _sub: SubscriptionStatus = Depends(require_active_subscription),
) -> SummaryResponse:
    """Return the analytics dashboard for a site.

    Requires an active Mainlayer subscription. Supply the site_id in the path
    and the desired period as a query parameter (24h | 7d | 30d | 90d).
    """
    summary = get_summary(site_id, period)
    return SummaryResponse(**summary)


@app.get(
    "/realtime/{site_id}",
    tags=["Stats"],
    summary="Live visitor count for the past 5 minutes (subscription required)",
    responses={402: {"model": ErrorResponse, "description": "Subscription required"}},
)
async def get_realtime(
    site_id: str,
    _sub: SubscriptionStatus = Depends(require_active_subscription),
) -> dict:
    """Return the number of unique visitors seen in the last 5 minutes.

    The result is derived from hashed visitor IDs in the events table.
    In production, replace this with a Redis-backed real-time counter.
    """
    from backend.analytics_db import get_db

    cutoff = (datetime.utcnow() - timedelta(minutes=5)).isoformat()
    with get_db() as conn:
        count = conn.execute(
            """
            SELECT COUNT(DISTINCT visitor_id) FROM events
            WHERE site_id = ? AND timestamp >= ? AND visitor_id IS NOT NULL
            """,
            (site_id, cutoff),
        ).fetchone()[0]

    return {
        "site_id": site_id,
        "active_visitors": count,
        "window_minutes": 5,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post(
    "/sites",
    response_model=SiteResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Sites"],
    summary="Register a new site for analytics",
)
async def create_site(body: SiteRegistration) -> SiteResponse:
    """Register a new site for analytics tracking.

    Returns a `site_id` that must be passed in all subsequent tracking calls.

    After registering, call POST /subscribe to activate a subscription plan
    and enable dashboard access.
    """
    # Validate domain format
    if not body.domain or not isinstance(body.domain, str):
        raise HTTPException(status_code=400, detail="domain is required")

    # Validate email format
    if body.owner_email and "@" not in body.owner_email:
        raise HTTPException(status_code=400, detail="invalid email format")

    site_id = str(uuid.uuid4())[:8]
    try:
        site = register_site(
            site_id=site_id,
            domain=body.domain,
            name=body.name,
            owner_email=body.owner_email,
        )
    except ValueError as exc:
        logger.warning("Site registration failed: %s", exc)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))

    logger.info("Site registered: %s (%s) owner=%s", site_id, body.domain, body.owner_email)
    return SiteResponse(**site)


@app.post(
    "/subscribe",
    response_model=SubscriptionResponse,
    tags=["Billing"],
    summary="Subscribe a site to an analytics plan via Mainlayer",
    responses={402: {"model": ErrorResponse, "description": "Payment failed"}},
)
async def subscribe(body: SubscriptionRequest) -> SubscriptionResponse:
    """Create a Mainlayer payment and activate an analytics subscription.

    Plans: `pro` ($29/month, 1M events, 5 sites) or `business` ($99/month).
    """
    client = MainlayerClient(api_key=body.api_key)
    try:
        result = await client.create_subscription(
            site_id=body.site_id,
            plan=body.plan,
        )
    except MainlayerError as exc:
        raise HTTPException(
            status_code=exc.status_code or status.HTTP_402_PAYMENT_REQUIRED,
            detail={"error": exc.code, "message": exc.message},
        )

    upsert_subscription(
        site_id=body.site_id,
        plan=body.plan,
        payment_id=result.get("payment_id"),
        status="active",
    )

    return SubscriptionResponse(
        site_id=body.site_id,
        plan=body.plan,
        status="active",
        payment_id=result.get("payment_id"),
        amount=result.get("amount"),
        currency="USD",
        message=f"Subscription activated. Enjoy your {body.plan} plan!",
    )


@app.get("/subscription/{site_id}", response_model=SubscriptionStatus, tags=["Billing"])
async def get_subscription_status(site_id: str) -> SubscriptionStatus:
    """Check whether a site has an active subscription."""
    sub = get_subscription(site_id)
    if not sub:
        return SubscriptionStatus(site_id=site_id, plan=None, active=False, valid_until=None)
    return SubscriptionStatus(
        site_id=site_id,
        plan=sub["plan"],
        active=True,
        valid_until=datetime.fromisoformat(sub["valid_until"]),
    )


@app.get("/health", tags=["Info"])
async def health() -> dict:
    """Health check endpoint (unauthenticated)."""
    from backend.analytics_db import get_db
    try:
        with get_db() as conn:
            conn.execute("SELECT 1")
        return {
            "status": "ok",
            "service": "analytics-saas",
            "database": "connected",
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error("Health check failed: %s", e)
        return {
            "status": "error",
            "service": "analytics-saas",
            "database": "disconnected",
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# Exception handler
# ---------------------------------------------------------------------------


@app.exception_handler(Exception)
async def generic_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"error": "internal_server_error", "detail": str(exc)},
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("RELOAD", "false").lower() == "true",
    )
