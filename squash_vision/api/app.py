"""FastAPI application — leaderboard and social endpoints.

Provides:
  - POST /sessions      Upload a session result
  - GET  /leaderboard   Global leaderboard (paginated)
  - GET  /users/{id}    User profile with session history
  - GET  /health        Health check
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session as DBSession, SQLModel, col, create_engine, select

from squash_vision.social.models import (
    LeaderboardEntry,
    Session,
    ShotRecord,
    User,
)

app = FastAPI(
    title="Squash Vision",
    description="Global leaderboard for squash straight-drive practice.",
    version="0.1.0",
)

DATABASE_URL = "sqlite:///squash_vision.db"
engine = create_engine(DATABASE_URL, echo=False)


@app.on_event("startup")
def on_startup():
    SQLModel.metadata.create_all(engine)


def get_db():
    with DBSession(engine) as session:
        yield session


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class SessionUpload(BaseModel):
    user_id: str
    duration_seconds: float
    total_shots: int
    straight_drives: int
    score_total: float
    score_wall_tightness: float
    score_length_accuracy: float
    score_straightness: float
    score_consistency: float
    shots: list[dict] = []


class LeaderboardResponse(BaseModel):
    rank: int
    username: str
    country_code: str
    best_session_score: float
    avg_wall_tightness: float
    total_sessions: int
    total_drives: int


class UserProfile(BaseModel):
    id: str
    username: str
    display_name: str
    country_code: str
    total_sessions: int
    best_score: float
    recent_sessions: list[dict]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/sessions", status_code=201)
def create_session(payload: SessionUpload, db: DBSession = Depends(get_db)):
    """Upload a completed session's scores."""
    user = db.get(User, payload.user_id)
    if not user:
        raise HTTPException(404, "User not found")

    session = Session(
        user_id=payload.user_id,
        duration_seconds=payload.duration_seconds,
        total_shots=payload.total_shots,
        straight_drives=payload.straight_drives,
        score_total=payload.score_total,
        score_wall_tightness=payload.score_wall_tightness,
        score_length_accuracy=payload.score_length_accuracy,
        score_straightness=payload.score_straightness,
        score_consistency=payload.score_consistency,
    )
    db.add(session)

    for i, s in enumerate(payload.shots):
        record = ShotRecord(
            session_id=session.id,
            shot_index=i,
            shot_type=s.get("shot_type", "straight_drive"),
            side=s.get("side", "unknown"),
            score_wall_tightness=s.get("wall_tightness", 0),
            score_length_accuracy=s.get("length_accuracy", 0),
            score_straightness=s.get("straightness", 0),
            score_total=s.get("total", 0),
        )
        db.add(record)

    # Update leaderboard
    entry = db.exec(
        select(LeaderboardEntry).where(LeaderboardEntry.user_id == payload.user_id)
    ).first()

    if entry is None:
        entry = LeaderboardEntry(
            user_id=payload.user_id,
            username=user.username,
            country_code=user.country_code,
            best_session_score=payload.score_total,
            best_session_id=session.id,
            avg_wall_tightness=payload.score_wall_tightness,
            total_sessions=1,
            total_drives=payload.straight_drives,
        )
        db.add(entry)
    else:
        entry.total_sessions += 1
        entry.total_drives += payload.straight_drives
        # Running average for wall tightness
        n = entry.total_sessions
        entry.avg_wall_tightness = (
            entry.avg_wall_tightness * (n - 1) + payload.score_wall_tightness
        ) / n
        if payload.score_total > entry.best_session_score:
            entry.best_session_score = payload.score_total
            entry.best_session_id = session.id
        entry.updated_at = datetime.now(timezone.utc)

    db.commit()
    return {"session_id": session.id, "score": payload.score_total}


@app.get("/leaderboard", response_model=list[LeaderboardResponse])
def leaderboard(
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    country: str | None = None,
    db: DBSession = Depends(get_db),
):
    """Global leaderboard ranked by best session score."""
    stmt = select(LeaderboardEntry).order_by(col(LeaderboardEntry.best_session_score).desc())
    if country:
        stmt = stmt.where(LeaderboardEntry.country_code == country.upper())
    stmt = stmt.offset(offset).limit(limit)
    entries = db.exec(stmt).all()

    return [
        LeaderboardResponse(
            rank=offset + i + 1,
            username=e.username,
            country_code=e.country_code,
            best_session_score=round(e.best_session_score, 1),
            avg_wall_tightness=round(e.avg_wall_tightness, 1),
            total_sessions=e.total_sessions,
            total_drives=e.total_drives,
        )
        for i, e in enumerate(entries)
    ]


@app.get("/users/{user_id}", response_model=UserProfile)
def get_user(user_id: str, db: DBSession = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")

    sessions = db.exec(
        select(Session)
        .where(Session.user_id == user_id)
        .order_by(col(Session.recorded_at).desc())
        .limit(20)
    ).all()

    entry = db.exec(
        select(LeaderboardEntry).where(LeaderboardEntry.user_id == user_id)
    ).first()

    return UserProfile(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        country_code=user.country_code,
        total_sessions=entry.total_sessions if entry else 0,
        best_score=entry.best_session_score if entry else 0.0,
        recent_sessions=[
            {
                "id": s.id,
                "recorded_at": s.recorded_at.isoformat(),
                "score": s.score_total,
                "straight_drives": s.straight_drives,
            }
            for s in sessions
        ],
    )
