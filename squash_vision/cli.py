"""CLI entry point for Squash Vision.

Usage:
    squash-vision analyze VIDEO_PATH [--camera-preset back_wall_left] [--upload]
    squash-vision register USERNAME DISPLAY_NAME [--country AU]
    squash-vision leaderboard [--country AU] [--limit 20]
    squash-vision stats [--period month]
    squash-vision history
    squash-vision serve [--port 8000]
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table

app = typer.Typer(
    name="squash-vision",
    help="Analyse squash practice sessions with computer vision.",
    add_completion=False,
)
console = Console()


# ---------------------------------------------------------------------------
# analyze
# ---------------------------------------------------------------------------

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
    upload: bool = typer.Option(False, "--upload", help="Upload results to the leaderboard."),
) -> None:
    """Analyse a squash practice video and score your straight drives."""
    import numpy as np

    from squash_vision.analysis.session import SessionAnalyzer
    from squash_vision.core.camera import get_preset, list_presets
    from squash_vision.social.history import save_session, get_user_id

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
        score_table.add_row("---", "---")
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

    # --- Save locally ---
    session_data = result.summary()
    session_data["score"] = result.score.as_dict()
    saved_path = save_session(session_data)
    console.print(f"\nSession saved locally: {saved_path}")

    # --- Upload to leaderboard ---
    if upload:
        user_id = get_user_id()
        if not user_id:
            console.print(
                "[yellow]Not logged in. Run 'squash-vision register' first to upload scores.[/yellow]"
            )
        else:
            _upload_session(result, user_id)

    console.print()


def _upload_session(result, user_id: str) -> None:
    """Upload a session result to the API."""
    from squash_vision.social.client import APIClient

    client = APIClient()
    if not client.health():
        console.print("[yellow]API server not reachable. Scores saved locally only.[/yellow]")
        return

    payload = {
        "user_id": user_id,
        "duration_seconds": result.duration_seconds,
        "total_shots": len(result.shots),
        "straight_drives": result.score.num_shots,
        "score_total": result.score.total,
        "score_wall_tightness": result.score.avg_wall_tightness,
        "score_length_accuracy": result.score.avg_length_accuracy,
        "score_straightness": result.score.avg_straightness,
        "score_consistency": result.score.consistency,
        "shots": [s.as_dict() for s in result.score.shot_scores],
    }

    try:
        resp = client.upload_session(payload)
        rank = resp.get("global_rank", "?")
        tier = resp.get("tier", "?")
        console.print(
            Panel(
                f"Uploaded to leaderboard!\n"
                f"Global rank: #{rank}  |  Tier: {tier}  |  Score: {result.score.total:.1f}",
                title="Leaderboard",
                border_style="green",
            )
        )
    except Exception as e:
        console.print(f"[yellow]Upload failed: {e}. Scores saved locally.[/yellow]")


# ---------------------------------------------------------------------------
# register
# ---------------------------------------------------------------------------

@app.command()
def register(
    username: str = typer.Argument(..., help="Unique username (letters, numbers, underscores)."),
    display_name: str = typer.Argument(..., help="Your display name."),
    country: str = typer.Option("", "--country", help="Country code (e.g. AU, US, GB)."),
    api_url: str = typer.Option("http://localhost:8000", "--api-url", help="API server URL."),
) -> None:
    """Register a new account for the leaderboard."""
    from squash_vision.social.client import APIClient
    from squash_vision.social.history import save_config, load_config

    client = APIClient(base_url=api_url)
    if not client.health():
        console.print(f"[red]Cannot reach API at {api_url}. Is the server running?[/red]")
        console.print("Start it with: squash-vision serve")
        raise typer.Exit(1)

    try:
        resp = client.register(username, display_name, country)
    except Exception as e:
        console.print(f"[red]Registration failed: {e}[/red]")
        raise typer.Exit(1)

    config = load_config()
    config["user_id"] = resp["id"]
    config["username"] = resp["username"]
    config["api_url"] = api_url
    save_config(config)

    console.print(
        Panel(
            f"Username: {resp['username']}\n"
            f"Display name: {resp['display_name']}\n"
            f"User ID: {resp['id']}",
            title="Registered",
            border_style="green",
        )
    )
    console.print("Your sessions will now upload to the leaderboard with --upload.")


# ---------------------------------------------------------------------------
# leaderboard
# ---------------------------------------------------------------------------

@app.command()
def leaderboard(
    limit: int = typer.Option(20, "--limit", help="Number of entries to show."),
    country: str = typer.Option(None, "--country", help="Filter by country code."),
    sort_by: str = typer.Option(
        "best", "--sort",
        help="Sort by: best (best session), avg (average), drives (total drives).",
    ),
) -> None:
    """View the global leaderboard."""
    from squash_vision.social.client import APIClient
    from squash_vision.social.history import get_user_id

    client = APIClient()
    if not client.health():
        console.print("[red]Cannot reach API. Is the server running?[/red]")
        raise typer.Exit(1)

    entries = client.get_leaderboard(limit=limit, country=country, sort_by=sort_by)
    my_id = get_user_id()

    if not entries:
        console.print("[yellow]No entries on the leaderboard yet.[/yellow]")
        return

    title = "Global Leaderboard"
    if country:
        title += f" ({country.upper()})"

    table = Table(title=title)
    table.add_column("Rank", justify="right", style="dim")
    table.add_column("Player", style="bold")
    table.add_column("Tier", justify="center")
    table.add_column("Best", justify="right", style="green")
    table.add_column("Avg", justify="right")
    table.add_column("Tightness", justify="right", style="cyan")
    table.add_column("Sessions", justify="right")
    table.add_column("Drives", justify="right")

    tier_colours = {
        "Diamond": "bright_cyan",
        "Platinum": "white",
        "Gold": "yellow",
        "Silver": "bright_black",
        "Bronze": "red",
        "Unranked": "dim",
    }

    for e in entries:
        tier_style = tier_colours.get(e["tier"], "dim")
        is_me = e.get("user_id") == my_id
        name = e["username"]
        if is_me:
            name = f">> {name} <<"

        country_flag = f" [{e['country_code']}]" if e["country_code"] else ""

        table.add_row(
            f"#{e['rank']}",
            f"{name}{country_flag}",
            f"[{tier_style}]{e['tier']}[/{tier_style}]",
            f"{e['best_session_score']:.1f}",
            f"{e['avg_session_score']:.1f}",
            f"{e['avg_wall_tightness']:.1f}",
            str(e["total_sessions"]),
            str(e["total_drives"]),
        )

    console.print(table)


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------

@app.command()
def stats(
    period: str = typer.Option("month", "--period", help="Time period: week, month, 3months, all."),
    local_only: bool = typer.Option(False, "--local", help="Show stats from local history only."),
) -> None:
    """View your personal progression stats."""
    from squash_vision.social.history import get_user_id, get_local_stats

    if local_only:
        data = get_local_stats()
        _print_local_stats(data)
        return

    user_id = get_user_id()
    if not user_id:
        console.print("[yellow]Not logged in. Showing local stats only.[/yellow]")
        data = get_local_stats()
        _print_local_stats(data)
        return

    from squash_vision.social.client import APIClient

    client = APIClient()
    if not client.health():
        console.print("[yellow]API not reachable. Showing local stats.[/yellow]")
        data = get_local_stats()
        _print_local_stats(data)
        return

    try:
        data = client.get_stats(user_id, period=period)
    except Exception:
        console.print("[yellow]Failed to fetch stats. Showing local stats.[/yellow]")
        data = get_local_stats()
        _print_local_stats(data)
        return

    console.print()
    console.rule(f"[bold]Your Stats ({period})")

    table = Table(show_header=False)
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")
    table.add_row("Sessions", str(data["sessions"]))
    table.add_row("Total drives", str(data["total_drives"]))
    table.add_row("Best score", f"{data['best_score']:.1f}")
    table.add_row("Average score", f"{data['avg_score']:.1f}")
    table.add_row("Avg wall tightness", f"{data['avg_wall_tightness']:.1f}")
    table.add_row("Avg length accuracy", f"{data['avg_length_accuracy']:.1f}")
    table.add_row("Avg straightness", f"{data['avg_straightness']:.1f}")
    table.add_row("Avg consistency", f"{data['avg_consistency']:.1f}")
    console.print(table)

    if data.get("score_trend"):
        console.print()
        trend_table = Table(title="Score Trend")
        trend_table.add_column("Date")
        trend_table.add_column("Score", justify="right")
        trend_table.add_column("Tightness", justify="right")
        for pt in data["score_trend"][-10:]:
            trend_table.add_row(
                pt["date"],
                f"{pt['score']:.1f}",
                f"{pt.get('wall_tightness', 0):.1f}",
            )
        console.print(trend_table)

    console.print()


def _print_local_stats(data: dict) -> None:
    console.print()
    console.rule("[bold]Local Stats")
    table = Table(show_header=False)
    table.add_column("Metric", style="bold")
    table.add_column("Value", justify="right")
    table.add_row("Sessions", str(data["total_sessions"]))
    table.add_row("Total drives", str(data["total_drives"]))
    table.add_row("Best score", f"{data['best_score']:.1f}")
    table.add_row("Average score", f"{data['avg_score']:.1f}")
    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# history
# ---------------------------------------------------------------------------

@app.command()
def history(
    limit: int = typer.Option(20, "--limit", help="Number of sessions to show."),
) -> None:
    """View your local session history."""
    from squash_vision.social.history import list_sessions

    sessions = list_sessions(limit=limit)
    if not sessions:
        console.print("[yellow]No sessions recorded yet. Run 'squash-vision analyze' on a video.[/yellow]")
        return

    table = Table(title="Session History")
    table.add_column("Date", style="dim")
    table.add_column("Video")
    table.add_column("Drives", justify="right")
    table.add_column("Score", justify="right", style="bold")
    table.add_column("Tightness", justify="right", style="cyan")

    for s in sessions:
        score = s.get("score", {})
        table.add_row(
            s.get("saved_at", "")[:16].replace("T", " "),
            s.get("video", "?")[:40],
            str(score.get("num_shots", 0)),
            f"{score.get('total', 0):.1f}",
            f"{score.get('avg_wall_tightness', 0):.1f}",
        )

    console.print(table)


# ---------------------------------------------------------------------------
# serve
# ---------------------------------------------------------------------------

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
