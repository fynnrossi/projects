"""Court detection and homography mapping.

Detects the squash court boundaries from a camera feed (typically mounted
above/behind the back wall) and builds a homography matrix that maps pixel
coordinates to real-world court coordinates in metres.

Standard squash court dimensions (metres):
    Width:  6.40
    Length: 9.75
    Service box width: 1.60
    Short line from front wall: 5.44
    Tin height: 0.43  (not used geometrically but useful context)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import cv2
import numpy as np


# ---------------------------------------------------------------------------
# Real-world court reference points (metres, origin = front-left corner)
# ---------------------------------------------------------------------------
COURT_WIDTH = 6.40
COURT_LENGTH = 9.75
SERVICE_BOX_WIDTH = 1.60
SHORT_LINE_Y = 5.44
HALF_COURT_X = COURT_WIDTH / 2

# Canonical reference points used for homography calibration.
# Order: front-left, front-right, back-right, back-left
COURT_CORNERS_REAL = np.array(
    [
        [0.0, 0.0],
        [COURT_WIDTH, 0.0],
        [COURT_WIDTH, COURT_LENGTH],
        [0.0, COURT_LENGTH],
    ],
    dtype=np.float32,
)


@dataclass
class CourtCalibration:
    """Stores homography and derived helpers for a single camera viewpoint."""

    homography: np.ndarray
    """3x3 perspective transform: pixel coords -> court coords (metres)."""

    inverse_homography: np.ndarray
    """3x3 inverse: court coords -> pixel coords (for overlay drawing)."""

    court_corners_px: np.ndarray
    """The four court corners in pixel space that were used for calibration."""

    frame_shape: tuple[int, int] = (0, 0)
    """(height, width) of the source frame."""

    def pixel_to_court(self, px: np.ndarray) -> np.ndarray:
        """Map Nx2 pixel coordinates to Nx2 court coordinates (metres)."""
        pts = np.asarray(px, dtype=np.float32).reshape(-1, 1, 2)
        transformed = cv2.perspectiveTransform(pts, self.homography)
        return transformed.reshape(-1, 2)

    def court_to_pixel(self, court: np.ndarray) -> np.ndarray:
        """Map Nx2 court coordinates (metres) to Nx2 pixel coordinates."""
        pts = np.asarray(court, dtype=np.float32).reshape(-1, 1, 2)
        transformed = cv2.perspectiveTransform(pts, self.inverse_homography)
        return transformed.reshape(-1, 2)

    def distance_from_wall(self, court_xy: np.ndarray, wall: str = "left") -> np.ndarray:
        """Return perpendicular distance (metres) from points to a wall.

        Parameters
        ----------
        court_xy : array of shape (N, 2)
            Points in court coordinate space.
        wall : str
            One of ``"left"``, ``"right"``, ``"front"``, ``"back"``.
        """
        pts = np.asarray(court_xy).reshape(-1, 2)
        if wall == "left":
            return pts[:, 0]
        if wall == "right":
            return COURT_WIDTH - pts[:, 0]
        if wall == "front":
            return pts[:, 1]
        if wall == "back":
            return COURT_LENGTH - pts[:, 1]
        raise ValueError(f"Unknown wall: {wall}")


# ---------------------------------------------------------------------------
# Automatic court corner detection
# ---------------------------------------------------------------------------

def _order_corners(pts: np.ndarray) -> np.ndarray:
    """Order four 2-D points as: top-left, top-right, bottom-right, bottom-left."""
    pts = pts.reshape(4, 2)
    s = pts.sum(axis=1)
    d = np.diff(pts, axis=1).ravel()
    ordered = np.zeros((4, 2), dtype=np.float32)
    ordered[0] = pts[np.argmin(s)]   # top-left
    ordered[2] = pts[np.argmax(s)]   # bottom-right
    ordered[1] = pts[np.argmin(d)]   # top-right
    ordered[3] = pts[np.argmax(d)]   # bottom-left
    return ordered


def detect_court_corners(
    frame: np.ndarray,
    *,
    canny_low: int = 50,
    canny_high: int = 150,
    hough_threshold: int = 120,
    min_line_length: int = 100,
) -> np.ndarray | None:
    """Attempt to auto-detect the four court corners via edge/line detection.

    This uses a classical CV pipeline:
      1. Convert to greyscale + Gaussian blur.
      2. Canny edge detection.
      3. Probabilistic Hough line transform.
      4. Cluster lines into the dominant quadrilateral.

    Returns the four corner points in pixel space (ordered) or ``None`` if
    detection fails.
    """
    grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(grey, (5, 5), 0)
    edges = cv2.Canny(blurred, canny_low, canny_high)

    lines = cv2.HoughLinesP(
        edges,
        rho=1,
        theta=np.pi / 180,
        threshold=hough_threshold,
        minLineLength=min_line_length,
        maxLineGap=15,
    )
    if lines is None or len(lines) < 4:
        return None

    # Find the largest quadrilateral contour from the edge map.
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)

    for contour in contours[:5]:
        peri = cv2.arcLength(contour, True)
        approx = cv2.approxPolyDP(contour, 0.02 * peri, True)
        if len(approx) == 4:
            return _order_corners(approx.reshape(4, 2).astype(np.float32))

    return None


def calibrate_court(
    frame: np.ndarray,
    corners_px: np.ndarray | None = None,
) -> CourtCalibration:
    """Build a ``CourtCalibration`` from a frame.

    Parameters
    ----------
    frame : np.ndarray
        A BGR image of the court.
    corners_px : np.ndarray, optional
        Four court corner pixel coords [front-left, front-right, back-right,
        back-left].  If ``None``, automatic detection is attempted.

    Raises
    ------
    RuntimeError
        If automatic detection fails and no manual corners were provided.
    """
    if corners_px is None:
        corners_px = detect_court_corners(frame)
        if corners_px is None:
            raise RuntimeError(
                "Automatic court detection failed. Provide corners_px manually."
            )

    corners_px = np.asarray(corners_px, dtype=np.float32).reshape(4, 2)
    H, status = cv2.findHomography(corners_px, COURT_CORNERS_REAL)
    H_inv, _ = cv2.findHomography(COURT_CORNERS_REAL, corners_px)

    h, w = frame.shape[:2]
    return CourtCalibration(
        homography=H,
        inverse_homography=H_inv,
        court_corners_px=corners_px,
        frame_shape=(h, w),
    )


def draw_court_overlay(frame: np.ndarray, cal: CourtCalibration) -> np.ndarray:
    """Draw court lines on the frame using the calibration.

    Draws: outer boundary, half-court line, short line, service boxes.
    """
    overlay = frame.copy()

    def _line(p1: Sequence[float], p2: Sequence[float], colour: tuple = (0, 255, 0)) -> None:
        a, b = cal.court_to_pixel(np.array([p1, p2], dtype=np.float32))
        cv2.line(overlay, tuple(a.astype(int)), tuple(b.astype(int)), colour, 2)

    # Outer walls
    _line([0, 0], [COURT_WIDTH, 0])
    _line([COURT_WIDTH, 0], [COURT_WIDTH, COURT_LENGTH])
    _line([COURT_WIDTH, COURT_LENGTH], [0, COURT_LENGTH])
    _line([0, COURT_LENGTH], [0, 0])

    # Half-court line
    _line([HALF_COURT_X, SHORT_LINE_Y], [HALF_COURT_X, COURT_LENGTH])

    # Short line
    _line([0, SHORT_LINE_Y], [COURT_WIDTH, SHORT_LINE_Y])

    # Service boxes
    _line([0, SHORT_LINE_Y], [SERVICE_BOX_WIDTH, SHORT_LINE_Y])
    _line([SERVICE_BOX_WIDTH, SHORT_LINE_Y], [SERVICE_BOX_WIDTH, SHORT_LINE_Y + SERVICE_BOX_WIDTH])
    _line([SERVICE_BOX_WIDTH, SHORT_LINE_Y + SERVICE_BOX_WIDTH], [0, SHORT_LINE_Y + SERVICE_BOX_WIDTH])

    _line([COURT_WIDTH, SHORT_LINE_Y], [COURT_WIDTH - SERVICE_BOX_WIDTH, SHORT_LINE_Y])
    _line(
        [COURT_WIDTH - SERVICE_BOX_WIDTH, SHORT_LINE_Y],
        [COURT_WIDTH - SERVICE_BOX_WIDTH, SHORT_LINE_Y + SERVICE_BOX_WIDTH],
    )
    _line(
        [COURT_WIDTH - SERVICE_BOX_WIDTH, SHORT_LINE_Y + SERVICE_BOX_WIDTH],
        [COURT_WIDTH, SHORT_LINE_Y + SERVICE_BOX_WIDTH],
    )

    return overlay
