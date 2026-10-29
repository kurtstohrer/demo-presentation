# demo-presentation contract

- The skill is `skills/demo-presentation/`. Keep `SKILL.md` under ~200 lines; detail goes
  in `references/`. Its `name` matches its folder.
- Skill text and code stay project- and vendor-neutral: no names of private toolchains,
  trackers or agent hosts. `python3 scripts/check.py` enforces it.
- The CLI needs only `uv` and `git` on the machine. Python dependencies go in the skill's
  `pyproject.toml`/`uv.lock`; no Node, ffmpeg or espeak-ng installs.
- `skills/demo-presentation/ui/` is built from `apps/review-ui`, and `vendor/` from
  `apps/vendor`. Edit the source, rebuild, commit the build. CI fails on a stale build.
- The review UI uses `src/tokens.css` and the local `src/components/`: monochrome, one
  blue accent, red for errors, `dark` and `light` only.
- Version lives in `.claude-plugin/plugin.json`, `SKILL.md` `metadata.version` and the
  top `CHANGELOG.md` entry; `scripts/release.sh` keeps them together and tags `vX.Y.Z`.
- Never commit runs or caches (`.demo/runs`, `.demo/local`, `node_modules`).
