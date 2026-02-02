"""Scoring engine for straight drives.

Produces a per-shot score and an aggregate session score that can be
used for the global leaderboard.

Scoring dimensions
------------------
1. **Wall tightness** (0–100)
   How close the ball trajectory stays to the nearest side wall.
   Measured as the average perpendicular distance from the wall across
   all trajectory points, mapped to a 0–100 scale where 0 m = 100 and
   ≥ COURT_WIDTH/2 = 0.

2. **Length accuracy** (0–100)
   How deep the ball reaches toward the back wall.  Good straight drives
   should "die" in the back corner.  Measured as how close the deepest
   Y point is to ``COURT_LENGTH``.

3. **Consistency** (0–100)
   How similar consecutive shots are to each other in terms of wall
   tightness and length.  Low variance = high consistency.  Computed
   over a sliding window of shots.

4. **Straightness** (0–100)
   How parallel the trajectory is to the side wall.  Measured via the
   R² of a linear fit to the court X coordinates — a perfectly straight
   line gives R² = 1 (score 100).

Aggregate session score
-----------------------
Weighted combination:
    ``0.35 * tightness + 0.25 * length + 0.25 * consistency + 0.15 * straightness``

The weights emphasise tightness (the core skill) and give meaningful
credit to length and consistency.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from squash_vision.analysis.shot_classifier import Shot, ShotType
from squash_vision.core.court import COURT_LENGTH, COURT_WIDTH


# ---------------------------------------------------------------------------
# Per-shot scoring
# ---------------------------------------------------------------------------

@dataclass
class ShotScore:
    """Score breakdown for a single straight drive."""

    wall_tightness: float = 0.0
    length_accuracy: float = 0.0
    straightness: float = 0.0
    total: float = 0.0

    def as_dict(self) -> dict[str, float]:
        return {
            "wall_tightness": round(self.wall_tightness, 1),
            "length_accuracy": round(self.length_accuracy, 1),
            "straightness": round(self.straightness, 1),
            "total": round(self.total, 1),
        }


@dataclass
class SessionScore:
    """Aggregate score for an entire practice session."""

    avg_wall_tightness: float = 0.0
    avg_length_accuracy: float = 0.0
    avg_straightness: float = 0.0
    consistency: float = 0.0
    total: float = 0.0
    num_shots: int = 0
    shot_scores: list[ShotScore] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.shot_scores is None:
            self.shot_scores = []

    def as_dict(self) -> dict:
        return {
            "avg_wall_tightness": round(self.avg_wall_tightness, 1),
            "avg_length_accuracy": round(self.avg_length_accuracy, 1),
            "avg_straightness": round(self.avg_straightness, 1),
            "consistency": round(self.consistency, 1),
            "total": round(self.total, 1),
            "num_shots": self.num_shots,
        }


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def score_wall_tightness(court_pts: np.ndarray) -> float:
    """Score 0–100 based on average distance from the nearest side wall."""
    if len(court_pts) == 0:
        return 0.0
    x = court_pts[:, 0]
    # Distance to nearest side wall for each point
    dist_left = x
    dist_right = COURT_WIDTH - x
    dist_wall = np.minimum(dist_left, dist_right)
    avg_dist = float(np.mean(dist_wall))
    # Map: 0 m -> 100,  COURT_WIDTH/2 -> 0  (linear)
    max_dist = COURT_WIDTH / 2
    return _clamp(100.0 * (1.0 - avg_dist / max_dist))


def score_length_accuracy(court_pts: np.ndarray) -> float:
    """Score 0–100 based on how deep the ball reaches toward the back wall."""
    if len(court_pts) == 0:
        return 0.0
    max_y = float(np.max(court_pts[:, 1]))
    # Good length = ball reaches within ~1 m of back wall
    dist_from_back = COURT_LENGTH - max_y
    # Map: 0 m -> 100,  >= 4 m -> 0
    return _clamp(100.0 * (1.0 - dist_from_back / 4.0))


def score_straightness(court_pts: np.ndarray) -> float:
    """Score 0–100 based on how straight the trajectory is (R² of X vs Y)."""
    if len(court_pts) < 3:
        return 0.0
    x, y = court_pts[:, 0], court_pts[:, 1]
    # If there's no variance in Y, can't compute R²
    if np.std(y) < 1e-6:
        return 50.0
    # Linear fit X = a*Y + b
    coeffs = np.polyfit(y, x, 1)
    x_pred = np.polyval(coeffs, y)
    ss_res = np.sum((x - x_pred) ** 2)
    ss_tot = np.sum((x - np.mean(x)) ** 2)
    if ss_tot < 1e-6:
        return 100.0  # All points at same X = perfectly straight
    r_squared = 1.0 - ss_res / ss_tot
    return _clamp(r_squared * 100.0)


def score_shot(shot: Shot) -> ShotScore:
    """Compute the score for a single straight drive."""
    pts = shot.court_points
    wt = score_wall_tightness(pts)
    la = score_length_accuracy(pts)
    st = score_straightness(pts)
    total = 0.40 * wt + 0.35 * la + 0.25 * st
    return ShotScore(
        wall_tightness=wt,
        length_accuracy=la,
        straightness=st,
        total=total,
    )


# ---------------------------------------------------------------------------
# Session scoring
# ---------------------------------------------------------------------------

def _consistency_score(shot_scores: list[ShotScore]) -> float:
    """Score 0–100 for how consistent the shots are with each other.

    Uses the inverse of coefficient of variation of the per-shot totals.
    """
    if len(shot_scores) < 2:
        return 100.0  # Can't measure consistency with < 2 shots
    totals = np.array([s.total for s in shot_scores])
    mean = np.mean(totals)
    if mean < 1e-6:
        return 0.0
    cv = float(np.std(totals) / mean)  # coefficient of variation
    # Map: cv=0 -> 100,  cv>=1 -> 0
    return _clamp(100.0 * (1.0 - cv))


def score_session(shots: list[Shot]) -> SessionScore:
    """Compute the aggregate session score from classified shots.

    Only straight drives are scored.  Other shot types are ignored.
    """
    drives = [s for s in shots if s.shot_type == ShotType.STRAIGHT_DRIVE]

    if not drives:
        return SessionScore(num_shots=0)

    shot_scores = [score_shot(s) for s in drives]

    avg_wt = float(np.mean([s.wall_tightness for s in shot_scores]))
    avg_la = float(np.mean([s.length_accuracy for s in shot_scores]))
    avg_st = float(np.mean([s.straightness for s in shot_scores]))
    consistency = _consistency_score(shot_scores)

    total = 0.35 * avg_wt + 0.25 * avg_la + 0.25 * consistency + 0.15 * avg_st

    return SessionScore(
        avg_wall_tightness=avg_wt,
        avg_length_accuracy=avg_la,
        avg_straightness=avg_st,
        consistency=consistency,
        total=total,
        num_shots=len(drives),
        shot_scores=shot_scores,
    )
