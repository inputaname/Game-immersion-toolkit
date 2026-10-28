import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from backend.capture import CaptureService, StableMatchTracker
from backend.models import TranscriptLine
from PIL import Image


def test_current_subtitle_visibility_expires_and_clears_per_channel() -> None:
    service = object.__new__(CaptureService)
    service._visible_text_by_channel = {}
    service._observe_visible_matches("dialogue", ["spoken-a"], 100.0)
    service._observe_visible_matches("tip", ["spoken-b"], 100.0)
    assert service._visible_text_ids(101.0) == ["spoken-a", "spoken-b"]
    service._observe_visible_matches("dialogue", [], 101.0)
    assert service._visible_text_ids(101.0) == ["spoken-b"]
    assert service._visible_text_ids(102.1) == []


def test_stable_tracker_emits_once_per_visible_line() -> None:
    tracker = StableMatchTracker(required_frames=2)
    assert tracker.observe("line-a") is False
    assert tracker.observe("line-a") is True
    assert tracker.observe("line-a") is False
    assert tracker.observe("line-a") is False


def test_stable_tracker_allows_same_line_after_it_disappears() -> None:
    tracker = StableMatchTracker(required_frames=2, blank_reset_frames=2)
    tracker.observe("line-a")
    assert tracker.observe("line-a") is True
    tracker.observe(None)
    tracker.observe(None)
    assert tracker.observe("line-a") is False
    assert tracker.observe("line-a") is True


def test_single_blank_frame_does_not_duplicate_line() -> None:
    tracker = StableMatchTracker(required_frames=2, blank_reset_frames=2)
    tracker.observe("line-a")
    assert tracker.observe("line-a") is True
    tracker.observe(None)
    assert tracker.observe("line-a") is False


def test_phone_screen_is_explicitly_excluded() -> None:
    lines = ["Knock Knock", "Anton", "[Completed] The prototype", "REPLY", "Daily Info"]
    assert CaptureService._is_phone_screen(lines) is True
    assert CaptureService._is_phone_screen(
        ["Fairy", "Oh, thanks!", "Daily Info - Latest messages displayed above -"]
    ) is True
    assert CaptureService._is_phone_screen(["Anby", "Stay close to me."]) is False


def test_same_textmap_id_has_emission_cooldown() -> None:
    service = object.__new__(CaptureService)
    service._last_emitted_at = {}
    service._last_emitted_key_by_channel = {}
    assert service._can_emit("dialogue\0line-a", 100.0) is True
    assert service._can_emit("dialogue\0line-a", 110.0) is False
    assert service._can_emit("cinematic\0line-a", 120.0) is False
    assert service._can_emit("dialogue\0line-b", 150.0) is True
    assert service._can_emit("dialogue\0line-a", 161.0) is True


def test_screen_header_classifier_excludes_history_interfaces() -> None:
    assert CaptureService._classify_screen_header(["51 FPS", "Story Recap"]) == "story_recap"
    assert CaptureService._classify_screen_header(["Knock Knock", "Anton"]) == "phone"
    assert CaptureService._classify_screen_header(["NEW!", "Story Commission", "70%"]) == "hdd"
    assert CaptureService._classify_screen_header(["Belobog Industries", "Ben"]) is None


def test_visual_novel_filmstrip_is_distinct_from_normal_gameplay() -> None:
    filmstrip = Image.new("RGB", (800, 100), (4, 4, 4))
    daylight = Image.new("RGB", (800, 100), (130, 105, 85))
    night_scene = Image.new("RGB", (800, 100), (30, 35, 48))
    assert CaptureService._is_visual_novel_layout(filmstrip)
    assert not CaptureService._is_visual_novel_layout(daylight)
    assert not CaptureService._is_visual_novel_layout(night_scene)


def test_broad_dark_gameplay_dialogue_box_is_detected() -> None:
    crop = Image.new("RGB", (1000, 300), (140, 110, 80))
    for x in range(150, 850):
        for y in range(135, 300):
            crop.putpixel((x, y), (8, 8, 8))
    plain_subtitles = Image.new("RGB", (1000, 300), (90, 100, 120))
    assert CaptureService._has_dialogue_box(crop)
    assert not CaptureService._has_dialogue_box(plain_subtitles)


