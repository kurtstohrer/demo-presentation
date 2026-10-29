---
name: demo-presentation
description: Produce narrated demo videos that sum up concepts, show UI updates and walk through features. Scenes are a hand-drawn whiteboard, a terminal running real commands, a code editor showing real files, and live Playwright UI walkthroughs, with a title card when the project sets a logo; narration is Kokoro TTS and ffmpeg stitches the result with captions and chapters. Records the video straight away (headless is fine; an outline goes to the user first only when they ask for one), then hands over a local review link where the user comments on the video, or runs the project's own publish command; where nothing can be recorded, it says "no demo possible here" instead of faking one. Use for "make a demo video", "record a walkthrough", "explain this feature in a video", "show what changed in the UI".
license: MIT
compatibility: Needs uv and git; everything else (Python env, Chromium, ffmpeg, voice model) installs on first use.
metadata:
  version: "1.1.0"
---

# Demo presentation

Turns a topic (a feature, a PR, a concept) into a 1–5 minute narrated MP4.
The skill is project-agnostic. What is specific to a repo lives there:

- `.demo/brief.md` — routes, selectors, safe and forbidden commands, quirks.
  **Read it before planning any scene.**
- `.demo/config.toml` — `base_url`, `theme` (`dark`, `light`), `logo` (opening and closing
  title card), `voice`, `lexicon`, `local_storage`, `[[services]]` (`name`, `start`, `stop`,
  `ready`) and `[publish] command` (step 6). `DEMO_CONFIG` points elsewhere.

Files:

- `scripts/demo` — CLI (`demo help`). It needs only `uv` and `git`: on first use it copies
  itself to `~/.cache/demo-presentation/` and installs one Python env there;
  the skill folder in the repo is never modified.
