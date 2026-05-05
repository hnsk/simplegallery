"""Top-level build orchestrator: scan → cache prune → render (media processing in later steps)."""

from __future__ import annotations

import logging
from pathlib import Path

from .cache import BuildCache
from .config import Config
from .renderer import Renderer
from .scanner import DirectoryScanner

log = logging.getLogger(__name__)


class GalleryBuilder:
    """Coordinate scanner, cache, renderer (and later: image/video processors)."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.scanner = DirectoryScanner(config)
        self.cache = BuildCache(config.output)
        self.renderer = Renderer(config)

    def build_all(self) -> list[Path]:
        """Full build. Returns list of rendered HTML paths (for tests/logging)."""
        self.config.output.mkdir(parents=True, exist_ok=True)
        self.cache.load()
        galleries = self.scanner.scan()
        log.info("scanned %d galler%s", len(galleries), "y" if len(galleries) == 1 else "ies")

        removed = self.cache.prune(galleries)
        for path in removed:
            log.info("pruned: %s", path)

        self.renderer.copy_assets()

        rendered: list[Path] = [self.renderer.render_index(galleries)]
        for gallery in galleries:
            rendered.append(self.renderer.render_gallery(gallery))

        self.cache.save()
        log.info("rendered %d page(s)", len(rendered))
        return rendered
