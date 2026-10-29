# script.json reference

A run is a directory containing `script.json`. Everything the pipeline produces
lands next to it (`audio/`, `storyboard/`, `scenes/`, `final.mp4`, ...).

```jsonc
{
  "title": "Editor dock in 90 seconds",   // required
  "voice": "af_heart",                    // Kokoro voice (see `demo voices`); a* = US, b* = UK
  "speed": 1.0,                           // narration speed
  "theme": "dark",                        // dark | light: HTML scenes + colorScheme
  "captions": true,                       // caption track in final.mp4, switchable in the player (captions.srt is always written)
  "lexicon": { "CLI": "C L I", "Kokoro": "/kˈOkəɹO/" }, // spoken substitutions (respelling or /IPA/); captions keep the original.
                                          // The project library .demo/pronunciations.json overrides these per word.
  "baseUrl": "http://localhost:3000",     // prefix for relative ui scene urls
  "localStorage": { "app:theme": "dark" },   // seeded into every ui scene before load
  "auth": [                               // live sites: secrets come from env vars, never from this file
    { "header": "Authorization", "prefix": "Bearer ", "url": "https://app.example.com/**", "env": "DEMO_APP_TOKEN" },
    { "cookie": "session", "domain": "app.example.com", "env": "DEMO_APP_SESSION" }
  ],                                      // also per ui scene; a header goes only to matching urls
  "viewport": { "width": 1920, "height": 1080 },
  "fps": 30, "crf": 18, "beatGap": 0.35,
  "scenes": [ /* ... */ ]
}
```

## Scenes and beats

Every scene has `id` (kebab-case, unique), `type`, optional `title`
(used for chapters and on-screen heading where applicable) and `beats`.

A **beat** is one narration line plus the actions that happen while it is spoken:

```jsonc
{ "say": "Press F1 and the dock opens.", "do": [ { "press": "F1" } ],
  "sync": "with",   // default: actions start with the voice. "after": actions start once the line ends
  "pause": 0.35,    // silence after the beat
  "hold": 0.3,      // minimum time after the last action
  "voice": "am_michael" }  // per-beat voice override
```

A beat lasts `max(narration + pause, actions + hold)`. Narration is placed at the
beat's real start, so audio stays in sync even when an action runs long. Keep
beats to one or two sentences: they are the unit for re-recording and review
comments.

`prepare` (any scene type) is a list of actions run **before** capture starts.
Use it for loading, logging in and seeding state that should not be on camera.

## whiteboard

Hand-drawn diagrams on a 1920×1080 board (rough.js + Caveat font). Coordinates
are board pixels, top-left origin. Leave ~100px margins; titles sit at y≈56.

| action | value |
|---|---|
| `title` | `"text"` (big handwritten heading) |
| `box` / `ellipse` | `{ id, text, x, y, w=360, h=150, color, fill, size=48, ms=700 }` — `text` may hold `"Main\nsmall subtitle"` |
| `text` | `{ id, text, x, y, w, size=44, color, align }` |
| `note` | `{ id, text, x, y, w=320, tilt }` sticky note |
| `list` | `{ id, items: [..], x, y, w, size=52, stagger=500 }` bullets appear one by one |
| `arrow` | `{ from, to, label, curve, both, color }` — connects element edges |
| `underline` / `circle` / `highlight` | `"id"` — emphasize an existing element |
| `erase` | `"id"` or `["id", ..]` |
| `clear` | `true` |
| `heading` / `subheading` / `wait` | shared actions |

Colors: `ink` (default), `accent`, `accent-2`, `good`, `warn`, `bad`, or `#hex`.

## terminal

xterm.js window. `cwd` is relative to the project root.

| action | value |
|---|---|
| `run` | `"command"` — executed for real in `cwd` before recording; output is replayed. Options on the action: `cwd`, `maxLines=40`, `timeout=60`, `allowFail` |
| `type` | `"command"` with `"output": "..."` — scripted output, nothing executed |
| `comment` | `"text"` — typed as a dim `# comment` |
| `clear` | `true` |

Scene options: `title`, `subtitle`, `windowTitle`, `prompt="$ "`, `fontSize=24`, `typeMs=38`, `maxLines`.
Command output is cached in `cache/commands.json`; `demo record <run> --refresh` re-runs commands.
Only use read-only, fast, deterministic commands on camera.

