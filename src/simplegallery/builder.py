"""Top-level build orchestrator: scan → cache → process images → render."""

from __future__ import annotations

import logging
import multiprocessing as mp
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from pathlib import Path

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

    def build_all(self) -> list[Path]:
        """Full build over the recursive web-root layout.

        Returns the list of rendered HTML paths (root + every non-empty
        subgallery). Empty trees produce no pages.
        """
        return self.build_tree()

    def build_tree(self) -> list[Path]:
        """DFS-walk the source tree, process all media, render every page."""
        self.config.output.mkdir(parents=True, exist_ok=True)
        self.cache.load()

        root = self.scanner.scan_tree()
        if root is None:
            log.info("no media found in %s", self.config.source)
            self.renderer.copy_assets()
            self.cache.prune([])
            self.cache.save()
            return []

        galleries = root.walk()
        log.info(
            "scanned %d galler%s",
            len(galleries),
            "y" if len(galleries) == 1 else "ies",
        )

        removed = self.cache.prune([root])
        for path in removed:
            log.info("pruned: %s", path)

        self.renderer.copy_assets()

        images = [m for g in galleries for m in g.images]
        exif_by_path = self._process_images(images)

        videos = [m for g in galleries for m in g.videos]
        self._process_videos(videos)

        rendered: list[Path] = []
        for gallery in galleries:
            exif_map = self._exif_for_gallery(gallery, exif_by_path)
            rendered.append(self.renderer.render_gallery(gallery, exif=exif_map))

        self.cache.save()
        log.info("rendered %d page(s)", len(rendered))
        return rendered

    def build_galleries(
        self,
        names: set[str] | None,
        rebuild_index: bool = True,
    ) -> list[Path]:
        """Watcher entrypoint — currently routes to a full ``build_tree()``.

        Per-dir dirty propagation under the recursive layout lands in substep
        10.8; until then any change triggers a full rebuild. ``names`` and
        ``rebuild_index`` are accepted for API stability but ignored.
        """
        del names, rebuild_index
        return self.build_tree()

    # --- image pipeline -------------------------------------------------

    def _process_images(self, images: list[MediaFile]) -> dict[Path, dict]:
        """Run thumbnail + full + EXIF for each image. Returns EXIF keyed by source path.

        Uses a process pool because ImageMagick / Wand is not thread-safe; concurrent
        wand calls in the same process collide on the global pixel cache.
        """
        exif: dict[Path, dict] = {}
        if not images:
            return exif

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

        with ProcessPoolExecutor(max_workers=workers, mp_context=_MP_CTX) as pool:
            futures = {pool.submit(_image_worker, spec): spec for spec in stale_specs}
            for fut in as_completed(futures):
                src, _, _ = futures[fut]
                try:
                    fut.result()
                    self.cache.mark_done(media_by_src[src])
                except Exception as exc:
                    log.warning("image failed: %s (%s)", src, exc)

        with ProcessPoolExecutor(max_workers=workers, mp_context=_MP_CTX) as pool:
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
        workers = max(1, int(self.config.workers))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(self._process_video, m): m for m in videos}
            for fut in as_completed(futures):
                media = futures[fut]
                try:
                    fut.result()
                except Exception as exc:
                    log.warning("video failed: %s (%s)", media.source, exc)

    def _process_video(self, media: MediaFile) -> None:
        if not self.cache.is_stale(media):
            return
        assert media.output_mp4 is not None and media.output_webm is not None
        info = video_processor.probe(media.source)
        video_processor.generate_thumbnail(media.source, media.output_thumb, info=info)
        video_processor.transcode_mp4(media.source, media.output_mp4, info=info)
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


def _image_worker(spec: tuple[Path, Path, Path | None]) -> None:
    src, thumb, full = spec
    image_processor.generate_thumbnail(src, thumb)
    if full is not None:
        image_processor.generate_full(src, full)


def _exif_worker(src: Path) -> dict:
    return image_processor.extract_exif(src)
