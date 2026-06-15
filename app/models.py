from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Issue(Base):
    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    source: Mapped[str] = mapped_column(String(32), default="web", index=True)
    user_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(String(220))
    category: Mapped[str] = mapped_column(String(40), index=True)
    district: Mapped[str] = mapped_column(String(40), index=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    address_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    photo_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    photo_evidence: Mapped[bool] = mapped_column(Boolean, default=False)
    resolution_photo_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resolution_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    risk_level: Mapped[str] = mapped_column(String(20), default="low", index=True)
    ai_confidence: Mapped[int] = mapped_column(Integer, default=70)
    ai_mode: Mapped[str] = mapped_column(String(32), default="rule_based", index=True)
    ai_explanation: Mapped[str] = mapped_column(Text)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)
    responsible_service: Mapped[str] = mapped_column(String(120), default="City Operations Center", index=True)
    assigned_to: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    sla_status: Mapped[str] = mapped_column(String(24), default="on_track", index=True)
    status: Mapped[str] = mapped_column(String(24), default="new", index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    status_history: Mapped[list["StatusHistory"]] = relationship(
        back_populates="issue",
        cascade="all, delete-orphan",
        order_by="StatusHistory.created_at.desc()",
    )


class StatusHistory(Base):
    __tablename__ = "status_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id", ondelete="CASCADE"), index=True)
    old_status: Mapped[str | None] = mapped_column(String(24), nullable=True)
    new_status: Mapped[str] = mapped_column(String(24))
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    issue: Mapped[Issue] = relationship(back_populates="status_history")


class DuplicateLink(Base):
    __tablename__ = "duplicate_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id", ondelete="CASCADE"), index=True)
    duplicate_issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id", ondelete="CASCADE"), index=True)
    similarity_score: Mapped[float] = mapped_column(Float)
    distance_meters: Mapped[float] = mapped_column(Float)
