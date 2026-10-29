# Where a demo can be recorded

## Headless is fine

- Chromium records headless by default (`--headed` is only for debugging a scene).
- Kokoro narrates on CPU (ONNX, no torch): a GPU makes no difference to narration.
- Only 3D/WebGL apps want a GPU. Without one, `--software-gl` forces SwiftShader.
- Whiteboard, terminal and code scenes need no services at all.

## Hard dependencies

A machine that records needs `uv` and `git` on `PATH`. Everything else comes through uv,
pinned in the skill's `uv.lock`:

- ffmpeg with libass and libx264 from the `imageio-ffmpeg` wheel (`DEMO_FFMPEG` overrides);
- espeak-ng from the `espeakng-loader` wheel, Playwright from its wheel (which carries its
  own Node; no system Node or npm);
- Chromium, which `demo setup` fetches with `playwright install chromium`. That is only the
  browser, not the OS libraries it links against: a bare Linux image may also need
  `python -m playwright install-deps chromium` (root);
- network on first use, for the env (~650 MB), Chromium (~650 MB with its headless shell) and the voice model
  (~350 MB into `~/.cache/demo-presentation/models`, `DEMO_MODELS` overrides; checked by sha256).

Narration is English only (voices `a*` US, `b*` UK). There is no onnxruntime wheel for
Intel Macs.

A machine that records often, such as a project workspace that agents are dispatched into,
should have `~/.cache/demo-presentation` pre-built (`demo setup` in its image or template), so a
dispatched run doesn't spend its first half hour installing.

## Long steps

`demo setup` and `demo build` run for minutes (recording is real time). Under a tool
timeout, run them in the background and wait for them to finish rather than polling.

## No demo possible here

Run `demo doctor` before planning scenes. If it fails, or a UI scene's service can't start,
don't record and never fake a video: no stand-in footage, no screenshots passed off as a
walkthrough. Say `No demo possible here: <reason, missing deps>` where the video would have
gone, and carry on without one.

## Remote machines

The review UI (`demo url` prints its port, 4177 or the next free one) listens on loopback only. From a remote workspace,
reach it through a port forward, never by exposing it. An unattended run skips `demo url`
and hands off the `final.mp4` path, or runs `demo publish`.