def test_visible_full_line_rejects_later_suffix_match() -> None:
    service = object.__new__(CaptureService)
    service._last_visible_match_by_channel = {}
    full = "But that's not important. We should start looking for the prototype."
    ocr = f"Ben {full}"
    assert service._is_redundant_visible_match("dialogue", full, ocr) is False
    assert service._is_redundant_visible_match("dialogue", full, ocr) is False
    assert service._is_redundant_visible_match("dialogue", "The prototype?", ocr) is True
    assert service._is_redundant_visible_match(
        "dialogue", "The prototype?", "Belle The prototype?"
    ) is False


def test_cinematic_panel_comparison_accepts_growth_and_detects_clear() -> None:
    first = "What are you doing here"
    grown = first + "We have to leave before it gets dark"
    next_panel = "Meanwhile back at Random Play"
    assert CaptureService._same_cinematic_panel(first, grown) is True
    assert CaptureService._same_cinematic_panel(grown, next_panel) is False


def test_static_match_is_not_paired_with_much_later_speech() -> None:
    service = object.__new__(CaptureService)
    service._visible_match_started = {}
    assert service._is_fresh_match("tip", "tip-a", 100.0) is True
    assert service._is_fresh_match("tip", "tip-a", 102.9) is True
    assert service._is_fresh_match("tip", "tip-a", 103.1) is False
    assert service._is_fresh_match("tip", "tip-b", 110.0) is True


def test_comic_rows_are_grouped_by_bubble_instead_of_global_reading_order() -> None:
    def row(text: str, left: float, top: float, right: float, bottom: float) -> dict:
        return {
            "text": text,
            "bounding_rect": {
                "x1": left, "y1": top,
                "x2": right, "y2": top,
                "x3": right, "y3": bottom,
                "x4": left, "y4": bottom,
            },
        }

    groups = CaptureService._spatial_text_groups({
        "lines": [
            row("I'm not sure why, but", 50, 70, 256, 90),
            row("something feels", 49, 92, 210, 111),
            row("Ah... W-Wait a sec,", 505, 76, 689, 95),
            row("different about this", 50, 112, 251, 131),
            row("Qingyi!", 503, 97, 572, 116),
            row("Bangboo. It looks", 50, 135, 219, 153),
            row("Saying things like that", 599, 301, 822, 320),
            row("get us reported!", 598, 366, 760, 385),
        ]
    })

    assert "Ah... W-Wait a sec, Qingyi!" in groups
    assert any(text.startswith("I'm not sure why") and text.endswith("Bangboo. It looks") for text in groups)
    assert any(text.startswith("Saying things") and text.endswith("get us reported!") for text in groups)


def test_comic_bubbles_are_ordered_left_to_right_before_vertical_position() -> None:
    def row(text: str, left: float, top: float, right: float, bottom: float) -> dict:
        return {
            "text": text,
            "bounding_rect": {
                "x1": left, "y1": top,
                "x2": right, "y2": top,
                "x3": right, "y3": bottom,
                "x4": left, "y4": bottom,
            },
        }

    groups = CaptureService._spatial_text_groups({
        "lines": [
            row("First, upper-left.", 50, 70, 250, 90),
            row("Third, upper-right.", 500, 80, 700, 100),
            row("Second, lower-left.", 260, 300, 460, 320),
        ]
    })

    assert groups == [
        "First, upper-left.",
        "Second, lower-left.",
        "Third, upper-right.",
    ]


