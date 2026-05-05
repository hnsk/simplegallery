"""Video processing: probe metadata, generate thumbnail, transcode MP4/WebM.

Backed by the system `ffmpeg` / `ffprobe` binaries (Alpine package `ffmpeg`).
Thumbnail piped through Wand so format/encoding matches `image_processor`.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from wand.image import Image

log = logging.getLogger(__name__)

THUMB_QUALITY = 80
THUMB_SEEK_FRACTION = 0.1
THUMB_SEEK_MAX = 1.0

MP4_CRF = 23
MP4_PRESET = "slow"
MP4_AUDIO_BITRATE = "128k"

WEBM_CRF = 33
WEBM_AUDIO_BITRATE = "96k"


class VideoProcessingError(RuntimeError):
    """Raised when ffmpeg/ffprobe fails."""


@dataclass(frozen=True)
class VideoInfo:
    """Result of `probe()` — only the fields the rest of the pipeline cares about."""

    width: int
    height: int
    duration: float
    codec: str
    has_audio: bool


def probe(src: Path) -> VideoInfo:
    """Run ffprobe, return VideoInfo. Raises VideoProcessingError on failure."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(src),
    ]
    proc = _run(cmd, capture=True)
    try:
        data = json.loads(proc.stdout or "{}")
    except ValueError as exc:
        raise VideoProcessingError(f"ffprobe returned non-JSON for {src}: {exc}") from exc

    streams = data.get("streams") or []
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video_stream is None:
        raise VideoProcessingError(f"no video stream in {src}")
    has_audio = any(s.get("codec_type") == "audio" for s in streams)

    width = int(video_stream.get("width") or 0)
    height = int(video_stream.get("height") or 0)
    codec = str(video_stream.get("codec_name") or "")

    duration = _duration(data, video_stream)

    return VideoInfo(
        width=width,
        height=height,
        duration=duration,
        codec=codec,
        has_audio=has_audio,
    )


def generate_thumbnail(src: Path, dst: Path, info: VideoInfo | None = None) -> None:
    """Seek to ~10% (capped at 1.0s), pipe one frame through Wand → WebP."""
    info = info or probe(src)
    seek = min(THUMB_SEEK_MAX, max(0.0, info.duration * THUMB_SEEK_FRACTION))
    dst.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-loglevel", "error",
        "-ss", f"{seek:.3f}",
        "-i", str(src),
        "-frames:v", "1",
        "-f", "image2pipe",
        "-vcodec", "png",
        "-",
    ]
    proc = _run(cmd, capture=True, binary=True)
    if not proc.stdout:
        raise VideoProcessingError(f"ffmpeg produced no thumbnail frame for {src}")

    with Image(blob=proc.stdout) as img:
        img.auto_orient()
        img.strip()
        img.format = "webp"
        img.compression_quality = THUMB_QUALITY
        img.save(filename=str(dst))


def transcode_mp4(src: Path, dst: Path, info: VideoInfo | None = None) -> None:
    """libx264 CRF23 preset slow, AAC 128k, +faststart, even-dim scale."""
    info = info or probe(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-loglevel", "error",
        "-y",
        "-i", str(src),
        "-vf", _even_scale_filter(),
        "-c:v", "libx264",
        "-preset", MP4_PRESET,
        "-crf", str(MP4_CRF),
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
    ]
    if info.has_audio:
        cmd += ["-c:a", "aac", "-b:a", MP4_AUDIO_BITRATE]
    else:
        cmd += ["-an"]
    cmd.append(str(dst))
    _run(cmd)


def transcode_webm(src: Path, dst: Path, info: VideoInfo | None = None) -> None:
    """libvpx-vp9 CRF33 b:v 0, libopus 96k. Skips audio when source has none."""
    info = info or probe(src)
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-loglevel", "error",
        "-y",
        "-i", str(src),
        "-vf", _even_scale_filter(),
        "-c:v", "libvpx-vp9",
        "-b:v", "0",
        "-crf", str(WEBM_CRF),
        "-row-mt", "1",
        "-pix_fmt", "yuv420p",
    ]
    if info.has_audio:
        cmd += ["-c:a", "libopus", "-b:a", WEBM_AUDIO_BITRATE]
    else:
        cmd += ["-an"]
    cmd.append(str(dst))
    _run(cmd)


# --- internals -------------------------------------------------------------


def _even_scale_filter() -> str:
    # libx264 / libvpx-vp9 with yuv420p require even width and height.
    return "scale=trunc(iw/2)*2:trunc(ih/2)*2"


def _duration(data: dict, video_stream: dict) -> float:
    for source in (video_stream, data.get("format") or {}):
        raw = source.get("duration")
        if raw in (None, "", "N/A"):
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    return 0.0


def _run(cmd: list[str], *, capture: bool = False, binary: bool = False) -> subprocess.CompletedProcess:
    log.debug("running: %s", " ".join(cmd))
    try:
        proc = subprocess.run(
            cmd,
            check=True,
            capture_output=capture,
            text=not binary if capture else False,
        )
    except FileNotFoundError as exc:
        raise VideoProcessingError(f"binary not found: {cmd[0]}") from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", "replace")
        raise VideoProcessingError(
            f"{cmd[0]} failed (exit {exc.returncode}): {stderr or '<no stderr>'}"
        ) from exc
    return proc
