from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
import uuid


class EventPayload(BaseModel):
    site_id: str = Field(..., description="Site identifier")
    name: str = Field(..., description="Event name, e.g. 'pageview', 'click'")
    url: str = Field(..., description="Page URL where event occurred")
    referrer: Optional[str] = Field(None, description="Referrer URL")
    props: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Custom event properties")
    user_agent: Optional[str] = Field(None, description="User agent string")
    ip: Optional[str] = Field(None, description="Client IP (hashed before storage)")


class EventResponse(BaseModel):
    id: str
    site_id: str
    name: str
    url: str
    timestamp: datetime
    message: str = "Event recorded"


class SiteRegistration(BaseModel):
    domain: str = Field(..., description="Site domain, e.g. 'example.com'")
    name: str = Field(..., description="Human-readable site name")
    owner_email: str = Field(..., description="Owner contact email")


class SiteResponse(BaseModel):
    site_id: str
    domain: str
    name: str
    owner_email: str
    created_at: datetime
    message: str = "Site registered successfully"


class PageviewsResponse(BaseModel):
    site_id: str
    period: str
    data: list
    total: int


class EventsResponse(BaseModel):
    site_id: str
    period: str
    events: list
    total: int


class SummaryResponse(BaseModel):
    site_id: str
    period: str
    total_pageviews: int
    unique_visitors: int
    bounce_rate: float
    avg_session_duration: float
    top_pages: list
    top_referrers: list
    top_events: list
    pageviews_trend: list


class SubscriptionRequest(BaseModel):
    site_id: str = Field(..., description="Site to activate subscription for")
    plan: str = Field("pro", description="Subscription plan: 'pro' or 'business'")
    api_key: str = Field(..., description="Mainlayer API key for billing")


class SubscriptionResponse(BaseModel):
    site_id: str
    plan: str
    status: str
    payment_id: Optional[str] = None
    amount: Optional[float] = None
    currency: str = "USD"
    message: str


class SubscriptionStatus(BaseModel):
    site_id: str
    plan: Optional[str]
    active: bool
    valid_until: Optional[datetime]


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None
