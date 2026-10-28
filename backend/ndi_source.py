"""Optional NDI® video source: game frames from devices on the local network.

NDI® is a registered trademark of Vizrt NDI AB; see https://ndi.video. The
toolkit never redistributes the NDI SDK or runtime. It loads the free NDI
Runtime the user installed (NDI Tools include it) and calls the C API with
ctypes. Structure layouts follow the SDK's MIT-licensed headers (v5/v6).

Frames travel directly between devices on the local network; the toolkit adds
no relay or cloud service. NDI is unencrypted and discoverable on that
network, so use it only on a network you trust.
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
import sys
import threading
import time

from PIL import Image

from .windows import WindowInfo

NDI_PROCESS = 'ndi'
NDI_LINK = 'https://ndi.video/tools/'
RECEIVER_NAME = b'Game immersion toolkit'
FRAME_WAIT_MS = 1000
# Static scenes can stall some senders; reuse the newest frame briefly.
STALE_FRAME_SECONDS = 5.0

FRAME_TYPE_NONE, FRAME_TYPE_VIDEO, FRAME_TYPE_ERROR = 0, 1, 4
COLOR_BGRX_BGRA = 0
BANDWIDTH_HIGHEST = 100


def _fourcc(code: str) -> int:
    return int.from_bytes(code.encode('ascii'), 'little')


PACKED_BGR = {_fourcc('BGRX'), _fourcc('BGRA')}


class NdiUnavailable(RuntimeError):
    """Actionable user-facing reason why NDI frames cannot be read."""


class Source(ctypes.Structure):
    # NDIlib_source_t; the second member is a union of two const char*.
    _fields_ = [('p_ndi_name', ctypes.c_char_p), ('p_url_address', ctypes.c_char_p)]


class FindCreate(ctypes.Structure):
    _fields_ = [('show_local_sources', ctypes.c_bool), ('p_groups', ctypes.c_char_p),
                ('p_extra_ips', ctypes.c_char_p)]


class RecvCreate(ctypes.Structure):
    # NDIlib_recv_create_v3_t; C enums are 32-bit ints on supported ABIs.
    _fields_ = [('source_to_connect_to', Source), ('color_format', ctypes.c_int),
                ('bandwidth', ctypes.c_int), ('allow_video_fields', ctypes.c_bool),
                ('p_ndi_recv_name', ctypes.c_char_p)]


class VideoFrame(ctypes.Structure):
    # NDIlib_video_frame_v2_t; line_stride_in_bytes shares a union with
    # data_size_in_bytes, which only applies to compressed FourCCs.
    _fields_ = [('xres', ctypes.c_int), ('yres', ctypes.c_int), ('FourCC', ctypes.c_uint32),
                ('frame_rate_N', ctypes.c_int), ('frame_rate_D', ctypes.c_int),
                ('picture_aspect_ratio', ctypes.c_float), ('frame_format_type', ctypes.c_int),
                ('timecode', ctypes.c_int64), ('p_data', ctypes.POINTER(ctypes.c_uint8)),
                ('line_stride_in_bytes', ctypes.c_int), ('p_metadata', ctypes.c_char_p),
                ('timestamp', ctypes.c_int64)]


def _windows_runtime_folders() -> list[str]:
    folders = []
    names = ('NDI_RUNTIME_DIR_V6', 'NDI_RUNTIME_DIR_V5')
    folders += [os.environ[name] for name in names if os.environ.get(name)]
    # The NDI installer sets a machine variable that an already running
    # companion has not inherited; read it so no restart is needed.
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r'SYSTEM\CurrentControlSet\Control\Session Manager\Environment')
        with key:
            for name in names:
                try:
                    folders.append(os.path.expandvars(winreg.QueryValueEx(key, name)[0]))
                except OSError:
                    pass
    except (ImportError, OSError):
        pass
    return list(dict.fromkeys(folders))


def library_candidates(platform: str = sys.platform) -> list[str]:
    if platform == 'win32':
        return [str(Path(folder) / 'Processing.NDI.Lib.x64.dll') for folder in _windows_runtime_folders()]
    if platform == 'darwin':
        folders = [os.environ[name] for name in ('NDI_RUNTIME_DIR_V6', 'NDI_RUNTIME_DIR_V5') if os.environ.get(name)]
        return [str(Path(folder) / 'libndi.dylib') for folder in folders] + ['/usr/local/lib/libndi.dylib']
    return ['libndi.so.6', 'libndi.so.5']


def _declare(lib):
    p = ctypes.c_void_p
    lib.NDIlib_initialize.restype = ctypes.c_bool
    lib.NDIlib_initialize.argtypes = []
    lib.NDIlib_find_create_v2.restype = p
    lib.NDIlib_find_create_v2.argtypes = [ctypes.POINTER(FindCreate)]
    lib.NDIlib_find_wait_for_sources.restype = ctypes.c_bool
    lib.NDIlib_find_wait_for_sources.argtypes = [p, ctypes.c_uint32]
    lib.NDIlib_find_get_current_sources.restype = ctypes.POINTER(Source)
    lib.NDIlib_find_get_current_sources.argtypes = [p, ctypes.POINTER(ctypes.c_uint32)]
    lib.NDIlib_find_destroy.restype = None
    lib.NDIlib_find_destroy.argtypes = [p]
    lib.NDIlib_recv_create_v3.restype = p
    lib.NDIlib_recv_create_v3.argtypes = [ctypes.POINTER(RecvCreate)]
    lib.NDIlib_recv_destroy.restype = None
    lib.NDIlib_recv_destroy.argtypes = [p]
    lib.NDIlib_recv_capture_v2.restype = ctypes.c_int
    lib.NDIlib_recv_capture_v2.argtypes = [p, ctypes.POINTER(VideoFrame), p, p, ctypes.c_uint32]
    lib.NDIlib_recv_free_video_v2.restype = None
    lib.NDIlib_recv_free_video_v2.argtypes = [p, ctypes.POINTER(VideoFrame)]
    return lib


_runtime = None
_runtime_lock = threading.Lock()
_dll_directories = []  # Handles must stay alive for dependent DLL lookup.


def load_runtime(candidates=None, loader=ctypes.CDLL):
    """Load and initialize the installed runtime once; never search the CWD."""
    global _runtime
    with _runtime_lock:
        if _runtime is not None:
            return _runtime
        for candidate in library_candidates() if candidates is None else candidates:
            if os.path.isabs(candidate) and not os.path.isfile(candidate):
                continue
            try:
                if os.name == 'nt':
                    _dll_directories.append(os.add_dll_directory(os.path.dirname(candidate)))
                lib = _declare(loader(candidate))
            except (OSError, AttributeError):
                continue
            if not lib.NDIlib_initialize():
                raise NdiUnavailable('NDI could not start on this PC. Check that this CPU and Windows version are supported by the NDI Runtime.')
            _runtime = lib
            return lib
        raise NdiUnavailable(f'Install the free NDI Runtime (included in NDI Tools, {NDI_LINK}) to receive NDI video.')


def list_sources(lib=None, timeout_ms: int = 1500) -> list[str]:
    lib = lib or load_runtime()
    settings = FindCreate(True, None, None)
    finder = lib.NDIlib_find_create_v2(ctypes.byref(settings))
    if not finder:
        raise NdiUnavailable('NDI source discovery could not start on this PC.')
    try:
        # Discovery is incremental; wait once so nearby senders can announce.
        lib.NDIlib_find_wait_for_sources(finder, timeout_ms)
        count = ctypes.c_uint32(0)
        sources = lib.NDIlib_find_get_current_sources(finder, ctypes.byref(count))
        names = [sources[i].p_ndi_name.decode('utf-8', 'replace') for i in range(count.value)
                 if sources and sources[i].p_ndi_name]
    finally:
        lib.NDIlib_find_destroy(finder)
    return sorted(set(names), key=str.casefold)


def frame_image(frame: VideoFrame) -> Image.Image:
    if frame.FourCC not in PACKED_BGR:
        raise NdiUnavailable('The NDI source sent an unsupported picture format.')
    width, height, stride = frame.xres, frame.yres, frame.line_stride_in_bytes
    if width <= 0 or height <= 0 or stride < width * 4 or not frame.p_data:
        raise NdiUnavailable('The NDI source sent an invalid video frame.')
    data = ctypes.string_at(frame.p_data, stride * height)
    return Image.frombytes('RGB', (width, height), data, 'raw', 'BGRX', stride)


class NdiCapture:
    """One receiver for the selected source; returns the newest frame on demand.

    Frames are pulled only when a scan needs one. Older queued frames are
    released without conversion, so idle video costs no pixel copies here.
    """

    def __init__(self, runtime=None, clock=time.monotonic):
        self._runtime, self._clock = runtime, clock
        self._lock = threading.RLock()
        self._receiver = None
        self._source = None
        self._image = None
        self._received_at = 0.0

    def close(self) -> None:
        with self._lock:
            receiver, self._receiver = self._receiver, None
            self._source, self._image = None, None
            if receiver:
                self._lib().NDIlib_recv_destroy(receiver)

    def _lib(self):
        if self._runtime is None:
            self._runtime = load_runtime()
        return self._runtime

    def _connect(self, source: str):
        if self._receiver and self._source == source:
            return self._receiver
        self.close()
        lib = self._lib()
        settings = RecvCreate(Source(source.encode('utf-8'), None), COLOR_BGRX_BGRA,
                              BANDWIDTH_HIGHEST, False, RECEIVER_NAME)
        receiver = lib.NDIlib_recv_create_v3(ctypes.byref(settings))
        if not receiver:
            raise NdiUnavailable('Could not open the NDI source. Check that it is still broadcasting.')
        self._receiver, self._source = receiver, source
        return receiver

    def frame(self, source: str) -> Image.Image:
        if not source:
            raise NdiUnavailable('Choose an NDI source in Capture setup.')
        with self._lock:
            lib, receiver = self._lib(), self._connect(source)
            newest = None
            # Drain without waiting, keeping only the newest queued frame.
            for timeout in (0, FRAME_WAIT_MS):
                while True:
                    video = VideoFrame()
                    kind = lib.NDIlib_recv_capture_v2(receiver, ctypes.byref(video), None, None, timeout)
                    if kind == FRAME_TYPE_VIDEO:
                        if newest is not None:
                            lib.NDIlib_recv_free_video_v2(receiver, ctypes.byref(newest))
                        newest = video
                        timeout = 0
                        continue
                    if kind == FRAME_TYPE_ERROR:
                        if newest is not None:
                            lib.NDIlib_recv_free_video_v2(receiver, ctypes.byref(newest))
                        self.close()
                        raise NdiUnavailable('The NDI connection was lost. Capture retries automatically.')
                    break
                if newest is not None or self._image is not None:
                    break
            if newest is not None:
                try:
                    self._image = frame_image(newest)
                finally:
                    lib.NDIlib_recv_free_video_v2(receiver, ctypes.byref(newest))
                self._received_at = self._clock()
            elif self._image is None or self._clock() - self._received_at > STALE_FRAME_SECONDS:
                self._image = None
                raise NdiUnavailable(f'Waiting for video from NDI source “{source}”. Start the broadcast on the sending device.')
            return self._image

    @staticmethod
    def window(source: str, image: Image.Image) -> WindowInfo:
        # A frame-sized virtual window lets calibrated relative regions,
        # picture-area cropping and OCR scaling work unchanged.
        return WindowInfo(0, f'NDI · {source}', NDI_PROCESS, (0, 0, image.width, image.height))
