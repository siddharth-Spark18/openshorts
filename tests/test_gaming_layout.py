import json
import shutil
import subprocess

import pytest
import gaming_layout


def test_camera_box_keeps_face_centered_near_source_edge():
    x, y, w, h = gaming_layout.face_panel_box((180, 600, 100, 120), 1920, 1080)
    assert x <= 180 and x + w >= 280
    assert y <= 600 and y + h >= 720
    assert abs((x + w / 2) - 230) < 2


def test_gaming_filter_keeps_full_game_and_camera_panels():
    plain = gaming_layout.filtergraph(1920, 1080, [])
    assert 'crop=' not in plain
    assert 'force_original_aspect_ratio=decrease' in plain
    two = gaming_layout.filtergraph(1920, 1080, [(0, 700, 400, 380), (1500, 700, 400, 380)])
    assert two.count('crop=') == 2
    assert 'overlay=20:920' in two and 'overlay=560:920' in two
    assert '[s0]scale=1080:608' in two


@pytest.mark.skipif(not shutil.which('ffmpeg'), reason='ffmpeg unavailable')
def test_gaming_render_preserves_audio_and_marks_layout(tmp_path, monkeypatch):
    source = tmp_path / 'source.mp4'
    output = tmp_path / 'out.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=red:s=320x180:r=10',
                    '-f', 'lavfi', '-i', 'sine=frequency=440', '-t', '0.5', '-c:v', 'libx264',
                    '-threads', '1', '-c:a', 'aac', str(source)], check=True)
    monkeypatch.setattr(gaming_layout, 'detect_cameras', lambda _: [(0, 60, 80, 100), (240, 60, 80, 100)])
    assert gaming_layout.render(str(source), str(output))
    data = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', str(output)]))
    video = next(stream for stream in data['streams'] if stream['codec_type'] == 'video')
    assert (video['width'], video['height']) == (1080, 1920)
    assert any(stream['codec_type'] == 'audio' for stream in data['streams'])
    assert json.loads((tmp_path / 'out.mp4.layout.json').read_text())['ranges'][0]['layout'] == 'wide'


def test_gaming_layout_can_be_selected_per_job():
    import app
    assert app.layout_env(['gaming'])['GAMING_LAYOUT'] == '1'
    assert 'GAMING_LAYOUT' not in app.layout_env(['none'])


@pytest.mark.asyncio
async def test_automatic_source_requests_shorter_gaming_clips(monkeypatch):
    import app
    seen = {}
    async def endpoint(request, **kwargs):
        seen.update(await request.json())
        return {'job_id': request.state._source_job_id}
    monkeypatch.setattr(app, 'process_endpoint', endpoint)
    result = await app._auto_submit_source('abcdefghijk', 'test-job')
    assert result == {'job_id': 'test-job'}
    assert seen['layouts'] == ['gaming']
    assert (seen['clip_min_seconds'], seen['clip_max_seconds']) == (15, 35)


def test_camera_detector_initializes_lazy_face_model(monkeypatch):
    import sys
    import types
    import numpy as np
    import cv2
    import screencast_layout
    fake_main = types.SimpleNamespace(face_detection=None)
    def initialize(frame):
        fake_main.face_detection = object()
        return []
    fake_main.detect_face_candidates = initialize
    monkeypatch.setitem(sys.modules, 'main', fake_main)
    monkeypatch.setattr(screencast_layout, 'detect_faces_full_res',
                        lambda frame: [{'box': [100, 650, 100, 100], 'score': 10000}]
                        if fake_main.face_detection else (_ for _ in ()).throw(AssertionError('not initialized')))
    class Capture:
        def __init__(self, path): pass
        def isOpened(self): return True
        def get(self, prop):
            return {cv2.CAP_PROP_FRAME_COUNT: 100, cv2.CAP_PROP_FRAME_WIDTH: 1920,
                    cv2.CAP_PROP_FRAME_HEIGHT: 1080}.get(prop, 0)
        def set(self, prop, value): pass
        def read(self): return True, np.zeros((1080, 1920, 3), dtype=np.uint8)
        def release(self): pass
    monkeypatch.setattr(cv2, 'VideoCapture', Capture)
    assert len(gaming_layout.detect_cameras('unused')) == 1
