"""Validate a script.json (the file or its run dir). Prints {"ok", "problems"} as JSON.

    python scripts/validate.py <script.json | run-dir>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import validate_script  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: validate.py <script.json | run-dir>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    if path.is_dir():
        path = path / "script.json"
    try:
        problems = validate_script(json.loads(path.read_text()))
    except (OSError, ValueError) as e:
        problems = [str(e)]
    print(json.dumps({"ok": not problems, "problems": problems}))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
