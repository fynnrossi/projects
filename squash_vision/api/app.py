"""FastAPI application — leaderboard and social endpoints.

Provides:
  - POST /register         Create a new user account
  - POST /sessions         Upload a session result
  - GET  /sessions/{id}    Session detail with per-shot breakdown
  - GET  /leaderboard      Global leaderboard (paginated, filterable)
  - GET  /users/{id}       User profile with session history
  - GET  /users/{id}/stats Progression stats over time
  - GET  /health           Health check
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field as PField
from sqlmodel import Session as DBSession, SQLModel, col, create_engine, func, select

from squash_vision.social.models import (
    LeaderboardEntry,
    Session,
    ShotRecord,
    User,
)

app = FastAPI(
    title="Squash Vision",
    description="Global leaderboard for squash straight-drive practice.",
    version="0.2.0",
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
# Request / Response Schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    username: str = PField(min_length=3, max_length=30, pattern=r"^[a-zA-Z0-9_]+$")
    display_name: str = PField(min_length=1, max_length=60)
    country_code: str = PField(default="", max_length=3)


class RegisterResponse(BaseModel):
    id: str
    username: str
    display_name: str


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


class SessionResponse(BaseModel):
    id: str
    user_id: str
    username: str
    recorded_at: str
    duration_seconds: float
    total_shots: int
    straight_drives: int
    score_total: float
    score_wall_tightness: float
    score_length_accuracy: float
    score_straightness: float
    score_consistency: float
    shots: list[dict]
    rank_at_time: int | None = None


class LeaderboardResponse(BaseModel):
    rank: int
    user_id: str
    username: str
    country_code: str
    best_session_score: float
    avg_session_score: float
    avg_wall_tightness: float
    total_sessions: int
    total_drives: int
    tier: str


class UserProfile(BaseModel):
    id: str
    username: str
    display_name: str
    country_code: str
    total_sessions: int
    best_score: float
    avg_score: float
    tier: str
    global_rank: int | None
    recent_sessions: list[dict]


class StatsResponse(BaseModel):
    """Progression stats for a user over time."""
    user_id: str
    period: str
    sessions: int
    avg_score: float
    best_score: float
    avg_wall_tightness: float
    avg_length_accuracy: float
    avg_straightness: float
    avg_consistency: float
    total_drives: int
    score_trend: list[dict]  # [{date, score}]


# ---------------------------------------------------------------------------
# Tier system
# ---------------------------------------------------------------------------

def _tier_for_score(score: float) -> str:
    """Map a best session score to a tier name."""
    if score >= 90:
        return "Diamond"
    elif score >= 80:
        return "Platinum"
    elif score >= 70:
        return "Gold"
    elif score >= 60:
        return "Silver"
    elif score >= 45:
        return "Bronze"
    else:
        return "Unranked"


def _global_rank(user_id: str, db: DBSession) -> int | None:
    """Get a user's global rank (1-indexed) by best session score."""
    entry = db.exec(
        select(LeaderboardEntry).where(LeaderboardEntry.user_id == user_id)
    ).first()
    if not entry:
        return None
    count = db.exec(
        select(func.count()).select_from(LeaderboardEntry).where(
            LeaderboardEntry.best_session_score > entry.best_session_score
        )
    ).one()
    return count + 1


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


# --- Registration ---

