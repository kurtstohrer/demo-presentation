# Changelog

## 1.0.0 — 2026-10-28

First standalone release.

- The skill lives in `skills/demo-presentation/`; the repo is also a Claude Code plugin
  and its own marketplace.
- Project settings move to `.demo/`: `config.toml` (top-level keys, `[[services]]`,
  `[publish]`), `pronunciations.json`, `brief.md`, and gitignored `runs/` and `local/`.
- Cache moves to `~/.cache/demo-presentation` (`DEMO_CACHE` overrides).
- New `demo publish <run> [args]` runs the project's `[publish] command` with
  `$DEMO_RUN`, `$DEMO_VIDEO`, `$DEMO_CAPTIONS`, `$DEMO_TIMELINE` and `$DEMO_TITLE`.
- Themes are `dark` and `light`: monochrome with one blue accent, in the scenes and the
  review UI. The review UI's components are local (`apps/review-ui/src/components`) and
  build from public npm packages only.
