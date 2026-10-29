"""Agent-side access to a run's review state.

    review.py <run-dir>                                   open decisions + comments, and what needs re-rendering
    review.py <run-dir> --reply <id> "text" [--status addressed|resolved|wontfix]
    review.py <run-dir> --done <decision-id> ["reply"]    mark a change request handled
    review.py <run-dir> --comment "text" [--at 12.5]      leave a comment (e.g. agent notes)
    review.py <run-dir> --status <draft|storyboard-review|approved-to-record|video-review|done>
    review.py <run-dir> --json                            raw review.json + staleness
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import reviewlib as rl  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--reply", nargs=2, metavar=("ID", "TEXT"))
    ap.add_argument("--done", nargs="+", metavar="ID [REPLY]")
    ap.add_argument("--comment")
    ap.add_argument("--at", type=float)
    ap.add_argument("--status")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--advance", help=argparse.SUPPRESS)
    a = ap.parse_args()
    run = Path(a.run_dir).resolve()

    if a.advance:
        rl.advance_after(run, a.advance)
        return 0
    if a.reply:
        cid, text = a.reply
        status = a.status if a.status in rl.COMMENT_STATUSES else "addressed"
        rl.update_comment(run, cid, status=status, reply=text, author="agent")
        print(f"{cid}: {status}")
        return 0
    if a.done:
        rl.close_decision(run, a.done[0], " ".join(a.done[1:]))
        print(f"{a.done[0]}: done")
        return 0
    if a.comment:
        c = rl.add_comment(run, a.comment, t=a.at, author="agent")
        print(f"{c['id']} on {c.get('key')}")
        return 0
    if a.status:
        rl.set_status(run, a.status)
        print(f"status: {a.status}")
        return 0
    if a.json:
        print(json.dumps({"review": rl.load(run), "stale": rl.stale(run)}, indent=2))
        return 0
    print(rl.summary(run))
    return 0


if __name__ == "__main__":
    sys.exit(main())
