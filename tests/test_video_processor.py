"""Step 6 video processor: probe, thumbnail, MP4/WebM transcode.

Fixture clips are generated on the fly via ffmpeg's lavfi sources so we don't
have to commit binary files. Transcode tests are marked `slow` — they run by
default but can be deselected with `-m "not slow"`.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from wand.image import Image as WandImage

from simplegallery.video_processor import (
    VideoInfo,
    VideoProcessingError,
    generate_thumbnail,
    probe,
    transcode_mp4,
    transcode_webm,
)


FIXTURE_WIDTH = 320
FIXTURE_HEIGHT = 240
FIXTURE_DURATION = 2  # seconds


def _ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


pytestmark = pytest.mark.skipif(
    not _ffmpeg_available(),
    reason="ffmpeg/ffprobe not installed",
)


def _make_clip(dst: Path, *, with_audio: bool) -> Path:
    """Build a short, low-res mp4 with `ffmpeg`'s synthetic sources."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-loglevel", "error",
        "-y",
        "-f", "lavfi",
        "-i", f"testsrc=duration={FIXTURE_DURATION}:size={FIXTURE_WIDTH}x{FIXTURE_HEIGHT}:rate=15",
    ]
    if with_audio:
        cmd += [
            "-f", "lavfi",
            "-i", f"sine=frequency=440:duration={FIXTURE_DURATION}",
            "-c:a", "aac",
            "-b:a", "64k",
        ]
    cmd += [
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-pix_fmt", "yuv420p",
        str(dst),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return dst


@pytest.fixture(scope="session")
def mp4_with_audio(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _make_clip(tmp_path_factory.mktemp("clips") / "with_audio.mp4", with_audio=True)


@pytest.fixture(scope="session")
def mp4_silent(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return _make_clip(tmp_path_factory.mktemp("clips") / "silent.mp4", with_audio=False)


# --- probe ---------------------------------------------------------------


def test_probe_returns_expected_fields(mp4_with_audio: Path) -> None:
    info = probe(mp4_with_audio)
    assert isinstance(info, VideoInfo)
    assert info.width == FIXTURE_WIDTH
    assert info.height == FIXTURE_HEIGHT
    assert info.codec == "h264"
    assert info.has_audio is True
    assert info.duration == pytest.approx(FIXTURE_DURATION, abs=0.5)


def test_probe_detects_silent_clip(mp4_silent: Path) -> None:
    info = probe(mp4_silent)
    assert info.has_audio is False


def test_probe_raises_on_missing_file(tmp_path: Path) -> None:
    with pytest.raises(VideoProcessingError):
        probe(tmp_path / "nope.mp4")


# --- thumbnail -----------------------------------------------------------


def test_generate_thumbnail_writes_webp(mp4_with_audio: Path, tmp_path: Path) -> None:
    dst = tmp_path / "nested" / "thumb.webp"
    generate_thumbnail(mp4_with_audio, dst)
    assert dst.is_file()
    with WandImage(filename=str(dst)) as img:
        assert img.format.upper() == "WEBP"
        assert img.width == FIXTURE_WIDTH
        assert img.height == FIXTURE_HEIGHT


def test_generate_thumbnail_uses_supplied_info(mp4_with_audio: Path, tmp_path: Path) -> None:
    info = probe(mp4_with_audio)
    dst = tmp_path / "thumb.webp"
    generate_thumbnail(mp4_with_audio, dst, info=info)
    assert dst.is_file()


# --- transcode (slow) ----------------------------------------------------


@pytest.mark.slow
def test_transcode_mp4_with_audio(mp4_with_audio: Path, tmp_path: Path) -> None:
    dst = tmp_path / "out.mp4"
    transcode_mp4(mp4_with_audio, dst)
    assert dst.is_file() and dst.stat().st_size > 0
    info = probe(dst)
    assert info.codec == "h264"
    assert info.has_audio is True


@pytest.mark.slow
def test_transcode_mp4_silent_omits_audio(mp4_silent: Path, tmp_path: Path) -> None:
    dst = tmp_path / "out.mp4"
    transcode_mp4(mp4_silent, dst)
    info = probe(dst)
    assert info.has_audio is False


@pytest.mark.slow
def test_transcode_webm_with_audio(mp4_with_audio: Path, tmp_path: Path) -> None:
    dst = tmp_path / "out.webm"
    transcode_webm(mp4_with_audio, dst)
    assert dst.is_file() and dst.stat().st_size > 0
    info = probe(dst)
    assert info.codec in {"vp9", "vp09"}
    assert info.has_audio is True


@pytest.mark.slow
def test_transcode_webm_silent_omits_audio(mp4_silent: Path, tmp_path: Path) -> None:
    dst = tmp_path / "out.webm"
    transcode_webm(mp4_silent, dst)
    info = probe(dst)
    assert info.has_audio is False
