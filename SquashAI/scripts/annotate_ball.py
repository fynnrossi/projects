"""Simple OpenCV annotation tool for squash ball labelling.

Opens each frame in a window. Click on the ball to mark its position.
Press 's' to skip (ball not visible). Press 'u' to undo. Press 'q' to quit.

Outputs YOLO-format label files (.txt) alongside each image:
    <class_id> <x_centre> <y_centre> <width> <height>
    (all normalised 0–1)

The ball bounding box is generated from the click point with a
configurable radius (default 12px) — squash balls are small.

Usage:
    python scripts/annotate_ball.py training/raw_frames --ball-radius 12

Keyboard controls:
    Left-click  Mark ball position
    s           Skip frame (no ball visible)
    u           Undo last annotation on this frame
    z           Zoom toggle (2x around cursor)
    q           Quit and save progress

Progress is saved automatically — rerun to continue where you left off.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np


class Annotator:
    def __init__(self, image_dir: Path, ball_radius: int = 12) -> None:
        self.image_dir = image_dir
        self.ball_radius = ball_radius
        self.images = sorted(image_dir.glob("*.png")) + sorted(image_dir.glob("*.jpg"))
        self.current_idx = 0
        self.click_pos: tuple[int, int] | None = None
        self.zoom = False

        # Skip already-annotated images
        self._skip_annotated()

    def _skip_annotated(self) -> None:
        """Advance index past images that already have label files."""
        while self.current_idx < len(self.images):
            label_path = self._label_path(self.images[self.current_idx])
            skip_path = label_path.with_suffix(".skip")
            if label_path.exists() or skip_path.exists():
                self.current_idx += 1
            else:
                break

    def _label_path(self, image_path: Path) -> Path:
        return image_path.with_suffix(".txt")

    def _save_label(self, image_path: Path, cx: int, cy: int) -> None:
        """Save a YOLO-format label file."""
        img = cv2.imread(str(image_path))
        h, w = img.shape[:2]

        # Normalised coords
        x_center = cx / w
        y_center = cy / h
        box_w = (self.ball_radius * 2) / w
        box_h = (self.ball_radius * 2) / h

        label_path = self._label_path(image_path)
        with open(label_path, "w") as f:
            f.write(f"0 {x_center:.6f} {y_center:.6f} {box_w:.6f} {box_h:.6f}\n")

    def _save_skip(self, image_path: Path) -> None:
        """Mark a frame as having no ball (empty label file)."""
        label_path = self._label_path(image_path)
        # Write empty label = no objects (YOLO convention for negative samples)
        with open(label_path, "w") as f:
            pass
        # Also write a .skip marker so we know it was intentional
        label_path.with_suffix(".skip").touch()

    def _mouse_callback(self, event: int, x: int, y: int, flags: int, param) -> None:
        if event == cv2.EVENT_LBUTTONDOWN:
            self.click_pos = (x, y)

    def run(self) -> None:
        total = len(self.images)
        annotated_count = self.current_idx  # Already done

        if self.current_idx >= total:
            print("All images already annotated!")
            return

        print(f"\nAnnotation tool")
        print(f"Images: {total} ({self.current_idx} already done)")
        print(f"Ball radius: {self.ball_radius}px")
        print(f"\nControls:")
        print(f"  Click     = mark ball position")
        print(f"  s         = skip (ball not visible)")
        print(f"  u         = undo annotation")
        print(f"  z         = toggle zoom")
        print(f"  q         = quit\n")

        cv2.namedWindow("Annotate", cv2.WINDOW_NORMAL)
        cv2.setMouseCallback("Annotate", self._mouse_callback)

        while self.current_idx < total:
            image_path = self.images[self.current_idx]
            frame = cv2.imread(str(image_path))
            if frame is None:
                self.current_idx += 1
                continue

            display = frame.copy()
            h, w = display.shape[:2]

            # Status bar
            cv2.rectangle(display, (0, 0), (w, 35), (0, 0, 0), -1)
            status = f"[{self.current_idx + 1}/{total}] {image_path.name}  |  Click=mark  s=skip  q=quit"
            cv2.putText(display, status, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            self.click_pos = None
            cv2.imshow("Annotate", display)

            while True:
                key = cv2.waitKey(50) & 0xFF

                if self.click_pos is not None:
                    cx, cy = self.click_pos
                    # Save and move to next
                    self._save_label(image_path, cx, cy)
                    annotated_count += 1
                    print(f"  [{annotated_count}] {image_path.name} -> ball at ({cx}, {cy})")
                    self.current_idx += 1
                    break

                if key == ord("s"):
                    self._save_skip(image_path)
                    annotated_count += 1
                    print(f"  [{annotated_count}] {image_path.name} -> skipped (no ball)")
                    self.current_idx += 1
                    break

                if key == ord("u"):
                    # Undo previous
                    if self.current_idx > 0:
                        self.current_idx -= 1
                        prev = self.images[self.current_idx]
                        self._label_path(prev).unlink(missing_ok=True)
                        self._label_path(prev).with_suffix(".skip").unlink(missing_ok=True)
                        annotated_count = max(0, annotated_count - 1)
                        print(f"  Undid {prev.name}")
                    break

                if key == ord("z"):
                    self.zoom = not self.zoom

                if key == ord("q"):
                    print(f"\nQuit. Annotated {annotated_count} images total.")
                    cv2.destroyAllWindows()
                    return

        cv2.destroyAllWindows()
        print(f"\nDone! Annotated all {total} images.")
        print(f"Labels saved alongside images in: {self.image_dir}")
        print(f"\nNext step: python scripts/prepare_dataset.py")


def main() -> None:
    p = argparse.ArgumentParser(description="Annotate squash ball positions.")
    p.add_argument("image_dir", type=Path, help="Directory containing extracted frames.")
    p.add_argument("--ball-radius", type=int, default=12, help="Ball bbox radius in pixels.")
    args = p.parse_args()

    annotator = Annotator(args.image_dir, ball_radius=args.ball_radius)
    annotator.run()


if __name__ == "__main__":
    main()
