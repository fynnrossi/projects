"""Shot segmentation and classification.

Splits a continuous ball trajectory into individual *shots* and classifies
each shot by type.  The initial focus is on **straight drives** — the most
common solo practice drill.

Shot segmentation
-----------------
A new shot is detected when the ball's direction reverses along the
court Y-axis (front-back).  The ball travels toward the front wall, hits
it, then returns — that's one shot.  We detect the "turn-around" and
split accordingly.

Shot classification
-------------------
Each segmented shot is classified by analysing its trajectory geometry:

* **Straight drive** — travels roughly parallel to the side wall.
  Lateral (X) deviation across the trajectory is small relative to the
  longitudinal (Y) travel.
* **Cross-court** — significant lateral movement crossing the centre line.
* **Boast** — hits a side wall before the front wall (lateral velocity
  reverses before longitudinal velocity).
* **Drop** — short trajectory ending near the front wall with low speed.
* **Lob** — similar to a drive but with a higher, slower arc (inferred
  from longer duration for the same Y distance).

For v0.1 we focus on detecting straight drives accurately; other types
are classified as ``"other"`` until we refine them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import numpy as np

from squash_vision.core.ball_tracker import BallPosition, Trajectory
from squash_vision.core.court import COURT_WIDTH, HALF_COURT_X


class ShotType(str, Enum):
    STRAIGHT_DRIVE = "straight_drive"
    CROSS_COURT = "cross_court"
    BOAST = "boast"
    DROP = "drop"
    LOB = "lob"
    OTHER = "other"


@dataclass
class Shot:
    """A single classified shot."""

    positions: list[BallPosition]
    shot_type: ShotType = ShotType.OTHER
    side: str = "unknown"  # "forehand" / "backhand" / "unknown"
    start_frame: int = 0
    end_frame: int = 0

    @property
    def court_points(self) -> np.ndarray:
        pts = [p.court_xy for p in self.positions if p.court_xy is not None]
        if not pts:
            return np.empty((0, 2), dtype=np.float32)
        return np.array(pts, dtype=np.float32)

    @property
    def duration_ms(self) -> float:
        if len(self.positions) < 2:
            return 0.0
        return self.positions[-1].timestamp_ms - self.positions[0].timestamp_ms


# ---------------------------------------------------------------------------
# Segmentation
# ---------------------------------------------------------------------------

def segment_shots(trajectory: Trajectory, min_positions: int = 5) -> list[Shot]:
    """Split a trajectory into individual shots based on Y-direction reversals.

    A reversal is detected when the ball's smoothed Y-velocity changes
    sign (i.e. it was going toward the front wall and is now coming back,
    or vice-versa).
    """
    positions = trajectory.positions
    court_pts = trajectory.court_points()
    if len(court_pts) < min_positions:
        return []

    # Smooth Y values to avoid false reversals from noise
    y_vals = court_pts[:, 1]
    kernel_size = min(5, len(y_vals))
    if kernel_size % 2 == 0:
        kernel_size -= 1
    if kernel_size >= 3:
        y_smooth = np.convolve(y_vals, np.ones(kernel_size) / kernel_size, mode="same")
    else:
        y_smooth = y_vals

    # Compute velocity sign changes
    dy = np.diff(y_smooth)
    sign_changes = np.where(np.diff(np.sign(dy)) != 0)[0] + 1  # indices in court_pts

    # Build segments between consecutive sign changes
    boundaries = [0] + sign_changes.tolist() + [len(positions)]
    shots: list[Shot] = []

    for i in range(len(boundaries) - 1):
        start, end = boundaries[i], boundaries[i + 1]
        segment = positions[start:end]
        if len(segment) < min_positions:
            continue
        shots.append(
            Shot(
                positions=segment,
                start_frame=segment[0].frame_idx,
                end_frame=segment[-1].frame_idx,
            )
        )

    return shots


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------

def _lateral_deviation(court_pts: np.ndarray) -> float:
    """Max absolute deviation in X from the mean X of the trajectory."""
    if len(court_pts) == 0:
        return float("inf")
    x_mean = court_pts[:, 0].mean()
    return float(np.max(np.abs(court_pts[:, 0] - x_mean)))


def _crosses_centre(court_pts: np.ndarray) -> bool:
    """Does the trajectory cross the centre line?"""
    if len(court_pts) < 2:
        return False
    return bool(court_pts[:, 0].min() < HALF_COURT_X < court_pts[:, 0].max())


def classify_shot(shot: Shot, straight_drive_max_deviation: float = 0.80) -> ShotType:
    """Classify a segmented shot.

    Parameters
    ----------
    shot : Shot
        The shot to classify.
    straight_drive_max_deviation : float
        Maximum lateral (X) deviation in metres for a shot to qualify as
        a straight drive.  Default is 0.80 m — roughly one-eighth of the
        court width.  Tighter thresholds can be used for scoring but this
        is deliberately generous for *classification*.
    """
    pts = shot.court_points
    if len(pts) < 3:
        return ShotType.OTHER

    dev = _lateral_deviation(pts)
    y_travel = float(np.ptp(pts[:, 1]))  # peak-to-peak Y distance
    crosses = _crosses_centre(pts)

    # Straight drive: small lateral deviation, doesn't cross centre
    if dev <= straight_drive_max_deviation and not crosses and y_travel > 2.0:
        return ShotType.STRAIGHT_DRIVE

    # Cross-court: crosses centre with significant Y travel
    if crosses and y_travel > 2.0:
        return ShotType.CROSS_COURT

    # Drop: short Y travel, ends near front wall
    if y_travel < 2.0 and pts[-1, 1] < 3.0:
        return ShotType.DROP

    return ShotType.OTHER


def classify_shots(shots: list[Shot], **kwargs) -> list[Shot]:
    """Classify a list of shots in-place and return them."""
    for shot in shots:
        shot.shot_type = classify_shot(shot, **kwargs)
        # Determine side based on average X position
        pts = shot.court_points
        if len(pts) > 0:
            avg_x = float(pts[:, 0].mean())
            shot.side = "forehand" if avg_x > HALF_COURT_X else "backhand"
    return shots
