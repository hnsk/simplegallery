"""Runtime configuration for simplegallery."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path


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
    """Runtime configuration. CLI flags override env vars override defaults."""

    source: Path
    output: Path
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

    @classmethod
    def from_env(cls) -> "Config":
        source = Path(_env("SIMPLEGALLERY_SOURCE", "/source") or "/source")
        output = Path(_env("SIMPLEGALLERY_OUTPUT", "/output") or "/output")
        title = _env("SIMPLEGALLERY_TITLE", "Gallery") or "Gallery"
        watch = (_env("SIMPLEGALLERY_WATCH", "0") or "0").lower() in {"1", "true", "yes"}
        workers = _env_int("SIMPLEGALLERY_WORKERS", 4)
        debounce = _env_float("SIMPLEGALLERY_DEBOUNCE", 2.0)
        log_level = _parse_log_level(_env("SIMPLEGALLERY_LOG_LEVEL", "INFO") or "INFO")
        return cls(
            source=source,
            output=output,
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