## code

Editor window with Shiki highlighting.

| action | value |
|---|---|
| `open` | `"path/from/root"` with optional `"lines": [start, end]` (required for >600 lines), `"lang"`, `"at": line` |
| `focus` | `[start, end]` — highlight, dim the rest, scroll to center |
| `highlight` | `[start, end]` — mark lines without dimming |
| `unfocus` | `true` |
| `scroll` | `line` |
| `insert` | `{ "after": line, "code": "new lines\n..." }` — typed live, shown as added |
| `callout` | `{ "line": n, "text": "..." }` — bubble to the right of the line |

Line numbers are file line numbers. After an `insert`, later lines shift down.
Scene options: `title`, `subtitle`, `fontSize=22`, `typeMs=22`.

## chat

A conversation with an agent: the user's prompt is typed into a message box and sent,
the agent's replies stream in, and the commands it runs show as rows with a result.
The window is neutral: no product's look or name. Everything in it is scripted, so
write what really happens: the user's real request and the steps the agent really
takes (`demo storyboard`, `demo build`), never a capability the agent lacks.

| action | value |
|---|---|
| `user` | `"text"` — typed into the message box, then sent as a bubble |
| `agent` | `"text"` or `{ text, ms=45 }` — streams in word by word (`ms` per word). Inline `` `code` ``, `**bold**`, `- ` lists, blank-line paragraphs |
| `thinking` | `ms` — typing indicator for that long |
| `tool` | `"command"` or `{ name, result, ms=1100, failed }` — a running row that turns into a check (or a red mark) with `result` |
| `clear` | `true` |
| `heading` / `subheading` / `wait` | shared actions |

Scene options: `title`, `subtitle`, `windowTitle="chat"`, `agentName="Agent"`,
`placeholder`, `fontSize=28`, `typeMs=34`, `streamMs=45`. About eight messages fit
on screen; older ones scroll up.

## card

A title card: the project's logo, a big title and a subtitle over the theme's
gradient. `demo new` opens and closes every video with one when the project sets
`logo` in `.demo/config.toml`; otherwise use it for any chapter card.

Scene fields: `logo` (path from the project root, or an `https://` URL), `title`, `subtitle`.

| action | value |
|---|---|
| `card` | `{ title, subtitle, logo }` — swaps any of them with a fade |
| `wait` | shared action |

## ui

A real browser session (Playwright Chromium) with a drawn cursor, click ripples,
spotlights and chapter cards.

Scene fields: `url` (absolute or relative to `baseUrl`), `ready` (selector, or
`{ "function": "js expression" }`), `localStorage`, `prepare`.

| action | value |
|---|---|
| `click` / `dblclick` / `rightClick` / `hover` | Playwright selector (`css`, `text=…`, `role=button[name="Save"]`) or `{ x, y }` |
| `fill` | `{ selector, text, delay=55, clear=true }` |
| `type` | `"text"` (keyboard into focused element) |
| `press` | `"F1"`, `"ControlOrMeta+s"` |
| `keyDown` / `keyUp` | key |
| `scroll` | `{ selector?, y }` |
| `drag` | `{ from, to }` or `{ from, dx, dy, ms }` |
| `move` | `{ x, y, ms }` |
| `spotlight` | selector or `{ selector, text, ms=1200, keep }` dims everything else |
| `clearSpotlight` | `true` |
| `chapter` | `"Title"` or `{ title, description, ms=1800 }` |
| `goto` | url |
| `waitFor` | selector; optional `"timeout"` ms on the action (default 120000) |
| `waitForFunction` | js expression; optional `"timeout"` and `"polling"` ms on the action |
| `eval` | js expression run in the page (drive app APIs, seed state) |
| `wait` | ms |

## Outputs

| path | from |
|---|---|
| `audio/<scene>.<beat>.wav`, `audio/audio.json` | `demo tts` |
| `storyboard/<scene>.<beat>.png`, `storyboard/index.html` | `demo storyboard` |
| `scenes/<scene>.mp4`, `timeline.json` | `demo record` |
| `narration.wav`, `captions.srt`, `chapters.txt`, `final.json`, `final.mp4` | `demo stitch` |

`final.json` maps every beat to its global start/end time in `final.mp4`; use it
to turn a reviewer's timestamp into a `scene.beat` key.
