import shutil
import subprocess
import wave
from pathlib import Path

import pytest
import factory_render


def test_dialogue_parser_accepts_character_lines_and_excludes_stage_directions():
    assert factory_render.dialogue_lines('Title: The meeting\n[Office]\nBoss: Hello there.\nEmployee: (sighs) Hello.') == [
        ('Boss', 'Hello there.'), ('Employee', 'Hello.')]
    with pytest.raises(ValueError):
        factory_render.dialogue_lines('Title: Empty\n[No dialogue]')
    with pytest.raises(ValueError):
        factory_render.dialogue_lines('\n'.join(f'Boss: Line {n}' for n in range(17)))


def test_speech_poses_follow_audio_activity(tmp_path):
    path = tmp_path / 'speech.wav'
    with wave.open(str(path), 'wb') as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(8000)
        output.writeframes((b'\x00\x00' * 1000) + (b'\x00\x20' * 1000))
    assert factory_render._speech_poses(path) == [0, 1]


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='ffmpeg unavailable')
def test_offline_render_produces_playable_video(tmp_path):
    speech = tmp_path / 'fake-speech'
    speech.write_text('''#!/usr/bin/env python3
import sys, wave
p = sys.argv[sys.argv.index('-w') + 1]
with wave.open(p, 'wb') as out:
    out.setnchannels(1); out.setsampwidth(2); out.setframerate(16000)
    out.writeframes(b'\\x00\\x00' * 16000)
''')
    speech.chmod(0o755)
    output = tmp_path / 'skit.mp4'
    factory_render.render('Boss: Welcome to work.\nWorker: Another meeting?', output, speech_command=str(speech))
    assert output.stat().st_size > 1000
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                             '-of', 'default=nw=1:nk=1', str(output)], capture_output=True, text=True, check=True)
    assert float(result.stdout.strip()) >= 1
