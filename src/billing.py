"""Mainlayer subscription billing helpers.

Provides the glue between the analytics API and the Mainlayer billing
platform for subscription activation, status checks, and cancellation.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from backend.analytics_db import get_subscription, has_active_subscription, upsert_subscription
from backend.mainlayer import MainlayerClient, MainlayerError, get_plan_features, get_plan_price

logger = logging.getLogger(__name__)

MAINLAYER_API_KEY = os.environ.get("MAINLAYER_API_KEY", "demo")


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


async def activate_subscription(
    site_id: str,
    plan: str,
    api_key: Optional[str] = None,
    customer_email: Optional[str] = None,
) -> dict:
    """Create a Mainlayer payment and record the subscription.

    Returns a dict with keys: payment_id, plan, status, amount, features.
    Raises MainlayerError on billing failure.
    """
    key = api_key or MAINLAYER_API_KEY
    client = MainlayerClient(api_key=key)

    result = await client.create_subscription(
        site_id=site_id,
        plan=plan,
        customer_email=customer_email,
    )

    upsert_subscription(
        site_id=site_id,
        plan=plan,
        payment_id=result.get("payment_id"),
        status="active",
    )

    logger.info("Subscription activated: site=%s plan=%s", site_id, plan)
    return {
        **result,
        "features": get_plan_features(plan),
    }


def check_subscription(site_id: str) -> dict:
    """Return subscription status for a site without hitting the payment API."""
    active = has_active_subscription(site_id)
    sub = get_subscription(site_id)
    return {
        "site_id": site_id,
        "active": active,
        "plan": sub["plan"] if sub else None,
        "valid_until": sub["valid_until"] if sub else None,
        "features": get_plan_features(sub["plan"]) if sub else {},
    }


def get_pricing() -> dict:
    """Return the current plan pricing table."""
    return {
        "pro": {
            "price_usd_per_month": get_plan_price("pro"),
            "features": get_plan_features("pro"),
        },
        "business": {
            "price_usd_per_month": get_plan_price("business"),
            "features": get_plan_features("business"),
        },
    }
