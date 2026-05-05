"""Step 4 image processor: thumbnail, full, EXIF, GPS strip, HEIC decode.

These tests need real image data. We use sample-data mounted at /sample-data
inside the container (per docker-compose.yml). If the directory isn't mounted
or is empty, the tests skip — sample-data is gitignored so anyone running
locally must drop their own files there.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from wand.image import Image as WandImage

from simplegallery import builder as builder_mod
from simplegallery.image_processor import (
    FULL_QUALITY,
    THUMB_HEIGHT,
    THUMB_WIDTH,
    extract_exif,
    generate_full,
    generate_thumbnail,
)


SAMPLE_DIR = Path(os.environ.get("SIMPLEGALLERY_SAMPLE_DATA", "/sample-data"))


def _first_match(patterns: tuple[str, ...]) -> Path | None:
    if not SAMPLE_DIR.is_dir():
        return None
    for pat in patterns:
        for p in sorted(SAMPLE_DIR.glob(pat)):
            if p.is_file():
                return p
    return None


def _require(patterns: tuple[str, ...], label: str) -> Path:
    src = _first_match(patterns)
    if src is None:
        pytest.skip(f"no {label} sample in {SAMPLE_DIR}")
    return src


@pytest.fixture
def jpeg_sample() -> Path:
    return _require(("*.jpg", "*.jpeg", "*.JPG", "*.JPEG"), "JPEG")


@pytest.fixture
def heic_sample() -> Path:
    return _require(("*.heic", "*.HEIC", "*.heif", "*.HEIF"), "HEIC")


def test_generate_thumbnail_dimensions_and_format(jpeg_sample: Path, tmp_path: Path) -> None:
    dst = tmp_path / "thumb.webp"
    generate_thumbnail(jpeg_sample, dst)
    assert dst.is_file()
    with WandImage(filename=str(dst)) as img:
        assert img.width == THUMB_WIDTH
        assert img.height == THUMB_HEIGHT
        assert img.format.upper() == "WEBP"


def test_generate_thumbnail_creates_parent_dirs(jpeg_sample: Path, tmp_path: Path) -> None:
    dst = tmp_path / "nested" / "deep" / "thumb.webp"
    generate_thumbnail(jpeg_sample, dst)
    assert dst.is_file()


def test_generate_full_is_jpeg_within_source_dimensions(
    jpeg_sample: Path, tmp_path: Path
) -> None:
    dst = tmp_path / "full.jpg"
    generate_full(jpeg_sample, dst)
    assert dst.is_file()

    with WandImage(filename=str(jpeg_sample)) as src_img:
        sw, sh = src_img.width, src_img.height
    with WandImage(filename=str(dst)) as out_img:
        assert out_img.format.upper() == "JPEG"
        assert out_img.width <= sw
        assert out_img.height <= sh
        # Wand reports the encoded JPEG quality back; allow ±2 tolerance.
        assert abs(out_img.compression_quality - FULL_QUALITY) <= 2


def test_generate_full_strips_gps_metadata(jpeg_sample: Path, tmp_path: Path) -> None:
    dst = tmp_path / "stripped.jpg"
    generate_full(jpeg_sample, dst)
    with WandImage(filename=str(dst)) as img:
        gps_keys = [k for k in img.metadata.keys() if k.startswith("exif:GPS")]
    assert gps_keys == []


def test_extract_exif_returns_camera_or_empty(jpeg_sample: Path) -> None:
    """Sample-data may or may not have EXIF — accept either, but type is dict[str, str]."""
    data = extract_exif(jpeg_sample)
    assert isinstance(data, dict)
    for k, v in data.items():
        assert isinstance(k, str)
        assert isinstance(v, str)
        assert v.strip() != ""


def test_extract_exif_camera_tags_when_present(jpeg_sample: Path) -> None:
    data = extract_exif(jpeg_sample)
    if not data:
        pytest.skip("sample JPEG has no EXIF")
    # At least one of the well-known camera-side keys should be present.
    assert any(key in data for key in ("Camera", "Lens", "Date", "Aperture", "Exposure", "ISO", "FocalLength"))


def test_heic_thumbnail_decodes(heic_sample: Path, tmp_path: Path) -> None:
    dst = tmp_path / "heic_thumb.webp"
    generate_thumbnail(heic_sample, dst)
    assert dst.is_file()
    with WandImage(filename=str(dst)) as img:
        assert img.width == THUMB_WIDTH
        assert img.height == THUMB_HEIGHT


def test_heic_full_converts_to_jpeg(heic_sample: Path, tmp_path: Path) -> None:
    dst = tmp_path / "heic_full.jpg"
    generate_full(heic_sample, dst)
    with WandImage(filename=str(dst)) as img:
        assert img.format.upper() == "JPEG"


# --- gate: builder._image_worker only runs generate_full when full is set ---


def _record_calls(monkeypatch: pytest.MonkeyPatch) -> tuple[list[Path], list[Path]]:
    thumb_calls: list[Path] = []
    full_calls: list[Path] = []

    def fake_thumb(src: Path, dst: Path) -> None:
        thumb_calls.append(src)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(b"thumb")

    def fake_full(src: Path, dst: Path) -> None:
        full_calls.append(src)
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(b"full")

    monkeypatch.setattr(builder_mod.image_processor, "generate_thumbnail", fake_thumb)
    monkeypatch.setattr(builder_mod.image_processor, "generate_full", fake_full)
    return thumb_calls, full_calls


def test_image_worker_runs_full_when_path_provided(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    thumbs, fulls = _record_calls(monkeypatch)
    src = tmp_path / "src.jpg"
    src.write_bytes(b"x")
    thumb = tmp_path / "out" / "thumbs" / "src.webp"
    full = tmp_path / "out" / "full" / "src.jpg"

    builder_mod._image_worker((src, thumb, full))

    assert thumbs == [src]
    assert fulls == [src]


def test_image_worker_skips_full_when_path_is_none(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Direct-served formats (jpg/png/webp/...) pass full=None — only the
    thumbnail is produced; the original is referenced as-is for inline view.
    """
    thumbs, fulls = _record_calls(monkeypatch)
    src = tmp_path / "src.jpg"
    src.write_bytes(b"x")
    thumb = tmp_path / "out" / "thumbs" / "src.webp"

    builder_mod._image_worker((src, thumb, None))

    assert thumbs == [src]
    assert fulls == []
