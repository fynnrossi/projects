"""Debug / evaluation script — run the pipeline on a video and save annotated output.

Produces:
  1. An annotated video with court overlay, ball trail, and player bbox drawn.
  2. A folder of keyframe snapshots (every Nth frame) as PNGs.
  3. A JSON report with all detections and scores.

Usage:
    python scripts/test_on_video.py VIDEO_PATH [--output-dir results] [--every-n 2] [--max-frames 500]

This is the fastest way to see what the model is actually doing on your footage.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import deque
from pathlib import Path

import cv2
import numpy as np


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Test squash vision on a video.")
    p.add_argument("video", type=Path, help="Path to input video file.")
    p.add_argument("--output-dir", type=Path, default=Path("results"), help="Output directory.")
    p.add_argument("--every-n", type=int, default=1, help="Process every Nth frame.")
    p.add_argument("--max-frames", type=int, default=None, help="Stop after N frames.")
    p.add_argument(
        "--corners",
        type=str,
        default=None,
        help='Manual court corners as JSON: "[[x1,y1],[x2,y2],[x3,y3],[x4,y4]]"',
    )
    p.add_argument("--no-yolo", action="store_true", help="Skip YOLO, use blob detection only.")
    p.add_argument("--ball-model", type=Path, default=None, help="Path to fine-tuned ball detection weights (.pt).")
    p.add_argument(
        "--camera-preset",
        type=str,
        default=None,
        help="Camera placement preset: back_wall_left, back_wall_right, "
             "back_wall_centre, back_wall_centre_high, side_left, side_right.",
    )
    p.add_argument("--save-every", type=int, default=60, help="Save a snapshot every N frames.")
    return p.parse_args()


def draw_ball_trail(
    frame: np.ndarray, trail: deque, colour: tuple = (0, 255, 255)
) -> np.ndarray:
    """Draw the recent ball positions as a fading trail."""
    for i in range(1, len(trail)):
        if trail[i] is None or trail[i - 1] is None:
            continue
        alpha = i / len(trail)
        thickness = max(1, int(3 * alpha))
        c = tuple(int(v * alpha) for v in colour)
        pt1 = tuple(int(v) for v in trail[i - 1])
        pt2 = tuple(int(v) for v in trail[i])
        cv2.line(frame, pt1, pt2, c, thickness)
    if trail and trail[-1] is not None:
        pt = tuple(int(v) for v in trail[-1])
        cv2.circle(frame, pt, 6, (0, 0, 255), -1)
        cv2.circle(frame, pt, 8, (255, 255, 255), 1)
    return frame


def draw_player_box(
    frame: np.ndarray, bbox: tuple, keypoints: np.ndarray | None = None
) -> np.ndarray:
    x1, y1, x2, y2 = [int(v) for v in bbox]
    cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
    cv2.putText(frame, "Player", (x1, y1 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)

    if keypoints is not None:
        for kp in keypoints:
            x, y, conf = kp
            if conf > 0.3:
                cv2.circle(frame, (int(x), int(y)), 3, (0, 255, 0), -1)
    return frame


def draw_info_overlay(
    frame: np.ndarray,
    frame_idx: int,
    ball_source: str | None,
    ball_conf: float,
    court_xy: tuple | None,
    shot_count: int,
) -> np.ndarray:
    """Draw a status bar at the top of the frame."""
    h, w = frame.shape[:2]
    cv2.rectangle(frame, (0, 0), (w, 40), (0, 0, 0), -1)

    parts = [f"Frame: {frame_idx}"]
    if ball_source:
        parts.append(f"Ball: {ball_source} ({ball_conf:.2f})")
    else:
        parts.append("Ball: not detected")
    if court_xy:
        parts.append(f"Court: ({court_xy[0]:.2f}, {court_xy[1]:.2f})m")
    parts.append(f"Shots: {shot_count}")

    text = "  |  ".join(parts)
    cv2.putText(frame, text, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    return frame


def main() -> None:
    args = parse_args()

    if not args.video.exists():
        print(f"Error: video not found: {args.video}")
        sys.exit(1)

    # Import here so missing deps give a clear error
    try:
        from squash_vision.core.court import calibrate_court, draw_court_overlay
        from squash_vision.core.ball_tracker import BallTracker
        from squash_vision.core.camera import get_preset, list_presets
        from squash_vision.core.player import PlayerDetector
        from squash_vision.analysis.shot_classifier import segment_shots, classify_shots
        from squash_vision.analysis.scoring import score_session
    except ImportError as e:
        print(f"Import error: {e}")
        print("Run: pip install -e .  (from the project root)")
        sys.exit(1)

    # Resolve camera profile
    camera_profile = None
    if args.camera_preset:
        try:
            camera_profile = get_preset(args.camera_preset)
            print(f"Camera preset: {args.camera_preset}")
        except KeyError:
            print(f"Unknown preset '{args.camera_preset}'. Available: {', '.join(list_presets())}")
            sys.exit(1)

    # Setup output dirs
    out_dir = args.output_dir / args.video.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    snapshots_dir = out_dir / "snapshots"
    snapshots_dir.mkdir(exist_ok=True)

    # Open video
    cap = cv2.VideoCapture(str(args.video))
    if not cap.isOpened():
        print(f"Error: cannot open video: {args.video}")
        sys.exit(1)

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w_frame = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h_frame = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    max_frames = args.max_frames or total

    print(f"Video: {args.video}")
    print(f"Resolution: {w_frame}x{h_frame} @ {fps:.1f} FPS, {total} frames")
    print(f"Processing up to {max_frames} frames (every {args.every_n})")
    print(f"Output: {out_dir}/")
    print()

    # --- Calibrate court from first frame ---
    ret, first_frame = cap.read()
    if not ret:
        print("Error: cannot read first frame.")
        sys.exit(1)

    corners_px = None
    if args.corners:
        corners_px = np.array(json.loads(args.corners), dtype=np.float32)

    try:
        calibration = calibrate_court(
            first_frame, corners_px=corners_px, camera_profile=camera_profile,
        )
        print("Court calibration: OK")
        court_ok = True
    except RuntimeError as e:
        print(f"Court calibration: FAILED ({e})")
        print("  -> Continuing without court mapping. Provide --corners or --camera-preset.")
        print("  -> Tip: open the first frame, note the pixel coords of the 4 court corners.")
        calibration = None
        court_ok = False

    # Save first frame with court overlay
    if court_ok:
        overlay = draw_court_overlay(first_frame, calibration)
        cv2.imwrite(str(out_dir / "court_calibration.png"), overlay)
        print(f"  -> Saved court overlay to {out_dir}/court_calibration.png")

    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    # --- Init trackers ---
    ball_tracker = BallTracker(
        model_path=args.ball_model,
        conf_threshold=0.25,
        blob_fallback=True,
        camera_profile=camera_profile,
    )
    if args.no_yolo:
        # Force blob-only by setting a very high YOLO threshold
        ball_tracker.conf_threshold = 0.99

    player_detector = PlayerDetector(conf_threshold=0.40)

    # --- Output video writer ---
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out_video_path = out_dir / "annotated.mp4"
    writer = cv2.VideoWriter(str(out_video_path), fourcc, fps, (w_frame, h_frame))

    # --- Process frames ---
    ball_trail: deque = deque(maxlen=30)
    frame_idx = 0
    detection_log: list[dict] = []

    while True:
        ret, frame = cap.read()
        if not ret or frame_idx >= max_frames:
            break

        annotated = frame.copy()
        ball_source = None
        ball_conf = 0.0
        court_xy = None

        if frame_idx % args.every_n == 0:
            timestamp_ms = (frame_idx / fps) * 1000.0

            # Ball detection
            ball_pos = ball_tracker.process_frame(frame, timestamp_ms)
            if ball_pos is not None:
                ball_trail.append(ball_pos.pixel_xy)
                ball_source = ball_pos.source
                ball_conf = ball_pos.confidence
                if calibration:
                    cxy = calibration.pixel_to_court(
                        np.array([ball_pos.pixel_xy], dtype=np.float32)
                    )[0]
                    ball_pos.court_xy = (float(cxy[0]), float(cxy[1]))
                    court_xy = ball_pos.court_xy
            else:
                ball_trail.append(None)

            # Player detection
            player_det = player_detector.detect(frame, frame_idx)
            if player_det is not None:
                annotated = draw_player_box(annotated, player_det.bbox, player_det.keypoints)

            # Log
            detection_log.append({
                "frame": frame_idx,
                "ball_detected": ball_pos is not None,
                "ball_source": ball_source,
                "ball_conf": ball_conf,
                "ball_px": list(ball_pos.pixel_xy) if ball_pos else None,
                "ball_court": list(court_xy) if court_xy else None,
                "player_detected": player_det is not None,
            })
        else:
            ball_trail.append(None)

        # Draw annotations
        if court_ok:
            annotated = draw_court_overlay(annotated, calibration)
        annotated = draw_ball_trail(annotated, ball_trail)

        shot_count = len(segment_shots(ball_tracker.get_trajectory()))
        annotated = draw_info_overlay(
            annotated, frame_idx, ball_source, ball_conf, court_xy, shot_count
        )

        writer.write(annotated)

        # Save snapshots
        if frame_idx % args.save_every == 0:
            cv2.imwrite(str(snapshots_dir / f"frame_{frame_idx:06d}.png"), annotated)

        # Progress
        if frame_idx % 100 == 0:
            pct = (frame_idx / max_frames) * 100
            det_rate = sum(1 for d in detection_log if d["ball_detected"]) / max(len(detection_log), 1)
            print(f"  [{pct:5.1f}%] frame {frame_idx}/{max_frames}  ball detection rate: {det_rate:.1%}")

        frame_idx += 1

    cap.release()
    writer.release()

    print(f"\nProcessed {frame_idx} frames.")
    print(f"Annotated video: {out_video_path}")

    # --- Shot analysis ---
    trajectory = ball_tracker.get_trajectory()
    shots = segment_shots(trajectory)
    shots = classify_shots(shots)
    session_score = score_session(shots)

    # --- Detection stats ---
    total_processed = len(detection_log)
    ball_detected = sum(1 for d in detection_log if d["ball_detected"])
    yolo_detections = sum(1 for d in detection_log if d["ball_source"] == "yolo")
    blob_detections = sum(1 for d in detection_log if d["ball_source"] == "blob")
    kalman_only = sum(1 for d in detection_log if d["ball_source"] == "kalman_predicted")
    player_detected = sum(1 for d in detection_log if d["player_detected"])

    stats = {
        "video": str(args.video),
        "total_frames": frame_idx,
        "frames_processed": total_processed,
        "detection_stats": {
            "ball_detected": ball_detected,
            "ball_detection_rate": round(ball_detected / max(total_processed, 1), 3),
            "yolo_detections": yolo_detections,
            "blob_detections": blob_detections,
            "kalman_predicted": kalman_only,
            "player_detected": player_detected,
            "player_detection_rate": round(player_detected / max(total_processed, 1), 3),
        },
        "shots": {
            "total_segmented": len(shots),
            "straight_drives": session_score.num_shots,
            "types": {},
        },
        "score": session_score.as_dict(),
    }

    # Shot type breakdown
    from squash_vision.analysis.shot_classifier import ShotType
    for st in ShotType:
        count = sum(1 for s in shots if s.shot_type == st)
        if count > 0:
            stats["shots"]["types"][st.value] = count

    report_path = out_dir / "report.json"
    with open(report_path, "w") as f:
        json.dump(stats, f, indent=2)

    # Print summary
    print("\n" + "=" * 50)
    print("DETECTION STATS")
    print("=" * 50)
    print(f"  Ball detection rate:   {ball_detected}/{total_processed} ({ball_detected/max(total_processed,1):.1%})")
    print(f"    - YOLO detections:   {yolo_detections}")
    print(f"    - Blob fallback:     {blob_detections}")
    print(f"    - Kalman predicted:  {kalman_only}")
    print(f"  Player detection rate: {player_detected}/{total_processed} ({player_detected/max(total_processed,1):.1%})")

    print(f"\nSHOTS")
    print(f"  Total segmented: {len(shots)}")
    for st, count in stats["shots"]["types"].items():
        print(f"    {st}: {count}")

    if session_score.num_shots > 0:
        print(f"\nSCORE (straight drives)")
        print(f"  Wall tightness: {session_score.avg_wall_tightness:.1f}/100")
        print(f"  Length accuracy: {session_score.avg_length_accuracy:.1f}/100")
        print(f"  Straightness:   {session_score.avg_straightness:.1f}/100")
        print(f"  Consistency:    {session_score.consistency:.1f}/100")
        print(f"  TOTAL:          {session_score.total:.1f}/100")
    else:
        print("\n  No straight drives detected.")

    print(f"\nFull report: {report_path}")
    print(f"Snapshots:   {snapshots_dir}/")
    print(f"Video:       {out_video_path}")


if __name__ == "__main__":
    main()
