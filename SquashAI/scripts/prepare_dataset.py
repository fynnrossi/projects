"""Prepare annotated frames into a YOLO training dataset.

Takes the annotated frames (images + .txt labels) and splits them into
train/val sets with the directory structure YOLO expects:

    training/dataset/
    ├── images/
    │   ├── train/
    │   └── val/
    ├── labels/
    │   ├── train/
    │   └── val/
    └── dataset.yaml

Usage:
    python scripts/prepare_dataset.py training/raw_frames \
        --output training/dataset \
        --val-split 0.15
"""

from __future__ import annotations

import argparse
import random
import shutil
from pathlib import Path

import yaml


def main() -> None:
    p = argparse.ArgumentParser(description="Prepare YOLO dataset from annotated frames.")
    p.add_argument("input_dir", type=Path, help="Directory with images and .txt labels.")
    p.add_argument("--output", type=Path, default=Path("training/dataset"))
    p.add_argument("--val-split", type=float, default=0.15, help="Fraction for validation.")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    random.seed(args.seed)

    # Find all images that have a corresponding label file
    image_exts = {".png", ".jpg", ".jpeg"}
    all_images = [
        f for f in sorted(args.input_dir.iterdir())
        if f.suffix.lower() in image_exts and f.with_suffix(".txt").exists()
    ]

    if not all_images:
        print("No annotated images found. Run annotate_ball.py first.")
        return

    # Shuffle and split
    random.shuffle(all_images)
    val_count = max(1, int(len(all_images) * args.val_split))
    val_images = all_images[:val_count]
    train_images = all_images[val_count:]

    print(f"Total annotated: {len(all_images)}")
    print(f"Train: {len(train_images)}, Val: {val_count}")

    # Create directory structure
    for split in ("train", "val"):
        (args.output / "images" / split).mkdir(parents=True, exist_ok=True)
        (args.output / "labels" / split).mkdir(parents=True, exist_ok=True)

    # Copy files
    def copy_split(images: list[Path], split: str) -> None:
        for img_path in images:
            label_path = img_path.with_suffix(".txt")
            shutil.copy2(img_path, args.output / "images" / split / img_path.name)
            shutil.copy2(label_path, args.output / "labels" / split / label_path.name)

    copy_split(train_images, "train")
    copy_split(val_images, "val")

    # Write dataset.yaml
    dataset_config = {
        "path": str(args.output.resolve()),
        "train": "images/train",
        "val": "images/val",
        "names": {
            0: "squash_ball",
        },
        "nc": 1,
    }

    yaml_path = args.output / "dataset.yaml"
    with open(yaml_path, "w") as f:
        yaml.dump(dataset_config, f, default_flow_style=False)

    print(f"\nDataset written to: {args.output}")
    print(f"Config: {yaml_path}")

    # Count positive vs negative samples
    pos_train = sum(1 for img in train_images if img.with_suffix(".txt").stat().st_size > 0)
    pos_val = sum(1 for img in val_images if img.with_suffix(".txt").stat().st_size > 0)
    print(f"\nTrain: {pos_train} with ball, {len(train_images) - pos_train} without")
    print(f"Val:   {pos_val} with ball, {val_count - pos_val} without")

    print(f"\nNext step: python scripts/train_ball_detector.py training/dataset/dataset.yaml")


if __name__ == "__main__":
    main()
