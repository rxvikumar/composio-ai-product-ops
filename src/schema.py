from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field, HttpUrl

AuthMethod = Literal["OAuth2", "API key", "Basic", "Bearer/token", "JWT", "Session/cookie", "Other", "Unknown"]
AccessMode = Literal["self-serve-free", "self-serve-trial", "self-serve-paid", "admin-approval", "partner/contact-sales", "mixed", "unknown", "gated-needs-outreach"]
BuildVerdict = Literal["toolkit-ready", "toolkit-ready-with-constraints", "gated-needs-outreach", "not-agent-ready", "unknown"]
Breadth = Literal["narrow", "moderate", "broad", "very-broad", "unknown"]

class Evidence(BaseModel):
    claim: str = Field(min_length=5)
    url: HttpUrl
    title: str = ""
    source_type: Literal["official-docs", "official-blog", "official-repo", "official-pricing", "official-mcp", "other"] = "official-docs"
    accessed_utc: str = ""

class ApiSurface(BaseModel):
    styles: list[str] = []
    breadth: Breadth = "unknown"
    notable_capabilities: list[str] = []
    webhooks_or_events: bool | None = None
    sdk_languages: list[str] = []
    existing_mcp: bool | None = None
    mcp_urls: list[HttpUrl] = []

class CredentialAccess(BaseModel):
    mode: AccessMode = "unknown"
    details: str = ""
    trial_available: bool | None = None
    paid_plan_required: bool | None = None
    admin_or_org_approval: bool | None = None
    contact_sales_or_partner: bool | None = None

class Buildability(BaseModel):
    verdict: BuildVerdict = "unknown"
    main_blocker: str = ""
    agent_actions: list[str] = []
    risk_flags: list[str] = []

class ResearchRecord(BaseModel):
    id: int
    app: str
    category: str
    website: str = ""
    what_it_does: str = Field(min_length=15)
    auth_methods: list[AuthMethod] = []
    auth_details: str = ""
    credential_access: CredentialAccess
    api_surface: ApiSurface
    buildability: Buildability
    likely_agent_use_cases: list[str] = []
    source_quality: Literal["high", "medium", "low"] = "low"
    confidence: float = Field(ge=0, le=1)
    evidence: list[Evidence] = Field(min_length=2)
    caveats: list[str] = []
    researched_at_utc: str = ""

class ResearchBatch(BaseModel):
    records: list[ResearchRecord]

class VerificationCheck(BaseModel):
    app_id: int
    app: str
    field: str
    expected: str
    observed: str
    match: bool
    evidence_url: HttpUrl | None = None
    notes: str = ""

class VerificationReport(BaseModel):
    sample_ids: list[int] = Field(default_factory=list)
    automated_checks: list[VerificationCheck] = Field(default_factory=list, alias="checks")
    first_pass_accuracy: float | None = None
    post_verification_accuracy: float | None = None
    human_checked_ids: list[int] = []
    human_notes: list[str] = []
