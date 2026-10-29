"""Bounded local decoder. All inputs are server-created paths, never URLs."""
import ctypes
import hashlib
import json
import math
import os
import subprocess
from contextlib import contextmanager
from decimal import Decimal
from pathlib import Path
from contracts.normalized import milliseconds

MAX_BYTES = 200_000_000
MAX_MS = 60_000


class MediaError(ValueError):
    pass


@contextmanager
def process_budget(process):
    """Windows Job Object imposes memory/CPU limits and kills descendants on close."""
    handle = None
    if os.name == 'nt':
        from ctypes import wintypes as w
        class BASIC(ctypes.Structure):
            _fields_ = [('process_time', ctypes.c_longlong), ('job_time', ctypes.c_longlong),
                ('flags', w.DWORD), ('min_ws', ctypes.c_size_t), ('max_ws', ctypes.c_size_t),
                ('active', w.DWORD), ('affinity', ctypes.c_size_t), ('priority', w.DWORD), ('scheduling', w.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(x, ctypes.c_ulonglong) for x in ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]
        class LIMIT(ctypes.Structure):
            _fields_ = [('basic', BASIC), ('io', IO), ('process_memory', ctypes.c_size_t),
                ('job_memory', ctypes.c_size_t), ('peak_process', ctypes.c_size_t), ('peak_job', ctypes.c_size_t)]
        kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        kernel.CreateJobObjectW.restype = w.HANDLE
        kernel.SetInformationJobObject.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
        kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
        kernel.CloseHandle.argtypes = [w.HANDLE]
        handle = kernel.CreateJobObjectW(None, None)
        limits = LIMIT()
        limits.basic.flags = 0x2000 | 0x100 | 0x2  # kill on close, process memory, process CPU
        limits.basic.process_time = 30 * 10_000_000
        limits.process_memory = 1024 * 1024 * 1024
        if not handle or not kernel.SetInformationJobObject(handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)) or not kernel.AssignProcessToJobObject(handle, w.HANDLE(int(process._handle))):
            process.kill()
            process.wait()
            if handle: kernel.CloseHandle(handle)
            raise MediaError('decoder_resource_isolation_unavailable')
    try:
        yield
    finally:
        if handle: kernel.CloseHandle(handle)


def decoder(args, timeout=25):
    kwargs = {}
    if os.name == 'nt':
        kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
    else:
        def limits():
            import resource
            resource.setrlimit(resource.RLIMIT_AS, (1024**3, 1024**3))
            resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
            resource.setrlimit(resource.RLIMIT_FSIZE, (20_000_000, 20_000_000))
        kwargs['preexec_fn'] = limits
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.DEVNULL, **kwargs)
    try:
        with process_budget(process):
            out, _ = process.communicate(timeout=timeout)
            if process.returncode != 0:
                raise MediaError('invalid_or_unsupported_media')
            return out
    except subprocess.TimeoutExpired:
        process.kill(); process.communicate()
        raise MediaError('decoder_timeout') from None


INPUT = ['-protocol_whitelist', 'file,pipe', '-format_whitelist', 'mov,mp4,m4a,3gp,3g2,mj2',
         '-enable_drefs', '0', '-use_absolute_path', '0', '-threads', '1']


def probe(path):
    with path.open('rb') as f:
        head = f.read(64)
    if len(head) < 12 or head[4:8] != b'ftyp' or head[8:12] not in (b'isom', b'iso2', b'mp41', b'mp42', b'avc1', b'dash', b'M4V '):
        raise MediaError('mp4_required')
    info = json.loads(decoder(['ffprobe','-v','error','-max_alloc','67108864',*INPUT,
        '-probesize','10000000','-analyzeduration','5000000','-show_format','-show_streams','-of','json',str(path)]))
    videos = [s for s in info['streams'] if s['codec_type'] == 'video']
    if len(videos) != 1:
        raise MediaError('one_video_track_required')
    stream = videos[0]
    duration = Decimal(info['format']['duration'])
    if not duration.is_finite() or not 0 < duration <= Decimal('60'):
        raise MediaError('maximum_duration_60_seconds')
    if stream['codec_name'] not in ('h264','hevc','av1','mpeg4','vp9') or not (1 <= stream['width'] <= 4096 and 1 <= stream['height'] <= 4096):
        raise MediaError('unsupported_codec_or_resolution')
    rate = stream.get('avg_frame_rate', '0/1').split('/')
    if len(rate) != 2 or float(rate[1]) == 0 or not 0 < float(rate[0])/float(rate[1]) <= 120:
        raise MediaError('unsupported_frame_rate')
    # Decode all frames before accepting bytes; probe alone misses truncated streams.
    decoder(['ffmpeg','-v','error','-xerror','-max_alloc','67108864',*INPUT,'-i',str(path),
        '-map','0:v:0','-an','-threads','1','-f','null','-'], timeout=35)
    audio = any(s['codec_type'] == 'audio' for s in info['streams'])
    return dict(duration_ms=milliseconds(float(duration)), width=stream['width'], height=stream['height'],
        audio_present=audio, bytes=path.stat().st_size, caveats=[] if audio else ['No audio track.'],
        codec=stream['codec_name'])


def scene_ranges(duration_ms):
    start, index = 0, 0
    while start < duration_ms:
        end = min(duration_ms, 3000 if index == 0 else start+5000)
        yield dict(scene_id=index, start_ms=start, end_ms=end)
        start, index = end, index+1


def extract(path, directory, duration_ms):
    scenes = []
    for scene in scene_ranges(duration_ms):
        frame = directory/f"frame-{scene['scene_id']}.jpg"
        decoder(['ffmpeg','-v','error','-xerror',*INPUT,'-ss',str(scene['start_ms']/1000),'-i',str(path),
            '-frames:v','1','-an','-vf','scale=640:640:force_original_aspect_ratio=decrease',
            '-threads','1','-y',str(frame)])
        if not frame.exists() or frame.stat().st_size > 2_000_000:
            raise MediaError('frame_extraction_failed')
        scenes.append({**scene, 'frame_path': frame, 'frame_sha256': hashlib.sha256(frame.read_bytes()).hexdigest(),
                       'transcript': None, 'ocr': None})
    return scenes