def test_overlapping_comic_columns_keep_separate_bubbles_and_sound_effects() -> None:
    def row(text, left, top, right, bottom):
        return {"text": text, "bounding_rect": {
            "x1": left, "x2": right, "x3": right, "x4": left,
            "y1": top, "y2": top, "y3": bottom, "y4": bottom}}

    groups = CaptureService._spatial_text_groups({"lines": [
        row("Keep the gate closed", 495, 452, 996, 501),
        row("until we return to", 494, 504, 1051, 553),
        row("town.", 495, 563, 541, 603),
        row("CRASH!", 1035, 583, 1463, 621),
        row("The bridge is still", 70, 669, 655, 718),
        row("too dangerous", 71, 728, 429, 768),
        row("for us to cross.", 70, 778, 651, 825),
        row("Will the supplies", 679, 986, 1245, 1040),
        row("arrive soon?", 682, 1046, 1012, 1087),
    ]})
    assert groups == [
        "The bridge is still too dangerous for us to cross.",
        "Keep the gate closed until we return to town.",
        "Will the supplies arrive soon?", "CRASH!",
    ]


def test_centered_short_final_comic_row_stays_in_its_bubble() -> None:
    def row(text, left, top, right):
        return {"text": text, "bounding_rect": {
            "x1": left, "x2": right, "x3": right, "x4": left,
            "y1": top, "y2": top, "y3": top + 20, "y4": top + 20}}
    assert CaptureService._spatial_text_groups({"lines": [
        row("We can continue our journey", 100, 100, 500),
        row("tomorrow.", 250, 125, 350),
    ]}) == ["We can continue our journey tomorrow."]

def test_scan_preview_is_encoded_only_when_requested():
    import threading
    service = object.__new__(CaptureService)
    service._preview, service._preview_image, service._preview_source = b"", None, None
    service._preview_lock = threading.RLock()
    encoded = []
    service._encode_preview = lambda image: encoded.append(image) or f"jpeg{len(encoded)}".encode()
    assert service.preview_bytes() == b""
    first, second = Image.new("RGB", (4, 2)), Image.new("RGB", (4, 2))
    service._set_preview(first)
    service._set_preview(second)
    assert encoded == []  # Scans without a viewer never encode.
    assert service.preview_bytes() == b"jpeg1"
    assert service.preview_bytes() == b"jpeg1"  # Cached until the next scan.
    assert encoded == [second]
    service._set_preview(first)
    assert service.preview_bytes() == b"jpeg2"
    assert encoded == [second, first]


def test_unprepared_language_blocks_capture_before_ocr_but_allows_preview(monkeypatch):
    from backend import capture as module
    from backend.models import CaptureRegion
    from backend.windows import WindowInfo
    from backend.games import GAME_PROFILES
    service = object.__new__(CaptureService)
    service.settings = SimpleNamespace(get=lambda: SimpleNamespace())
    service._scan_epoch = 0
    service._scan_index = 0
    service._tracker = StableMatchTracker(2)
    service.language_setup = lambda game: False
    service.snapshot = lambda: SimpleNamespace(active_game=None)
    service._caption_context = []
    service._caption_context_tracker = StableMatchTracker(2)
    status = []
    service._update_snapshot = lambda **values: status.append(values)
    service._prepare_window_capture = lambda _: None
    service._capture = lambda bounds: Image.new('RGB', bounds[2:])
    service._encode_preview = lambda image: b'preview'
    monkeypatch.setattr(module, 'find_active_game_window', lambda _: (GAME_PROFILES['cyberpunk'],
        WindowInfo(0, 'Cyberpunk', 'Cyberpunk2077.exe', (0, 0, 1280, 720))))
    assert service._scan_once().emitted_lines == []
    assert status[-1]['phase'] == 'needs_language_setup'
    assert service.preview_for_region(CaptureRegion(left=0, top=0, width=1, height=1)) == b'preview'
    service.language_setup = lambda game: True
    service.settings = SimpleNamespace(get=lambda: SimpleNamespace(capture_unvoiced=False))
    monkeypatch.setattr(module, 'find_active_game_window', lambda _: (GAME_PROFILES['halflife'],
        WindowInfo(0, 'Half-Life', 'hl.exe', (0, 0, 1280, 720))))
    assert service._scan_once().emitted_lines == []
    assert status[-1]['phase'] == 'unvoiced_disabled'
    assert 'spoken dialogue capture is not implemented' in status[-1]['message']
