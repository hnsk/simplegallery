"""Source directory scanner: discover galleries and media files."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from .config import Config
from .slugify import slugify

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class MediaFile:
    """A single image or video discovered in a gallery directory."""

    source: Path
    kind: str  # "image" or "video"
    slug: str
    size: int
    mtime: float
    output_thumb: Path
    output_full: Path | None = None  # images
    output_mp4: Path | None = None   # videos
    output_webm: Path | None = None  # videos

    @property
    def is_image(self) -> bool:
        return self.kind == "image"

    @property
    def is_video(self) -> bool:
        return self.kind == "video"

    def output_paths(self) -> list[Path]:
        paths: list[Path] = [self.output_thumb]
        for p in (self.output_full, self.output_mp4, self.output_webm):
            if p is not None:
                paths.append(p)
        return paths


@dataclass
class Gallery:
    """A top-level subdirectory of source, treated as a single gallery."""

    name: str
    slug: str
    source_dir: Path
    output_dir: Path
    images: list[MediaFile] = field(default_factory=list)
    videos: list[MediaFile] = field(default_factory=list)
    cover_file: MediaFile | None = None

    @property
    def media(self) -> list[MediaFile]:
        return [*self.images, *self.videos]

    @property
    def count(self) -> int:
        return len(self.images) + len(self.videos)


class DirectoryScanner:
    """Walk source directory, build Gallery list."""

    def __init__(self, config: Config) -> None:
        self.config = config

    def scan(self) -> list[Gallery]:
        source = self.config.source
        if not source.is_dir():
            log.warning("source dir does not exist: %s", source)
            return []

        galleries: list[Gallery] = []
        gallery_slugs: set[str] = set()

        for entry in sorted(source.iterdir(), key=lambda p: p.name.lower()):
            if not entry.is_dir():
                continue
            if entry.name.startswith("."):
                continue
            slug = slugify(entry.name, gallery_slugs)
            gallery_slugs.add(slug)
            gallery = self._scan_gallery(entry, slug)
            if gallery.count == 0:
                log.info("skipping empty gallery: %s", entry.name)
                continue
            galleries.append(gallery)
        return galleries

    def _scan_gallery(self, source_dir: Path, slug: str) -> Gallery:
        output_dir = self.config.output / slug
        gallery = Gallery(
            name=source_dir.name,
            slug=slug,
            source_dir=source_dir,
            output_dir=output_dir,
        )

        image_exts = self.config.image_extensions
        video_exts = self.config.video_extensions
        file_slugs: set[str] = set()

        for f in sorted(source_dir.iterdir(), key=lambda p: p.name.lower()):
            if not f.is_file():
                continue
            if f.name.startswith("."):
                continue
            ext = f.suffix.lower()
            if ext in image_exts:
                kind = "image"
            elif ext in video_exts:
                kind = "video"
            else:
                continue

            try:
                stat = f.stat()
            except OSError as exc:
                log.warning("stat failed: %s (%s)", f, exc)
                continue

            file_slug = slugify(f.stem, file_slugs)
            file_slugs.add(file_slug)
            media = self._build_media(f, kind, file_slug, stat.st_size, stat.st_mtime, output_dir)
            if kind == "image":
                gallery.images.append(media)
            else:
                gallery.videos.append(media)

        gallery.cover_file = gallery.images[0] if gallery.images else (
            gallery.videos[0] if gallery.videos else None
        )
        return gallery

    @staticmethod
    def _build_media(
        source: Path, kind: str, slug: str, size: int, mtime: float, output_dir: Path
    ) -> MediaFile:
        thumb = output_dir / "thumbs" / f"{slug}.webp"
        if kind == "image":
            return MediaFile(
                source=source,
                kind=kind,
                slug=slug,
                size=size,
                mtime=mtime,
                output_thumb=thumb,
                output_full=output_dir / "full" / f"{slug}.jpg",
            )
        return MediaFile(
            source=source,
            kind=kind,
            slug=slug,
            size=size,
            mtime=mtime,
            output_thumb=thumb,
            output_mp4=output_dir / "video" / f"{slug}.mp4",
            output_webm=output_dir / "video" / f"{slug}.webm",
        )
