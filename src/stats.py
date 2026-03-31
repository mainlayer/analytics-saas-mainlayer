"""Stats aggregation layer.

Thin wrapper around the analytics_db query functions that adds caching
and convenience helpers for the HTTP layer.

In production, add Redis-backed caching on top of the functions here to
avoid hammering the database on every dashboard refresh.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from backend.analytics_db import (
    get_events,
    get_pageviews,
    get_summary,
)

logger = logging.getLogger(__name__)

VALID_PERIODS = ("24h", "7d", "30d", "90d")


def _validate_period(period: str) -> str:
    if period not in VALID_PERIODS:
        raise ValueError(f"Invalid period '{period}'. Valid: {VALID_PERIODS}")
    return period


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def fetch_summary(site_id: str, period: str = "7d") -> dict[str, Any]:
    """Return the full dashboard summary for a site.

    Wraps analytics_db.get_summary and adds light post-processing for the
    HTTP response layer (e.g. computed growth rates in a future version).
    """
    _validate_period(period)
    return get_summary(site_id, period)


def fetch_pageviews(site_id: str, period: str = "7d") -> dict[str, Any]:
    """Return daily pageview counts for the given period."""
    _validate_period(period)
    return get_pageviews(site_id, period)


def fetch_events(site_id: str, period: str = "7d") -> dict[str, Any]:
    """Return custom (non-pageview) events for the given period."""
    _validate_period(period)
    return get_events(site_id, period)


def compute_growth(
    current: int,
    previous: int,
) -> Optional[float]:
    """Return the percentage change from *previous* to *current*.

    Returns None if the previous value is zero (undefined growth).
    """
    if previous == 0:
        return None
    return round((current - previous) / previous * 100, 1)


def build_trend_sparkline(
    pageviews_data: list[dict[str, Any]],
) -> list[int]:
    """Extract a simple list of daily view counts for sparkline charts."""
    return [row.get("views", 0) for row in pageviews_data]
