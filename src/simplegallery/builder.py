"""Top-level build orchestrator: scan → cache → process images → render."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import image_processor, video_processor
from .cache import BuildCache
from .config import Config
from .renderer import Renderer
from .scanner import DirectoryScanner, Gallery, MediaFile

log = logging.getLogger(__name__)


class GalleryBuilder:
    """Coordinate scanner, cache, image + video processors, renderer."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.scanner = DirectoryScanner(config)
        self.cache = BuildCache(config.output)
        self.renderer = Renderer(config)

    def build_all(self) -> list[Path]:
        """Full build. Returns list of rendered HTML paths (for tests/logging)."""
        return self._build(selected_names=None, rebuild_index=True)

    def build_galleries(
        self,
        names: set[str] | None,
        rebuild_index: bool = True,
    ) -> list[Path]:
        """Partial rebuild.

        names=None → full build (alias for build_all).
        names=empty set → only re-render index (no per-gallery work).
        names=non-empty set → process only galleries whose source dir name is in the set;
        always re-render index when rebuild_index is True.
        """
        return self._build(selected_names=names, rebuild_index=rebuild_index)

    # --- internal -------------------------------------------------------

    def _build(
        self,
        selected_names: set[str] | None,
        rebuild_index: bool,
    ) -> list[Path]:
        self.config.output.mkdir(parents=True, exist_ok=True)
        self.cache.load()
        galleries = self.scanner.scan()
        log.info("scanned %d galler%s", len(galleries), "y" if len(galleries) == 1 else "ies")

        removed = self.cache.prune(galleries)
        for path in removed:
            log.info("pruned: %s", path)

        self.renderer.copy_assets()

        if selected_names is None:
            selected = galleries
        else:
            selected = [g for g in galleries if g.source_dir.name in selected_names]
            missing = selected_names - {g.source_dir.name for g in galleries}
            if missing:
                log.info("dirty galleries no longer present: %s", sorted(missing))

        images = [m for g in selected for m in g.images]
        exif_by_path = self._process_images(images)

        videos = [m for g in selected for m in g.videos]
        self._process_videos(videos)

        rendered: list[Path] = []
        if rebuild_index:
            rendered.append(self.renderer.render_index(galleries))
        for gallery in selected:
            exif_map = self._exif_for_gallery(gallery, exif_by_path)
            rendered.append(self.renderer.render_gallery(gallery, exif=exif_map))

        self.cache.save()
        log.info("rendered %d page(s)", len(rendered))
        return rendered

    # --- image pipeline -------------------------------------------------

    def _process_images(self, images: list[MediaFile]) -> dict[Path, dict]:
        """Run thumbnail + full + EXIF for each image. Returns EXIF keyed by source path."""
        exif: dict[Path, dict] = {}
        if not images:
            return exif

        workers = max(1, int(self.config.workers))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(self._process_image, m): m for m in images}
            for fut in as_completed(futures):
                media = futures[fut]
                try:
                    exif[media.source] = fut.result()
                except Exception as exc:
                    log.warning("image failed: %s (%s)", media.source, exc)
        return exif

    def _process_image(self, media: MediaFile) -> dict:
        """Per-image worker: regenerate outputs if stale, always read EXIF."""
        if self.cache.is_stale(media):
            assert media.output_full is not None  # scanner guarantees for images
            image_processor.generate_thumbnail(media.source, media.output_thumb)
            image_processor.generate_full(media.source, media.output_full)
            self.cache.mark_done(media)
        try:
            return image_processor.extract_exif(media.source)
        except Exception as exc:
            log.debug("exif read failed: %s (%s)", media.source, exc)
            return {}

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
