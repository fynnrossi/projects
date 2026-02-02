"""Extract frames from squash videos for annotation.

Extracts frames using two strategies to get a diverse training set:
  1. Uniform sampling — every Nth frame for general coverage.
  2. Motion-based sampling — frames where significant motion is detected
     (more likely to contain a visible, moving ball).

Usage:
    python scripts/extract_frames.py VIDEO [VIDEO ...] \
        --output-dir training/raw_frames \
        --uniform-every 30 \
        --motion-frames 200 \
        --max-per-video 300
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


def extract_uniform(
    cap: cv2.VideoCapture, every_n: int, max_frames: int
) -> list[tuple[int, np.ndarray]]:
    """Sample every Nth frame."""
    frames = []
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    for idx in range(0, total, every_n):
        if len(frames) >= max_frames:
            break
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if ret:
            frames.append((idx, frame))
    return frames


def extract_motion(
    cap: cv2.VideoCapture, target_count: int, max_frames: int
) -> list[tuple[int, np.ndarray]]:
    """Sample frames with highest motion (likely ball movement)."""
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # First pass: compute motion scores for sampled frames
    scores: list[tuple[int, float]] = []
    prev_grey = None
    sample_step = max(1, total // 2000)  # Don't process every frame for speed

    for idx in range(0, total, sample_step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if not ret:
            break
        grey = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        grey = cv2.GaussianBlur(grey, (5, 5), 0)
        if prev_grey is not None:
            diff = cv2.absdiff(prev_grey, grey)
            score = float(np.mean(diff))
            scores.append((idx, score))
        prev_grey = grey

    # Pick frames with highest motion
    scores.sort(key=lambda x: x[1], reverse=True)
    selected_indices = [s[0] for s in scores[:target_count]]
    selected_indices.sort()

    frames = []
    for idx in selected_indices[:max_frames]:
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ret, frame = cap.read()
        if ret:
            frames.append((idx, frame))

    return frames


def main() -> None:
    p = argparse.ArgumentParser(description="Extract frames from squash videos.")
    p.add_argument("videos", nargs="+", type=Path, help="Video file(s).")
    p.add_argument("--output-dir", type=Path, default=Path("training/raw_frames"))
    p.add_argument("--uniform-every", type=int, default=30, help="Uniform sample interval.")
    p.add_argument("--motion-frames", type=int, default=200, help="Number of high-motion frames.")
    p.add_argument("--max-per-video", type=int, default=300, help="Max frames per video.")
    args = p.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    total_saved = 0

    for video_path in args.videos:
        if not video_path.exists():
            print(f"Skipping {video_path} (not found)")
            continue

        print(f"\nProcessing: {video_path}")
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            print(f"  Cannot open, skipping.")
            continue

        fps = cap.get(cv2.CAP_PROP_FPS)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        print(f"  {total} frames @ {fps:.0f} FPS")

        # Extract both types
        max_uniform = args.max_per_video // 2
        max_motion = args.max_per_video - max_uniform

        print(f"  Extracting ~{max_uniform} uniform + ~{max_motion} motion frames...")
        uniform_frames = extract_uniform(cap, args.uniform_every, max_uniform)
        motion_frames = extract_motion(cap, args.motion_frames, max_motion)
        cap.release()

        # Deduplicate by frame index
        seen = set()
        all_frames = []
        for idx, frame in uniform_frames + motion_frames:
            if idx not in seen:
                seen.add(idx)
                all_frames.append((idx, frame))
        all_frames.sort(key=lambda x: x[0])

        # Save
        stem = video_path.stem
        for idx, frame in all_frames:
            out_path = args.output_dir / f"{stem}_frame{idx:06d}.png"
            cv2.imwrite(str(out_path), frame)
            total_saved += 1

        print(f"  Saved {len(all_frames)} frames")

    print(f"\nTotal frames saved: {total_saved}")
    print(f"Output directory: {args.output_dir}")
    print(f"\nNext step: annotate these frames with scripts/annotate_ball.py")


if __name__ == "__main__":
    main()
