"""Database models for the social leaderboard.

Uses SQLModel (SQLAlchemy + Pydantic) for a clean ORM that doubles as
API schema validation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from pydantic import computed_field
from sqlmodel import Field, Relationship, SQLModel


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid4())


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------

class User(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    username: str = Field(index=True, unique=True, max_length=30)
    display_name: str = Field(max_length=60)
    country_code: str = Field(default="", max_length=3)
    created_at: datetime = Field(default_factory=_utcnow)

    sessions: list["Session"] = Relationship(back_populates="user")


# ---------------------------------------------------------------------------
# Session (a single practice recording)
# ---------------------------------------------------------------------------

class Session(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    user_id: str = Field(foreign_key="user.id", index=True)
    recorded_at: datetime = Field(default_factory=_utcnow)
    duration_seconds: float = 0.0
    total_shots: int = 0
    straight_drives: int = 0

    # Aggregate scores (0–100)
    score_total: float = 0.0
    score_wall_tightness: float = 0.0
    score_length_accuracy: float = 0.0
    score_straightness: float = 0.0
    score_consistency: float = 0.0

    user: Optional[User] = Relationship(back_populates="sessions")
    shot_records: list["ShotRecord"] = Relationship(back_populates="session")


# ---------------------------------------------------------------------------
# ShotRecord (per-shot detail)
# ---------------------------------------------------------------------------

class ShotRecord(SQLModel, table=True):
    id: str = Field(default_factory=_uuid, primary_key=True)
    session_id: str = Field(foreign_key="session.id", index=True)
    shot_index: int = 0
    shot_type: str = "straight_drive"
    side: str = "unknown"
    score_wall_tightness: float = 0.0
    score_length_accuracy: float = 0.0
    score_straightness: float = 0.0
    score_total: float = 0.0

    session: Optional[Session] = Relationship(back_populates="shot_records")


# ---------------------------------------------------------------------------
# Leaderboard entry (materialised view / cache for fast ranking queries)
# ---------------------------------------------------------------------------

class LeaderboardEntry(SQLModel, table=True):
    """Denormalised leaderboard row — one per user, updated after each session."""

    id: str = Field(default_factory=_uuid, primary_key=True)
    user_id: str = Field(foreign_key="user.id", unique=True, index=True)
    username: str = Field(index=True)
    country_code: str = ""
    best_session_score: float = Field(default=0.0, index=True)
    best_session_id: str = ""
    avg_wall_tightness: float = 0.0
    total_sessions: int = 0
    total_drives: int = 0
    updated_at: datetime = Field(default_factory=_utcnow)
