"""Player detection and pose tracking.

Uses YOLOv8-pose to detect the player's bounding box and keypoints.
For solo practice analysis the main uses are:
  - Identifying which side of the court the player is on.
  - Detecting the moment of racket-ball contact (swing apex).
  - Filtering out the player's body from ball detection candidates.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass
class PlayerDetection:
    """Single-frame player detection result."""

    frame_idx: int
    bbox: tuple[float, float, float, float]  # x1, y1, x2, y2
    centre: tuple[float, float]
    court_xy: tuple[float, float] | None = None
    keypoints: np.ndarray | None = None  # 17x3 COCO keypoints (x, y, conf)
    confidence: float = 0.0

    @property
    def wrist_right(self) -> tuple[float, float] | None:
        """Right wrist keypoint (COCO index 10)."""
        if self.keypoints is not None and self.keypoints[10, 2] > 0.3:
            return (float(self.keypoints[10, 0]), float(self.keypoints[10, 1]))
        return None

    @property
    def wrist_left(self) -> tuple[float, float] | None:
        """Left wrist keypoint (COCO index 9)."""
        if self.keypoints is not None and self.keypoints[9, 2] > 0.3:
            return (float(self.keypoints[9, 0]), float(self.keypoints[9, 1]))
        return None


class PlayerDetector:
    """Detects a single player using YOLOv8-pose.

    For solo practice we assume a single player is visible.  If multiple
    people are detected we pick the one with the highest confidence.
    """

    def __init__(
        self,
        model_path: Path | str | None = None,
        conf_threshold: float = 0.50,
    ) -> None:
        self.conf_threshold = conf_threshold
        self._model = None
        self._model_path = model_path

    def _load_model(self):
        from ultralytics import YOLO

        path = self._model_path or "yolov8n-pose.pt"
        self._model = YOLO(str(path))

    def detect(self, frame: np.ndarray, frame_idx: int = 0) -> PlayerDetection | None:
        """Detect the player in a single frame."""
        if self._model is None:
            self._load_model()

        results = self._model(frame, verbose=False)  # type: ignore[union-attr]
        best: PlayerDetection | None = None
        best_conf = 0.0

        for result in results:
            if result.keypoints is None:
                continue
            for i, box in enumerate(result.boxes):
                conf = float(box.conf[0])
                cls = int(box.cls[0])
                # COCO class 0 = person
                if cls != 0 or conf < self.conf_threshold:
                    continue
                if conf <= best_conf:
                    continue
                x1, y1, x2, y2 = box.xyxy[0].tolist()
                kps = result.keypoints.data[i].cpu().numpy()  # (17, 3)
                best = PlayerDetection(
                    frame_idx=frame_idx,
                    bbox=(x1, y1, x2, y2),
                    centre=((x1 + x2) / 2, (y1 + y2) / 2),
                    keypoints=kps,
                    confidence=conf,
                )
                best_conf = conf

        return best


def estimate_swing_frame(
    detections: list[PlayerDetection],
    hand: str = "right",
) -> int | None:
    """Estimate the frame index where the player's racket swing peaks.

    Uses vertical velocity of the dominant wrist keypoint — the swing
    apex is approximated as the frame where wrist velocity magnitude is
    highest and direction reverses.

    Returns the frame index or ``None`` if insufficient data.
    """
    wrist_series: list[tuple[int, float, float]] = []
    for det in detections:
        wrist = det.wrist_right if hand == "right" else det.wrist_left
        if wrist is not None:
            wrist_series.append((det.frame_idx, wrist[0], wrist[1]))

    if len(wrist_series) < 3:
        return None

    # Compute velocity magnitudes
    velocities: list[tuple[int, float]] = []
    for i in range(1, len(wrist_series)):
        fi, x1, y1 = wrist_series[i]
        _, x0, y0 = wrist_series[i - 1]
        v = np.sqrt((x1 - x0) ** 2 + (y1 - y0) ** 2)
        velocities.append((fi, v))

    if not velocities:
        return None

    # Frame with max velocity ≈ swing apex
    return max(velocities, key=lambda t: t[1])[0]