@app.post("/register", response_model=RegisterResponse, status_code=201)
def register(payload: RegisterRequest, db: DBSession = Depends(get_db)):
    """Create a new user account."""
    existing = db.exec(
        select(User).where(User.username == payload.username)
    ).first()
    if existing:
        raise HTTPException(409, f"Username '{payload.username}' is already taken")

    user = User(
        username=payload.username,
        display_name=payload.display_name,
        country_code=payload.country_code.upper(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return RegisterResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
    )


# --- Sessions ---

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

    # Update leaderboard entry
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
        n = entry.total_sessions
        entry.avg_wall_tightness = (
            entry.avg_wall_tightness * (n - 1) + payload.score_wall_tightness
        ) / n
        if payload.score_total > entry.best_session_score:
            entry.best_session_score = payload.score_total
            entry.best_session_id = session.id
        entry.updated_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(session)

    rank = _global_rank(payload.user_id, db)
    tier = _tier_for_score(entry.best_session_score)

    return {
        "session_id": session.id,
        "score": payload.score_total,
        "global_rank": rank,
        "tier": tier,
    }


@app.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: str, db: DBSession = Depends(get_db)):
    """Get full session detail with per-shot breakdown."""
    session = db.get(Session, session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    user = db.get(User, session.user_id)
    shots = db.exec(
        select(ShotRecord)
        .where(ShotRecord.session_id == session_id)
        .order_by(ShotRecord.shot_index)
    ).all()

    return SessionResponse(
        id=session.id,
        user_id=session.user_id,
        username=user.username if user else "unknown",
        recorded_at=session.recorded_at.isoformat(),
        duration_seconds=session.duration_seconds,
        total_shots=session.total_shots,
        straight_drives=session.straight_drives,
        score_total=round(session.score_total, 1),
        score_wall_tightness=round(session.score_wall_tightness, 1),
        score_length_accuracy=round(session.score_length_accuracy, 1),
        score_straightness=round(session.score_straightness, 1),
        score_consistency=round(session.score_consistency, 1),
        shots=[
            {
                "index": s.shot_index,
                "type": s.shot_type,
                "side": s.side,
                "wall_tightness": round(s.score_wall_tightness, 1),
                "length_accuracy": round(s.score_length_accuracy, 1),
                "straightness": round(s.score_straightness, 1),
                "total": round(s.score_total, 1),
            }
            for s in shots
        ],
    )


# --- Leaderboard ---

@app.get("/leaderboard", response_model=list[LeaderboardResponse])
def leaderboard(
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    country: str | None = None,
    period: str | None = Query(
        default=None,
        description="Filter by time period: 'week', 'month', 'all' (default: all)",
    ),
    sort_by: str = Query(
        default="best",
        description="Sort by: 'best' (best session), 'avg' (average score), 'drives' (total drives)",
    ),
    db: DBSession = Depends(get_db),
):
    """Global leaderboard ranked by score."""
    # Determine sort column
    if sort_by == "avg":
        order_col = col(LeaderboardEntry.avg_wall_tightness).desc()
    elif sort_by == "drives":
        order_col = col(LeaderboardEntry.total_drives).desc()
    else:
        order_col = col(LeaderboardEntry.best_session_score).desc()

    stmt = select(LeaderboardEntry).order_by(order_col)

    if country:
        stmt = stmt.where(LeaderboardEntry.country_code == country.upper())

    if period and period != "all":
        cutoff = datetime.now(timezone.utc)
        if period == "week":
            cutoff -= timedelta(days=7)
        elif period == "month":
            cutoff -= timedelta(days=30)
        stmt = stmt.where(LeaderboardEntry.updated_at >= cutoff)

    stmt = stmt.offset(offset).limit(limit)
    entries = db.exec(stmt).all()

    # Compute average session score per user
    results = []
    for i, e in enumerate(entries):
        avg_score_row = db.exec(
            select(func.avg(Session.score_total)).where(Session.user_id == e.user_id)
        ).one()
        avg_score = round(float(avg_score_row or 0), 1)

        results.append(
            LeaderboardResponse(
                rank=offset + i + 1,
                user_id=e.user_id,
                username=e.username,
                country_code=e.country_code,
                best_session_score=round(e.best_session_score, 1),
                avg_session_score=avg_score,
                avg_wall_tightness=round(e.avg_wall_tightness, 1),
                total_sessions=e.total_sessions,
                total_drives=e.total_drives,
                tier=_tier_for_score(e.best_session_score),
            )
        )

    return results


# --- User profile ---

@app.get("/users/{user_id}", response_model=UserProfile)
def get_user(user_id: str, db: DBSession = Depends(get_db)):
    """User profile with session history and rank."""
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

    avg_score_row = db.exec(
        select(func.avg(Session.score_total)).where(Session.user_id == user_id)
    ).one()
    avg_score = round(float(avg_score_row or 0), 1)

    best = entry.best_session_score if entry else 0.0
    rank = _global_rank(user_id, db)

    return UserProfile(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        country_code=user.country_code,
        total_sessions=entry.total_sessions if entry else 0,
        best_score=round(best, 1),
        avg_score=avg_score,
        tier=_tier_for_score(best),
        global_rank=rank,
        recent_sessions=[
            {
                "id": s.id,
                "recorded_at": s.recorded_at.isoformat(),
                "score": round(s.score_total, 1),
                "straight_drives": s.straight_drives,
                "wall_tightness": round(s.score_wall_tightness, 1),
            }
            for s in sessions
        ],
    )


# --- Progression stats ---

@app.get("/users/{user_id}/stats", response_model=StatsResponse)
def get_user_stats(
    user_id: str,
    period: str = Query(
        default="month",
        description="Time period: 'week', 'month', '3months', 'all'",
    ),
    db: DBSession = Depends(get_db),
):
    """Get progression stats for a user over a time period."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "User not found")

    cutoff = None
    now = datetime.now(timezone.utc)
    if period == "week":
        cutoff = now - timedelta(days=7)
    elif period == "month":
        cutoff = now - timedelta(days=30)
    elif period == "3months":
        cutoff = now - timedelta(days=90)

    stmt = select(Session).where(Session.user_id == user_id)
    if cutoff:
        stmt = stmt.where(Session.recorded_at >= cutoff)
    stmt = stmt.order_by(Session.recorded_at)
    sessions = db.exec(stmt).all()

    if not sessions:
        return StatsResponse(
            user_id=user_id,
            period=period,
            sessions=0,
            avg_score=0,
            best_score=0,
            avg_wall_tightness=0,
            avg_length_accuracy=0,
            avg_straightness=0,
            avg_consistency=0,
            total_drives=0,
            score_trend=[],
        )

    scores = [s.score_total for s in sessions]
    return StatsResponse(
        user_id=user_id,
        period=period,
        sessions=len(sessions),
        avg_score=round(sum(scores) / len(scores), 1),
        best_score=round(max(scores), 1),
        avg_wall_tightness=round(
            sum(s.score_wall_tightness for s in sessions) / len(sessions), 1
        ),
        avg_length_accuracy=round(
            sum(s.score_length_accuracy for s in sessions) / len(sessions), 1
        ),
        avg_straightness=round(
            sum(s.score_straightness for s in sessions) / len(sessions), 1
        ),
        avg_consistency=round(
            sum(s.score_consistency for s in sessions) / len(sessions), 1
        ),
        total_drives=sum(s.straight_drives for s in sessions),
        score_trend=[
            {
                "date": s.recorded_at.strftime("%Y-%m-%d"),
                "score": round(s.score_total, 1),
                "wall_tightness": round(s.score_wall_tightness, 1),
            }
            for s in sessions
        ],
    )
