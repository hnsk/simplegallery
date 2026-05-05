"""Image processing: thumbnails, full-size derivatives, EXIF extraction.

Backed by Wand (ImageMagick + libheif). Camera RAW (NEF/CR2/CR3/ARW/RAF/DNG/...)
goes through libraw's ``dcraw_emu`` first — it produces a full-resolution,
white-balanced sRGB TIFF on stdout which Wand then reads as a normal TIFF blob.
This avoids relying on an IM raw delegate (Alpine's IM build has none) and
gives deterministic, decoder-correct results regardless of the RAW container's
TIFF-magic-byte mimicry.

EXIF read uses Wand's metadata first and falls back to exifread for formats /
tags Wand misses. For RAW files the wand path is expected to fail (no decoder
for the original container); exifread reads tags from the RAW directly.

Privacy note on GPS metadata: ``generate_full`` strips EXIF GPS tags from the
JPEG derivative it produces. Derivatives are only generated for formats that
need transcoding (HEIC/HEIF/TIFF + camera RAW). Browser-friendly originals
(jpg/jpeg/png/webp/gif/avif) are served directly from ``<gallery_subdir>/``
without modification, so any GPS tags they carry remain in the file the visitor
downloads. Strip GPS upstream if that matters for the source set.
"""

from __future__ import annotations

import logging
import subprocess
from contextlib import contextmanager
from fractions import Fraction
from pathlib import Path
from typing import Iterator, Mapping

import exifread
from wand.image import Image

from .config import RAW_IMAGE_EXTENSIONS

log = logging.getLogger(__name__)

THUMB_WIDTH = 400
THUMB_HEIGHT = 300
THUMB_QUALITY = 80
FULL_QUALITY = 92

_GPS_PREFIX = "exif:GPS"

# libraw CLI used to demosaic camera RAW into TIFF. ``-T`` TIFF output,
# ``-Z -`` write to stdout, ``-w`` apply camera white balance (otherwise the
# result is grey-cast). Full-resolution demosaic — ~10× slower than ``-h``
# half-size, but the JPEG derivative carries the sensor's full pixel count.
_DCRAW_EMU = "dcraw_emu"
_DCRAW_EMU_ARGS: tuple[str, ...] = ("-T", "-w", "-Z", "-")


def _is_raw(src: Path) -> bool:
    return src.suffix.lower() in RAW_IMAGE_EXTENSIONS


def _read_raw_tiff(src: Path) -> bytes:
    """Demosaic a camera RAW via libraw and return the TIFF bytes."""
    try:
        proc = subprocess.run(
            [_DCRAW_EMU, *_DCRAW_EMU_ARGS, str(src)],
            check=True,
            capture_output=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"{_DCRAW_EMU} not on PATH — install libraw-tools to decode camera RAW"
        ) from exc
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(f"{_DCRAW_EMU} failed for {src}: {stderr}") from exc
    if not proc.stdout:
        raise RuntimeError(f"{_DCRAW_EMU} produced empty output for {src}")
    return proc.stdout


@contextmanager
def _open_image(src: Path) -> Iterator[Image]:
    """Yield a Wand ``Image`` for ``src``, transparently handling camera RAW."""
    if _is_raw(src):
        blob = _read_raw_tiff(src)
        with Image(blob=blob, format="tiff") as img:
            yield img
    else:
        with Image(filename=str(src)) as img:
            yield img

# Map source EXIF keys → display label. Wand keys come as "exif:Make"; exifread
# tag names come as "Image Make" / "EXIF FNumber" / etc.
_DISPLAY_FIELDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Make",        ("exif:Make", "Image Make")),
    ("Model",       ("exif:Model", "Image Model")),
    ("Lens",        ("exif:LensModel", "EXIF LensModel", "MakerNote LensModel")),
    ("Date",        ("exif:DateTimeOriginal", "EXIF DateTimeOriginal", "Image DateTime")),
    ("Exposure",    ("exif:ExposureTime", "EXIF ExposureTime")),
    ("Aperture",    ("exif:FNumber", "EXIF FNumber")),
    ("ISO",         ("exif:PhotographicSensitivity", "exif:ISOSpeedRatings", "EXIF ISOSpeedRatings")),
    ("FocalLength", ("exif:FocalLength", "EXIF FocalLength")),
)


