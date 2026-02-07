"""Ball detection and trajectory tracking.

Uses a combination of:
  1. YOLOv8 object detection (for initial ball localisation).
  2. Background-subtracted blob detection as a fast fallback when YOLO
     confidence is low (squash balls are small and fast).
  3. A Kalman filter to smooth the trajectory and interpolate across
     frames where the ball is occluded.

The tracker outputs a time-series of ``BallPosition`` records that
downstream modules use for shot segmentation and scoring.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np


@dataclass
class BallPosition:
    """A single ball observation."""

    frame_idx: int
    timestamp_ms: float
    pixel_xy: tuple[float, float]
    court_xy: tuple[float, float] | None = None
    confidence: float = 0.0
    source: str = "yolo"  # "yolo" | "blob" | "kalman_predicted"


@dataclass
class Trajectory:
    """An ordered sequence of ball positions forming a continuous trajectory."""

    positions: list[BallPosition] = field(default_factory=list)

    @property
    def length(self) -> int:
        return len(self.positions)

    @property
    def duration_ms(self) -> float:
        if len(self.positions) < 2:
            return 0.0
        return self.positions[-1].timestamp_ms - self.positions[0].timestamp_ms

    def court_points(self) -> np.ndarray:
        """Return Nx2 array of court coordinates (only non-None entries)."""
        pts = [p.court_xy for p in self.positions if p.court_xy is not None]
        if not pts:
            return np.empty((0, 2), dtype=np.float32)
        return np.array(pts, dtype=np.float32)

    def pixel_points(self) -> np.ndarray:
        return np.array([p.pixel_xy for p in self.positions], dtype=np.float32)


class BallTracker:
    """Tracks the squash ball across video frames.

    Parameters
    ----------
    model_path : Path or str, optional
        Path to a YOLOv8 ``.pt`` weights file fine-tuned for squash ball
        detection.  If ``None`` a generic ``yolov8n.pt`` is used (you
        should fine-tune for best results).
    conf_threshold : float
        Minimum YOLO confidence to accept a detection.
    blob_fallback : bool
        Whether to fall back to background-subtracted blob detection when
        YOLO confidence is low.
    """

    def __init__(
        self,
        model_path: Path | str | None = None,
        conf_threshold: float = 0.35,
        blob_fallback: bool = True,
        camera_profile: "CameraProfile | None" = None,
    ) -> None:
        self.conf_threshold = conf_threshold
        self.blob_fallback = blob_fallback
        self._model = None
        self._model_path = model_path
        self._camera_profile = camera_profile

        # Kalman filter state (initialised on first detection)
        self._kalman: cv2.KalmanFilter | None = None

        # Background subtractor for blob fallback
        self._bg_sub = cv2.createBackgroundSubtractorMOG2(
            history=200, varThreshold=40, detectShadows=False
        )

        self._trajectory = Trajectory()
        self._frame_idx = 0

    # ------------------------------------------------------------------
    # Lazy YOLO loading (avoid import cost until actually needed)
    # ------------------------------------------------------------------

    def _load_model(self):
        from ultralytics import YOLO

        path = self._model_path or "yolov8n.pt"
        self._model = YOLO(str(path))

    @classmethod
    def from_trained(cls, weights_path: str | Path, **kwargs) -> "BallTracker":
        """Create a tracker using a fine-tuned squash ball model.

        Usage:
            tracker = BallTracker.from_trained("training/runs/squash_ball/weights/best.pt")
        """
        return cls(model_path=weights_path, conf_threshold=kwargs.pop("conf_threshold", 0.30), **kwargs)

    # ------------------------------------------------------------------
    # Kalman filter helpers
    # ------------------------------------------------------------------

    def _init_kalman(self, x: float, y: float) -> None:
        kf = cv2.KalmanFilter(4, 2)
        kf.measurementMatrix = np.array(
            [[1, 0, 0, 0], [0, 1, 0, 0]], dtype=np.float32
        )
        kf.transitionMatrix = np.array(
            [[1, 0, 1, 0], [0, 1, 0, 1], [0, 0, 1, 0], [0, 0, 0, 1]], dtype=np.float32
        )
        process_noise = self._camera_profile.kalman_process_noise if self._camera_profile else 1e-2
        kf.processNoiseCov = np.eye(4, dtype=np.float32) * process_noise
        kf.measurementNoiseCov = np.eye(2, dtype=np.float32) * 1e-1
        kf.statePost = np.array([x, y, 0, 0], dtype=np.float32)
        self._kalman = kf

    def _kalman_predict(self) -> tuple[float, float]:
        assert self._kalman is not None
        pred = self._kalman.predict()
        return float(pred[0]), float(pred[1])

    def _kalman_correct(self, x: float, y: float) -> tuple[float, float]:
        assert self._kalman is not None
        measurement = np.array([x, y], dtype=np.float32)
        corrected = self._kalman.correct(measurement)
        return float(corrected[0]), float(corrected[1])

    # ------------------------------------------------------------------
    # Detection methods
    # ------------------------------------------------------------------

    def _detect_yolo(self, frame: np.ndarray) -> tuple[float, float, float] | None:
        """Run YOLO and return (x, y, confidence) or None."""
        if self._model is None:
            self._load_model()

        # Determine if this is a fine-tuned single-class model or generic COCO
        num_classes = len(self._model.names)  # type: ignore[union-attr]
        is_finetuned = num_classes == 1

        results = self._model(frame, verbose=False)  # type: ignore[union-attr]
        best = None
        best_conf = 0.0
        for result in results:
            for box in result.boxes:
                conf = float(box.conf[0])
                cls = int(box.cls[0])

                # For generic COCO: only accept sports-ball (class 32)
                # For fine-tuned: accept class 0 (squash_ball)
                if not is_finetuned and cls != 32:
                    continue

                if conf > best_conf and conf >= self.conf_threshold:
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                    best = (cx, cy, conf)
                    best_conf = conf
        return best

    def _detect_blob(self, frame: np.ndarray) -> tuple[float, float, float] | None:
        """Background-subtracted blob detection fallback."""
        fg_mask = self._bg_sub.apply(frame)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))

        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        # Filter by area — squash ball is small.
        # Use camera-aware size range if available.
        if self._camera_profile:
            area_min, area_max = self._camera_profile.expected_ball_area_range
        else:
            area_min, area_max = 20, 800

        candidates = []
        for c in contours:
            area = cv2.contourArea(c)
            if area_min < area < area_max:
                M = cv2.moments(c)
                if M["m00"] > 0:
                    cx = M["m10"] / M["m00"]
                    cy = M["m01"] / M["m00"]
                    candidates.append((cx, cy, min(area / 800, 1.0)))
        if not candidates:
            return None
        # Pick the candidate closest to the Kalman prediction if available
        if self._kalman is not None:
            pred = self._kalman_predict()
            candidates.sort(key=lambda c: (c[0] - pred[0]) ** 2 + (c[1] - pred[1]) ** 2)
        return candidates[0]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process_frame(self, frame: np.ndarray, timestamp_ms: float) -> BallPosition | None:
        """Process a single video frame and return the ball position (if found)."""
        detection = self._detect_yolo(frame)
        source = "yolo"

        if detection is None and self.blob_fallback:
            detection = self._detect_blob(frame)
            source = "blob"

        if detection is not None:
            cx, cy, conf = detection
            if self._kalman is None:
                self._init_kalman(cx, cy)
            sx, sy = self._kalman_correct(cx, cy)
            pos = BallPosition(
                frame_idx=self._frame_idx,
                timestamp_ms=timestamp_ms,
                pixel_xy=(sx, sy),
                confidence=conf,
                source=source,
            )
        elif self._kalman is not None:
            # No detection — use Kalman prediction only
            px, py = self._kalman_predict()
            pos = BallPosition(
                frame_idx=self._frame_idx,
                timestamp_ms=timestamp_ms,
                pixel_xy=(px, py),
                confidence=0.0,
                source="kalman_predicted",
            )
        else:
            pos = None

        if pos is not None:
            self._trajectory.positions.append(pos)

        self._frame_idx += 1
        return pos

    def get_trajectory(self) -> Trajectory:
        return self._trajectory

    def reset(self) -> None:
        """Reset tracker state for a new session."""
        self._trajectory = Trajectory()
        self._kalman = None
        self._frame_idx = 0
        self._bg_sub = cv2.createBackgroundSubtractorMOG2(
            history=200, varThreshold=40, detectShadows=False
        )
