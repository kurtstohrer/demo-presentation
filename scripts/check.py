#!/usr/bin/env python3
"""Repository gate: python3 scripts/check.py [--tag vX.Y.Z]

Static checks that need no Node or network. CI also rebuilds apps/review-ui and
apps/vendor and fails when the committed skill/ui or skill/vendor differs.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/demo-presentation"
PROBLEMS: list[str] = []

# Names of the private toolchain this skill was split out of; none may come back.
# Spelled in pieces so this file does not trip its own check.
FORBIDDEN = re.compile("|".join([r"wild" + r"\s?ride", "alma" + "nac", "an" + "vil", "nexus" + r"\.", r"@wild" + "ride"]), re.I)
TEXT_SUFFIXES = {".md", ".py", ".js", ".mjs", ".ts", ".vue", ".css", ".html", ".json", ".toml", ".yml", ".yaml", ".txt", ""}


def fail(msg: str) -> None:
    PROBLEMS.append(msg)


def tracked_files() -> list[Path]:
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        return [ROOT / p for p in out.split("\0") if p]
    except (OSError, subprocess.CalledProcessError):
        return [p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts and "node_modules" not in p.parts]


def frontmatter(path: Path) -> dict[str, str]:
    text = path.read_text()
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        k, _, v = line.partition(":")
        if k.strip() and not line.startswith(" "):
            out[k.strip()] = v.strip()
        elif line.strip().startswith("version:"):
            out["metadata.version"] = v.strip().strip('"')
    return out


def check_branding() -> None:
    for f in tracked_files():
        if f.suffix not in TEXT_SUFFIXES or f.name.endswith(".lock") or f.name == "package-lock.json" or "/vendor/" in f.as_posix():
            continue
        if f == Path(__file__).resolve() or not f.is_file():
            continue
        for n, line in enumerate(f.read_text(errors="ignore").splitlines(), 1):
            if FORBIDDEN.search(line):
                fail(f"{f.relative_to(ROOT)}:{n}: names the private toolchain: {line.strip()[:120]}")


def check_skill() -> dict[str, str]:
    md = SKILL / "SKILL.md"
    fm = frontmatter(md)
    if fm.get("name") != SKILL.name:
        fail(f"SKILL.md name {fm.get('name')!r} must match its folder {SKILL.name!r}")
    if not 1 <= len(fm.get("description", "")) <= 1024:
        fail("SKILL.md description must be 1-1024 characters")
    if len(md.read_text().splitlines()) > 220:
        fail("SKILL.md is over ~200 lines: move detail into references/")
    for f in (SKILL / "scripts").iterdir():
        if f.is_file() and not f.suffix and f.read_text(errors="ignore").startswith("#!") and not f.stat().st_mode & 0o111:
            fail(f"{f.relative_to(ROOT)}: has a shebang but is not executable")
    return fm


def check_versions(fm: dict[str, str], tag: str | None) -> None:
    plugin = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
    market = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
    version = plugin.get("version", "")
    if fm.get("metadata.version") != version:
        fail(f"SKILL.md metadata.version {fm.get('metadata.version')!r} != plugin.json version {version!r}")
    names = [p.get("name") for p in market.get("plugins", [])]
    if plugin.get("name") not in names:
        fail(f"marketplace.json does not list plugin {plugin.get('name')!r}")
    changelog = (ROOT / "CHANGELOG.md").read_text()
    m = re.search(r"^## \[?(\d+\.\d+\.\d+)", changelog, re.M)
    if not m or m.group(1) != version:
        fail(f"CHANGELOG.md's newest entry {m.group(1) if m else None!r} != plugin.json version {version!r}")
    if tag and tag.removeprefix("v") != version:
        fail(f"tag {tag} != plugin.json version {version}")


def check_review_ui() -> None:
    """The review UI ships prebuilt (apps/review-ui builds into the skill): it must exist and be complete."""
    ui = SKILL / "ui"
    index = ui / "index.html"
    if not index.is_file():
        fail("skills/demo-presentation/ui/index.html missing: run `npm run build` in apps/review-ui")
        return
    refs = re.findall(r'(?:src|href)="\./(assets/[^"]+)"', index.read_text())
    if not refs:
        fail("skills/demo-presentation/ui/index.html references no built assets")
    for ref in refs:
        if not (ui / ref).is_file():
            fail(f"skills/demo-presentation/ui/{ref} is referenced but missing: rebuild apps/review-ui")


def check_vendor() -> None:
    """Scenes load fonts and libraries from the skill's vendor/ (apps/vendor builds it): every reference must exist."""
    for f in (SKILL / "scenes").glob("*"):
        text = f.read_text()
        for ref in re.findall(r"/skill/(vendor/[^'\")\s]+)", text):
            if not (SKILL / ref).is_file():
                fail(f"scenes/{f.name} loads /skill/{ref}, which is missing: run `npm run build` in apps/vendor")
        if "/nm/" in text:
            fail(f"scenes/{f.name} loads from /nm/: scenes use the vendored files under /skill/vendor/")
    css = SKILL / "vendor/fonts.css"
    for ref in re.findall(r"url\(\./([^)]+)\)", css.read_text() if css.is_file() else ""):
        if not (css.parent / ref).is_file():
            fail(f"vendor/fonts.css references {ref}, which is missing: rebuild apps/vendor")


def check_json() -> None:
    for f in [*SKILL.glob("examples/*.json"), SKILL / "templates/script.json", *ROOT.glob(".claude-plugin/*.json")]:
        try:
            json.loads(f.read_text())
        except json.JSONDecodeError as e:
            fail(f"{f.relative_to(ROOT)}: {e}")


def main() -> int:
    tag = sys.argv[sys.argv.index("--tag") + 1] if "--tag" in sys.argv else None
    check_branding()
    fm = check_skill()
    check_versions(fm, tag)
    check_review_ui()
    check_vendor()
    check_json()
    for p in PROBLEMS:
        print(f"FAIL {p}")
    print("ok" if not PROBLEMS else f"{len(PROBLEMS)} problem(s)")
    return 1 if PROBLEMS else 0


if __name__ == "__main__":
    sys.exit(main())
