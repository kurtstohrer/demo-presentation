"""Demo review adapter: timeline anchors, workflow transitions and narration."""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

from core import review as core
from core.review import (
    COMMENT_STATUSES, close_decision, delete_comment, empty_review, locked,
    new_id, now_iso, read_json, update_comment, write_json,
)

STATUSES = ["draft", "storyboard-review", "approved-to-record", "video-review", "done"]
DEFAULT_VOICE = "af_heart"


def load(run: Path) -> dict:
    review = core.load(run)
    # Supply the UI's legacy fields even for anchor-only records; no migration
    # occurs on disk, and arbitrary anchor/extension fields survive mutations.
    for c in review["comments"]:
        anchor = core.comment_anchor(c)
        for field in ("t", "key", "region"):
            c[field] = anchor.get(field)
    return review


def add_comment(run: Path, text: str, t: float | None = None, key: str | None = None,
                region: dict | None = None, author: str = "reviewer", *, anchor: dict | None = None) -> dict:
    if anchor is not None and not isinstance(anchor, dict):
        raise ValueError("anchor must be an object")
    anchor = dict(anchor or {})
    t = anchor.get("t", t)
    key = anchor.get("key", key)
    if t is not None and not key:
        key = beat_at(run, float(t))
        anchor["key"] = key
    return core.add_comment(run, text, t, key, region, author, anchor=anchor, legacy_fields=True)


def add_decision(run: Path, scope: str, key: str | None, decision: str, note: str = "", author: str = "reviewer") -> dict:
    return core.add_decision(run, scope, key, decision, note, author, scopes=("run", "scene", "beat"),
                             approval_transitions={"draft": "approved-to-record", "storyboard-review": "approved-to-record",
                                                   "video-review": "done"})


def set_status(run: Path, status: str) -> None:
    core.set_status(run, status, statuses=STATUSES)


def snapshot_version(run: Path) -> int:
    return core.snapshot_version(run, ("script.json", "final.json"), transition=lambda review: _advance(review, "stitch"))


def beat_at(run: Path, t: float) -> str | None:
    final = read_json(run / "final.json", None)
    if not final:
        return None
    for scene in final["scenes"]:
        if scene["start"] <= t < scene["end"]:
            best = None
            for b in scene["beats"]:
                if b["start"] <= t:
                    best = b["key"]
            return best or (scene["beats"][0]["key"] if scene["beats"] else None)
    return None


def beat_text(script: dict, key: str) -> str:
    scene_id, _, idx = key.rpartition(".")
    for s in script.get("scenes", []):
        if s["id"] == scene_id and idx.isdigit() and int(idx) < len(s["beats"]):
            return s["beats"][int(idx)].get("say", "")
    return ""


def advance_after(run: Path, job: str) -> None:
    """Status transitions that follow from a finished render step."""
    with locked(run) as review:
        _advance(review, job)


def _advance(review: dict, job: str) -> None:
    if job == "storyboard" and review["status"] == "draft":
        review["status"] = "storyboard-review"
    if job == "stitch" and review["status"] in ("draft", "storyboard-review", "approved-to-record", "done"):
        review["status"] = "video-review"


# ---------- staleness: what needs re-rendering after script edits ----------

# ---------- pronunciation: the project library + the script's lexicon ----------

def library_path(run: Path | None = None) -> Path:
    """The project's pronunciation library, shared by every run (committed with the project)."""
    if os.environ.get("DEMO_LEXICON"):
        return Path(os.environ["DEMO_LEXICON"])
    if os.environ.get("DEMO_PROJECT_ROOT"):
        return Path(os.environ["DEMO_PROJECT_ROOT"]) / ".demo" / "pronunciations.json"
    # runs live at <root>/.demo/runs/<name>
    return (run.parent.parent if run else Path.cwd() / ".demo") / "pronunciations.json"


def load_library(run: Path | None = None) -> dict[str, str]:
    data = read_json(library_path(run), {}) or {}
    return {str(k): str(v) for k, v in data.items() if str(k).strip() and str(v).strip()}


def lexicon_for(run: Path, script: dict) -> dict[str, str]:
    """Effective lexicon: the library wins over the script's own entries."""
    return {**script.get("lexicon", {}), **load_library(run)}


def say_as(word: str, say: str) -> str:
    """A lexicon value is a sound-alike respelling, or /IPA/ phonemes passed to Kokoro as [word](/ipa/)."""
    say = say.strip()
    return f"[{word}]({say})" if len(say) > 2 and say[0] == say[-1] == "/" else say


def spoken_map(text: str, lexicon: dict) -> tuple[str, list[int]]:
    """Spoken text after lexicon substitution, plus for each spoken char the index of the
    whitespace-separated word of `text` it came from (-1 between words)."""
    owner = [-1] * len(text)
    for i, m in enumerate(re.finditer(r"\S+", text)):
        owner[m.start():m.end()] = [i] * (m.end() - m.start())
    keys = sorted((k for k in lexicon if k), key=len, reverse=True)
    if not keys:
        return text, owner
    out, cmap, last = [], [], 0
    for m in re.finditer(r"\b(?:" + "|".join(re.escape(k) for k in keys) + r")\b", text):
        out.append(text[last:m.start()])
        cmap += owner[last:m.start()]
        rep = say_as(m.group(0), lexicon[m.group(0)])
        out.append(rep)
        cmap += [owner[m.start()]] * len(rep)
        last = m.end()
    out.append(text[last:])
    cmap += owner[last:]
    return "".join(out), cmap


def spoken_text(text: str, lexicon: dict) -> str:
    return spoken_map(text, lexicon)[0]


