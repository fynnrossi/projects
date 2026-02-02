"""Fine-tune YOLOv8 for squash ball detection.

Trains a YOLOv8n (nano) model on the annotated squash ball dataset.
Uses aggressive augmentation tuned for the specific challenges of
squash ball detection:
  - Small object (ball is ~10-20px across at 1080p)
  - Fast motion (motion blur)
  - Similar colour to court floor (dark ball on dark floor)
  - Partial occlusions (player body, racket)

Usage:
    python scripts/train_ball_detector.py training/dataset/dataset.yaml

    # With custom parameters
    python scripts/train_ball_detector.py training/dataset/dataset.yaml \
        --epochs 150 \
        --batch 16 \
        --imgsz 640 \
        --base-model yolov8n.pt

    # Resume interrupted training
    python scripts/train_ball_detector.py training/dataset/dataset.yaml --resume
"""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    p = argparse.ArgumentParser(description="Train YOLOv8 squash ball detector.")
    p.add_argument("dataset", type=Path, help="Path to dataset.yaml")
    p.add_argument("--base-model", type=str, default="yolov8n.pt", help="Base YOLO model.")
    p.add_argument("--epochs", type=int, default=120, help="Training epochs.")
    p.add_argument("--batch", type=int, default=16, help="Batch size.")
    p.add_argument("--imgsz", type=int, default=640, help="Input image size.")
    p.add_argument("--device", type=str, default="", help="Device (cuda:0, cpu, etc).")
    p.add_argument("--resume", action="store_true", help="Resume from last checkpoint.")
    p.add_argument("--project", type=str, default="training/runs", help="Output directory.")
    p.add_argument("--name", type=str, default="squash_ball", help="Run name.")
    args = p.parse_args()

    from ultralytics import YOLO

    if args.resume:
        # Find the last checkpoint
        last = Path(args.project) / args.name / "weights" / "last.pt"
        if not last.exists():
            print(f"No checkpoint found at {last}, starting fresh.")
            model = YOLO(args.base_model)
        else:
            print(f"Resuming from {last}")
            model = YOLO(str(last))
    else:
        model = YOLO(args.base_model)

    print(f"\nTraining configuration:")
    print(f"  Dataset:    {args.dataset}")
    print(f"  Base model: {args.base_model}")
    print(f"  Epochs:     {args.epochs}")
    print(f"  Batch size: {args.batch}")
    print(f"  Image size: {args.imgsz}")
    print(f"  Output:     {args.project}/{args.name}")
    print()

    results = model.train(
        data=str(args.dataset),
        epochs=args.epochs,
        batch=args.batch,
        imgsz=args.imgsz,
        device=args.device or None,
        project=args.project,
        name=args.name,
        exist_ok=True,

        # --- Augmentation tuned for small ball detection ---

        # Mosaic: combines 4 images — helps the model see the ball in
        # different court positions and scales.
        mosaic=1.0,

        # Mixup: blends two images — mild regularisation.
        mixup=0.1,

        # Scale: random resize ±50% — critical because the ball size
        # varies significantly with camera distance and angle.
        scale=0.5,

        # Flip: horizontal flip is valid (left/right side of court).
        fliplr=0.5,
        flipud=0.0,  # No vertical flip (not physically meaningful)

        # HSV augmentation: helps with varying lighting conditions
        # and the dark ball on similarly-dark court surfaces.
        hsv_h=0.015,
        hsv_s=0.5,
        hsv_v=0.4,

        # Translate: shift image ±20% — ball can be anywhere on court.
        translate=0.2,

        # Perspective: mild perspective warp to simulate different
        # camera angles.
        perspective=0.0005,

        # --- Training hyperparameters ---

        # Optimiser
        optimizer="AdamW",
        lr0=0.002,
        lrf=0.01,  # Final LR = lr0 * lrf
        weight_decay=0.0005,
        warmup_epochs=5,

        # Loss weights — boost box loss for small objects
        box=10.0,   # Higher box loss weight (default 7.5)
        cls=0.5,    # Lower cls weight (only 1 class)

        # Early stopping
        patience=20,

        # Workers
        workers=4,

        # Verbose
        verbose=True,
    )

    # Print results
    best_weights = Path(args.project) / args.name / "weights" / "best.pt"
    print(f"\n{'='*50}")
    print(f"Training complete!")
    print(f"Best weights: {best_weights}")
    print(f"\nTo use in the tracker:")
    print(f"  squash-vision analyze video.mp4  (update ball_model_path)")
    print(f"\nOr test directly:")
    print(f"  python scripts/test_on_video.py video.mp4")
    print(f"  (after updating BallTracker model path)")

    # Run validation
    print(f"\nRunning validation...")
    metrics = model.val()
    print(f"  mAP50:    {metrics.box.map50:.3f}")
    print(f"  mAP50-95: {metrics.box.map:.3f}")


if __name__ == "__main__":
    main()
