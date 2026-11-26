"""Bound ASR memory and preserve completed work across long-video retries."""
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile


def _offset_segment(segment, offset, start, end):
    # Context on either side lets ASR hear a whole word at a chunk boundary.
    # Keep each word only in the interval owning its midpoint.
    def belongs(item):
        return start <= offset + (item["start"] + item["end"]) / 2 < end

    def shifted(item):
        return {**item, "start": max(start, item["start"] + offset),
                "end": min(end, item["end"] + offset)}

    words = segment.get("words") or []
    if not words:
        return shifted(segment) if belongs(segment) else None
    kept = [shifted(word) for word in words if belongs(word)]
    if not kept:
        return None
    return {**segment, "start": kept[0]["start"], "end": kept[-1]["end"],
            "text": " ".join(w["word"].strip() for w in kept), "words": kept}


def transcribe_parts(source, duration, output_dir, seconds, transcribe):
    path = Path(source)
    with path.open("rb") as media:
        head = media.read(65536)
        media.seek(max(0, path.stat().st_size - 65536))
        fingerprint = hashlib.sha256(head + media.read()).hexdigest()
    config = [os.getenv(k) for k in ("TRANSCRIBE_BACKEND", "WHISPER_MODEL", "WHISPER_BEAM_SIZE")]
    key = json.dumps([fingerprint, path.stat().st_size, round(duration, 1), seconds, config])
    cache = Path(output_dir) / ".asr-parts" / hashlib.sha256(key.encode()).hexdigest()
    cache.mkdir(parents=True, exist_ok=True)
    segments = []
    languages = {}
    for start in range(0, math.ceil(duration), seconds):
        end = min(duration, start + seconds)
        offset = max(0, start - 2)
        checkpoint = cache / f"{start}.json"
        try:
            part = json.loads(checkpoint.read_text())
        except (FileNotFoundError, ValueError):
            print(f"Transcribing minutes {start / 60:.0f}–{end / 60:.1f}", flush=True)
            with tempfile.TemporaryDirectory(dir=cache) as tmp:
                audio = str(Path(tmp) / "audio.wav")
                subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", str(offset),
                                "-i", str(path), "-t", str(min(duration, end + 2) - offset),
                                "-vn", "-ac", "1", "-ar", "16000", audio], check=True)
                part = transcribe(audio)
                draft = Path(tmp) / "part.json"
                draft.write_text(json.dumps(part))
                draft.replace(checkpoint)
        for segment in part["segments"]:
            kept = _offset_segment(segment, offset, start, end)
            if kept is not None:
                segments.append(kept)
                language = part["language"]
                languages[language] = languages.get(language, 0) + kept["end"] - kept["start"]
    return {"text": " ".join(s["text"].strip() for s in segments), "segments": segments,
            "language": max(languages, key=languages.get) if languages else "unknown"}
