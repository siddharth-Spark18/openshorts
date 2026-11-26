import wave

import pytest

from long_transcript import transcribe_parts


def test_interrupted_run_reuses_only_finished_parts(tmp_path):
    source = tmp_path / "input.wav"
    with wave.open(str(source), "wb") as wav:
        wav.setparams((1, 2, 8000, 0, "NONE", "uncompressed"))
        wav.writeframes(bytes(5 * 8000 * 2))
    calls = []

    def decode(path):
        calls.append(path)
        if len(calls) == 2:
            raise RuntimeError("worker stopped")
        return {"language": "en", "segments": [{"start": 0, "end": 4, "words": [
            {"word": str(n), "start": n, "end": n + 0.5} for n in range(4)]}]}

    with pytest.raises(RuntimeError):
        transcribe_parts(source, 5, tmp_path, 2, decode)
    result = transcribe_parts(source, 5, tmp_path, 2, decode)
    assert len(calls) == 4
    assert [w["start"] for s in result["segments"] for w in s["words"]] == [0, 1, 2, 3, 4]
    assert result["language"] == "en"
