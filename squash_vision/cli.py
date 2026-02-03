"""CLI entry point for Squash Vision.

Usage:
    squash-vision analyze VIDEO_PATH [--corners JSON] [--skip-player] [--every-n 2]
    squash-vision serve [--port 8000]
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table

app = typer.Typer(
    name="squash-vision",
    help="Analyse squash practice sessions with computer vision.",
    add_completion=False,
)
console = Console()


@app.command()
def analyze(
    video: Path = typer.Argument(..., help="Path to the video file."),
    corners: str = typer.Option(
        None,
        help='Court corners as JSON: [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]',
    ),
    camera_preset: str = typer.Option(
        None,
        "--camera-preset",
        help="Camera placement preset. Options: back_wall_left, back_wall_right, "
             "back_wall_centre, back_wall_centre_high, side_left, side_right.",
    ),
    ball_model: Path = typer.Option(
        None, "--ball-model", help="Path to fine-tuned YOLOv8 weights for ball detection.",
    ),
    skip_player: bool = typer.Option(False, "--skip-player", help="Skip player detection."),
    every_n: int = typer.Option(1, "--every-n", help="Process every Nth frame."),
    max_frames: int = typer.Option(None, "--max-frames", help="Stop after N frames."),
) -> None:
    """Analyse a squash practice video and score your straight drives."""
    import numpy as np

    from squash_vision.analysis.session import SessionAnalyzer
    from squash_vision.core.camera import get_preset, list_presets

    corners_px = None
    if corners:
        corners_px = np.array(json.loads(corners), dtype=np.float32)

    camera_profile = None
    if camera_preset:
        try:
            camera_profile = get_preset(camera_preset)
            console.print(f"Using camera preset: [bold]{camera_preset}[/bold]")
        except KeyError:
            options = ", ".join(list_presets())
            console.print(f"[red]Unknown preset '{camera_preset}'. Available: {options}[/red]")
            raise typer.Exit(1)

    analyzer = SessionAnalyzer(
        ball_model_path=ball_model,
        court_corners_px=corners_px,
        camera_profile=camera_profile,
        skip_player=skip_player,
        process_every_n=every_n,
    )

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total} frames"),
        console=console,
    ) as progress:
        task = progress.add_task("Analysing video...", total=0)

        def on_progress(current: int, total: int) -> None:
            progress.update(task, completed=current, total=total)

        result = analyzer.analyze(
            video,
            max_frames=max_frames,
            on_progress=on_progress,
        )

    # --- Display results ---
    console.print()
    console.rule("[bold green]Session Results")

    info_table = Table(show_header=False)
    info_table.add_column("Key", style="bold")
    info_table.add_column("Value")
    info_table.add_row("Video", result.video_path)
    info_table.add_row("Duration", f"{result.duration_seconds:.1f}s")
    info_table.add_row("Frames processed", str(result.total_frames))
    info_table.add_row("Shots detected", str(len(result.shots)))
    info_table.add_row("Straight drives", str(result.score.num_shots))
    console.print(info_table)

    if result.score.num_shots > 0:
        console.print()
        score_table = Table(title="Straight Drive Scores")
        score_table.add_column("Metric", style="cyan")
        score_table.add_column("Score", justify="right", style="bold")
        score_table.add_row("Wall Tightness", f"{result.score.avg_wall_tightness:.1f}/100")
        score_table.add_row("Length Accuracy", f"{result.score.avg_length_accuracy:.1f}/100")
        score_table.add_row("Straightness", f"{result.score.avg_straightness:.1f}/100")
        score_table.add_row("Consistency", f"{result.score.consistency:.1f}/100")
        score_table.add_row("─" * 20, "─" * 10)
        score_table.add_row("[bold]TOTAL", f"[bold]{result.score.total:.1f}/100")
        console.print(score_table)

        # Per-shot breakdown
        console.print()
        shot_table = Table(title="Per-Shot Breakdown")
        shot_table.add_column("#", justify="right")
        shot_table.add_column("Tightness", justify="right")
        shot_table.add_column("Length", justify="right")
        shot_table.add_column("Straight", justify="right")
        shot_table.add_column("Total", justify="right", style="bold")
        for i, ss in enumerate(result.score.shot_scores, 1):
            shot_table.add_row(
                str(i),
                f"{ss.wall_tightness:.1f}",
                f"{ss.length_accuracy:.1f}",
                f"{ss.straightness:.1f}",
                f"{ss.total:.1f}",
            )
        console.print(shot_table)
    else:
        console.print("[yellow]No straight drives detected in this session.[/yellow]")

    console.print()


@app.command()
def serve(
    port: int = typer.Option(8000, help="Port to run the API server on."),
    host: str = typer.Option("0.0.0.0", help="Host to bind to."),
) -> None:
    """Start the leaderboard API server."""
    import uvicorn

    console.print(f"Starting Squash Vision API on {host}:{port}")
    uvicorn.run("squash_vision.api.app:app", host=host, port=port, reload=True)


if __name__ == "__main__":
    app()
