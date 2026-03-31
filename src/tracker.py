"""Event ingestion layer.

Validates and normalises raw event data before it is written to the
analytics store.  In production, swap the synchronous SQLite writes for
a high-throughput queue (Kafka, SQS) that feeds a ClickHouse sink.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any, Optional
from urllib.parse import urlparse

from backend.analytics_db import record_event

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ALLOWED_EVENTS = {
    "pageview",
    "click",
    "conversion",
    "form_submit",
    "outbound_link",
    "file_download",
    "404",
    "custom",
}

MAX_PROPS_KEYS = 30
MAX_PROP_VALUE_LEN = 1_000
MAX_URL_LEN = 2_048
MAX_REFERRER_LEN = 2_048


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _sanitise_url(raw: Optional[str]) -> Optional[str]:
    """Strip PII from a URL (query strings that look like email/token params)."""
    if not raw:
        return None
    if len(raw) > MAX_URL_LEN:
        raw = raw[:MAX_URL_LEN]
    try:
        parsed = urlparse(raw)
        # Return just scheme + netloc + path — drop query & fragment
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}" if parsed.scheme else raw
    except Exception:
        return raw


def _sanitise_props(props: Optional[dict[str, Any]]) -> Optional[str]:
    """Truncate oversized props and serialise to JSON."""
    if not props:
        return None
    cleaned: dict[str, Any] = {}
    for k, v in list(props.items())[:MAX_PROPS_KEYS]:
        if isinstance(v, str) and len(v) > MAX_PROP_VALUE_LEN:
            v = v[:MAX_PROP_VALUE_LEN]
        cleaned[k] = v
    return json.dumps(cleaned)


def _validate_site_id(site_id: str) -> None:
    if not site_id or not re.match(r"^[a-zA-Z0-9_-]{1,64}$", site_id):
        raise ValueError(f"Invalid site_id: {site_id!r}")


def _validate_event_name(name: str) -> str:
    name = name.strip().lower()
    if not name:
        raise ValueError("Event name must not be empty")
    if len(name) > 100:
        raise ValueError("Event name exceeds 100 characters")
    return name


# ---------------------------------------------------------------------------
# Public ingest function
# ---------------------------------------------------------------------------


def ingest_event(
    *,
    site_id: str,
    name: str,
    url: str,
    referrer: Optional[str] = None,
    ip: Optional[str] = None,
    props: Optional[dict[str, Any]] = None,
) -> str:
    """Validate, sanitise, and persist a single analytics event.

    Returns the generated event UUID on success.
    Raises ``ValueError`` for invalid inputs.
    """
    _validate_site_id(site_id)
    name = _validate_event_name(name)
    url = _sanitise_url(url) or ""
    referrer = _sanitise_url(referrer)
    props_json = _sanitise_props(props)

    event_id = str(uuid.uuid4())

    record_event(
        event_id=event_id,
        site_id=site_id,
        name=name,
        url=url,
        referrer=referrer,
        ip=ip,
        props=props_json,
    )

    logger.debug("Ingested event id=%s site=%s name=%s", event_id, site_id, name)
    return event_id


# ---------------------------------------------------------------------------
# Batch ingest
# ---------------------------------------------------------------------------


def ingest_batch(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Ingest a list of events, collecting per-item errors.

    Returns a summary dict with ``accepted`` and ``rejected`` counts,
    plus an ``errors`` list for failed items.
    """
    accepted = 0
    rejected = 0
    errors: list[dict[str, Any]] = []

    for i, ev in enumerate(events):
        try:
            ingest_event(
                site_id=ev.get("site_id", ""),
                name=ev.get("name", ""),
                url=ev.get("url", ""),
                referrer=ev.get("referrer"),
                ip=ev.get("ip"),
                props=ev.get("props"),
            )
            accepted += 1
        except (ValueError, Exception) as exc:
            rejected += 1
            errors.append({"index": i, "error": str(exc)})

    return {"accepted": accepted, "rejected": rejected, "errors": errors}
