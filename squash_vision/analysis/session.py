"""Session analyzer — orchestrates the full video analysis pipeline.

Pipeline:
  1. Open video file.
  2. Calibrate court (first frame or user-provided corners).
  3. For each frame: detect ball, detect player, map to court coords.
  4. Segment trajectory into shots.
  5. Classify shots.
  6. Score straight drives.
  7. Return a SessionResult with all data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from squash_vision.analysis.scoring import SessionScore, score_session
from squash_vision.analysis.shot_classifier import Shot, classify_shots, segment_shots
from squash_vision.core.ball_tracker import BallTracker, Trajectory
from squash_vision.core.camera import CameraProfile
from squash_vision.core.court import CourtCalibration, calibrate_court
from squash_vision.core.player import PlayerDetection, PlayerDetector


@dataclass
class SessionResult:
    """Complete output of a session analysis."""

    video_path: str
    fps: float
    total_frames: int
    calibration: CourtCalibration
    trajectory: Trajectory
    shots: list[Shot]
    score: SessionScore
    player_detections: list[PlayerDetection] = field(default_factory=list)

    @property
    def duration_seconds(self) -> float:
        return self.total_frames / self.fps if self.fps > 0 else 0.0

    def summary(self) -> dict:
        return {
            "video": self.video_path,
            "duration_s": round(self.duration_seconds, 1),
            "total_frames": self.total_frames,
            "total_shots_detected": len(self.shots),
            "straight_drives": self.score.num_shots,
            "score": self.score.as_dict(),
        }


class SessionAnalyzer:
    """End-to-end video analysis pipeline.

    Parameters
    ----------
    ball_model_path : Path, optional
        YOLOv8 weights for ball detection.
    player_model_path : Path, optional
        YOLOv8-pose weights for player detection.
    court_corners_px : np.ndarray, optional
        Manual court corner pixel coordinates.  If not provided the
        system will attempt automatic detection on the first frame.
    skip_player : bool
        Skip player detection to speed up processing (ball-only mode).
    process_every_n : int
        Process every Nth frame (1 = every frame).  Higher values speed
        up processing at the cost of trajectory resolution.
    """

    def __init__(
        self,
        ball_model_path: Path | str | None = None,
        player_model_path: Path | str | None = None,
        court_corners_px: np.ndarray | None = None,
        camera_profile: CameraProfile | None = None,
        skip_player: bool = False,
        process_every_n: int = 1,
    ) -> None:
        self._ball_tracker = BallTracker(
            model_path=ball_model_path,
            camera_profile=camera_profile,
        )
        self._player_detector = PlayerDetector(model_path=player_model_path) if not skip_player else None
        self._court_corners_px = court_corners_px
        self._camera_profile = camera_profile
        self._process_every_n = max(1, process_every_n)

    def analyze(
        self,
        video_path: str | Path,
        max_frames: int | None = None,
        on_progress: callable = None,  # type: ignore[assignment]
    ) -> SessionResult:
        """Run the full analysis pipeline on a video file.

        Parameters
        ----------
        video_path : str or Path
            Path to the video file.
        max_frames : int, optional
            Stop after this many frames (useful for testing).
        on_progress : callable, optional
            Called with (current_frame, total_frames) for progress reporting.
        """
        video_path = str(video_path)
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            raise FileNotFoundError(f"Cannot open video: {video_path}")

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if max_frames is not None:
            total_frames = min(total_frames, max_frames)

        # --- Step 1: Calibrate court from first frame ---
        ret, first_frame = cap.read()
        if not ret:
            raise RuntimeError("Cannot read first frame from video.")

        calibration = calibrate_court(
            first_frame,
            corners_px=self._court_corners_px,
            camera_profile=self._camera_profile,
        )

        # Rewind
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

        # --- Step 2: Process frames ---
        player_detections: list[PlayerDetection] = []
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret or (max_frames is not None and frame_idx >= max_frames):
                break

            if frame_idx % self._process_every_n == 0:
                timestamp_ms = (frame_idx / fps) * 1000.0

                # Ball tracking
                ball_pos = self._ball_tracker.process_frame(frame, timestamp_ms)
                if ball_pos is not None:
                    court_xy = calibration.pixel_to_court(
                        np.array([ball_pos.pixel_xy], dtype=np.float32)
                    )[0]
                    ball_pos.court_xy = (float(court_xy[0]), float(court_xy[1]))

                # Player detection
                if self._player_detector is not None:
                    player_det = self._player_detector.detect(frame, frame_idx)
                    if player_det is not None:
                        court_xy = calibration.pixel_to_court(
                            np.array([player_det.centre], dtype=np.float32)
                        )[0]
                        player_det.court_xy = (float(court_xy[0]), float(court_xy[1]))
                        player_detections.append(player_det)

            if on_progress is not None:
                on_progress(frame_idx, total_frames)

            frame_idx += 1

        cap.release()

        # --- Step 3: Segment and classify shots ---
        trajectory = self._ball_tracker.get_trajectory()
        shots = segment_shots(trajectory)
        shots = classify_shots(shots)

        # --- Step 4: Score session ---
        session_score = score_session(shots)

        return SessionResult(
            video_path=video_path,
            fps=fps,
            total_frames=frame_idx,
            calibration=calibration,
            trajectory=trajectory,
            shots=shots,
            score=session_score,
            player_detections=player_detections,
        )
