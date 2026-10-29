"""Review server for demo-presentation runs. Localhost only.

    scripts/demo serve [--port 4177]

Serves the review UI (ui/), run files (storyboard frames, final.mp4 with range
requests), the review API (review.json via reviewlib), the project pronunciation
library with spoken previews, and render jobs that shell out to scripts/demo.
All state lives in the run directories and the library file.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from pathlib import Path

from fastapi import Body, HTTPException
from fastapi.responses import Response
from core.server import create_app, guard, mount_ui, serve
from core.review import list_versions, load_version

sys.path.insert(0, str(Path(__file__).parent))
import reviewlib as rl  # noqa: E402
from common import validate_script  # noqa: E402

SKILL = Path(__file__).resolve().parent.parent
RUNS = Path(os.environ.get("DEMO_RUNS_DIR", SKILL / "runs")).resolve()
DEMO = SKILL / "scripts" / "demo"
JOB_KINDS = ("storyboard", "tts", "record", "stitch", "build")
WATCHED = ("script.json", "review.json", "final.json", "timeline.json", "storyboard/storyboard.json", "audio/audio.json")

# ---------- runs ----------

def mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


def fingerprint(d: Path) -> str:
    return ",".join(f"{mtime(d / f):.3f}" for f in (*WATCHED, "final.mp4"))


def watch_key(d: Path) -> str:
    """What the SSE stream watches: the run files plus the shared pronunciation library."""
    return f"{fingerprint(d)},{mtime(rl.library_path(d)):.3f}"


def job_command(name: str, kind: str, scenes: list[str]) -> list[str]:
    args = [str(DEMO), kind, str(RUNS / name)]
    if scenes and kind in ("record", "build", "storyboard"):
        args += ["--scene", ",".join(scenes)]
    return args


app = create_app(title="demo-presentation review", runs=RUNS, marker="script.json", review=rl,
                 kinds=JOB_KINDS, command=job_command, watch=watch_key)
run_dir = app.state.run_dir
JOBS = app.state.runner.jobs


def thumb(d: Path, script: dict) -> str | None:
    first = script.get("scenes", [{}])[0].get("id")
    for name in ([f"{first}.0.png"] if first else []) + sorted(p.name for p in (d / "storyboard").glob("*.png")):
        if (d / "storyboard" / name).exists():
            return f"storyboard/{name}"
    return None


def project_name() -> str:
    root = os.environ.get("DEMO_PROJECT_ROOT")
    return Path(root).name if root else RUNS.parent.parent.name


@app.get("/api/project")
def project():
    return {"name": project_name(), "runs": str(RUNS)}


@app.get("/api/runs")
def list_runs():
    out = []
    for d in sorted(RUNS.iterdir() if RUNS.exists() else [], key=lambda p: -mtime(p / "script.json")):
        if not d.is_dir() or not (d / "script.json").exists():
            continue
        script = rl.read_json(d / "script.json", {}) or {}
        final = rl.read_json(d / "final.json", None)
        review = rl.load(d)
        out.append({
            "name": d.name, "title": script.get("title", d.name), "status": review["status"], "version": review["version"],
            "scenes": len(script.get("scenes", [])), "duration": final and final.get("duration"),
            "openComments": sum(1 for c in review["comments"] if c["status"] == "open"),
            "openDecisions": sum(1 for x in review["decisions"] if x.get("state") == "open"),
            "updated": max(mtime(d / f) for f in (*WATCHED, "final.mp4")),
            "thumb": thumb(d, script),
            "job": JOBS[d.name].public() if d.name in JOBS else None,
        })
    return out


@app.get("/api/runs/{name}")
def get_run(name: str):
    d = run_dir(name)
    board = rl.read_json(d / "storyboard" / "storyboard.json", None)
    return {
        "name": name,
        "project": project_name(),
        "script": rl.read_json(d / "script.json"),
        "review": rl.load(d),
        "audio": rl.read_json(d / "audio" / "audio.json", {}),
        "final": rl.read_json(d / "final.json", None),
        "hasFinal": (d / "final.mp4").exists(),
        "videoVersion": f"{mtime(d / 'final.mp4'):.3f}",
        "library": rl.load_library(d),
        "storyboard": {"recordedAt": board.get("recordedAt")} if board else None,
        "frames": sorted(p.name for p in (d / "storyboard").glob("*.png")),
        "stale": rl.stale(d),
        "job": JOBS[name].public() if name in JOBS else None,
        "fingerprint": fingerprint(d),
        "versions": [{"version": int(p.name), "hasScript": (p / "script.json").exists()}
                     for p in list_versions(d)],
    }


@app.get("/api/runs/{name}/versions/{version}")
def get_version(name: str, version: int):
    data = guard(load_version, run_dir(name), version, ("script.json", "final.json"))
    return {"script": data["script.json"], "final": data["final.json"]}


@app.put("/api/runs/{name}/script")
def put_script(name: str, script: dict = Body(...)):
    d = run_dir(name)
    problems = validate_script(script)
    verdict = {"ok": not problems, "problems": problems}
    if not verdict["ok"]:
        raise HTTPException(422, {"problems": verdict["problems"]})
    rl.write_json(d / "script.json", script)
    return {"ok": True, "stale": rl.stale(d)}


# ---------- review ----------

@app.get("/api/runs/{name}/agent-brief")
def agent_brief(name: str):
    d = run_dir(name)
    return {"text": rl.summary(d)}


# ---------- pronunciation library ----------

def library_file() -> Path:
    return rl.library_path(RUNS / "_")  # any path inside the runs dir resolves the same library


@app.get("/api/pronunciations")
def get_library():
    return {"path": str(library_file()), "entries": rl.load_library(RUNS / "_")}


@app.put("/api/pronunciations")
def put_library(entries: dict = Body(...)):
    clean = {}
    for k, v in entries.items():
        if not isinstance(v, str) or not k.strip() or not v.strip():
            raise HTTPException(422, f"entry {k!r}: word and pronunciation are required")
        if any(ch.isspace() for ch in k.strip()):
            raise HTTPException(422, f"entry {k!r}: one word per entry")
        clean[k.strip()] = v.strip()
    rl.write_json(library_file(), dict(sorted(clean.items(), key=lambda kv: kv[0].lower())))
    return {"ok": True, "entries": clean}


_tts_lock = threading.Lock()


@app.post("/api/pronounce")
def pronounce(body: dict = Body(...)):
    """Speak `text` with `voice` through `lexicon` (the caller's effective entries, drafts included). Returns WAV."""
    import io

    text = (body.get("text") or "").strip()
    if not text or len(text) > 600:
        raise HTTPException(422, "text is required (at most 600 characters)")
    import soundfile as sf
    import tts

    voice = body.get("voice") or rl.DEFAULT_VOICE
    lexicon = {str(k): str(v) for k, v in (body.get("lexicon") or {}).items() if str(v).strip()}
    with _tts_lock:  # one synthesis at a time; the model loads on first use
        audio, _ = tts.synthesize(rl.spoken_text(text, lexicon), voice, float(body.get("speed") or 1.0))
    buf = io.BytesIO()
    sf.write(buf, audio, tts.SAMPLE_RATE, format="WAV")
    return Response(buf.getvalue(), media_type="audio/wav")


mount_ui(app, SKILL / "ui")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=4177)
    a = ap.parse_args()
    print(f"demo review UI: http://127.0.0.1:{a.port}/  (runs: {RUNS})", flush=True)
    serve(app, a.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
