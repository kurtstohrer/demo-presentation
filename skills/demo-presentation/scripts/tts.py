"""Generate Kokoro narration for every beat of a run.

    uv run scripts/tts.py <run-dir> [--force]
    uv run scripts/tts.py --voices <out-dir> [--text "..."] [--voices-list af_heart,am_michael]

Writes audio/<scene>.<beat>.wav and audio/audio.json ({key: {file, duration, hash, words}});
`words` are [{w, s, e}] per word of the written narration, timed from Kokoro's phoneme durations.
Beats whose spoken text, voice and speed are unchanged are reused from cache.
The lexicon is the script's `lexicon` overlaid by the project pronunciation library.

Kokoro runs as ONNX on the CPU (kokoro-onnx + onnxruntime, no torch); misaki turns text
into phonemes, so `/IPA/` lexicon entries and respellings work as before. English voices
only (a* US, b* UK). The model downloads once into DEMO_MODELS (default
~/.cache/demo-presentation/models) and is checked against its sha256.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import urllib.request
from pathlib import Path

import numpy as np
import soundfile as sf

sys.path.insert(0, str(Path(__file__).parent))
import reviewlib as rl  # noqa: E402

SAMPLE_RATE = 24000
DEFAULT_VOICE = "af_heart"
SAMPLE_VOICES = ["af_heart", "af_bella", "af_nicole", "am_michael", "am_fenrir", "am_puck", "bf_emma", "bm_george", "bm_fable"]
# v1.1 of the ONNX export is the one with the duration output that word timings need.
MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/"
MODEL_FILES = {
    "kokoro-v1.0.onnx": "beb0d1848dee9a49da392cc3df26958d46cfa35d321edf434f52949153f0df3a",
    "voices-v1.0.bin": "bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d",
}
MAX_PHONEMES = 400  # per model call; the model's hard limit is 510
FRAMES_PER_SECOND = 80  # Kokoro's duration unit: one frame is 1/80 s at speed 1
BREAKS = set(".!?;:,—")

_engine: dict[str, object] = {}


def models_dir() -> Path:
    cache = os.environ.get("DEMO_CACHE") or Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "demo-presentation"
    return Path(os.environ.get("DEMO_MODELS") or Path(cache) / "models")


def ensure_models() -> Path:
    d = models_dir()
    d.mkdir(parents=True, exist_ok=True)
    for name, sha in MODEL_FILES.items():
        f = d / name
        if f.exists() and f.stat().st_size:
            continue
        print(f"  downloading {name} into {d} (once)", flush=True)
        h = hashlib.sha256()
        with tempfile.NamedTemporaryFile(dir=d, delete=False) as tmp, urllib.request.urlopen(MODEL_URL + name) as resp:
            while chunk := resp.read(1 << 20):
                h.update(chunk)
                tmp.write(chunk)
        if h.hexdigest() != sha:
            os.unlink(tmp.name)
            raise RuntimeError(f"{name}: sha256 {h.hexdigest()} does not match the pinned {sha}")
        os.chmod(tmp.name, 0o644)
        os.replace(tmp.name, f)
    return d


def _short_espeak_data() -> None:
    """espeak-ng silently fails on a data path over ~160 bytes: link a long one from a short path."""
    import espeakng_loader
    from phonemizer.backend.espeak.wrapper import EspeakWrapper

    data = espeakng_loader.get_data_path()
    if len(str(data).encode()) < 150:
        return
    link = Path(tempfile.gettempdir()) / f"demo-espeak-{os.getuid() if hasattr(os, 'getuid') else 'user'}"
    if not (link.is_symlink() and os.readlink(link) == str(data)):
        link.unlink(missing_ok=True)
        link.symlink_to(data, target_is_directory=True)
    EspeakWrapper.set_data_path(str(link))


def engine(lang: str):
    """(g2p, kokoro) for a voice language, created once: a = US English, b = UK English."""
    if lang not in _engine:
        if lang not in "ab":
            raise ValueError(f"voice language {lang!r}: only English voices (a*, b*) are supported")
        import onnxruntime as ort
        from kokoro_onnx import Kokoro
        from misaki import en, espeak  # imported lazily: spacy start-up is slow

        _short_espeak_data()
        d = ensure_models()
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = min(8, os.cpu_count() or 4)  # more threads burn CPU for no speed-up
        session = ort.InferenceSession(str(d / "kokoro-v1.0.onnx"), opts, providers=["CPUExecutionProvider"])
        british = lang == "b"
        g2p = en.G2P(trf=False, british=british, fallback=espeak.EspeakFallback(british=british), unk="")
        _engine[lang] = (g2p, Kokoro.from_session(session, str(d / "voices-v1.0.bin")))
    return _engine[lang]


def chunks(tokens: list) -> list[list]:
    """Split misaki tokens into model-sized runs, at punctuation where possible."""
    out, cur, size, cut = [], [], 0, 0
    for t in tokens:
        cur.append(t)
        size += len(t.phonemes or "") + (1 if t.whitespace else 0)
        if t.text and t.text[-1] in BREAKS:
            cut = len(cur)
        if size > MAX_PHONEMES:
            at = cut or len(cur)
            out.append(cur[:at])
            cur = cur[at:]
            size, cut = sum(len(x.phonemes or "") + (1 if x.whitespace else 0) for x in cur), 0
    return [c for c in (*out, cur) if c]


def place_tokens(tokens: list, durations: np.ndarray) -> None:
    """Set start_ts/end_ts (seconds) on tokens from the model's per-phoneme frame counts (kokoro's join_timestamps)."""
    left = right = 2 * max(0, int(durations[0]) - 3)
    i = 1
    for t in tokens:
        if i >= len(durations) - 1:
            break
        if not t.phonemes:
            if t.whitespace:
                i += 1
                left = right + int(durations[i])
                right = left + int(durations[i])
                i += 1
            continue
        j = i + len(t.phonemes)
        if j >= len(durations):
            break
        t.start_ts = left / FRAMES_PER_SECOND
        token = int(durations[i:j].sum())
        space = int(durations[j]) if t.whitespace else 0
        left = right + 2 * token + space
        t.end_ts = left / FRAMES_PER_SECOND
        right = left + space
        i = j + (1 if t.whitespace else 0)


def synthesize(text: str, voice: str, speed: float) -> tuple[np.ndarray, list[tuple[str, float, float]]]:
    """Audio plus token timings (text, start, end) in seconds of the returned audio."""
    g2p, kokoro = engine(voice[0])
    style_table = kokoro.get_voice_style(voice)
    audio_parts, timed, offset = [], [], 0.0
    for line in (x for x in text.split("\n") if x.strip()):
        _, tokens = g2p(line)
        for run in chunks(tokens):
            phonemes = "".join((t.phonemes or "") + (" " if t.whitespace else "") for t in run).strip()
            ids = kokoro.tokenizer.tokenize(phonemes)
            if not ids:
                continue
            audio, durations = kokoro._infer(ids, kokoro._style_for(style_table, len(ids)), speed)
            place_tokens(run, durations)
            timed += [(t.text, offset + t.start_ts, offset + t.end_ts) for t in run if t.start_ts is not None and t.end_ts is not None]
            audio_parts.append(np.asarray(audio, dtype=np.float32))
            offset += len(audio) / SAMPLE_RATE
    if not audio_parts:
        return np.zeros(int(SAMPLE_RATE * 0.2), dtype=np.float32), []
    audio, cut = trim_silence(np.concatenate(audio_parts))
    shift = cut / SAMPLE_RATE
    return audio, [(x, s - shift, e - shift) for x, s, e in timed]


def trim_silence(audio: np.ndarray, threshold: float = 0.005, keep: float = 0.06) -> tuple[np.ndarray, int]:
    """Trimmed audio and the number of samples cut from the start."""
    loud = np.flatnonzero(np.abs(audio) > threshold)
    if not len(loud):
        return audio, 0
    pad = int(SAMPLE_RATE * keep)
    start = max(0, loud[0] - pad)
    return audio[start : min(len(audio), loud[-1] + pad)], int(start)


def run_dir_tts(run_dir: Path, force: bool) -> None:
    script = json.loads((run_dir / "script.json").read_text())
    voice = script.get("voice", DEFAULT_VOICE)
    speed = float(script.get("speed", 1.0))
    lexicon = rl.lexicon_for(run_dir, script)
    out_dir = run_dir / "audio"
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "audio.json"
    manifest = {} if force or not manifest_path.exists() else json.loads(manifest_path.read_text())

    fresh = {}
    made = reused = 0
    for scene in script["scenes"]:
        for i, beat in enumerate(scene["beats"]):
            say = (beat.get("say") or "").strip()
            if not say:
                continue
            key = f"{scene['id']}.{i}"
            beat_voice = beat.get("voice", scene.get("voice", voice))
            spoken, cmap = rl.spoken_map(say, lexicon)
            digest = rl.narration_hash(beat_voice, speed, spoken)
            wav = out_dir / f"{key}.wav"
            prev = manifest.get(key)
            if prev and prev.get("hash") == digest and wav.exists():
                fresh[key] = prev
                reused += 1
                continue
            print(f"  tts {key}: {say[:70]}{'…' if len(say) > 70 else ''}", flush=True)
            audio, tokens = synthesize(spoken, beat_voice, speed)
            sf.write(wav, audio, SAMPLE_RATE)
            duration = round(len(audio) / SAMPLE_RATE, 3)
            fresh[key] = {"file": wav.name, "duration": duration, "hash": digest,
                          "words": rl.align_words(say, spoken, cmap, tokens, duration)}
            made += 1
    manifest_path.write_text(json.dumps(fresh, indent=2) + "\n")
    total = sum(v["duration"] for v in fresh.values())
    print(f"narration: {made} generated, {reused} cached, {total:.1f}s total -> {manifest_path}")


def sample_voices(out_dir: Path, text: str, voices: list[str]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for v in voices:
        print(f"  voice {v}", flush=True)
        sf.write(out_dir / f"{v}.wav", synthesize(text, v, 1.0)[0], SAMPLE_RATE)
    print(f"wrote {len(voices)} samples to {out_dir}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", nargs="?")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--voices", metavar="OUT_DIR")
    ap.add_argument("--voices-list", default=",".join(SAMPLE_VOICES))
    ap.add_argument("--text", default="Here's a quick walkthrough of what changed, and why it matters.")
    a = ap.parse_args()
    if a.voices:
        sample_voices(Path(a.voices), a.text, [v for v in a.voices_list.split(",") if v])
        return 0
    if not a.run_dir:
        ap.error("run_dir is required")
    run_dir_tts(Path(a.run_dir).resolve(), a.force)
    return 0


if __name__ == "__main__":
    sys.exit(main())
