"""Example: fetch analytics stats and realtime data.

Usage:
    SITE_ID=abc123 python examples/get_stats.py

Requires an active subscription for the site.
Set MAINLAYER_TOKEN with a valid payment token.
"""

import os

import httpx

BASE_URL = os.environ.get("ANALYTICS_API_URL", "http://localhost:8000")
SITE_ID = os.environ.get("SITE_ID", "demo-site")
PERIOD = os.environ.get("PERIOD", "7d")

# With a real subscription the server validates the token and site.
HEADERS = {"x-mainlayer-token": os.environ.get("MAINLAYER_TOKEN", "demo-token")}


def print_section(title: str) -> None:
    print(f"\n{'=' * 50}")
    print(f"  {title}")
    print("=" * 50)


def get_stats() -> None:
    print_section(f"Dashboard stats for site={SITE_ID!r}, period={PERIOD!r}")
    resp = httpx.get(
        f"{BASE_URL}/stats/{SITE_ID}",
        params={"period": PERIOD},
        headers=HEADERS,
        timeout=10,
    )
    if resp.status_code == 402:
        print("No active subscription. POST /subscribe first.")
        return
    resp.raise_for_status()
    data = resp.json()

    print(f"Total pageviews : {data['total_pageviews']}")
    print(f"Unique visitors : {data['unique_visitors']}")
    print(f"Bounce rate     : {data['bounce_rate']:.0%}")
    print(f"Avg session     : {data['avg_session_duration']:.0f}s")

    print("\nTop pages:")
    for page in data.get("top_pages", [])[:5]:
        print(f"  {page['url']}  ({page['views']} views)")

    print("\nTop referrers:")
    for ref in data.get("top_referrers", [])[:5]:
        print(f"  {ref['referrer']}  ({ref['count']})")


def get_realtime() -> None:
    print_section("Realtime (last 5 minutes)")
    resp = httpx.get(
        f"{BASE_URL}/realtime/{SITE_ID}",
        headers=HEADERS,
        timeout=10,
    )
    if resp.status_code == 402:
        print("No active subscription. POST /subscribe first.")
        return
    resp.raise_for_status()
    data = resp.json()
    print(f"Active visitors: {data['active_visitors']} (window: {data['window_minutes']} min)")


def check_subscription() -> None:
    print_section("Subscription status")
    resp = httpx.get(f"{BASE_URL}/subscription/{SITE_ID}", timeout=10)
    resp.raise_for_status()
    data = resp.json()
    print(f"Active : {data['active']}")
    print(f"Plan   : {data.get('plan', 'none')}")
    print(f"Until  : {data.get('valid_until', 'n/a')}")


def main() -> None:
    check_subscription()
    get_stats()
    get_realtime()


if __name__ == "__main__":
    main()
