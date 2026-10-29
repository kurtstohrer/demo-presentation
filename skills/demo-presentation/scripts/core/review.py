"""Lossless review state, threads and snapshots; workflow policy belongs to callers."""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import time
import uuid
import tempfile
import math
import copy
from pathlib import Path

# Windows has no fcntl; msvcrt locks a byte range of the lock file instead.
try:
    import fcntl  # type: ignore

    def _lock(f):
        fcntl.flock(f, fcntl.LOCK_EX)

    def _unlock(f):
        fcntl.flock(f, fcntl.LOCK_UN)
except ImportError:
    import msvcrt  # type: ignore

    def _lock(f):
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)

    def _unlock(f):
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)

COMMENT_STATUSES = ["open", "addressed", "resolved", "wontfix"]


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    # Unique siblings also make independent thread writers safe. Replacement is
    # atomic; read-modify-write callers must additionally hold locked().
    tmp = None
    try:
        with tempfile.NamedTemporaryFile("w", dir=path.parent, prefix=path.name + ".", suffix=".tmp",
                                         encoding="utf-8", delete=False) as f:
            tmp = Path(f.name)
            json.dump(value, f, indent=2, ensure_ascii=False)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        # NamedTemporaryFile creates 0600; keep the umask mode a plain write would give.
        umask = os.umask(0)
        os.umask(umask)
        tmp.chmod(0o666 & ~umask)
        tmp.replace(path)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def empty_review() -> dict:
    return {"status": "draft", "version": 0, "decisions": [], "comments": []}


@contextlib.contextmanager
def locked(run: Path, *, write: bool = True):
    """Exclusive snapshot or read-modify-write of review.json across processes."""
    run.mkdir(parents=True, exist_ok=True)
    with open(run / ".review.lock", "a+") as lock:
        _lock(lock)
        try:
            review = read_json(run / "review.json", None) or empty_review()
            yield review
            if write:
                write_json(run / "review.json", review)
        finally:
            _unlock(lock)


def load(run: Path) -> dict:
    return read_json(run / "review.json", None) or empty_review()


def new_id(prefix: str) -> str:
    return f"{prefix}{uuid.uuid4().hex[:6]}"


def normalized_region(region: dict | None) -> dict | None:
    """Validate a fractional rectangle without discarding extension fields."""
    if region is None:
        return None
    if not isinstance(region, dict):
        raise ValueError("region must be an object")
    result = copy.deepcopy(region)
    for key in ("x", "y", "w", "h"):
        value = result.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"region.{key} must be a finite fraction between 0 and 1")
    if result["x"] + result["w"] > 1 + 1e-9 or result["y"] + result["h"] > 1 + 1e-9:
        raise ValueError("region must fit within the frame")
    return result


def comment_anchor(comment: dict) -> dict:
    """Project legacy fields into an anchor without migrating the stored record.

    Explicit anchor fields win; unknown fields in either form are retained.
    """
    anchor = copy.deepcopy(comment.get("anchor") or {})
    for key in ("t", "key", "region"):
        if key in comment:
            anchor.setdefault(key, copy.deepcopy(comment[key]))
    return anchor


def add_comment(run: Path, text: str, t: float | None = None, key: str | None = None,
                region: dict | None = None, author: str = "reviewer", *,
                anchor: dict | None = None, legacy_fields: bool = False) -> dict:
    if anchor is not None and not isinstance(anchor, dict):
        raise ValueError("anchor must be an object")
    anchor = copy.deepcopy(anchor) if anchor is not None else {}
    for field, value in (("t", t), ("key", key), ("region", region)):
        if value is not None:
            anchor.setdefault(field, value)
    if anchor.get("t") is not None:
        anchor["t"] = round(float(anchor["t"]), 2)
        if not math.isfinite(anchor["t"]):
            raise ValueError("anchor.t must be finite")
    if anchor.get("region") is not None:
        anchor["region"] = normalized_region(anchor["region"])
    with locked(run) as review:
        c = {"id": new_id("c"), "anchor": anchor,
             "text": text.strip(), "status": "open", "author": author, "version": review["version"],
             "at": now_iso(), "replies": []}
        if legacy_fields:
            c.update({field: anchor.get(field) for field in ("t", "key", "region")})
        review["comments"].append(c)
    return c


