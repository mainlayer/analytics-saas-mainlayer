"""Tests for the analytics stats API."""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# Ensure the test DB is isolated in a temp location
os.environ.setdefault("DB_PATH", "/tmp/analytics_test.db")

from src.main import app  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db(tmp_path):
    """Each test gets a fresh SQLite database."""
    db_file = tmp_path / "analytics_test.db"
    with patch.dict(os.environ, {"DB_PATH": str(db_file)}):
        from backend import analytics_db
        analytics_db.DB_PATH = str(db_file)
        analytics_db.init_db()
        yield


@pytest.fixture()
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def site_id(client):
    """Register a site and return its ID."""
    resp = client.post(
        "/sites",
        json={
            "domain": f"test-{uuid.uuid4().hex[:6]}.example.com",
            "name": "Test Site",
            "owner_email": "test@example.com",
        },
    )
    assert resp.status_code == 201
    return resp.json()["site_id"]


@pytest.fixture()
def subscribed_site(site_id):
    """Activate a subscription for the site directly in the DB."""
    from backend.analytics_db import upsert_subscription
    upsert_subscription(site_id=site_id, plan="pro", payment_id="pay_test_001")
    return site_id


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# Site registration
# ---------------------------------------------------------------------------


def test_register_site(client):
    resp = client.post(
        "/sites",
        json={
            "domain": "example.com",
            "name": "Example",
            "owner_email": "admin@example.com",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "site_id" in body
    assert body["domain"] == "example.com"


def test_register_duplicate_domain(client):
    payload = {
        "domain": "dup-test.example.com",
        "name": "Dup",
        "owner_email": "dup@example.com",
    }
    client.post("/sites", json=payload).raise_for_status()
    resp = client.post("/sites", json=payload)
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Event tracking
# ---------------------------------------------------------------------------


def test_track_event_requires_token(client, site_id):
    resp = client.post(
        "/track",
        json={
            "site_id": site_id,
            "name": "pageview",
            "url": "https://example.com/",
        },
    )
    assert resp.status_code == 402


def test_track_event_with_token(client, site_id):
    resp = client.post(
        "/track",
        json={
            "site_id": site_id,
            "name": "pageview",
            "url": "https://example.com/",
        },
        headers={"x-mainlayer-token": "tok_demo"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["site_id"] == site_id
    assert body["name"] == "pageview"


# ---------------------------------------------------------------------------
# Stats (subscription required)
# ---------------------------------------------------------------------------


def test_stats_without_subscription_returns_402(client, site_id):
    resp = client.get(f"/stats/{site_id}")
    assert resp.status_code == 402


def test_stats_with_subscription(client, subscribed_site):
    # Track a pageview first
    client.post(
        "/track",
        json={
            "site_id": subscribed_site,
            "name": "pageview",
            "url": "https://example.com/",
        },
        headers={"x-mainlayer-token": "tok_demo"},
    )

    resp = client.get(f"/stats/{subscribed_site}", params={"period": "7d"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["site_id"] == subscribed_site
    assert "total_pageviews" in body
    assert body["total_pageviews"] >= 1


def test_realtime_without_subscription_returns_402(client, site_id):
    resp = client.get(f"/realtime/{site_id}")
    assert resp.status_code == 402


def test_realtime_with_subscription(client, subscribed_site):
    resp = client.get(f"/realtime/{subscribed_site}")
    assert resp.status_code == 200
    body = resp.json()
    assert "active_visitors" in body
    assert body["window_minutes"] == 5


# ---------------------------------------------------------------------------
# Subscription status endpoint
# ---------------------------------------------------------------------------


def test_subscription_status_inactive(client, site_id):
    resp = client.get(f"/subscription/{site_id}")
    assert resp.status_code == 200
    assert resp.json()["active"] is False


def test_subscription_status_active(client, subscribed_site):
    resp = client.get(f"/subscription/{subscribed_site}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["active"] is True
    assert body["plan"] == "pro"


# ---------------------------------------------------------------------------
# Subscribe endpoint (mock Mainlayer)
# ---------------------------------------------------------------------------


def test_subscribe_mocked(client, site_id):
    mock_result = {
        "payment_id": "pay_mock_001",
        "status": "pending",
        "amount": 29.0,
        "currency": "USD",
        "plan": "pro",
    }
    with patch("src.main.MainlayerClient") as MockClient:
        instance = MagicMock()
        instance.create_subscription = MagicMock(return_value=mock_result)
        # make it awaitable
        import asyncio
        async def _coro(*a, **kw):
            return mock_result
        instance.create_subscription.side_effect = _coro
        MockClient.return_value = instance

        resp = client.post(
            "/subscribe",
            json={"site_id": site_id, "plan": "pro", "api_key": "sk_test"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["plan"] == "pro"
    assert body["status"] == "active"
