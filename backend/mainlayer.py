"""
Mainlayer billing integration.

Mainlayer is the API-native billing layer for SaaS products.
Base URL: https://api.mainlayer.xyz
Auth: Bearer <api_key>
"""

import httpx
import logging
from typing import Optional
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

MAINLAYER_BASE_URL = "https://api.mainlayer.xyz"

PLAN_PRICES = {
    "pro": 29.00,
    "business": 99.00,
}

PLAN_FEATURES = {
    "pro": {
        "sites": 5,
        "events_per_month": 1_000_000,
        "retention_days": 365,
        "custom_events": True,
        "api_access": True,
    },
    "business": {
        "sites": 25,
        "events_per_month": 10_000_000,
        "retention_days": 730,
        "custom_events": True,
        "api_access": True,
        "priority_support": True,
        "white_label": True,
    },
}


class MainlayerClient:
    """Client for interacting with the Mainlayer billing API."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = MAINLAYER_BASE_URL
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "analytics-saas-mainlayer/1.0",
        }

    async def create_subscription(
        self,
        site_id: str,
        plan: str,
        customer_email: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> dict:
        """
        Create a subscription via Mainlayer.

        Returns a dict with payment_id, status, and amount on success.
        Raises MainlayerError on failure.
        """
        if plan not in PLAN_PRICES:
            raise MainlayerError(
                f"Unknown plan '{plan}'. Valid plans: {list(PLAN_PRICES.keys())}",
                code="INVALID_PLAN",
            )

        amount = PLAN_PRICES[plan]
        payload = {
            "amount": amount,
            "currency": "USD",
            "description": f"Analytics SaaS — {plan.capitalize()} plan for site {site_id}",
            "metadata": {
                "site_id": site_id,
                "plan": plan,
                **(metadata or {}),
            },
        }
        if customer_email:
            payload["customer_email"] = customer_email

        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/payments",
                    json=payload,
                    headers=self.headers,
                )
                response.raise_for_status()
                data = response.json()
                logger.info(
                    "Mainlayer payment created",
                    extra={"site_id": site_id, "plan": plan, "payment_id": data.get("id")},
                )
                return {
                    "payment_id": data.get("id"),
                    "status": data.get("status", "pending"),
                    "amount": amount,
                    "currency": "USD",
                    "plan": plan,
                }
            except httpx.HTTPStatusError as exc:
                body = {}
                try:
                    body = exc.response.json()
                except Exception:
                    pass
                raise MainlayerError(
                    body.get("message", "Payment creation failed"),
                    code=body.get("code", "PAYMENT_FAILED"),
                    status_code=exc.response.status_code,
                ) from exc
            except httpx.RequestError as exc:
                raise MainlayerError(
                    "Could not reach Mainlayer API. Check your network connection.",
                    code="NETWORK_ERROR",
                ) from exc

    async def get_payment(self, payment_id: str) -> dict:
        """Retrieve payment details from Mainlayer."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/payments/{payment_id}",
                    headers=self.headers,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                raise MainlayerError(
                    "Payment not found",
                    code="NOT_FOUND",
                    status_code=exc.response.status_code,
                ) from exc

    async def list_subscriptions(self, site_id: str) -> list:
        """List all subscriptions for a site."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(
                    f"{self.base_url}/subscriptions",
                    params={"metadata[site_id]": site_id},
                    headers=self.headers,
                )
                response.raise_for_status()
                data = response.json()
                return data.get("data", [])
            except httpx.RequestError:
                return []

    async def cancel_subscription(self, subscription_id: str) -> dict:
        """Cancel a Mainlayer subscription."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.delete(
                f"{self.base_url}/subscriptions/{subscription_id}",
                headers=self.headers,
            )
            response.raise_for_status()
            return response.json()


class MainlayerError(Exception):
    """Raised when a Mainlayer API call fails."""

    def __init__(self, message: str, code: str = "MAINLAYER_ERROR", status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


def get_plan_features(plan: str) -> dict:
    """Return the feature set for a given plan."""
    return PLAN_FEATURES.get(plan, {})


def get_plan_price(plan: str) -> Optional[float]:
    """Return the monthly price for a given plan."""
    return PLAN_PRICES.get(plan)
