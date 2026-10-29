"""Service lifecycle for the [[services]] a project configures."""
from __future__ import annotations

import subprocess
import time
import urllib.request
from pathlib import Path


def is_ready(check: str, root: str) -> bool:
    if check.startswith(("http://", "https://")):
        try:
            with urllib.request.urlopen(check, timeout=3) as r:
                return r.status < 500
        except Exception:
            return False
    return subprocess.run(check, shell=True, cwd=root, capture_output=True).returncode == 0


def up(root: str, services: list[dict]) -> int:
    if not services:
        print("no [[services]] configured; start what the demo needs per .demo/brief.md")
        return 0
    log_dir = Path(root) / ".demo" / "local" / "services"
    log_dir.mkdir(parents=True, exist_ok=True)
    for s in services:
        name, ready = s["name"], s.get("ready", "")
        if ready and is_ready(ready, root):
            print(f"ok   {name} (already up)")
            continue
        with open(log_dir / f"{name}.log", "ab") as log:
            subprocess.Popen(s["start"], shell=True, cwd=root, stdout=log, stderr=log, start_new_session=True)
        deadline = time.time() + float(s.get("timeout", 180))
        while ready and time.time() < deadline and not is_ready(ready, root):
            time.sleep(2)
        if ready and not is_ready(ready, root):
            print(f"FAIL {name}: not ready after {s.get('timeout', 180)}s (log: {log_dir / (name + '.log')})")
            return 1
        print(f"ok   {name}")
    return 0


def down(root: str, services: list[dict]) -> int:
    for s in services:
        if s.get("stop"):
            r = subprocess.run(s["stop"], shell=True, cwd=root)
            print(f"{'ok  ' if r.returncode == 0 else 'FAIL'} stop {s['name']}")
        else:
            print(f"skip {s['name']}: no stop command")
    return 0