def generate_thumbnail(src: Path, dst: Path) -> None:
    """Write a 400×300 WebP crop-fill thumbnail. Auto-oriented."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    with _open_image(src) as img:
        img.auto_orient()
        _crop_fill(img, THUMB_WIDTH, THUMB_HEIGHT)
        img.strip()
        img.format = "webp"
        img.compression_quality = THUMB_QUALITY
        img.save(filename=str(dst))


def generate_full(src: Path, dst: Path) -> None:
    """Write an auto-oriented JPEG with GPS metadata removed, camera tags kept."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    with _open_image(src) as img:
        img.auto_orient()
        for key in [k for k in img.metadata.keys() if k.startswith(_GPS_PREFIX)]:
            try:
                del img.metadata[key]
            except KeyError:
                pass
        img.format = "jpeg"
        img.compression_quality = FULL_QUALITY
        img.save(filename=str(dst))


def extract_exif(src: Path) -> dict[str, str]:
    """Return a small dict of human-readable EXIF tags. Empty if none found."""
    wand_tags = _read_with_wand(src)
    exifread_tags = _read_with_exifread(src)

    out: dict[str, str] = {}
    for label, keys in _DISPLAY_FIELDS:
        for key in keys:
            value = wand_tags.get(key) or exifread_tags.get(key)
            if value:
                out[label] = value
                break

    return _humanize(out)


# --- internals -------------------------------------------------------------


def _crop_fill(img: Image, target_w: int, target_h: int) -> None:
    sw, sh = img.width, img.height
    if sw == 0 or sh == 0:
        raise ValueError(f"image has zero dimension: {sw}x{sh}")
    scale = max(target_w / sw, target_h / sh)
    new_w = max(target_w, int(round(sw * scale)))
    new_h = max(target_h, int(round(sh * scale)))
    img.resize(new_w, new_h)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    img.crop(left=left, top=top, width=target_w, height=target_h)


def _read_with_wand(src: Path) -> dict[str, str]:
    # RAW originals have no IM coder — skip and let exifread do the work.
    if _is_raw(src):
        return {}
    try:
        with Image(filename=str(src)) as img:
            return {k: str(v) for k, v in img.metadata.items() if v}
    except Exception as exc:
        log.debug("wand metadata read failed for %s: %s", src, exc)
        return {}


def _read_with_exifread(src: Path) -> dict[str, str]:
    try:
        with src.open("rb") as fh:
            tags = exifread.process_file(fh, details=False)
    except Exception as exc:
        log.debug("exifread failed for %s: %s", src, exc)
        return {}
    return {k: str(v) for k, v in tags.items() if v and not k.startswith("JPEGThumbnail")}


def _humanize(raw: Mapping[str, str]) -> dict[str, str]:
    """Combine make+model, format exposure/aperture/focal length sensibly."""
    out: dict[str, str] = {}

    make = raw.get("Make", "").strip()
    model = raw.get("Model", "").strip()
    if make and model and not model.lower().startswith(make.lower()):
        out["Camera"] = f"{make} {model}"
    elif model:
        out["Camera"] = model
    elif make:
        out["Camera"] = make

    if "Lens" in raw:
        lens = raw["Lens"].strip()
        if lens:
            out["Lens"] = lens

    if "Date" in raw:
        out["Date"] = raw["Date"].strip()

    if "Exposure" in raw:
        out["Exposure"] = _format_exposure(raw["Exposure"])

    if "Aperture" in raw:
        f = _format_fstop(raw["Aperture"])
        if f:
            out["Aperture"] = f

    if "ISO" in raw:
        iso = raw["ISO"].strip()
        if iso:
            out["ISO"] = iso

    if "FocalLength" in raw:
        focal = _format_focal(raw["FocalLength"])
        if focal:
            out["FocalLength"] = focal

    return out


def _format_exposure(value: str) -> str:
    value = value.strip()
    frac = _to_fraction(value)
    if frac is None:
        return value
    if frac >= 1:
        return f"{float(frac):g}s"
    inv = (1 / frac).limit_denominator(1)
    return f"1/{int(inv)}s"


def _format_fstop(value: str) -> str:
    frac = _to_fraction(value.strip())
    if frac is None:
        return ""
    return f"f/{float(frac):g}"


def _format_focal(value: str) -> str:
    frac = _to_fraction(value.strip())
    if frac is None:
        return value.strip()
    return f"{float(frac):g}mm"


def _to_fraction(value: str) -> Fraction | None:
    s = value.strip()
    if not s:
        return None
    try:
        if "/" in s:
            num, _, den = s.partition("/")
            return Fraction(int(num.strip()), int(den.strip()))
        return Fraction(s)
    except (ValueError, ZeroDivisionError):
        return None
