"""Builds storyboard/index.html from script.json + storyboard screenshots.

    python scripts/storyboard_page.py <run-dir>
"""

from __future__ import annotations

import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import beat_key, estimate_seconds, load_run  # noqa: E402

CSS = """:root{--bg:#f4f5f7;--card:#fff;--fg:#1b1f27;--muted:#5f6878;--line:#dde1e8;--accent:#e5641a}
@media (prefers-color-scheme:dark){:root{--bg:#0f1115;--card:#181b22;--fg:#e8eaf0;--muted:#8b93a5;--line:#2a2f3a;--accent:#ff8a3d}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,sans-serif;padding:24px 16px 80px}
main{max-width:1500px;margin:0 auto}h1{margin:0 0 4px}.sub{color:var(--muted);margin:0 0 28px}
h2{font-size:19px;display:flex;gap:10px;align-items:center;margin:34px 0 12px}h2 span{background:var(--accent);color:#111;border-radius:6px;padding:0 8px}
h2 em{font-style:normal;font-size:12px;color:var(--muted);border:1px solid var(--line);border-radius:99px;padding:1px 9px}
.beats{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:16px}
.beat{background:var(--card);border:1px solid var(--line);border-radius:10px;overflow:hidden}
.beat img,.noshot{display:block;width:100%;aspect-ratio:16/9;object-fit:cover;background:#000}.noshot{display:grid;place-items:center;color:var(--muted)}
.meta{display:flex;justify-content:space-between;padding:8px 12px 0;font-size:12px;color:var(--muted)}.key{font-family:ui-monospace,monospace}
.say{margin:6px 12px 8px}ul{margin:0 12px 12px;padding:0;list-style:none;font-size:12.5px;color:var(--muted)}
code{font-size:11.5px;background:color-mix(in srgb,var(--accent) 16%,transparent);color:var(--fg);padding:0 5px;border-radius:4px}"""


def esc(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def summarize(action: dict) -> str:
    k, v = next(((k, v) for k, v in action.items() if not k.startswith("__")), ("?", ""))
    if isinstance(v, dict):
        v = v.get("text") or v.get("selector") or v.get("title") or v.get("code") or json.dumps(v)
    return f"<code>{esc(k)}</code> {esc(str(v)[:80])}"


def main() -> int:
    run, script, audio = load_run(sys.argv[1])
    total = 0.0
    sections = []
    for si, scene in enumerate(script["scenes"]):
        beats = []
        for i, beat in enumerate(scene["beats"]):
            key = beat_key(scene["id"], i)
            measured = key in audio
            secs = audio[key]["duration"] if measured else estimate_seconds(beat.get("say"))
            total += secs + 0.35
            shot = f"{key}.png"
            img = f'<img src="{shot}" alt="{esc(key)}">' if (run / "storyboard" / shot).exists() else '<div class="noshot">no frame</div>'
            acts = "".join(f"<li>{summarize(a)}</li>" for a in beat.get("do") or [])
            beats.append(f'<article class="beat">{img}<div class="meta"><span class="key">{esc(key)}</span>'
                         f'<span class="dur">{secs:.1f}s{"" if measured else " est"}</span></div>\n'
                         f'      <p class="say">{esc(beat.get("say") or "—")}</p><ul>{acts}</ul></article>')
        sections.append(f'<section><h2><span>{si + 1}</span> {esc(scene.get("title") or scene["id"])} <em>{esc(scene["type"])}</em></h2>'
                        f'<div class="beats">{"".join(beats)}</div></section>')
    page = (f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n'
            f'<title>{esc(script["title"])} — storyboard</title><style>\n{CSS}\n</style></head><body><main><h1>{esc(script["title"])}</h1>\n'
            f'<p class="sub">{len(script["scenes"])} scenes · ~{round(total)}s narration · voice {esc(script.get("voice") or "af_heart")}</p>'
            f'{"".join(sections)}</main></body></html>')
    out = run / "storyboard" / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page)
    print(f"storyboard: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
