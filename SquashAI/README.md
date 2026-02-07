# Squash Vision

Computer vision analysis for squash practice sessions. Track your straight drives, get scored on accuracy, and compete on a global leaderboard.

## What it does

Point a camera at a squash court (ideally mounted behind the back wall glass), record your solo practice, and Squash Vision will:

1. **Detect the court** — automatically finds court boundaries and maps the camera perspective to real-world coordinates.
2. **Track the ball** — uses YOLOv8 + Kalman filtering to follow the ball through each rally.
3. **Classify shots** — segments the ball trajectory into individual shots and identifies straight drives.
4. **Score your drives** on four dimensions:
   - **Wall tightness** — how close to the side wall (the money metric)
   - **Length accuracy** — how deep toward the back wall
   - **Straightness** — how parallel to the side wall
   - **Consistency** — how repeatable your shots are
5. **Compete globally** — upload scores to the leaderboard API and see how you rank worldwide.

## Project structure

```
squash_vision/
├── core/
│   ├── court.py          # Court detection + homography calibration
│   ├── ball_tracker.py   # Ball detection (YOLO + blob fallback) + Kalman filter
│   └── player.py         # Player pose detection + swing estimation
├── analysis/
│   ├── shot_classifier.py  # Shot segmentation + classification
│   ├── scoring.py          # Per-shot and session scoring engine
│   └── session.py          # End-to-end video analysis pipeline
├── social/
│   └── models.py         # SQLModel database models (users, sessions, leaderboard)
├── api/
│   └── app.py            # FastAPI leaderboard endpoints
└── cli.py                # Typer CLI entry point
```

## Quick start

```bash
pip install -e .

# Analyse a practice video
squash-vision analyze my_session.mp4

# With manual court corners (if auto-detection fails)
squash-vision analyze my_session.mp4 --corners '[[100,200],[500,200],[520,600],[80,600]]'

# Process every 2nd frame for speed
squash-vision analyze my_session.mp4 --every-n 2

# Start the leaderboard API
squash-vision serve --port 8000
```

## Scoring formula

**Per-shot** (straight drives only):
```
shot_total = 0.40 * wall_tightness + 0.35 * length_accuracy + 0.25 * straightness
```

**Session aggregate**:
```
session_total = 0.35 * avg_tightness + 0.25 * avg_length + 0.25 * consistency + 0.15 * avg_straightness
```

Wall tightness is weighted highest because keeping the ball tight to the wall is the core skill that separates levels in squash.

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/sessions` | Upload a session result |
| `GET` | `/leaderboard` | Global rankings (supports `?country=` filter) |
| `GET` | `/users/{id}` | User profile + session history |

## Camera setup

For best results:
- Mount the camera **behind the back wall glass**, centred, looking down the court.
- A wide-angle lens helps capture the full court.
- 30+ FPS recommended (60 FPS ideal for fast ball tracking).
- Good lighting with minimal shadows improves detection accuracy.

## Roadmap

- [ ] Fine-tuned YOLOv8 model trained specifically on squash balls
- [ ] Full match analysis (two players, rally scoring)
- [ ] Shot type expansion (cross-courts, boasts, drops, lobs, volleys)
- [ ] Movement pattern analysis (ghosting efficiency, T-position recovery)
- [ ] Mobile app with real-time overlay
- [ ] Video highlight export (best/worst shots)

## Tech stack

- **OpenCV** — frame processing, homography, edge detection
- **Ultralytics YOLOv8** — object detection (ball, player) and pose estimation
- **NumPy / SciPy** — trajectory math and scoring
- **FastAPI** — leaderboard API
- **SQLModel** — database ORM
- **Typer + Rich** — CLI interface
