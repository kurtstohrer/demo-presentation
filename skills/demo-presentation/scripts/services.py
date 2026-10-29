"""Project-config helpers for scripts/demo. Reads $DEMO_CONFIG (default .demo/config.toml).

    services.py template <template.json> <title>   script.json seeded from the config
    services.py up <project-root>                   start [[services]] and wait until ready
    services.py down <project-root>                 stop them
    services.py publish <run-dir> [args...]          run the [publish] command for a finished run

Keys: base_url, theme, voice, speed, lexicon, local_storage, logo,
[[services]] = {name, start, stop, ready, timeout}, and [publish] command = "..." where ready is an http(s) URL
or a shell command that exits 0 once the service is usable.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
import os
import subprocess
import tomllib
from core import services


def demo_cfg() -> dict:
    path = Path(os.environ.get("DEMO_CONFIG") or ".demo/config.toml")
    if not path.is_file():
        return {}
    return tomllib.loads(path.read_text())


def up(root: str) -> int:
    return services.up(root, demo_cfg().get("services", []))


def down(root: str) -> int:
    return services.down(root, demo_cfg().get("services", []))


def template(path: str, title: str) -> None:
    cfg = demo_cfg()
    script = json.loads(Path(path).read_text().replace("__TITLE__", title))
    for src, dst in (("voice", "voice"), ("speed", "speed"), ("theme", "theme"), ("base_url", "baseUrl")):
        if cfg.get(src) is not None:
            script[dst] = cfg[src]
    if cfg.get("lexicon"):
        script["lexicon"] = {**script.get("lexicon", {}), **cfg["lexicon"]}
    if cfg.get("local_storage"):
        script["localStorage"] = cfg["local_storage"]
    logo = cfg.get("logo")
    if logo:
        # A project with a logo opens and closes every video on its title card.
        card = lambda sid, say: {"id": sid, "type": "card", "logo": logo, "title": title, "beats": [{"say": say}]}
        script["scenes"] = [card("title-card", f"{title}."), *script["scenes"], card("end-card", "Thanks for watching.")]
    if script.get("baseUrl"):
        for scene in script["scenes"]:
            if scene["type"] == "ui" and scene.get("url", "").startswith("http://localhost:3000"):
                scene["url"] = "/"
    print(json.dumps(script, indent=2))


def publish(run: str, args: list[str]) -> int:
    """Hand a finished run to whatever the project uses: a tracker, a bucket, a chat."""
    command = (demo_cfg().get("publish") or {}).get("command")
    if not command:
        print("no [publish] command in .demo/config.toml; hand off the review link or final.mp4 instead", file=sys.stderr)
        return 2
    d = Path(run)
    if not (d / "final.mp4").is_file():
        print(f"no final.mp4 in {d}: run `demo build` first", file=sys.stderr)
        return 1
    title = json.loads((d / "script.json").read_text()).get("title", d.name)
    env = {**os.environ, "DEMO_RUN": str(d), "DEMO_TITLE": title, "DEMO_VIDEO": str(d / "final.mp4"),
           "DEMO_CAPTIONS": str(d / "captions.srt"), "DEMO_TIMELINE": str(d / "final.json")}
    root = os.environ.get("DEMO_PROJECT_ROOT") or "."
    # Extra arguments reach the command as "$@".
    return subprocess.run(["sh", "-c", command, "demo-publish", *args], cwd=root, env=env).returncode


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "template":
        template(sys.argv[2], sys.argv[3])
    elif cmd == "up":
        sys.exit(up(sys.argv[2]))
    elif cmd == "down":
        sys.exit(down(sys.argv[2]))
    elif cmd == "publish":
        sys.exit(publish(sys.argv[2], sys.argv[3:]))
    else:
        print(__doc__)
        sys.exit(2)
