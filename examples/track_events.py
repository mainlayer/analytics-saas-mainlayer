"""Example: track analytics events via the Analytics SaaS API.

Usage:
    python examples/track_events.py

Set ANALYTICS_API_URL to point at your running instance (default: localhost:8000).
Set MAINLAYER_TOKEN to a valid payment token.
"""

import os
import time

import httpx

BASE_URL = os.environ.get("ANALYTICS_API_URL", "http://localhost:8000")
TOKEN = os.environ.get("MAINLAYER_TOKEN", "demo-token")
SITE_ID = os.environ.get("SITE_ID", "demo-site")

HEADERS = {"x-mainlayer-token": TOKEN}


def register_site() -> str:
    """Register a demo site and return its site_id."""
    resp = httpx.post(
        f"{BASE_URL}/sites",
        json={
            "domain": f"demo-{int(time.time())}.example.com",
            "name": "Demo Site",
            "owner_email": "demo@example.com",
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    print(f"Site registered: {data['site_id']} ({data['domain']})")
    return data["site_id"]


def track_pageview(site_id: str) -> None:
    resp = httpx.post(
        f"{BASE_URL}/track",
        json={
            "site_id": site_id,
            "name": "pageview",
            "url": "https://demo.example.com/blog/hello-world",
            "referrer": "https://twitter.com",
            "props": {"author": "alice"},
        },
        headers=HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    print(f"Pageview tracked: {resp.json()['id']}")


def track_custom_event(site_id: str) -> None:
    resp = httpx.post(
        f"{BASE_URL}/track",
        json={
            "site_id": site_id,
            "name": "signup",
            "url": "https://demo.example.com/signup",
            "props": {"plan": "pro", "source": "homepage_cta"},
        },
        headers=HEADERS,
        timeout=10,
    )
    resp.raise_for_status()
    print(f"Custom event tracked: {resp.json()['id']}")


def main() -> None:
    site_id = register_site()

    print("\nTracking 5 pageviews and 2 custom events...")
    pages = [
        "/",
        "/pricing",
        "/docs",
        "/blog/hello-world",
        "/contact",
    ]
    for page in pages:
        httpx.post(
            f"{BASE_URL}/track",
            json={
                "site_id": site_id,
                "name": "pageview",
                "url": f"https://demo.example.com{page}",
            },
            headers=HEADERS,
            timeout=10,
        ).raise_for_status()

    track_custom_event(site_id)
    track_pageview(site_id)

    print("\nAll events tracked successfully.")
    print(f"Run GET {BASE_URL}/stats/{site_id} with a subscription to view stats.")


if __name__ == "__main__":
    main()
