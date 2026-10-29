"""Records every scene of a run with Playwright.

    python scripts/record.py <run-dir> [--scene id[,id]] [--storyboard] [--refresh] [--keep-frames] [--headed] [--software-gl]

Full mode captures screencast frames per scene and encodes scenes/<id>.mp4,
writing scene timing to timeline.json. --storyboard skips frames, compresses
time, and screenshots the end of every beat into storyboard/.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
import datetime
import functools
import http.server
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import SKILL_DIR, beat_key, estimate_seconds, ffmpeg, load_run, project_root, read_json, write_json  # noqa: E402
from core.page_driver import PageDriver  # noqa: E402

LEAD_IN = 0.5
LEAD_OUT = 0.8
LANG_BY_EXT = {".mjs": "js", ".cjs": "js", ".yml": "yaml", ".rs": "rust", ".sh": "bash", ".txt": "text", ".py": "python",
               ".md": "markdown", ".ts": "typescript", ".js": "javascript", ".toml": "toml", ".json": "json"}
CURSOR_JS = (SKILL_DIR / "scripts" / "lib" / "cursor.js").read_text()
LOCAL_STORAGE_JS = """(entries) => {
  for (const [k, v] of Object.entries(entries)) { try { localStorage.setItem(k, typeof v === 'string' ? v : JSON.stringify(v)) } catch {} }
}"""


def now() -> float:
    return time.perf_counter()


# ---------- static server for HTML scenes ----------

class SceneFiles(http.server.SimpleHTTPRequestHandler):
    """/skill/ serves the skill (scenes, vendored fonts and libraries); /project/ the consuming repo (a card's logo)."""

    mounts: dict[str, Path] = {}

    def translate_path(self, path: str) -> str:
        from urllib.parse import unquote

        path = unquote(path.split("?", 1)[0].split("#", 1)[0])
        for prefix, root in self.mounts.items():
            if path.startswith(prefix):
                f = (root / path[len(prefix):]).resolve()
                if f == root or root in f.parents:
                    return str(f)
        return str(SKILL_DIR / ".not-served")  # does not exist: a 404

    def log_message(self, *args) -> None:
        pass


SceneFiles.extensions_map = {**SceneFiles.extensions_map, ".js": "text/javascript", ".mjs": "text/javascript",
                             ".woff2": "font/woff2", ".webp": "image/webp"}


def start_server(root: Path) -> http.server.ThreadingHTTPServer:
    handler = type("Files", (SceneFiles,), {"mounts": {"/skill/": SKILL_DIR, "/project/": root.resolve()}})
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(handler, directory=str(SKILL_DIR)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


# ---------- pre-processing: command output and code ----------

class Prep:
    def __init__(self, run: Path, root: Path, refresh: bool):
        self.root = root
        self.cache_path = run / "cache" / "commands.json"
        self.cache = {} if refresh else read_json(self.cache_path, {})

    def run_command(self, cmd: str, cwd: Path, timeout: float) -> dict:
        key = f"{cwd}::{cmd}"
        if key in self.cache:
            return self.cache[key]
        print(f"  $ {cmd}", flush=True)
        # Windows has no /bin/bash: use Git Bash (DEMO_BASH overrides).
        shell = os.environ.get("DEMO_BASH") or ("C:/Program Files/Git/usr/bin/bash.exe" if platform.system() == "Windows" else "/bin/bash")
        env = {**os.environ, "FORCE_COLOR": "1", "CLICOLOR_FORCE": "1", "COLUMNS": "110"}
        try:
            p = subprocess.run([shell, "-c", cmd], cwd=cwd, env=env, capture_output=True, timeout=timeout)
            result = {"output": (p.stdout + p.stderr).decode("utf-8", "replace"), "exitCode": p.returncode}
        except subprocess.TimeoutExpired as e:
            result = {"output": ((e.stdout or b"") + (e.stderr or b"")).decode("utf-8", "replace"), "exitCode": 124}
        self.cache[key] = result
        write_json(self.cache_path, self.cache)
        return result

    @staticmethod
    def trim(text: str, max_lines: int | None) -> str:
        lines = text.rstrip().split("\n")
        if not max_lines or len(lines) <= max_lines:
            return "\n".join(lines)
        return "\n".join([*lines[:max_lines], f"\x1b[2m… {len(lines) - max_lines} more lines\x1b[0m"])

    def scene(self, scene: dict) -> None:
        lang = "text"
        for beat in scene["beats"]:
            for action in beat.get("do") or []:
                if scene["type"] == "terminal" and action.get("run"):
                    cwd = (self.root / (action.get("cwd") or scene.get("cwd") or ".")).resolve()
                    res = self.run_command(action["run"], cwd, action.get("timeout") or scene.get("timeout") or 60)
                    action["__output"] = self.trim(res["output"], action.get("maxLines", scene.get("maxLines", 40)))
                    if res["exitCode"] and not action.get("allowFail"):
                        raise RuntimeError(f"[{scene['id']}] command failed (exit {res['exitCode']}): {action['run']}\n"
                                           f"{res['output'][-1500:]}\nSet \"allowFail\": true to show a failing command on purpose.")
                    action["__exitCode"] = res["exitCode"]
                if scene["type"] == "code" and action.get("open"):
                    f = (self.root / action["open"]).resolve()
                    if not f.is_file():
                        raise FileNotFoundError(f"[{scene['id']}] code file not found: {action['open']}")
                    lines = f.read_text().removesuffix("\n").split("\n")
                    a, b = action.get("lines") or [1, len(lines)]
                    if b - a > 600:
                        raise ValueError(f"[{scene['id']}] {action['open']} has {len(lines)} lines; pass \"lines\": [start, end]")
                    lang = action.get("lang") or LANG_BY_EXT.get(f.suffix) or f.suffix[1:] or "text"
                    # Highlighting happens in the page (vendored shiki): pass the code and its language.
                    action["__file"] = {"code": "\n".join(lines[a - 1:b]), "firstLine": a, "lang": lang}


# ---------- auth for live sites ----------
# Each entry names an environment variable that holds the secret, so script.json never does:
#   { "header": "Authorization", "prefix": "Bearer ", "url": "https://app.example.com/**", "env": "DEMO_APP_TOKEN" }
#   { "cookie": "session", "domain": "app.example.com", "env": "DEMO_APP_SESSION" }
# A header is sent only to requests matching `url`; a cookie only to its domain.

async def apply_auth(context, entries: list[dict]) -> None:
    for e in entries:
        value = os.environ.get(e.get("env") or "")
        if not e.get("env") or not value:
            raise RuntimeError(f"auth: environment variable {e.get('env') or '(none named)'} is not set")
        if e.get("header"):
            if not e.get("url"):
                raise RuntimeError(f"auth: header {e['header']} needs a url pattern")
            name, val = e["header"].lower(), (e.get("prefix") or "") + value

            async def add_header(route, name=name, val=val):
                await route.continue_(headers={**route.request.headers, name: val})

            await context.route(e["url"], add_header)
        elif e.get("cookie"):
            if not e.get("domain"):
                raise RuntimeError(f"auth: cookie {e['cookie']} needs a domain")
            await context.add_cookies([{"name": e["cookie"], "value": value, "domain": e["domain"], "path": e.get("path") or "/",
                                        "secure": e.get("secure") is not False, "httpOnly": True}])
        else:
            raise RuntimeError(f"auth: entry needs header or cookie: { {**e, 'env': e.get('env')} }")


# ---------- scene recording ----------

class Recorder:
    def __init__(self, args, run: Path, script: dict, audio: dict, root: Path):
        self.args, self.run, self.script, self.audio, self.root = args, run, script, audio, root
        self.storyboard = bool(args.storyboard)
        self.speed = float(args.speed) if self.storyboard else 1.0
        self.fps = script.get("fps") or 30
        self.view = script.get("viewport") or {"width": 1920, "height": 1080}
        self.theme = script.get("theme") or "dark"
        self.light = self.theme.endswith("light")
        self.beat_gap = script.get("beatGap", 0.35)
        self.prep = Prep(run, root, args.refresh)

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(max(0.0, seconds / self.speed))

    async def open_scene(self, browser, scene: dict, port: int):
        context = await browser.new_context(viewport=self.view, device_scale_factor=1, color_scheme="light" if self.light else "dark")
        page = await context.new_page()
        page.on("pageerror", lambda e: print(f"  [{scene['id']}] page error: {e}", flush=True))
        if scene["type"] == "ui":
            await apply_auth(context, [*(self.script.get("auth") or []), *(scene.get("auth") or [])])
            ls = {**(self.script.get("localStorage") or {}), **(scene.get("localStorage") or {})}
            await context.add_init_script(f"({LOCAL_STORAGE_JS})({json.dumps(ls)})")
            await context.add_init_script(CURSOR_JS)
            driver = PageDriver(page, viewport=self.view, speed=self.speed, overlay="__demoOverlay",
                                base_url=scene.get("baseUrl") or self.script.get("baseUrl") or "")
            await driver.apply({"goto": scene["url"]})
            # ready: a selector string, or { "function": "<js expression that becomes truthy>" }
            if scene.get("ready"):
                ready = scene["ready"]
                await driver.apply({"waitFor": ready} if isinstance(ready, str) else {"waitForFunction": ready["function"]})
            for a in scene.get("prepare") or []:
                await driver.apply(a)
            await page.evaluate("() => window.__demoOverlay?.install()")
            return context, page, driver.apply
        await page.goto(f"http://127.0.0.1:{port}/skill/scenes/{scene['type']}.html")
        await page.evaluate("s => (window.__speed = s)", self.speed)
        meta = {k: v for k, v in scene.items() if k != "beats"}
        await page.evaluate("s => window.__scene.init(s)", {**meta, "theme": scene.get("theme") or self.theme})

        async def apply(a):
            await page.evaluate("x => window.__scene.apply(x)", a)

        for a in scene.get("prepare") or []:
            await apply(a)
        return context, page, apply

    def beat_seconds(self, scene: dict, i: int) -> float:
        a = self.audio.get(beat_key(scene["id"], i))
        return a["duration"] if a else estimate_seconds(scene["beats"][i].get("say"))

    async def record_scene(self, browser, scene: dict, port: int) -> dict:
        print(f"scene {scene['id']} ({scene['type']}){' [storyboard]' if self.storyboard else ''}", flush=True)
        # Snapshot of the scene as authored, so the review server can tell which scenes changed since.
        authored = copy.deepcopy(scene)
        self.prep.scene(scene)
        context, page, apply = await self.open_scene(browser, scene, port)
        scene_dir = self.run / "scenes" / scene["id"]
        frames_dir = scene_dir / "frames"
        frames: list[tuple[str, float]] = []
        writer = ThreadPoolExecutor(max_workers=1)  # JPEG writes off the event loop, so frame times stay even

        if not self.storyboard:
            shutil.rmtree(frames_dir, ignore_errors=True)
            frames_dir.mkdir(parents=True)
            first = asyncio.Event()

            def on_frame(frame) -> None:
                t = now()
                name = f"f{len(frames):06d}.jpg"
                frames.append((name, t))
                writer.submit((frames_dir / name).write_bytes, frame["data"])
                first.set()

            await page.screencast.start(size=self.view, quality=self.script.get("jpegQuality") or 90, on_frame=on_frame)
            # Nudge a repaint so a first frame arrives even on a static page.
            await page.evaluate("() => { document.body.style.outline = '0.01px solid transparent' }")
            try:
                await asyncio.wait_for(first.wait(), 3)
            except asyncio.TimeoutError:
                pass
            t0 = frames[0][1] if frames else now()
        else:
            t0 = now()

        beats = []
        await self.sleep(LEAD_IN)
        for i, beat in enumerate(scene["beats"]):
            start = now()
            dur = self.beat_seconds(scene, i)
            pause = beat.get("pause", self.beat_gap)
            if beat.get("sync") == "after":
                await self.sleep(dur)
            for a in beat.get("do") or []:
                try:
                    await apply(a)
                except Exception as e:
                    raise RuntimeError(f"[{scene['id']} beat {i}] action {str(a)[:200]} failed: {e}") from e
            min_end = start + max(dur, 0) / self.speed + pause / self.speed
            end = max(min_end, now() + beat.get("hold", 0.3) / self.speed)
            await asyncio.sleep(max(0.0, end - now()))
            beats.append({"index": i, "start": start - t0, "end": now() - t0, "say": beat.get("say") or ""})
            if self.storyboard:
                shot = self.run / "storyboard" / f"{scene['id']}.{i}.png"
                shot.parent.mkdir(parents=True, exist_ok=True)
                await page.screenshot(path=str(shot), animations="disabled")
        await self.sleep(LEAD_OUT)
        duration = now() - t0

        if not self.storyboard:
            await page.screencast.stop()
            writer.shutdown(wait=True)
            self.encode(frames, frames_dir, self.run / "scenes" / f"{scene['id']}.mp4", t0, duration)
            if not self.args.keep_frames:
                shutil.rmtree(scene_dir, ignore_errors=True)
        await context.close()
        return {"id": scene["id"], "type": scene["type"], "duration": duration, "beats": beats, "scene": authored}

    def encode(self, frames, frames_dir: Path, out: Path, t0: float, duration: float) -> None:
        if not frames:
            raise RuntimeError(f"no frames captured for {out}")
        lines = ["ffconcat version 1.0"]
        for i, (name, t) in enumerate(frames):
            nxt = frames[i + 1][1] - t0 if i + 1 < len(frames) else duration
            lines += [f"file '{name}'", f"duration {max(0.001, nxt - (t - t0)):.4f}"]
        lines.append(f"file '{frames[-1][0]}'")
        listing = frames_dir / "frames.ffconcat"
        listing.write_text("\n".join(lines) + "\n")
        w, h = self.view["width"], self.view["height"]
        p = subprocess.run([ffmpeg(), "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                            "-vf", f"fps={self.fps},scale={w}:{h}:flags=lanczos,format=yuv420p", "-t", f"{duration:.3f}",
                            "-c:v", "libx264", "-preset", "medium", "-crf", str(self.script.get("crf") or 18), str(out)],
                           capture_output=True, text=True)
        if p.returncode:
            raise RuntimeError(f"ffmpeg exited {p.returncode}\n{p.stderr[-3000:]}")


async def main_async(args) -> int:
    from playwright.async_api import async_playwright

    run, script, audio = load_run(args.run_dir)
    root = project_root()
    rec = Recorder(args, run, script, audio, root)
    only = set(args.scene.split(",")) if args.scene else None
    server = start_server(root)
    port = server.server_address[1]
    # Hardware WebGL by default (headless otherwise falls back to SwiftShader, which
    # makes 3D apps crawl under screencast). --software-gl opts out.
    gpu = [] if args.software_gl else ["--use-angle=gl", "--enable-gpu", "--ignore-gpu-blocklist"]
    out_name = "storyboard/storyboard.json" if rec.storyboard else "timeline.json"
    previous = read_json(run / out_name, {"scenes": []})
    results = {s["id"]: s for s in previous.get("scenes", [])}
    failed = None
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=not args.headed,
                                           args=["--autoplay-policy=no-user-gesture-required", "--hide-scrollbars", *gpu])
        try:
            for scene in script["scenes"]:
                if only and scene["id"] not in only:
                    continue
                results[scene["id"]] = await rec.record_scene(browser, scene, port)
        except Exception as e:  # report which scene failed; keep the scenes already recorded
            failed = e
        finally:
            await browser.close()
            server.shutdown()
    ordered = [results[s["id"]] for s in script["scenes"] if s["id"] in results]
    write_json(run / out_name, {"title": script["title"], "speed": rec.speed,
                                "recordedAt": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
                                "scenes": ordered})
    if failed:
        print(f"\nFAILED: {failed}", file=sys.stderr)
        return 1
    print(f"wrote {run / out_name}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--scene")
    ap.add_argument("--storyboard", action="store_true")
    ap.add_argument("--speed", default="12")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--keep-frames", action="store_true")
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--software-gl", action="store_true")
    return asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    sys.exit(main())
