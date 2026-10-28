"""Synthetic NDI runtime: no SDK, network or sender is required."""
import ctypes
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend import ndi_source
from backend.capture import CaptureService
from backend.games import GAME_PROFILES
from backend.models import AppSettings, CaptureRegion
from backend.ndi_source import NdiCapture, NdiUnavailable, VideoFrame


def test_structure_layouts_match_sdk_headers():
    # Offsets from compiling the NDI SDK v6 headers for 64-bit Windows/Linux.
    assert [ctypes.sizeof(t) for t in (ndi_source.Source, ndi_source.FindCreate,
                                       ndi_source.RecvCreate, VideoFrame)] == [16, 24, 40, 72]
    recv = ndi_source.RecvCreate
    assert [recv.color_format.offset, recv.bandwidth.offset, recv.allow_video_fields.offset,
            recv.p_ndi_recv_name.offset] == [16, 20, 24, 32]
    assert [VideoFrame.FourCC.offset, VideoFrame.frame_format_type.offset, VideoFrame.timecode.offset,
            VideoFrame.p_data.offset, VideoFrame.line_stride_in_bytes.offset,
            VideoFrame.p_metadata.offset, VideoFrame.timestamp.offset] == [8, 24, 32, 40, 48, 56, 64]
    assert ndi_source._fourcc('BGRX') == 1481787202 and ndi_source._fourcc('BGRA') == 1095911234


class FakeRuntime:
    """Implements the C entry points used by the toolkit with Python frames."""

    def __init__(self, queue=(), sources=()):
        self.queue, self.sources = list(queue), list(sources)
        self.buffers, self.freed, self.created, self.destroyed, self.waits = [], [], [], [], []

    def frame(self, width, height, pixel, padding=8, fourcc='BGRX'):
        stride = width * 4 + padding
        row = bytes(pixel) + b'\xff'
        data = (row * width + b'\x00' * padding) * height
        buffer = ctypes.create_string_buffer(data, len(data))
        self.buffers.append(buffer)
        return ndi_source.FRAME_TYPE_VIDEO, dict(xres=width, yres=height, FourCC=ndi_source._fourcc(fourcc),
                                                 p_data=ctypes.cast(buffer, ctypes.POINTER(ctypes.c_uint8)),
                                                 line_stride_in_bytes=stride)

    def NDIlib_recv_create_v3(self, settings):
        value = settings._obj
        self.created.append((value.source_to_connect_to.p_ndi_name, value.color_format, value.bandwidth))
        return 1234

    def NDIlib_recv_destroy(self, receiver):
        self.destroyed.append(receiver)

    def NDIlib_recv_capture_v2(self, receiver, video, audio, metadata, timeout):
        self.waits.append(timeout)
        if not self.queue:
            return ndi_source.FRAME_TYPE_NONE
        kind, fields = self.queue.pop(0)
        for name, value in (fields or {}).items():
            setattr(video._obj, name, value)
        return kind

    def NDIlib_recv_free_video_v2(self, receiver, video):
        self.freed.append(video._obj.xres)

    def NDIlib_find_create_v2(self, settings):
        assert settings._obj.show_local_sources
        return 99

    def NDIlib_find_wait_for_sources(self, finder, timeout):
        self.waits.append(timeout)
        return True

    def NDIlib_find_get_current_sources(self, finder, count):
        array = (ndi_source.Source * max(1, len(self.sources)))(
            *[ndi_source.Source(name.encode(), None) for name in self.sources])
        self.buffers.append(array)
        count._obj.value = len(self.sources)
        return array

    def NDIlib_find_destroy(self, finder):
        self.destroyed.append(finder)


def test_frame_conversion_honors_stride_and_channel_order():
    runtime = FakeRuntime()
    _, fields = runtime.frame(3, 2, (10, 20, 30))  # B, G, R
    image = ndi_source.frame_image(VideoFrame(**fields))
    assert image.mode == 'RGB' and image.size == (3, 2)
    assert set(image.getdata()) == {(30, 20, 10)}
    with pytest.raises(NdiUnavailable):
        ndi_source.frame_image(VideoFrame(**{**fields, 'FourCC': ndi_source._fourcc('UYVY')}))


def test_capture_keeps_newest_frame_and_releases_every_frame():
    runtime = FakeRuntime()
    runtime.queue = [runtime.frame(2, 1, (0, 0, 1)), runtime.frame(3, 1, (0, 0, 2)), runtime.frame(4, 1, (0, 0, 3))]
    capture = NdiCapture(runtime)
    image = capture.frame('PHONE (Screen)')
    assert image.size == (4, 1) and image.getpixel((0, 0)) == (3, 0, 0)
    assert sorted(runtime.freed) == [2, 3, 4]
    assert runtime.created == [(b'PHONE (Screen)', ndi_source.COLOR_BGRX_BGRA, ndi_source.BANDWIDTH_HIGHEST)]
    assert capture.window('PHONE (Screen)', image).bounds == (0, 0, 4, 1)
    capture.close()
    assert runtime.destroyed == [1234]


def test_static_scene_reuses_recent_frame_then_reports_missing_video():
    now = [0.0]
    runtime = FakeRuntime()
    runtime.queue = [runtime.frame(2, 2, (1, 2, 3))]
    capture = NdiCapture(runtime, clock=lambda: now[0])
    first = capture.frame('PHONE')
    now[0] = 4.0
    assert capture.frame('PHONE') is first
    assert runtime.waits[-1] == 0  # A cached frame never blocks the scan.
    now[0] = 10.0
    with pytest.raises(NdiUnavailable, match='Waiting for video'):
        capture.frame('PHONE')
    with pytest.raises(NdiUnavailable, match='Waiting for video'):
        capture.frame('PHONE')
    assert runtime.waits[-1] == ndi_source.FRAME_WAIT_MS