- `scripts/` — `record.py` (Playwright), `tts.py` (Kokoro ONNX), `stitch.py` (ffmpeg)
- `scenes/` — HTML renderers for whiteboard / terminal / code / card scenes; `vendor/` their fonts and libraries
- `references/script-format.md` — **the full `script.json` action reference**
- `references/environment.md` — headless recording, hard dependencies, remote machines
- `scripts/serve.py` + `ui/` — review web UI (`demo url`); `scripts/review.py` — agent side (`demo review`)
- `.demo/pronunciations.json` in the project — the pronunciation library (step 4)
- `examples/` — working scripts (`skill-tour.json`: whiteboard/terminal/code; `ui-walkthrough.json`: UI)
- runs: `<repo>/.demo/runs/<name>/` — one directory per video (add `.demo/runs/` and
  `.demo/local/` to the project's `.gitignore`)

Below, `demo` means `<this skill dir>/scripts/demo`.

## Workflow

### 0. Setup (first use only)

```bash
demo doctor || demo setup
```

Any command installs what it needs on first use; `setup` does it up front (a uv env
with Playwright, ffmpeg and Kokoro ONNX, plus Chromium: ~1.3 GB, once per version). The
voice model (~350 MB) downloads to `~/.cache/demo-presentation/models` on first narration.
`demo up` / `demo down` start and stop the configured services.

It records headless and narrates on CPU; only 3D/WebGL apps want a GPU. The hard
dependencies, long steps and remote machines are in
[references/environment.md](references/environment.md). **No demo possible here:** if
`demo doctor` fails or a needed service can't start, never fake a video. Say
`No demo possible here: <reason>` where the video would have gone, and carry on.

### 1. Understand the subject

Read the code, diff, PR, or docs the demo is about. Decide the single takeaway.
Check `.demo/brief.md` for what can actually be shown: which UI
routes exist, what must be running, which commands are safe on camera.

### 2. Outline — then record straight away

Write a short outline and keep going: the user reviews the video, not the outline. It
goes into the hand-off (step 6) with the link and chapters. **Only when the user asks** to see
the outline first ("outline first"), post it and wait for approval, for that video only.
Nothing else goes to the user before the video: no script, no storyboard.

```
**<title>** · ~<N> s
- <scene>: <what it shows> (~15 s)
- <scene>: <what it shows> (~40 s, needs <service>)
- Recap (~10 s)
```

3–7 bullets, one line each, estimated seconds (≈2.6 spoken words per second).
Add one line for anything risky (live services, slow boot, network commands).

### 3. Write the script and check it yourself

```bash
demo new <name>            # script.json seeded with base_url, theme, voice, lexicon from .demo/config.toml
```

Write scenes and beats per `references/script-format.md`. Guidelines:

- Narration: conversational, second person, one or two sentences per beat.
- Start with a whiteboard (the concept), end with a short recap whiteboard.
- Every action that changes the screen belongs to the beat that talks about it.
- UI scenes: put loading, login and seeding in `prepare` so it is not filmed.
  Prefer stable selectors from the brief.
- Terminal scenes: only fast, read-only commands. Use `maxLines`.
- Code scenes: show 20–40 relevant lines with `lines`, then `focus` ranges.

```bash
demo validate <name>
demo storyboard <name>     # one screenshot per beat, in seconds; ui scenes include app boot
```

Look at every `storyboard/*.png` yourself — overlapping whiteboard elements,
wrong selectors, clipped terminal output, wrong file ranges — and fix them before
recording, since recording runs in real time. This is your check, not a review
step for the user.

### 4. Pronunciation

Narration runs through the project's **pronunciation library**,
`.demo/pronunciations.json` (`{"word": "say it as"}`, committed with the
project), overlaid on the script's own `lexicon`; the library wins. A value is a
sound-alike spelling (`"CLI": "C L I"`) or IPA between slashes
(`"Kokoro": "/kˈOkəɹO/"`). Add acronyms and product names you expect the TTS to
miss; the user edits the library in the review UI.

### 5. Record

```bash
demo build <name>          # tts (cached per beat) + record + stitch -> <run>/final.mp4
```

Recording is real time (a 2-minute video takes ~2 minutes plus app boot). The
UI scenes need the app running (`demo up`). Command output is cached in
`cache/commands.json`; pass `--refresh` to re-run commands. Single steps:
`demo tts`, `demo record [--scene a,b]`, `demo stitch`.

Extract a few frames and look at them before handing off, especially UI scenes:
`ffmpeg -ss <t> -i final.mp4 -frames:v 1 frame.png`.

### 6. Hand off

**By default** the run goes to the local review UI (localhost only):

```bash
demo url <name>      # reuses this project's server or starts one on a free port; prints the link
```

Give the user that link with the outline, the duration and the chapter list.
Other projects' review servers hold their own ports, so never guess the port.
If the server cannot run (no browser on this machine, remote session), give the path
to `final.mp4` instead. The review UI stays on loopback. Never expose it to share a video.

**A project that publishes videos somewhere** (a tracker, a bucket, a chat) sets
`[publish] command` in `.demo/config.toml`, and the run goes there:

```bash
demo publish <name> [args...]   # runs the command with $DEMO_RUN, $DEMO_VIDEO, $DEMO_CAPTIONS,
                                # $DEMO_TIMELINE, $DEMO_TITLE set; args arrive as "$@"
```

Follow the project's brief on when to publish and which args to pass, and give the user
whatever the command prints. An unattended run skips `demo url`: it publishes, or hands
off the `final.mp4` path.

The review UI opens on the video with a live transcript: the user leaves comments
pinned to timestamps and screen regions, and while paused fixes how a word is
said (that writes the library). Its top bar holds the tools — script and
storyboard editing, the pronunciation library, change requests, a script diff
against earlier renders — and render buttons that run the same `scripts/demo`
commands. Only the latest `final.mp4` is kept; each stitch snapshots
`versions/<n>/{script,final}.json`.

### Review loop

All review state is `<run>/review.json`. When the user says they left
feedback, do not open the UI — read it:

```bash
demo review <name>                         # open change requests + comments, mapped to beats, and what needs re-rendering
demo review <name> --reply <id> "what I changed" [--status addressed|resolved|wontfix]
demo review <name> --done <decision-id> "what I changed"
```

Then edit `script.json`, re-render only what changed
(`demo build <name> --scene <ids>` — `demo review` prints which scenes, including
beats whose pronunciation changed), reply to every item, and send the link again.
Feedback typed in chat with timestamps: map each time to a beat with `final.json`
(`scenes[].beats[].start/end/key`, `words[]` per beat), or record it with
`demo review <name> --comment "..." --at <t>` so it lives with the run.

## Troubleshooting

| symptom | fix |
|---|---|
| `action ... failed: Timeout` in a ui scene | wrong selector or app not ready; check `ready`/`prepare`, run `demo storyboard` with `--headed` |
| 3D app crawls or looks wrong | recording uses hardware WebGL (`--use-angle=gl`; on WSL `MESA_D3D12_DEFAULT_ADAPTER_NAME` picks the GPU, default `NVIDIA`). Try `--headed`; `--software-gl` forces SwiftShader |
| narration and action out of step | split the beat, or use `"sync": "after"` |
| command fails on camera | fix the command or set `"allowFail": true` deliberately |
| no captions on screen | they are a subtitle track, never burned in: turn subtitles on in the player; `captions.srt` sits next to `final.mp4` |
| narration slow or fails at once | first run downloads the model (`demo doctor` shows it); Kokoro runs on CPU, no GPU needed |
