# demo-presentation

An agent skill that turns a topic (a feature, a PR, a concept) into a 1–5 minute narrated
MP4, then hands you a local review page to comment on it.

- **Scenes:** a hand-drawn whiteboard, a terminal running real commands, a code editor
  showing real files, live Playwright walkthroughs of your app, and title cards.
- **Narration:** Kokoro TTS on CPU, with a per-project pronunciation library.
- **Output:** `final.mp4` with burned-in captions, chapters, and a timeline that maps every
  beat to its time in the video.
- **Review:** a local web UI with the video, a live transcript, comments pinned to times and
  screen regions, script and storyboard editing, and re-render buttons. The agent reads
  your feedback with `demo review` and re-renders only what changed.

It needs only `uv` and `git`. Python, Chromium, ffmpeg and the voice model install on first
use (~1.3 GB, once).

## Install

**Claude Code** (plugin). At the prompt:

```
/plugin install demo-presentation --marketplace kurtstohrer/demo-presentation
```

From a shell: `claude plugin install demo-presentation --marketplace kurtstohrer/demo-presentation`.

**Any agent that reads Agent Skills** (`SKILL.md`):

```bash
npx skills add kurtstohrer/demo-presentation
```

**By hand:** download `demo-presentation-vX.Y.Z.zip` from
[Releases](https://github.com/kurtstohrer/demo-presentation/releases) and unzip it into your
agent's skills directory, or copy `skills/demo-presentation/` from a checkout.

## Use

Ask your agent for a video: *"make a demo video of the new settings page"*, *"record a
walkthrough of this PR"*. The skill writes a `script.json`, checks a storyboard, records,
and gives you the review link.

The CLI behind it is `skills/demo-presentation/scripts/demo`:

```bash
demo doctor               # what is installed, what will install on first use
demo new intro            # .demo/runs/intro/script.json
demo storyboard intro     # one screenshot per beat, in seconds
demo build intro          # narrate + record + stitch -> final.mp4
demo url intro            # local review UI link
demo review intro         # open comments and change requests, mapped to beats
```

## Project settings

Everything a project configures lives in `.demo/` at its root:

| path | what | commit it |
|---|---|---|
| `.demo/config.toml` | `base_url`, `theme` (`dark`/`light`), `voice`, `lexicon`, `logo`, `[[services]]`, `[publish]` | yes |
| `.demo/brief.md` | what the agent may show: routes, selectors, safe commands | yes |
| `.demo/pronunciations.json` | `{"word": "say it as"}`, edited from the review UI | yes |
| `.demo/runs/`, `.demo/local/` | one folder per video; service logs | no (gitignore) |

```toml
# .demo/config.toml
base_url = "http://localhost:5173"
theme = "dark"
voice = "af_heart"

[[services]]
name = "web"
start = "npm run dev"
stop = "pkill -f vite"
ready = "http://localhost:5173"

# Optional: where finished videos go. `demo publish <run> [args]` runs this with
# $DEMO_RUN, $DEMO_VIDEO, $DEMO_CAPTIONS, $DEMO_TIMELINE and $DEMO_TITLE set.
[publish]
command = 'gh release upload "$1" "$DEMO_VIDEO"'
```

## Repository layout

```
skills/demo-presentation/   the skill: SKILL.md, scripts/ (CLI), scenes/, references/,
                            examples/, and the prebuilt ui/ and vendor/
apps/review-ui/             Vue source of the review UI -> skills/demo-presentation/ui
apps/vendor/                fonts and browser libraries -> skills/demo-presentation/vendor
.claude-plugin/             plugin manifest; the repo is also its own marketplace
scripts/check.py            repository gate (CI runs it)
scripts/release.sh          bump versions, tag a release
tests/
```

## Develop

```bash
python3 scripts/check.py                                   # gate (Python 3.11+)
uv run --no-project --python 3.12 --with fastapi --with httpx --with uvicorn \
  python -m unittest discover -s tests
(cd apps/review-ui && npm ci && npm run build)             # rebuild ui/, commit the result
(cd apps/vendor && npm ci && npm run build)                # rebuild vendor/, commit the result
```

CI rebuilds both apps and fails if the committed `ui/` or `vendor/` differs from what the
source produces.

## Release

1. Add a `## X.Y.Z — date` entry at the top of `CHANGELOG.md`.
2. `scripts/release.sh X.Y.Z`: sets the version in `.claude-plugin/plugin.json` and
   `SKILL.md`, runs the gate, commits and tags `vX.Y.Z`.
3. `git push origin main vX.Y.Z`: the release workflow reruns CI, checks the tag matches,
   and publishes a GitHub release with the skill zip and its checksum.

Plugin users get the new version on update; `version` in `plugin.json` is what Claude
Code compares.

## License

MIT
