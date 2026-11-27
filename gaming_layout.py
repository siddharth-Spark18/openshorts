"""Preserve the whole game screen and optionally enlarge stable corner faces."""
import subprocess

import camera_inset
import layout_ranges
from ffmpeg_utils import video_encode_args, DELIVERY, METADATA_SCRUB


def face_panel_box(box, width, height):
    """Square crop centered on the face, with headroom and shoulders when available."""
    x, y, w, h = box
    size = int(min(width, height, max(w, h) * 3.4))
    size = max(2, size - size % 2)
    left = max(0, min(int(x + w / 2 - size / 2), width - size))
    top = max(0, min(int(y + h / 2 - size * .43), height - size))
    return (left - left % 2, top - top % 2, size, size)


def detect_cameras(path, samples=6):
    """Find stable lower-corner faces. Missing cameras are simply left out."""
    import cv2
    import numpy as np
    import screencast_layout

    cap = cv2.VideoCapture(path)
    try:
        if not cap.isOpened():
            return []
        count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if count <= 0 or width <= 0 or height <= 0:
            return []
        by_side = {'left': [], 'right': []}
        for i in range(samples):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int((i + 0.5) * count / samples))
            ok, frame = cap.read()
            if not ok:
                continue
            candidates = {'left': [], 'right': []}
            for face in screencast_layout.detect_faces_full_res(frame):
                box = face['box']
                x, y, w, h = box
                cx, cy = (x + w / 2) / width, (y + h / 2) / height
                if cy < .55 or .35 < cx < .65 or w <= 0 or h <= 0:
                    continue
                candidates['left' if cx < .5 else 'right'].append(face)
            for side, faces in candidates.items():
                if faces:
                    box = max(faces, key=lambda face: face['score'])['box']
                    by_side[side].append(face_panel_box(box, width, height))
        result = []
        for boxes in by_side.values():
            if len(boxes) < max(2, samples // 3):
                continue
            arr = np.array(boxes, dtype=float)
            centres = arr[:, 0] + arr[:, 2] / 2
            if np.max(np.abs(centres - np.median(centres))) > width * .08:
                continue
            box = tuple(int(round(value)) for value in np.median(arr, axis=0))
            if camera_inset.usable(box, height, min_ratio=.08, max_ratio=.55):
                result.append(box)
        return result
    finally:
        cap.release()


def filtergraph(width, height, cameras):
    """Full source is visible; optional camera crops occupy separate panels."""
    cameras = list(cameras[:2])
    outputs = ''.join(f'[s{i}]' for i in range(1 + len(cameras)))
    graph = [f'[0:v]split={1 + len(cameras)}{outputs}' if cameras else '[0:v]null[s0]',
             '[s0]scale=1080:608:force_original_aspect_ratio=decrease,'
             'pad=1080:1920:(ow-iw)/2:210:color=0x10161f[base]']
    for i, box in enumerate(cameras):
        x, y, w, h = [max(0, int(v) // 2 * 2) for v in box]
        w, h = max(2, min(w, width - x)), max(2, min(h, height - y))
        panel_w = 520 if len(cameras) == 2 else 780
        graph.append(f'[s{i+1}]crop={w}:{h}:{x}:{y},scale={panel_w}:510:force_original_aspect_ratio=decrease,'
                     f'pad={panel_w}:510:(ow-iw)/2:(oh-ih)/2:color=0x10161f[cam{i}]')
        x_pos = 20 + i * 540 if len(cameras) == 2 else 150
        graph.append(f'[{"base" if i == 0 else "lay" + str(i-1)}][cam{i}]overlay={x_pos}:920:shortest=1[lay{i}]')
    graph.append(f'[{"lay" + str(len(cameras)-1) if cameras else "base"}]setsar=1[v]')
    return ';'.join(graph)


def is_landscape(path):
    import cv2
    cap = cv2.VideoCapture(path)
    try:
        width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        if width <= 0 or height <= 0:
            raise RuntimeError('Could not read game clip dimensions.')
        return width > height
    finally:
        cap.release()


def render(input_path, output_path):
    import cv2
    cap = cv2.VideoCapture(input_path)
    try:
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
    finally:
        cap.release()
    if width < 2 or height < 2 or not fps or not frames:
        raise RuntimeError('Could not read game clip dimensions or duration.')
    if width / height <= 1:
        raise RuntimeError('Gaming layout requires a landscape source.')
    try:
        cameras = detect_cameras(input_path)
    except Exception as exc:
        print(f'   Gaming camera detection unavailable: {type(exc).__name__}; keeping full gameplay.')
        cameras = []
    graph = filtergraph(width, height, cameras)
    cmd = ['ffmpeg', '-y', '-i', input_path, '-filter_complex', graph, '-map', '[v]',
           '-map', '0:a?', *video_encode_args(DELIVERY), '-threads', '2', '-c:a', 'aac',
           *METADATA_SCRUB, '-movflags', '+faststart', output_path]
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=1800)
    if result.returncode:
        raise RuntimeError('Gaming layout render failed: ' + result.stderr.decode(errors='replace')[-500:])
    layout_ranges.write(output_path, [(0, frames / fps, 'wide')])
    print(f'   🎮 Gaming layout: full source and {len(cameras)} camera panel(s).')
    return True
