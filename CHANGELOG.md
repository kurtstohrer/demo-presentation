# Changelog

## 1.2.0 — 2026-10-29

- New `chat` scene type: someone prompting an agent. The user's message is typed into a
  message box and sent, replies stream in, and the commands the agent runs show as rows
  with their result (`user`, `agent`, `thinking`, `tool`, `clear`). Neutral look, both
  themes; see `references/script-format.md` and `examples/agent-chat.json`.
- The validator checks chat actions; the review UI's timeline colours chat scenes.

## 1.1.0 — 2026-10-29

- Captions go into `final.mp4` as a soft subtitle track (`mov_text`, English) that
  players switch on and off. They are never burned into the frames; `captions.srt` is
  still written next to the video, and `stitch --no-captions` leaves the track out.
- `demo doctor` no longer checks ffmpeg for libass.
- README: two videos made with the skill, and a step-by-step Use section.

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
