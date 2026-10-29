"""Stitch recorded scenes and narration into the final video.

    uv run scripts/stitch.py <run-dir> [--no-captions] [--out final.mp4]

Inputs:  timeline.json (record.mjs), scenes/<id>.mp4, audio/audio.json (tts.py)
Outputs: narration.wav, captions.srt, chapters.txt, final.json (global timeline
         that the review UI and the agent use to map timestamps to beats), final.mp4
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent))
import reviewlib  # noqa: E402
from common import SKILL_DIR, ffmpeg  # noqa: E402

SAMPLE_RATE = 24000
FADE = 0.25
MAX_CAPTION = 84


def fmt_srt(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02}:{m:02}:{s:02},{ms:03}"


def fmt_chapter(t: float) -> str:
    m, s = divmod(int(t), 60)
    return f"{m}:{s:02}"


def caption_chunks(text: str) -> list[str]:
    """Split narration into caption-sized phrases, preferring sentence and clause breaks."""
    out: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
        words, cur = sentence.split(), ""
        for w in words:
            if cur and len(cur) + 1 + len(w) > MAX_CAPTION:
                out.append(cur)
                cur = w
            else:
                cur = f"{cur} {w}".strip()
            if cur.endswith((",", ";", ":", "—")) and len(cur) > MAX_CAPTION * 0.55:
                out.append(cur)
                cur = ""
        if cur:
            out.append(cur)
    return out


def wrap2(text: str, width: int = 44) -> str:
    if len(text) <= width:
        return text
    mid = len(text) // 2
    cut = min((i for i, ch in enumerate(text) if ch == " "), key=lambda i: abs(i - mid), default=mid)
    return text[:cut] + "\n" + text[cut + 1 :]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--no-captions", action="store_true")
    ap.add_argument("--out", default="final.mp4")
    a = ap.parse_args()
    run = Path(a.run_dir).resolve()
    script = json.loads((run / "script.json").read_text())
    timeline = json.loads((run / "timeline.json").read_text())
    audio = json.loads((run / "audio" / "audio.json").read_text()) if (run / "audio" / "audio.json").exists() else {}

    recorded = {s["id"]: s for s in timeline["scenes"]}
    missing = [s["id"] for s in script["scenes"] if s["id"] not in recorded or not (run / "scenes" / f"{s['id']}.mp4").exists()]
    if missing:
        print(f"not recorded yet: {', '.join(missing)} — run record first", file=sys.stderr)
        return 1

    # Global timeline: scene offsets are cumulative because fades do not overlap scenes.
    scenes_out, offset = [], 0.0
    beats_by_key = {(s["id"], i): b for s in script["scenes"] for i, b in enumerate(s["beats"])}
    for scene in script["scenes"]:
        rec = recorded[scene["id"]]
        beats = []
        for b in rec["beats"]:
            key = f"{scene['id']}.{b['index']}"
            say = beats_by_key[(scene["id"], b["index"])].get("say", "")
            meta = audio.get(key, {})
            start = round(offset + b["start"], 3)
            # Word timings from tts (Kokoro tokens); older narration falls back to proportional timing.
            words = meta.get("words") or []
            if len(words) != len(say.split()):
                words = reviewlib.proportional_words(say, meta.get("duration", 0))
            beats.append({
                "key": key, "index": b["index"], "start": start, "end": round(offset + b["end"], 3),
                "say": say, "audio": meta.get("duration", 0),
                "words": [{"w": w["w"], "s": round(start + w["s"], 3), "e": round(start + w["e"], 3)} for w in words],
            })
        scenes_out.append({"id": scene["id"], "type": scene["type"], "title": scene.get("title", scene["id"]), "start": round(offset, 3),
                           "end": round(offset + rec["duration"], 3), "beats": beats})
        offset += rec["duration"]
    total = offset

    # Narration track, sample-accurate.
    track = np.zeros(int(total * SAMPLE_RATE) + SAMPLE_RATE, dtype=np.float32)
    for s in scenes_out:
        for b in s["beats"]:
            meta = audio.get(b["key"])
            if not meta:
                continue
            data, sr = sf.read(run / "audio" / meta["file"], dtype="float32")
            if sr != SAMPLE_RATE:
                raise SystemExit(f"unexpected sample rate {sr} in {meta['file']}")
            i = int(b["start"] * SAMPLE_RATE)
            track[i : i + len(data)] += data[: len(track) - i]
    peak = float(np.max(np.abs(track))) or 1.0
    track = track / max(peak, 1.0) * 0.98 if peak > 0.98 else track
    sf.write(run / "narration.wav", track[: int(total * SAMPLE_RATE)], SAMPLE_RATE)

    # Captions: phrases timed by their words; each runs until the next phrase starts.
    cues = []
    for s in scenes_out:
        for b in s["beats"]:
            if not b["say"] or not b["audio"]:
                continue
            words, i = b["words"], 0
            for c in caption_chunks(b["say"]):
                n = len(c.split())
                end = words[i + n]["s"] if i + n < len(words) else b["start"] + b["audio"]
                cues.append((words[i]["s"], end, wrap2(c)))
                i += n
    (run / "captions.srt").write_text("".join(f"{n}\n{fmt_srt(s)} --> {fmt_srt(e)}\n{txt}\n\n" for n, (s, e, txt) in enumerate(cues, 1)))
    (run / "chapters.txt").write_text("".join(f"{fmt_chapter(s['start'])} {s['title']}\n" for s in scenes_out))
    final = {"title": script["title"], "duration": round(total, 3), "video": a.out, "scenes": scenes_out}
    (run / "final.json").write_text(json.dumps(final, indent=2) + "\n")

    # Video: fade each scene, concat, burn captions, mux narration.
    cmd = [ffmpeg(), "-y", "-loglevel", "error"]
    parts = []
    for i, s in enumerate(scenes_out):
        cmd += ["-i", f"scenes/{s['id']}.mp4"]
        d = s["end"] - s["start"]
        parts.append(f"[{i}:v]fade=t=in:st=0:d={FADE},fade=t=out:st={max(0, d - FADE):.3f}:d={FADE},setsar=1[v{i}]")
    n = len(scenes_out)
    cmd += ["-i", "narration.wav"]
    vf = ";".join(parts) + ";" + "".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[cat]"
    if not a.no_captions and script.get("captions", True) and cues:
        style = "FontName=Inter,FontSize=10,PrimaryColour=&H00FFFFFF,OutlineColour=&H90000000,BorderStyle=3,Outline=4,Shadow=0,MarginV=22"
        # libass finds Inter in the vendored TTF, not in whatever the system has installed.
        fonts = (SKILL_DIR / "vendor" / "fonts").as_posix().replace(":", "\\:")
        vf += f";[cat]subtitles=captions.srt:fontsdir='{fonts}':force_style='{style}'[outv]"
    else:
        vf += ";[cat]null[outv]"
    vf += f";[{n}:a]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[aout]"
    cmd += ["-filter_complex", vf, "-map", "[outv]", "-map", "[aout]", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-t", f"{total:.3f}", a.out]
    subprocess.run(cmd, cwd=run, check=True)
    version = reviewlib.snapshot_version(run)
    final["version"] = version
    (run / "final.json").write_text(json.dumps(final, indent=2) + "\n")
    print(f"version {version}")
    print(f"final video: {run / a.out} ({total:.1f}s, {len(cues)} captions, {n} scene{'s' if n != 1 else ''})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
