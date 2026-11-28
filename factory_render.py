"""Low-resource, offline illustrated skit renderer for the owner workspace."""
import re
import array
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

MAX_LINES = 16
MAX_LINE_LENGTH = 150


def dialogue_lines(script):
    """Extract clearly labelled dialogue; scene directions are not spoken."""
    lines = []
    for raw in script.splitlines():
        match = re.match(r'^\s*([\w][\w .-]{0,28}):\s*(\S.*)$', raw)
        if not match:
            continue
        speaker, text = match.groups()
        if speaker.lower() in {'title', 'scene', 'setting', 'narration', 'hook', 'description'}:
            continue
        text = re.sub(r'\[[^\]]*\]|\([^)]*\)', '', text).strip().strip('"')
        if text:
            if len(text) > MAX_LINE_LENGTH:
                raise ValueError(f'Keep each dialogue line under {MAX_LINE_LENGTH} characters; split long lines.')
            lines.append((speaker.strip(), text))
    if not lines or len(lines) > MAX_LINES:
        raise ValueError('Use 1–16 lines of dialogue in the form Character: dialogue.')
    return lines


def _font(size):
    for path in ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', '/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf', '/System/Library/Fonts/Helvetica.ttc'):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def _draw_frame(path, title, speaker, text, index, *, mouth_open=False, gesture=False):
    image = Image.new('RGB', (720, 1280), '#e8e3d9')
    d = ImageDraw.Draw(image)
    d.rectangle((0, 0, 720, 370), fill='#cbd8dc')
    d.rectangle((0, 790, 720, 1280), fill='#c6b39c')
    d.rounded_rectangle((42, 45, 678, 230), radius=18, fill='#fffaf1')
    d.text((65, 75), title[:35], font=_font(34), fill='#1b2631')
    # Simple original office character, deliberately using fixed-size geometry.
    skin = '#e0ae88' if index % 2 == 0 else '#bb886a'
    d.ellipse((263, 365, 457, 560), fill=skin, outline='#263344', width=8)
    d.ellipse((318, 438, 332, 452), fill='#263344')
    d.ellipse((390, 438, 404, 452), fill='#263344')
    if mouth_open:
        d.ellipse((342, 474, 378, 496), fill='#263344')
    else:
        d.arc((330, 450, 390, 500), 0, 180, fill='#263344', width=5)
    d.rounded_rectangle((230, 555, 490, 900), radius=30, fill='#345c79' if index % 2 == 0 else '#ab6956')
    d.line((248, 610, 185 if gesture else 215, 720 if gesture else 800), fill=skin, width=30)
    d.ellipse((168 if gesture else 198, 703 if gesture else 783, 202 if gesture else 232, 737 if gesture else 817), fill=skin)
    d.rounded_rectangle((40, 930, 680, 1230), radius=18, fill='#fffaf1')
    d.text((65, 950), speaker[:25], font=_font(32), fill='#2f5873')
    font = _font(42)
    words, current, lines = text.split(), '', []
    for word in words:
        candidate = f'{current} {word}'.strip()
        if d.textlength(candidate, font=font) > 560 and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    d.multiline_text((65, 1000), '\n'.join(lines[:3]), font=font, fill='#1b2631', spacing=8)
    image.save(path)


def _caption_chunks(text, limit=35):
    """Keep captions short enough to read on a vertical screen."""
    chunks, current = [], ''
    for word in text.split():
        candidate = f'{current} {word}'.strip()
        if current and len(candidate) > limit:
            chunks.append(current)
            current = word
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks or [text]


def _speech_poses(path, frames_per_second=8):
    """Choose reusable mouth poses from short PCM volume windows."""
    with wave.open(str(path), 'rb') as voice:
        if voice.getsampwidth() != 2 or voice.getcomptype() != 'NONE':
            raise ValueError('Speech audio must be 16-bit PCM.')
        window = max(1, voice.getframerate() // frames_per_second)
        poses = []
        while raw := voice.readframes(window):
            samples = array.array('h')
            samples.frombytes(raw)
            if sys.byteorder != 'little':
                samples.byteswap()
            amplitude = sum(abs(sample) for sample in samples) / max(1, len(samples))
            poses.append(1 if amplitude >= 250 else 0)
    return poses or [0]


def render(script, output_path, *, speech_command='espeak-ng', ffmpeg_command='ffmpeg', voice_settings=None):
    lines = dialogue_lines(script)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix='.skit-') as temporary:
        temp = Path(temporary)
        speakers = {}
        segments = []
        for idx, (speaker, text) in enumerate(lines):
            speaker_id = speakers.setdefault(speaker.lower(), len(speakers))
            wav, segment = temp / f'{idx}.wav', temp / f'{idx}.mp4'
            if voice_settings and voice_settings['provider'] == 'google':
                import factory_tts
                voice = voice_settings['voice_one'] if speaker_id % 2 == 0 else voice_settings['voice_two']
                factory_tts.synthesize(text, wav, voice)
            else:
                subprocess.run([speech_command, '-s', '155', '-p', str(40 + (speaker_id % 4) * 12),
                                '-w', str(wav)], input=text.encode('utf-8'), check=True, timeout=60, capture_output=True)
            captions = _caption_chunks(text)
            frames = []
            for caption_index, caption in enumerate(captions):
                variants = [temp / f'{idx}-caption-{caption_index}-pose-{pose}.png' for pose in range(4)]
                for pose, frame in enumerate(variants):
                    _draw_frame(frame, 'WORKPLACE STORIES', speaker, caption, speaker_id,
                                mouth_open=bool(pose % 2), gesture=pose >= 2)
                frames.append(variants)
            poses = _speech_poses(wav)
            manifest = temp / f'{idx}-poses.txt'
            total_weight = sum(len(caption) for caption in captions)
            frame_names = []
            for n, mouth in enumerate(poses):
                position = n * total_weight / len(poses)
                caption_index = 0
                while caption_index < len(captions) - 1 and position >= len(captions[caption_index]):
                    position -= len(captions[caption_index])
                    caption_index += 1
                frame_names.append(frames[caption_index][mouth + (2 if (n // 8) % 2 else 0)].name)
            manifest.write_text(''.join(f"file '{name}'\nduration 0.125\n" for name in frame_names) +
                                f"file '{frame_names[-1]}'\n", encoding='utf-8')
            subprocess.run([ffmpeg_command, '-v', 'error', '-y', '-f', 'concat', '-safe', '1',
                            '-i', str(manifest), '-i', str(wav), '-r', '12', '-shortest', '-c:v', 'libx264',
                            '-preset', 'ultrafast', '-threads', '1', '-pix_fmt', 'yuv420p',
                            '-c:a', 'aac', '-af', 'adenorm,loudnorm=I=-16:TP=-1.5:LRA=11', '-ar', '24000', '-movflags', '+faststart', str(segment)],
                           check=True, timeout=180, capture_output=True)
            segments.append(segment)
        manifest = temp / 'concat.txt'
        manifest.write_text(''.join(f"file '{part.name}'\n" for part in segments), encoding='utf-8')
        complete = temp / 'complete.mp4'
        subprocess.run([ffmpeg_command, '-v', 'error', '-y', '-f', 'concat', '-safe', '1',
                        '-i', str(manifest), '-c', 'copy', '-movflags', '+faststart', str(complete)],
                       check=True, timeout=120, capture_output=True)
        complete.replace(output)
