"""Shared helpers for the recorder, validator and storyboard page: paths, run loading, script checks."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
SCENE_TYPES = ("whiteboard", "terminal", "code", "chat", "ui", "card")
WORDS_PER_SECOND = 2.6


def project_root() -> Path:
    if os.environ.get("DEMO_PROJECT_ROOT"):
        return Path(os.environ["DEMO_PROJECT_ROOT"]).resolve()
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True).stdout
        return Path(out.strip())
    except (OSError, subprocess.CalledProcessError):
        return Path.cwd()


_MISSING = object()


def read_json(path: Path, fallback=_MISSING):
    if not path.exists():
        if fallback is not _MISSING:
            return fallback
        raise FileNotFoundError(f"missing {path}")
    return json.loads(path.read_text())


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def beat_key(scene_id: str, i: int) -> str:
    return f"{scene_id}.{i}"


def estimate_seconds(text: str | None) -> float:
    words = len(str(text or "").split())
    return words / WORDS_PER_SECOND + 0.3 if words else 0.0


def ffmpeg() -> str:
    """The ffmpeg binary: DEMO_FFMPEG, else the one the imageio-ffmpeg wheel ships (libx264)."""
    if os.environ.get("DEMO_FFMPEG"):
        return os.environ["DEMO_FFMPEG"]
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def validate_script(script) -> list[str]:
    if not isinstance(script, dict):
        return ["script must be an object"]
    problems = []
    if not script.get("title"):
        problems.append("title is required")
    scenes = script.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        problems.append("scenes must be a non-empty array")
        scenes = scenes if isinstance(scenes, list) else []
    ids = set()
    for si, scene in enumerate(scenes):
        scene = scene if isinstance(scene, dict) else {}
        where = f"scenes[{si}]" + (f" ({scene['id']})" if scene.get("id") else "")
        sid = scene.get("id")
        if not isinstance(sid, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", sid):
            problems.append(f"{where}: id must be kebab-case")
        if sid in ids:
            problems.append(f"{where}: duplicate id")
        ids.add(sid)
        if scene.get("type") not in SCENE_TYPES:
            problems.append(f"{where}: type must be one of {', '.join(SCENE_TYPES)}")
        if scene.get("type") == "ui" and not scene.get("url"):
            problems.append(f"{where}: ui scenes need url")
        beats = scene.get("beats")
        if not isinstance(beats, list) or not beats:
            problems.append(f"{where}: beats must be a non-empty array")
            beats = beats if isinstance(beats, list) else []
        for bi, beat in enumerate(beats):
            beat = beat if isinstance(beat, dict) else {}
            if "say" in beat and not isinstance(beat["say"], str):
                problems.append(f"{where} beats[{bi}]: say must be a string")
            if "do" in beat and not isinstance(beat["do"], list):
                problems.append(f"{where} beats[{bi}]: do must be an array")
            actions = beat["do"] if isinstance(beat.get("do"), list) else []
            for a in actions:
                if not isinstance(a, dict):
                    problems.append(f"{where} beats[{bi}]: each action must be an object")
                elif scene.get("type") == "chat":
                    problems += chat_action_problems(a, f"{where} beats[{bi}]")
    return problems


def chat_action_problems(a: dict, where: str) -> list[str]:
    if "user" in a and not isinstance(a["user"], str):
        return [f"{where}: chat user must be a string"]
    if "agent" in a and not (isinstance(a["agent"], str) or isinstance(a["agent"], dict) and isinstance(a["agent"].get("text"), str)):
        return [f"{where}: chat agent must be a string or {{text}}"]
    if "tool" in a and not (isinstance(a["tool"], str) or isinstance(a["tool"], dict) and isinstance(a["tool"].get("name"), str)):
        return [f"{where}: chat tool must be a string or {{name}}"]
    return []


def load_run(run_dir: str | Path) -> tuple[Path, dict, dict]:
    """(run dir, script, audio manifest); raises on an invalid script."""
    d = Path(run_dir).resolve()
    script = read_json(d / "script.json")
    problems = validate_script(script)
    if problems:
        raise ValueError("script.json is invalid:\n  - " + "\n  - ".join(problems))
    return d, script, read_json(d / "audio" / "audio.json", {})


if __name__ == "__main__":
    import sys

    if sys.argv[1:] == ["ffmpeg"]:  # scripts/demo doctor: where ffmpeg is
        print(ffmpeg())
