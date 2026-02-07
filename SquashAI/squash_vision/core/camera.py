"""Camera placement profiles.

Encodes where the phone/camera is physically positioned relative to the
court.  Knowing this lets us:

1. **Seed court corner estimation** — instead of blind edge detection we
   can predict roughly where the four corners fall in the frame.
2. **Tune blob detection** — expected ball size in pixels varies with
   camera distance and angle.
3. **Adjust Canny/Hough parameters** — viewing angle affects line
   visibility.
4. **Set Kalman filter noise** — a closer camera means the ball moves
   faster in pixel-space per frame.

Pre-built presets cover common phone placements.  Users pick one (or
define their own) and it flows through the whole pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import numpy as np


# ---------------------------------------------------------------------------
# Court constants (duplicated here to avoid circular import)
# ---------------------------------------------------------------------------
_COURT_WIDTH = 6.40
_COURT_LENGTH = 9.75


class CameraSide(str, Enum):
    """Which side of the court the camera is closest to."""
    LEFT = "left"
    RIGHT = "right"
    CENTRE = "centre"


@dataclass
class CameraProfile:
    """Describes a physical camera placement.

    All distances are in metres.  Angles in degrees.

    Attributes
    ----------
    name : str
        Human-readable label (e.g. "back_wall_left").
    wall : str
        Which wall the camera is on: "back", "side_left", "side_right",
        or "above".
    side : CameraSide
        Lateral position along the wall.
    height_m : float
        Height of the camera from the floor (metres).
    distance_from_wall_m : float
        How far the camera sits from the wall surface (e.g. propped 0.3 m
        out from the back glass).
    offset_from_centre_m : float
        Lateral offset from the centre of the wall.  Positive = toward
        the right wall when facing the front wall.
    tilt_deg : float
        Downward tilt angle.  0 = horizontal, 90 = straight down.
    fov_deg : float
        Approximate field of view of the camera (most phones ~70-80°).

    Derived attributes (computed)
    ---
    expected_ball_radius_px : tuple[int, int]
        Min/max expected ball radius in pixels (for blob filtering).
    corner_seed_regions : dict
        Approximate pixel regions where each court corner should appear.
    court_detection_params : dict
        Tuned Canny/Hough parameters for this viewpoint.
    """

    name: str
    wall: str = "back"
    side: CameraSide = CameraSide.LEFT
    height_m: float = 0.30
    distance_from_wall_m: float = 0.05
    offset_from_centre_m: float = -2.50
    tilt_deg: float = 5.0
    fov_deg: float = 75.0

    # --- Derived detection tuning ---

    @property
    def expected_ball_area_range(self) -> tuple[int, int]:
        """Expected blob area range in pixels (for 1080p).

        A squash ball is ~40 mm diameter.  At different camera distances
        this maps to different pixel sizes.
        """
        # Rough distance from camera to mid-court
        if self.wall == "back":
            dist_to_mid = _COURT_LENGTH / 2 + self.distance_from_wall_m
        elif self.wall in ("side_left", "side_right"):
            dist_to_mid = _COURT_WIDTH / 2 + self.distance_from_wall_m
        else:
            dist_to_mid = max(self.height_m, 2.0)

        # At ~5m, ball ≈ 15px radius on 1080p (~700 px² area)
        # At ~10m, ball ≈ 7px radius (~150 px² area)
        # Scale inversely with distance
        ref_dist = 5.0
        ref_area_min, ref_area_max = 50, 700
        scale = ref_dist / max(dist_to_mid, 1.0)

        area_min = max(10, int(ref_area_min * scale))
        area_max = max(50, int(ref_area_max * scale * 1.5))
        return (area_min, area_max)

    @property
    def court_detection_params(self) -> dict:
        """Canny/Hough params tuned for this camera angle."""
        if self.wall == "back":
            # Back wall: lines are more foreshortened toward front wall.
            # Need lower Hough threshold for short-appearing front lines.
            if abs(self.offset_from_centre_m) > 1.5:
                # Off-centre: more perspective distortion, relax thresholds
                return {
                    "canny_low": 40,
                    "canny_high": 130,
                    "hough_threshold": 80,
                    "min_line_length": 60,
                }
            else:
                return {
                    "canny_low": 50,
                    "canny_high": 150,
                    "hough_threshold": 100,
                    "min_line_length": 80,
                }
        elif self.wall in ("side_left", "side_right"):
            # Side wall: side lines are long and clear, far wall is short.
            return {
                "canny_low": 45,
                "canny_high": 140,
                "hough_threshold": 90,
                "min_line_length": 70,
            }
        else:
            # Overhead / unknown: use defaults
            return {
                "canny_low": 50,
                "canny_high": 150,
                "hough_threshold": 120,
                "min_line_length": 100,
            }

    @property
    def kalman_process_noise(self) -> float:
        """Process noise scale for the Kalman filter.

        Closer cameras see faster apparent ball motion in pixels, so
        the Kalman filter needs higher process noise to keep up.
        """
        if self.wall == "back":
            dist = _COURT_LENGTH / 2 + self.distance_from_wall_m
        else:
            dist = _COURT_WIDTH / 2 + self.distance_from_wall_m
        # Closer = more noise needed
        return max(0.005, 0.05 / max(dist / 5.0, 0.5))

    def seed_corners(self, frame_w: int, frame_h: int) -> np.ndarray:
        """Estimate approximate court corner positions in the frame.

        Returns 4x2 array of (x, y) pixel estimates for
        [front-left, front-right, back-right, back-left].

        These aren't precise — they're seeds that narrow the search
        space for the auto-detector.
        """
        if self.wall == "back":
            return self._seed_from_back(frame_w, frame_h)
        elif self.wall == "side_left":
            return self._seed_from_side(frame_w, frame_h, left=True)
        elif self.wall == "side_right":
            return self._seed_from_side(frame_w, frame_h, left=False)
        else:
            # Default: assume vaguely centred view
            return np.array([
                [frame_w * 0.2, frame_h * 0.15],
                [frame_w * 0.8, frame_h * 0.15],
                [frame_w * 0.9, frame_h * 0.85],
                [frame_w * 0.1, frame_h * 0.85],
            ], dtype=np.float32)

    def _seed_from_back(self, w: int, h: int) -> np.ndarray:
        """Corner seeds for a camera on the back wall."""
        # Camera offset determines left/right skew
        # offset < 0 = camera toward left wall (front-left corner appears wider)
        norm_offset = self.offset_from_centre_m / (_COURT_WIDTH / 2)
        # Clamp to [-1, 1]
        norm_offset = max(-1.0, min(1.0, norm_offset))

        # Base layout for a centred back-wall camera
        # Front wall corners are near the top of frame (small due to distance)
        # Back wall corners are near the bottom (larger, closer)
        cx = w * 0.5

        # Shift centre based on lateral offset
        cx_shift = -norm_offset * w * 0.15

        # Front wall (far away = converged toward centre, higher up)
        front_spread = w * (0.25 + 0.10 * (1 - abs(norm_offset)))
        front_y = h * 0.12

        # Back wall (close = wider spread, lower)
        back_spread = w * (0.45 + 0.05 * (1 - abs(norm_offset)))
        back_y = h * 0.92

        # Lateral skew: the side closer to the camera appears wider
        skew = norm_offset * w * 0.08

        return np.array([
            [cx + cx_shift - front_spread + skew, front_y],   # front-left
            [cx + cx_shift + front_spread + skew, front_y],   # front-right
            [cx + cx_shift + back_spread, back_y],             # back-right
            [cx + cx_shift - back_spread, back_y],             # back-left
        ], dtype=np.float32)

    def _seed_from_side(self, w: int, h: int, left: bool) -> np.ndarray:
        """Corner seeds for a camera on a side wall."""
        if left:
            # Camera on left wall looking right
            # Near side wall (left) = bottom of frame, far wall (right) = top
            return np.array([
                [w * 0.1, h * 0.2],    # front-left (near, top-ish)
                [w * 0.85, h * 0.15],   # front-right (far)
                [w * 0.9, h * 0.85],    # back-right (far)
                [w * 0.15, h * 0.9],    # back-left (near)
            ], dtype=np.float32)
        else:
            return np.array([
                [w * 0.15, h * 0.15],   # front-left (far)
                [w * 0.9, h * 0.2],     # front-right (near)
                [w * 0.85, h * 0.9],    # back-right (near)
                [w * 0.1, h * 0.85],    # back-left (far)
            ], dtype=np.float32)


# ---------------------------------------------------------------------------
# Pre-built presets
# ---------------------------------------------------------------------------

PRESETS: dict[str, CameraProfile] = {
    "back_wall_left": CameraProfile(
        name="back_wall_left",
        wall="back",
        side=CameraSide.LEFT,
        height_m=0.30,
        distance_from_wall_m=0.05,
        offset_from_centre_m=-2.50,
        tilt_deg=5.0,
        fov_deg=75.0,
    ),
    "back_wall_right": CameraProfile(
        name="back_wall_right",
        wall="back",
        side=CameraSide.RIGHT,
        height_m=0.30,
        distance_from_wall_m=0.05,
        offset_from_centre_m=2.50,
        tilt_deg=5.0,
        fov_deg=75.0,
    ),
    "back_wall_centre": CameraProfile(
        name="back_wall_centre",
        wall="back",
        side=CameraSide.CENTRE,
        height_m=0.30,
        distance_from_wall_m=0.05,
        offset_from_centre_m=0.0,
        tilt_deg=5.0,
        fov_deg=75.0,
    ),
    "back_wall_centre_high": CameraProfile(
        name="back_wall_centre_high",
        wall="back",
        side=CameraSide.CENTRE,
        height_m=2.50,
        distance_from_wall_m=0.10,
        offset_from_centre_m=0.0,
        tilt_deg=15.0,
        fov_deg=75.0,
    ),
    "side_left": CameraProfile(
        name="side_left",
        wall="side_left",
        side=CameraSide.LEFT,
        height_m=2.0,
        distance_from_wall_m=0.10,
        offset_from_centre_m=0.0,
        tilt_deg=10.0,
        fov_deg=75.0,
    ),
    "side_right": CameraProfile(
        name="side_right",
        wall="side_right",
        side=CameraSide.RIGHT,
        height_m=2.0,
        distance_from_wall_m=0.10,
        offset_from_centre_m=0.0,
        tilt_deg=10.0,
        fov_deg=75.0,
    ),
}


def get_preset(name: str) -> CameraProfile:
    """Get a pre-built camera profile by name.

    Raises KeyError with available options if name is invalid.
    """
    if name not in PRESETS:
        options = ", ".join(sorted(PRESETS.keys()))
        raise KeyError(f"Unknown preset '{name}'. Available: {options}")
    return PRESETS[name]


def list_presets() -> list[str]:
    """Return sorted list of available preset names."""
    return sorted(PRESETS.keys())
