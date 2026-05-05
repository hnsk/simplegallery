"""HTML rendering: copy hashed static assets and render index + gallery pages."""

from __future__ import annotations

import hashlib
import json
import logging
import posixpath
import shutil
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Iterable

from jinja2 import Environment, PackageLoader, select_autoescape

from .config import Config
from .scanner import Gallery, MediaFile

log = logging.getLogger(__name__)

ASSETS_DIRNAME = "assets"
HASH_LENGTH = 10
INDEX_FILENAME = "index.html"

_STATIC_FILES = ("gallery.css", "gallery.js")


@dataclass(frozen=True)
class Asset:
    """One static asset emitted into output/assets/ with a content-hashed name."""

    logical: str            # e.g. "gallery.css"
    rel_output: str         # e.g. "assets/gallery.abc1234567.css" (posix, relative to output root)


class Renderer:
    """Render index + gallery pages and copy hashed static assets."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.env = Environment(
            loader=PackageLoader("simplegallery", "templates"),
            autoescape=select_autoescape(["html", "xml", "j2"]),
            keep_trailing_newline=True,
        )
        self._assets: dict[str, Asset] = {}

    # --- assets ---------------------------------------------------------

    def copy_assets(self) -> dict[str, Asset]:
        """Copy bundled static files into <output>/assets/ with content-hashed names.

        Existing files in the assets dir are removed first so old hashes do not accumulate.
        """
        assets_dir = self.config.output / ASSETS_DIRNAME
        if assets_dir.exists():
            shutil.rmtree(assets_dir)
        assets_dir.mkdir(parents=True, exist_ok=True)

        result: dict[str, Asset] = {}
        static_root = resources.files("simplegallery").joinpath("static")
        for logical in _STATIC_FILES:
            src = static_root.joinpath(logical)
            data = src.read_bytes()
            digest = hashlib.sha256(data).hexdigest()[:HASH_LENGTH]
            stem, _, ext = logical.rpartition(".")
            hashed_name = f"{stem}.{digest}.{ext}"
            (assets_dir / hashed_name).write_bytes(data)
            result[logical] = Asset(
                logical=logical,
                rel_output=f"{ASSETS_DIRNAME}/{hashed_name}",
            )
        self._assets = result
        return result

    @property
    def assets(self) -> dict[str, Asset]:
        return self._assets

    # --- rendering ------------------------------------------------------

    def render_index(self, galleries: Iterable[Gallery]) -> Path:
        galleries = list(galleries)
        out_path = self.config.output / INDEX_FILENAME
        page_dir = out_path.parent
        ctx = {
            "site_title": self.config.title,
            "galleries": [self._index_entry(g, page_dir) for g in galleries],
            "assets": self._page_assets(page_dir),
        }
        template = self.env.get_template("index.html.j2")
        self._write(out_path, template.render(**ctx))
        return out_path

    def render_gallery(
        self,
        gallery: Gallery,
        exif: dict[str, dict] | None = None,
    ) -> Path:
        out_path = gallery.output_dir / INDEX_FILENAME
        page_dir = out_path.parent
        index_path = self.config.output / INDEX_FILENAME
        exif_map = exif or {}
        ctx = {
            "site_title": self.config.title,
            "gallery": gallery,
            "items": [
                self._gallery_item(m, page_dir, exif_map.get(m.slug))
                for m in gallery.media
            ],
            "index_href": self._rel(index_path, page_dir),
            "assets": self._page_assets(page_dir),
        }
        template = self.env.get_template("gallery.html.j2")
        self._write(out_path, template.render(**ctx))
        return out_path

    # --- helpers --------------------------------------------------------

    def _page_assets(self, page_dir: Path) -> dict[str, str]:
        if not self._assets:
            raise RuntimeError("copy_assets() must be called before rendering")
        out: dict[str, str] = {}
        for logical, asset in self._assets.items():
            absolute = self.config.output / asset.rel_output
            short = logical.rsplit(".", 1)[-1]
            out[short] = self._rel(absolute, page_dir)
        return out

    def _index_entry(self, gallery: Gallery, page_dir: Path) -> dict:
        cover_thumb = (
            self._rel(gallery.cover_file.output_thumb, page_dir)
            if gallery.cover_file is not None
            else None
        )
        gallery_index = gallery.output_dir / INDEX_FILENAME
        return {
            "name": gallery.name,
            "slug": gallery.slug,
            "href": self._rel(gallery_index, page_dir),
            "cover_thumb": cover_thumb,
            "count": gallery.count,
        }

    def _gallery_item(
        self,
        media: MediaFile,
        page_dir: Path,
        exif: dict | None = None,
    ) -> dict:
        item: dict[str, object] = {
            "kind": media.kind,
            "name": media.source.name,
            "slug": media.slug,
            "thumb": self._rel(media.output_thumb, page_dir),
        }
        if media.output_full is not None:
            item["full"] = self._rel(media.output_full, page_dir)
        if media.output_mp4 is not None:
            item["mp4"] = self._rel(media.output_mp4, page_dir)
        if media.output_webm is not None:
            item["webm"] = self._rel(media.output_webm, page_dir)
        serialized = serialize_exif(exif)
        if serialized is not None:
            item["exif"] = serialized
        return item

    @staticmethod
    def _rel(target: Path, page_dir: Path) -> str:
        return posixpath.relpath(target.as_posix(), page_dir.as_posix())

    @staticmethod
    def _write(path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


def serialize_exif(exif: dict | None) -> str | None:
    """Serialize EXIF dict for `data-exif` attribute (JSON, attribute-safe)."""
    if not exif:
        return None
    return json.dumps(exif, ensure_ascii=False, separators=(",", ":"))