def narration_hash(voice: str, speed: float, spoken: str) -> str:
    return hashlib.sha1(f"{voice}|{speed}|{spoken}".encode()).hexdigest()[:16]


def proportional_words(text: str, duration: float, start: float = 0.0) -> list[dict]:
    """Fallback word timing: spread the words over the audio by character count."""
    words = text.split()
    total = sum(len(w) + 1 for w in words) or 1
    out, t = [], start
    for w in words:
        d = duration * (len(w) + 1) / total
        out.append({"w": w, "s": round(t, 3), "e": round(t + d, 3)})
        t += d
    return out


def align_words(text: str, spoken: str, cmap: list[int], tokens: list[tuple[str, float, float]], duration: float) -> list[dict]:
    """Map TTS tokens (text, start, end) on the spoken text back to the words of the original text."""
    words = text.split()
    if not words:
        return []
    times: list[list[float] | None] = [None] * len(words)
    cursor = 0
    for tok, s, e in tokens:
        tok = tok.strip()
        at = spoken.find(tok, cursor) if tok else -1
        if at < 0:
            continue
        cursor = at + len(tok)
        wi = next((cmap[j] for j in range(at, cursor) if cmap[j] >= 0), -1)
        if wi < 0:
            continue
        cur = times[wi]
        times[wi] = [min(cur[0], s), max(cur[1], e)] if cur else [s, e]
    if not any(times):
        return proportional_words(text, duration)
    # Words the TTS gave no time (lone punctuation, skipped tokens) get the gap next to them.
    out = []
    for i, w in enumerate(words):
        if times[i] is None:
            prev = next((times[j][1] for j in range(i - 1, -1, -1) if times[j]), 0.0)
            nxt = next((times[j][0] for j in range(i + 1, len(words)) if times[j]), duration)
            times[i] = [prev, max(prev, nxt)]
        s, e = times[i]
        out.append({"w": w, "s": round(max(0.0, s), 3), "e": round(min(duration, max(s, e)), 3)})
    return out


def stale(run: Path) -> dict:
    script = read_json(run / "script.json", {}) or {}
    audio = read_json(run / "audio" / "audio.json", {}) or {}
    timeline = read_json(run / "timeline.json", {"scenes": []}) or {"scenes": []}
    board = read_json(run / "storyboard" / "storyboard.json", {"scenes": []}) or {"scenes": []}
    voice = script.get("voice", DEFAULT_VOICE)
    speed = float(script.get("speed", 1.0))
    lexicon = lexicon_for(run, script)

    narration = []
    for s in script.get("scenes", []):
        for i, b in enumerate(s.get("beats", [])):
            say = (b.get("say") or "").strip()
            if not say:
                continue
            bv = b.get("voice", s.get("voice", voice))
            digest = narration_hash(bv, speed, spoken_text(say, lexicon))
            key = f"{s['id']}.{i}"
            if audio.get(key, {}).get("hash") != digest:
                narration.append(key)

    def changed(recorded: dict) -> list[str]:
        by_id = {x["id"]: x for x in recorded.get("scenes", [])}
        return [s["id"] for s in script.get("scenes", []) if by_id.get(s["id"], {}).get("scene") != s]

    narrated_scenes = sorted({k.rpartition(".")[0] for k in narration})
    record = sorted(set(changed(timeline)) | set(narrated_scenes), key=[s["id"] for s in script.get("scenes", [])].index)
    final = run / "final.mp4"
    newest_input = max([p.stat().st_mtime for p in (run / "scenes").glob("*.mp4")] + [0])
    return {
        "narration": narration,
        "record": record,
        "storyboard": changed(board),
        "stitch": bool(record) or not final.exists() or final.stat().st_mtime < newest_input,
    }


def summary(run: Path) -> str:
    """Plain-text digest of open review items, for the agent."""
    review = load(run)
    script = read_json(run / "script.json", {}) or {}
    out = [f"run: {run.name}  status: {review['status']}  version: {review['version']}"]
    st = stale(run)
    needs = [f"tts {len(st['narration'])} beats" if st["narration"] else "", f"record {','.join(st['record'])}" if st["record"] else "",
             "stitch" if st["stitch"] else ""]
    if any(needs):
        out.append("needs: " + "; ".join(n for n in needs if n))
    decisions = [d for d in review["decisions"] if d.get("state") == "open"]
    comments = [c for c in review["comments"] if c["status"] == "open"]
    if not decisions and not comments:
        out.append("no open review items")
        return "\n".join(out)
    for d in decisions:
        target = d.get("key") or "whole demo"
        out.append(f"\n[{d['id']}] CHANGES REQUESTED on {d['scope']} {target} (v{d['version']})")
        if d["scope"] == "beat":
            out.append(f"    narration: \"{beat_text(script, d['key'])}\"")
        if d.get("note"):
            out.append(f"    note: {d['note']}")
    for c in sorted(comments, key=lambda c: (c["t"] is None, c["t"] or 0)):
        when = f"@{c['t']:.1f}s " if c["t"] is not None else ""
        out.append(f"\n[{c['id']}] {when}beat {c.get('key') or '?'} (v{c['version']})")
        if c.get("key"):
            out.append(f"    narration: \"{beat_text(script, c['key'])}\"")
        if c.get("region"):
            r = c["region"]
            out.append(f"    region: x={r['x']:.2f} y={r['y']:.2f} w={r['w']:.2f} h={r['h']:.2f} (fractions of the frame)")
        out.append(f"    comment: {c['text']}")
        for rep in c.get("replies", []):
            out.append(f"    ↳ {rep['author']}: {rep['text']}")
    return "\n".join(out)