def update_comment(run: Path, cid: str, status: str | None = None, reply: str | None = None,
                   author: str = "agent", text: str | None = None) -> dict:
    if status and status not in COMMENT_STATUSES:
        raise ValueError(f"status must be one of {COMMENT_STATUSES}")
    with locked(run) as review:
        for c in review["comments"]:
            if c["id"] == cid:
                if status:
                    c["status"] = status
                if text is not None:
                    c["text"] = text.strip()
                if reply:
                    c.setdefault("replies", []).append({"author": author, "text": reply.strip(), "at": now_iso()})
                return c
    raise KeyError(cid)


def delete_comment(run: Path, cid: str) -> None:
    with locked(run) as review:
        review["comments"] = [c for c in review["comments"] if c["id"] != cid]


def add_decision(run: Path, scope: str, key: str | None, decision: str, note: str = "", author: str = "reviewer",
                 *, scopes=None, approval_transitions=None) -> dict:
    if (scopes is not None and scope not in scopes) or decision not in ("approve", "changes"):
        raise ValueError(f"scope must be one of {scopes} and decision approve|changes")
    with locked(run) as review:
        # A newer decision on the same target supersedes the old one.
        for d in review["decisions"]:
            if d["scope"] == scope and d.get("key") == key and d.get("state", "open") == "open":
                d["state"] = "superseded"
        d = {"id": new_id("d"), "scope": scope, "key": key, "decision": decision, "note": note.strip(),
             "author": author, "version": review["version"], "at": now_iso(),
             "state": "open" if decision == "changes" else "done"}
        review["decisions"].append(d)
        if scope == "run" and decision == "approve":
            review["status"] = (approval_transitions or {}).get(review["status"], review["status"])
    return d


def close_decision(run: Path, did: str, reply: str = "") -> dict:
    with locked(run) as review:
        for d in review["decisions"]:
            if d["id"] == did:
                d["state"] = "done"
                if reply:
                    d["reply"] = reply.strip()
                return d
    raise KeyError(did)


def set_status(run: Path, status: str, *, statuses=None) -> None:
    if statuses is not None and status not in statuses:
        raise ValueError(f"status must be one of {statuses}")
    with locked(run) as review:
        review["status"] = status


def snapshot_version(run: Path, files: tuple[str, ...], *, transition=None) -> int:
    """Publish a snapshot and its version under the same review lock.

    Copy failure leaves the review untouched. Earlier snapshots are immutable.
    transition, if supplied, mutates review state inside this transaction.
    """
    dest = None
    try:
        with locked(run) as review:
            v = review["version"] + 1
            candidate = run / "versions" / str(v)
            candidate.mkdir(parents=True, exist_ok=False)
            dest = candidate
            for name in files:
                if (run / name).exists():
                    (dest / name).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(run / name, dest / name)
            review["version"] = v
            review.setdefault("versions", []).append({"version": v, "at": now_iso()})
            if transition:
                transition(review)
    except BaseException:
        if dest is not None:
            shutil.rmtree(dest)
        raise
    return v


def list_versions(run: Path) -> list[Path]:
    return sorted((p for p in (run / "versions").glob("*") if p.is_dir() and p.name.isdigit()),
                  key=lambda p: int(p.name))


def load_version(run: Path, version: int, files: tuple[str, ...]) -> dict:
    dest = run / "versions" / str(version)
    if not dest.is_dir():
        raise KeyError(version)
    return {name: read_json(dest / name, None) for name in files}
