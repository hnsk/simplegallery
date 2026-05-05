"""Runtime configuration for simplegallery."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_GALLERY_SUBDIR = "gallery"

# Names reserved at the web_root. User content under any of these (other than
# the configured gallery_subdir itself) is treated as a collision and skipped.
# `gallery_subdir` is the only writable user area; `assets/` and `index.html`
# are owned by the build output.
RESERVED_ROOT_NAMES: frozenset[str] = frozenset({"assets", "index.html"})


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"env {name} must be int, got {raw!r}") from exc


def _env_float(name: str, default: float) -> float:
    raw = _env(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"env {name} must be float, got {raw!r}") from exc


@dataclass
class Config:
    """Runtime configuration. CLI flags override env vars override defaults.

    The web layout owns a single directory mount: ``web_root``. User-supplied
    media lives under ``web_root / gallery_subdir`` (default ``gallery``).
    Generated HTML, ``assets/``, and per-gallery thumb/full/video derivatives
    are written to ``web_root``. ``source`` and ``output`` are derived from
    these and exposed as fields for downstream code that has not yet been
    migrated to the recursive layout.
    """

    web_root: Path | None = None
    gallery_subdir: str = DEFAULT_GALLERY_SUBDIR
    source: Path | None = None
    output: Path | None = None
    title: str = "Gallery"
    watch: bool = False
    workers: int = 4
    debounce_seconds: float = 2.0
    log_level: int = logging.INFO

    image_extensions: frozenset[str] = field(
        default_factory=lambda: frozenset(
            {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".tif", ".tiff", ".gif"}
        )
    )
    video_extensions: frozenset[str] = field(
        default_factory=lambda: frozenset({".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"})
    )
    # Browser-friendly image formats — referenced as originals rather than
    # transcoded to JPEG. Anything in image_extensions not listed here is
    # transcode_needed (HEIC/HEIF/TIFF).
    direct_image_extensions: frozenset[str] = field(
        default_factory=lambda: frozenset({".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"})
    )

    def __post_init__(self) -> None:
        if self.web_root is not None:
            if self.source is None:
                self.source = self.web_root / self.gallery_subdir
            if self.output is None:
                self.output = self.web_root
        if self.source is None or self.output is None:
            raise ValueError("Config requires web_root or explicit source+output")

    @property
    def reserved_root_names(self) -> frozenset[str]:
        """Names disallowed under web_root alongside gallery_subdir."""
        return RESERVED_ROOT_NAMES | {self.gallery_subdir}

    @classmethod
    def from_env(cls) -> "Config":
        web_root = Path(_env("SIMPLEGALLERY_WEB", "/web") or "/web")
        gallery_subdir = _env("SIMPLEGALLERY_GALLERY_SUBDIR", DEFAULT_GALLERY_SUBDIR) or DEFAULT_GALLERY_SUBDIR
        title = _env("SIMPLEGALLERY_TITLE", "Gallery") or "Gallery"
        watch = (_env("SIMPLEGALLERY_WATCH", "0") or "0").lower() in {"1", "true", "yes"}
        workers = _env_int("SIMPLEGALLERY_WORKERS", 4)
        debounce = _env_float("SIMPLEGALLERY_DEBOUNCE", 2.0)
        log_level = _parse_log_level(_env("SIMPLEGALLERY_LOG_LEVEL", "INFO") or "INFO")
        return cls(
            web_root=web_root,
            gallery_subdir=gallery_subdir,
            title=title,
            watch=watch,
            workers=workers,
            debounce_seconds=debounce,
            log_level=log_level,
        )


def _parse_log_level(value: str) -> int:
    name = value.strip().upper()
    level = logging.getLevelNamesMapping().get(name) if hasattr(logging, "getLevelNamesMapping") else None
    if level is None:
        level = getattr(logging, name, None)
    if not isinstance(level, int):
        raise ValueError(f"unknown log level: {value!r}")
    return level