def test_connection_error_closes_receiver_and_frees_pending_frame():
    runtime = FakeRuntime()
    runtime.queue = [runtime.frame(2, 1, (0, 0, 0)), (ndi_source.FRAME_TYPE_ERROR, None)]
    capture = NdiCapture(runtime)
    with pytest.raises(NdiUnavailable, match='connection was lost'):
        capture.frame('PHONE')
    assert runtime.freed == [2] and runtime.destroyed == [1234]


def test_source_change_replaces_receiver_and_empty_source_is_actionable():
    runtime = FakeRuntime()
    capture = NdiCapture(runtime)
    runtime.queue = [runtime.frame(2, 1, (0, 0, 0))]
    capture.frame('A')
    runtime.queue = [runtime.frame(2, 1, (0, 0, 0))]
    capture.frame('B')
    assert [name for name, *_ in runtime.created] == [b'A', b'B'] and runtime.destroyed == [1234]
    with pytest.raises(NdiUnavailable, match='Choose an NDI source'):
        capture.frame('')


def test_discovery_lists_unique_sorted_names():
    runtime = FakeRuntime(sources=['studio (OBS)', 'IPAD (Screen)', 'studio (OBS)'])
    assert ndi_source.list_sources(runtime) == ['IPAD (Screen)', 'studio (OBS)']
    assert runtime.destroyed == [99]


def test_missing_runtime_points_to_free_installer(monkeypatch):
    monkeypatch.setattr(ndi_source, '_runtime', None)
    with pytest.raises(NdiUnavailable, match='ndi.video'):
        ndi_source.load_runtime(candidates=['/nonexistent/Processing.NDI.Lib.x64.dll'])


def ndi_service(monkeypatch, settings, capture):
    import threading
    from backend import capture as module
    service = object.__new__(CaptureService)
    service.settings = SimpleNamespace(get=lambda: settings)
    service._ndi = capture
    service._window_frame = threading.local()
    service._background_capture = SimpleNamespace(close=lambda: None,
        frame=lambda window: pytest.fail('NDI must not start window capture'))

    class NoDesktop:
        def __enter__(self):
            pytest.fail('NDI must never screenshot the PC desktop')
    monkeypatch.setattr(module.mss, 'mss', NoDesktop)
    monkeypatch.setattr(module, 'find_active_game_window', lambda _: pytest.fail('NDI must not search windows'))
    return service


def test_capture_service_crops_regions_from_ndi_frame(monkeypatch):
    runtime = FakeRuntime()
    runtime.queue = [runtime.frame(100, 50, (0, 0, 200))]
    settings = AppSettings(capture_source='ndi', ndi_source='IPAD (Screen)', ndi_game='genshin')
    service = ndi_service(monkeypatch, settings, NdiCapture(runtime))
    profile, window = service._find_active(settings)
    assert profile is GAME_PROFILES['genshin']
    assert window.title == 'NDI · IPAD (Screen)' and window.bounds == (0, 0, 100, 50)
    service._prepare_window_capture(window)
    bounds = service._region_bounds(window, CaptureRegion(left=.1, top=.7, width=.8, height=.28))
    crop = service._capture(bounds)
    assert bounds[:3] == (10, 35, 80) and crop.size == bounds[2:] and crop.getpixel((0, 0)) == (200, 0, 0)
    service._encode_preview = lambda image: b'jpeg'
    assert service.preview_for_region(CaptureRegion(left=0, top=0, width=1, height=1)) == b'jpeg'


def test_ndi_without_game_or_runtime_reports_waiting_reason(monkeypatch):
    settings = AppSettings(capture_source='ndi', ndi_source='IPAD (Screen)')
    service = ndi_service(monkeypatch, settings, NdiCapture(FakeRuntime()))
    with pytest.raises(NdiUnavailable, match='Choose the game'):
        service._find_active(settings)
    service._scan_epoch = service._scan_index = 0
    service._tracker = service._tip_tracker = service._cinematic_tracker = SimpleNamespace(observe=lambda _: None)
    status = []
    service._update_snapshot = lambda **values: status.append(values)
    assert service._scan_once().emitted_lines == []
    assert status[-1]['phase'] == 'waiting_for_game' and 'Choose the game' in status[-1]['message']
    assert service.preview_for_region(CaptureRegion(left=0, top=0, width=1, height=1)) == b''


def test_ndi_discovery_endpoint(monkeypatch):
    from backend import api
    client = TestClient(api.app, base_url='http://127.0.0.1:8766')
    monkeypatch.setattr(api, 'list_ndi_sources', lambda: ['IPAD (Screen)'])
    assert client.get('/api/ndi/sources').json() == {
        'available': True, 'message': None, 'sources': ['IPAD (Screen)'], 'link': ndi_source.NDI_LINK}

    def missing():
        raise NdiUnavailable('Install the free NDI Runtime')
    monkeypatch.setattr(api, 'list_ndi_sources', missing)
    body = client.get('/api/ndi/sources').json()
    assert body['available'] is False and body['sources'] == [] and 'NDI Runtime' in body['message']
    assert client.get('/api/ndi/sources', headers={'Origin': 'https://example.test'}).status_code == 403


def test_settings_reject_unknown_capture_source():
    with pytest.raises(ValueError):
        AppSettings(capture_source='vdo')
    assert AppSettings().capture_source == 'window'
