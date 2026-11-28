import screencast_layout
from screencast_layout import (
    content_side,
    overlapping_width,
    screencast_filtergraph,
    speaker_crop,
)


class TestContentSide:
    def test_content_is_the_side_away_from_the_presenter(self):
        # Presenter on the right (body 1200-1700): the chart is on the left,
        # stopping short of the body.
        x, w = content_side(1920, 1200, 1700)
        assert x == 0 and w < 1200

    def test_presenter_on_the_left_leaves_the_right(self):
        x, w = content_side(1920, 100, 700)
        assert x > 700 and x + w == 1920

    def test_no_room_beside_the_presenter_means_no_stack(self):
        # A person filling the middle of the frame: neither side is wide
        # enough, so the scene stays with the face classifier.
        assert content_side(1920, 500, 1500) is None

    def test_columns_are_even(self):
        x, w = content_side(1919, 101, 703)
        assert x % 2 == 0 and w % 2 == 0


class TestSpeakerCrop:
    def test_crop_stays_inside_the_source(self):
        w, h, x, y = speaker_crop(1920, 1080, 1080, 1312, (1748, 832))
        assert 0 <= x <= 1920 - w
        assert 0 <= y <= 1080 - h

    def test_crop_is_even(self):
        w, h, x, y = speaker_crop(1920, 1080, 1080, 1312, (777, 333))
        assert w % 2 == 0 and h % 2 == 0 and x % 2 == 0 and y % 2 == 0

    def test_crop_follows_the_face_horizontally(self):
        _, _, left_x, _ = speaker_crop(1920, 1080, 1080, 1312, (400, 500))
        _, _, right_x, _ = speaker_crop(1920, 1080, 1080, 1312, (1500, 500))
        assert left_x < right_x

    def test_corner_presenter_is_clamped_not_dropped(self):
        w, _h, x, _y = speaker_crop(1920, 1080, 1080, 1312, (1900, 1000))
        assert x == 1920 - w


class TestOverlappingWidth:
    def test_no_ranges_means_no_width(self):
        assert overlapping_width(0, 10, []) == 0.0

    def test_returns_the_width_of_an_overlapping_range(self):
        assert overlapping_width(5, 15, [(0, 20, "chart", 0.7)]) == 0.7

    def test_ignores_ranges_that_do_not_overlap(self):
        assert overlapping_width(30, 40, [(0, 20, "chart", 0.9)]) == 0.0

    def test_a_brush_of_overlap_does_not_count(self):
        # Under MIN_OVERLAP_SECONDS: a scene that merely touches the range.
        assert overlapping_width(19.9, 30, [(0, 20, "chart", 0.9)]) == 0.0

    def test_widest_overlapping_range_wins(self):
        ranges = [(0, 20, "ticker", 0.15), (0, 20, "spreadsheet", 0.95)]
        assert overlapping_width(5, 15, ranges) == 0.95

    def test_corner_ticker_width_is_reported_not_swallowed(self):
        # The gate lives in detect_content_ranges; this function must report
        # small widths faithfully so that gate can do its job.
        assert overlapping_width(5, 15, [(0, 20, "ticker", 0.15)]) == 0.15


class TestScreencastFiltergraph:
    CONTENT = (0, 1100)   # the chart left of a presenter at x~1748

    def test_top_band_is_only_the_content_columns(self):
        # The whole frame up there showed the presenter twice (17-oct-2026).
        graph = screencast_filtergraph(1920, 1080, 1080, 1920, (1748, 832),
                                       self.CONTENT)
        content = graph.split("[ca]")[-1].split("[content]")[0]
        assert "crop=w=1100:h=1080:x=0:y=0" in content

    def test_content_fits_without_distortion(self):
        graph = screencast_filtergraph(1920, 1080, 1080, 1920, (1748, 832),
                                       self.CONTENT)
        content = graph.split("[ca]")[-1].split("[content]")[0]
        sw, sh = map(int, content.split("scale=")[1].split(":"))
        assert abs(sw / sh - 1100 / 1080) < 0.02
        assert sh <= 1920 * 0.55

    def test_speaker_takes_the_rest_of_the_height(self):
        graph = screencast_filtergraph(1920, 1080, 1080, 1920, (1748, 832),
                                       self.CONTENT)
        content = graph.split("[ca]")[-1].split("[content]")[0]
        sh = int(content.split("scale=")[1].split(":")[1])
        speaker = graph.split("[sa]")[-1].split("[speaker]")[0]
        assert "crop=" in speaker
        assert f"scale=1080:{1920 - sh}" in speaker
        assert f"overlay=x=0:y={sh}" in graph
        assert graph.endswith("[v]")


class TestGating:
    def test_disabled_module_detects_nothing(self, monkeypatch):
        monkeypatch.setattr(screencast_layout, "ENABLED", False)
        assert screencast_layout.detect_content_ranges("x.mp4", [], 30.0) == []

    def test_no_ranges_means_no_scenes_touched(self, monkeypatch):
        monkeypatch.setattr(screencast_layout, "ENABLED", True)
        assert screencast_layout.detect_screencast_scenes(
            "x.mp4", [], [], []) == {}


class TestFilmedPerson:
    """A presenter standing at a whiteboard was called "screen" by the shot
    check (17-oct-2026); a full-height person means a filmed room."""

    class _Cap:
        def __init__(self, h):
            self.h = h

        def get(self, prop):
            return self.h

        def set(self, *_):
            pass

        def read(self):
            return True, object()

    class _Main:
        def __init__(self, box):
            self.box = box

        def detect_person_yolo(self, frame):
            return self.box

    def test_full_height_person_is_a_filmed_room(self):
        # YOLO box of a person standing in a 1080p shot, top 40% kept.
        m = self._Main([900, 100, 500, int(900 * 0.4)])
        assert screencast_layout._filmed_person(self._Cap(1080), m, 0, 100)

    def test_webcam_over_a_screen_is_not(self):
        # Measured: a corner webcam's YOLO box on a 720p walkthrough.
        m = self._Main([991, 502, 246, 86])
        assert not screencast_layout._filmed_person(self._Cap(720), m, 0, 100)

    def test_no_person_is_not(self):
        assert not screencast_layout._filmed_person(
            self._Cap(1080), self._Main(None), 0, 100)
