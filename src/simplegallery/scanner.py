"""Source directory scanner: discover galleries and media files."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from .config import Config
from .slugify import slugify

log = logging.getLogger(__name__)

# Image extensions that need transcoding to JPEG for inline display. Anything
# outside this set in `Config.image_extensions` is treated as browser-friendly
# and referenced directly via its original URL.
TRANSCODE_EXTS: frozenset[str] = frozenset({".heic", ".heif", ".tif", ".tiff"})


@dataclass(frozen=True)
class MediaFile:
    """A single image or video discovered in a gallery directory."""

    source: Path
    kind: str  # "image" or "video"
    slug: str
    size: int
    mtime: float
    output_thumb: Path
    output_full: Path | None = None  # images requiring transcode (HEIC/TIFF)
    output_mp4: Path | None = None   # videos
    output_webm: Path | None = None  # videos
    transcode_needed: bool = False
    # Path to the original media relative to web_root (POSIX form). Used as
    # data-src for browser-friendly images and as the lightbox download link
    # for every media item.
    original_rel: PurePosixPath = field(default_factory=PurePosixPath)

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
    """A directory of media. May contain own media and/or nested subgalleries."""

    name: str
    slug: str
    source_dir: Path
    output_dir: Path
    images: list[MediaFile] = field(default_factory=list)
    videos: list[MediaFile] = field(default_factory=list)
    cover_file: MediaFile | None = None
    rel_path: PurePosixPath = field(default_factory=PurePosixPath)
    subgalleries: list["Gallery"] = field(default_factory=list)
    # Ancestors + self chain as (name, rel_path). Renderer turns rel_path into
    # an href relative to the page being rendered.
    breadcrumbs: list[tuple[str, PurePosixPath]] = field(default_factory=list)

    @property
    def media(self) -> list[MediaFile]:
        return [*self.images, *self.videos]

    @property
    def count(self) -> int:
        """Own media count (non-recursive)."""
        return len(self.images) + len(self.videos)

    @property
    def subcount(self) -> int:
        """Direct subgallery count (non-recursive)."""
        return len(self.subgalleries)

    def walk(self) -> list["Gallery"]:
        """DFS pre-order over self + all descendants."""
        out: list[Gallery] = [self]
        for sg in self.subgalleries:
            out.extend(sg.walk())
        return out


class DirectoryScanner:
    """Walk source directory recursively and build a Gallery tree."""

    def __init__(self, config: Config) -> None:
        self.config = config

    def scan_tree(self) -> Gallery | None:
        """Return the root Gallery covering the entire source tree, or None
        if the tree has no media at any depth.

        Output dirs mirror source rel paths under `web_root` (Config.output).
        Reserved names at the source root (`assets`, `index.html`,
        `<gallery_subdir>`) are skipped with a warning to keep generated
        output and source distinct.
        """
        source = self.config.source
        if not source.is_dir():
            log.warning("source dir does not exist: %s", source)
            return None

        title = self.config.title
        root = self._scan_tree_dir(
            path=source,
            rel_path=PurePosixPath(),
            name=title,
            breadcrumbs=[(title, PurePosixPath())],
            depth=0,
        )
        return root

    def _scan_tree_dir(
        self,
        *,
        path: Path,
        rel_path: PurePosixPath,
        name: str,
        breadcrumbs: list[tuple[str, PurePosixPath]],
        depth: int,
    ) -> Gallery | None:
        web_root = self.config.output
        output_dir = web_root / rel_path if str(rel_path) else web_root
        gallery_slug = slugify(name) if depth > 0 else slugify(name or "gallery")
        gallery = Gallery(
            name=name,
            slug=gallery_slug,
            source_dir=path,
            output_dir=output_dir,
            rel_path=rel_path,
            breadcrumbs=breadcrumbs,
        )

        image_exts = self.config.image_extensions
        video_exts = self.config.video_extensions
        direct_exts = self.config.direct_image_extensions
        reserved = self.config.reserved_root_names

        subdirs: list[Path] = []
        file_slugs: set[str] = set()

        for entry in sorted(path.iterdir(), key=lambda p: p.name.lower()):
            if entry.name.startswith("."):
                continue
            if entry.is_dir():
                if depth == 0 and entry.name in reserved:
                    log.warning(
                        "skipping reserved name at source root: %s (collides with output)",
                        entry.name,
                    )
                    continue
                subdirs.append(entry)
                continue
            if not entry.is_file():
                continue
            ext = entry.suffix.lower()
            if ext in image_exts:
                kind = "image"
            elif ext in video_exts:
                kind = "video"
            else:
                continue
            try:
                stat = entry.stat()
            except OSError as exc:
                log.warning("stat failed: %s (%s)", entry, exc)
                continue
            file_slug = slugify(entry.stem, file_slugs)
            file_slugs.add(file_slug)
            transcode = (kind == "image") and (ext not in direct_exts)
            original_rel = PurePosixPath(self.config.gallery_subdir) / rel_path / entry.name
            media = self._build_media(
                source=entry,
                kind=kind,
                slug=file_slug,
                size=stat.st_size,
                mtime=stat.st_mtime,
                output_dir=output_dir,
                original_rel=original_rel,
                transcode_needed=transcode,
            )
            if kind == "image":
                gallery.images.append(media)
            else:
                gallery.videos.append(media)

        for sub in subdirs:
            sub_rel = rel_path / sub.name if str(rel_path) else PurePosixPath(sub.name)
            sub_crumbs = [*breadcrumbs, (sub.name, sub_rel)]
            sg = self._scan_tree_dir(
                path=sub,
                rel_path=sub_rel,
                name=sub.name,
                breadcrumbs=sub_crumbs,
                depth=depth + 1,
            )
            if sg is not None:
                gallery.subgalleries.append(sg)

        if gallery.count == 0 and gallery.subcount == 0:
            log.info("skipping empty gallery: %s", path)
            return None

        gallery.cover_file = (
            gallery.images[0] if gallery.images else (gallery.videos[0] if gallery.videos else None)
        )
        return gallery

    @staticmethod
    def _build_media(
        *,
        source: Path,
        kind: str,
        slug: str,
        size: int,
        mtime: float,
        output_dir: Path,
        original_rel: PurePosixPath,
        transcode_needed: bool,
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
                output_full=(output_dir / "full" / f"{slug}.jpg") if transcode_needed else None,
                transcode_needed=transcode_needed,
                original_rel=original_rel,
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
            transcode_needed=False,
            original_rel=original_rel,
        )
