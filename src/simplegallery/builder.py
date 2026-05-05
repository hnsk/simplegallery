"""Top-level build orchestrator: scan → cache → process images → render."""

from __future__ import annotations

import logging
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable

from . import image_processor, video_processor
from .cache import BuildCache
from .config import Config
from .renderer import Renderer
from .scanner import DirectoryScanner, Gallery, MediaFile

_MP_CTX = mp.get_context("spawn")

log = logging.getLogger(__name__)


class GalleryBuilder:
    """Coordinate scanner, cache, image + video processors, renderer."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.scanner = DirectoryScanner(config)
        self.cache = BuildCache(
            config.output, reserved_root_names=config.reserved_root_names
        )
        self.renderer = Renderer(config)

    def build_all(
        self,
        dirty_rels: Iterable[str] | None = None,
    ) -> list[Path]:
        """Build the gallery tree.

        Full build when ``dirty_rels`` is None or empty: every gallery
        (re)processed and rendered. Otherwise scoped partial rebuild —
        ``dirty_rels`` are POSIX rel paths under ``config.source`` (``""``
        denotes the source root); media inside any dirty rel (or
        descendant) is reprocessed, while the rel plus every ancestor is
        re-rendered (ancestor pages show subgallery cards whose counts
        depend on descendants).
        """
        norm = _normalize_rels(dirty_rels) if dirty_rels is not None else None
        partial = bool(norm)

        self.config.output.mkdir(parents=True, exist_ok=True)
        self.cache.load()

        root = self.scanner.scan_tree()
        if root is None:
            if not partial:
                log.info("no media found in %s", self.config.source)
            self.renderer.copy_assets()
            self.cache.prune([])
            self.cache.save()
            return []

        galleries = root.walk()
        if partial:
            in_scope: list[Gallery] = []
            to_render: list[Gallery] = []
            for g in galleries:
                rel = _gallery_rel(g)
                if _is_dirty_or_descendant(rel, norm):
                    in_scope.append(g)
                    to_render.append(g)
                elif _is_ancestor_of_dirty(rel, norm):
                    to_render.append(g)
        else:
            in_scope = galleries
            to_render = galleries
            log.info(
                "scanned %d galler%s",
                len(galleries),
                "y" if len(galleries) == 1 else "ies",
            )

        removed = self.cache.prune([root])
        for path in removed:
            log.info("pruned: %s", path)

        self.renderer.copy_assets()

        process_imgs = [m for g in in_scope for m in g.images]
        self._process_image_pipeline(process_imgs)

        exif_imgs = [m for g in to_render for m in g.images]
        exif_by_path = self._extract_exif_batch(exif_imgs)

        videos = [m for g in in_scope for m in g.videos]
        self._process_videos(videos)

        rendered: list[Path] = []
        for gallery in to_render:
            exif_map = self._exif_for_gallery(gallery, exif_by_path)
            rendered.append(self.renderer.render_gallery(gallery, exif=exif_map))

        self.cache.save()
        if partial:
            log.info(
                "partial rebuild: %d dirty rel(s) → rendered %d page(s)",
                len(norm),
                len(rendered),
            )
        else:
            log.info("rendered %d page(s)", len(rendered))
        return rendered

    # --- image pipeline -------------------------------------------------

    def _process_image_pipeline(self, images: list[MediaFile]) -> None:
        """Run thumbnail + (optional) full re-encode for stale images.

        Uses a process pool because ImageMagick / Wand is not thread-safe;
        concurrent wand calls in the same process collide on the global
        pixel cache. Cache is updated for every successful image.
        """
        if not images:
            return
        workers = max(1, int(self.config.workers))
        stale_specs: list[tuple[Path, Path, Path | None]] = []
        media_by_src: dict[Path, MediaFile] = {}
        for media in images:
            media_by_src[media.source] = media
            if self.cache.is_stale(media):
                # output_full is set iff a JPEG derivative is needed (HEIC/TIFF
                # in tree mode). Browser-friendly originals (jpg/png/webp/...)
                # have output_full=None and are referenced directly.
                stale_specs.append(
                    (media.source, media.output_thumb, media.output_full)
                )
        if not stale_specs:
            return
        log.info("processing %d image(s)", len(stale_specs))
        with ProcessPoolExecutor(
            max_workers=workers,
            mp_context=_MP_CTX,
            initializer=_worker_log_init,
            initargs=(self.config.log_level,),
        ) as pool:
            futures = {pool.submit(_image_worker, spec): spec for spec in stale_specs}
            for fut in as_completed(futures):
                src, _, _ = futures[fut]
                try:
                    fut.result()
                    self.cache.mark_done(media_by_src[src])
                    log.info("image done: %s", src)
                except Exception as exc:
                    log.warning("image failed: %s (%s)", src, exc)

    def _extract_exif_batch(self, images: list[MediaFile]) -> dict[Path, dict]:
        """Read EXIF for every supplied image. Returns dict keyed by source path."""
        exif: dict[Path, dict] = {}
        if not images:
            return exif
        workers = max(1, int(self.config.workers))
        with ProcessPoolExecutor(
            max_workers=workers,
            mp_context=_MP_CTX,
            initializer=_worker_log_init,
            initargs=(self.config.log_level,),
        ) as pool:
            exif_futures = {pool.submit(_exif_worker, m.source): m for m in images}
            for fut in as_completed(exif_futures):
                media = exif_futures[fut]
                try:
                    exif[media.source] = fut.result()
                except Exception as exc:
                    log.debug("exif read failed: %s (%s)", media.source, exc)
                    exif[media.source] = {}
        return exif

    # --- video pipeline -------------------------------------------------

    def _process_videos(self, videos: list[MediaFile]) -> None:
        if not videos:
            return
        stale = [m for m in videos if self.cache.is_stale(m)]
        if not stale:
            return
        workers = max(1, int(self.config.workers))
        log.info("processing %d video(s)", len(stale))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(self._process_video, m): m for m in stale}
            for fut in as_completed(futures):
                media = futures[fut]
                try:
                    fut.result()
                    log.info("video done: %s", media.source)
                except Exception as exc:
                    log.warning("video failed: %s (%s)", media.source, exc)

    def _process_video(self, media: MediaFile) -> None:
        log.info("processing video: %s", media.source)
        info = video_processor.probe(media.source)
        video_processor.generate_thumbnail(media.source, media.output_thumb, info=info)
        if media.output_mp4 is not None:
            video_processor.transcode_mp4(media.source, media.output_mp4, info=info)
        if media.output_webm is not None:
            video_processor.transcode_webm(media.source, media.output_webm, info=info)
        self.cache.mark_done(media)

    @staticmethod
    def _exif_for_gallery(
        gallery: Gallery, exif_by_path: dict[Path, dict]
    ) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for media in gallery.images:
            data = exif_by_path.get(media.source)
            if data:
                out[media.slug] = data
        return out


def _worker_log_init(level: int) -> None:
    """Configure logging in spawned worker processes.

    ProcessPoolExecutor + spawn re-imports modules in child without inheriting
    the root logger config, so without this each worker would silently drop
    log records.
    """
    import sys

    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
        )
        root.addHandler(handler)
    root.setLevel(level)


def _image_worker(spec: tuple[Path, Path, Path | None]) -> None:
    src, thumb, full = spec
    log.info("processing image: %s", src)
    image_processor.generate_thumbnail(src, thumb)
    if full is not None:
        image_processor.generate_full(src, full)


def _exif_worker(src: Path) -> dict:
    return image_processor.extract_exif(src)


def _gallery_rel(g: Gallery) -> str:
    """POSIX rel path string of gallery under source. ``""`` for the root."""
    s = g.rel_path.as_posix()
    return "" if s in ("", ".") else s


def _normalize_rels(rels: Iterable[str]) -> set[str]:
    """Strip leading/trailing slashes; ``"."``/``""`` collapse to ``""``."""
    out: set[str] = set()
    for r in rels:
        s = r.strip("/")
        out.add("" if s in ("", ".") else s)
    return out


def _is_dirty_or_descendant(rel: str, dirty: set[str]) -> bool:
    """Is ``rel`` exactly a dirty rel, or nested inside one?"""
    for d in dirty:
        if d == "":
            return True
        if rel == d or rel.startswith(d + "/"):
            return True
    return False


def _is_ancestor_of_dirty(rel: str, dirty: set[str]) -> bool:
    """Is ``rel`` a strict ancestor of any dirty rel?"""
    for d in dirty:
        if d == "":
            continue
        if rel == "":
            return True
        if d.startswith(rel + "/"):
            return True
    return False
