from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


CATEGORIES = [
    "transport",
    "roads",
    "lighting",
    "flooding",
    "snow_ice",
    "trash",
    "smell_ecology",
    "playground",
    "safety",
    "utilities",
    "other",
]

DISTRICTS = ["Esil", "Nura", "Almaty", "Saryarka", "Baikonur", "Unknown"]
STATUSES = ["new", "in_progress", "resolved", "rejected"]


class IssueCreate(BaseModel):
    user_name: str | None = None
    text: str = Field(min_length=5)
    address_text: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    category_hint: str | None = None


class StatusUpdate(BaseModel):
    status: str
    comment: str | None = None


class IssueRead(BaseModel):
    id: int
    source: str
    user_name: str | None
    text: str
    summary: str
    category: str
    district: str
    latitude: float | None
    longitude: float | None
    address_text: str | None
    photo_path: str | None
    photo_evidence: bool
    resolution_photo_path: str | None
    resolution_comment: str | None
    priority_score: int
    risk_level: str
    ai_confidence: int
    ai_mode: str
    ai_explanation: str
    tags: list[str]
    responsible_service: str
    assigned_to: str | None
    sla_due_at: datetime | None
    sla_status: str
    status: str
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DuplicateRead(BaseModel):
    issue_id: int
    duplicate_issue_id: int
    similarity_score: float
    distance_meters: float
    duplicate: IssueRead | None = None
