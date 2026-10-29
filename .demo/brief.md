# Demo brief: demo-presentation

This repo is the demo-presentation skill itself. Its videos explain the skill and show how
to use it. They stay unbranded: no logo, no names of private toolchains or agent hosts.

## What can be shown

- **Terminal scenes** run in the repo root, or with `cwd: "skills/demo-presentation"` so the
  CLI reads as `scripts/demo`:
  - `demo help`, `demo doctor`, `demo path <run>`, `demo validate <run>`, `demo review <run>`
    (read-only without flags)
  - `git log`, `ls`, `cat` of files in this repo
  - `python3 scripts/check.py`
  - `demo doctor` prints home-directory paths: show its output with `type`, `$HOME` as `~`.
- **Code scenes:** any file in this repo. Good ones: `skills/demo-presentation/examples/skill-tour.json`,
  `skills/demo-presentation/templates/script.json`, `.demo/config.toml`,
  `.claude-plugin/marketplace.json`.
- **UI scenes, sample app** (`base_url`, started by `demo up`): `/` lists projects, `/settings/`
  has `#profile`, `#notifications` (switches `role=switch[name="Weekly digest"]`, `"Mentions"`;
  a toggle shows `text=Saved`) and `#integrations` (`input[type=search]` filters the list).
- **UI scenes, external sites:** public pages only, such as this repo on GitHub. A site
  behind a login takes `auth` from environment variables, never from the script.
- **UI scenes, review UI:** the review UI. Its port varies: run `demo url <run>` and use the printed
  URL. Routes: `#/run/<run>/video`, `/storyboard`, `/pronunciation`, `/review`, `/changes`.
  Seed comments in `prepare`, not on camera. Point UI scenes at a small finished run made
  for the purpose (`ui-sample`), not at the video being recorded.

## Never on camera

- `demo build`, `demo record`, `demo storyboard` (slow, real time). Show them with
  `type` and scripted output instead.
- Anything that pushes, publishes or creates releases (`git push`, `gh release`, `demo publish`).
