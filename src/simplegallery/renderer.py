"""HTML rendering: copy hashed static assets and render gallery pages.

Single template (`gallery.html.j2`) handles every page including the root.
Each page receives breadcrumbs, a subgallery card grid (above) and the media
grid (below). Lightbox `data-src` points at the JPEG derivative when one was
generated (HEIC/HEIF/TIFF) and at the original otherwise. `data-original`
always points at the user's original file so the lightbox download button has
something to grab.
"""

from __future__ import annotations

import hashlib
import json
import logging
import posixpath
import shutil
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from .config import Config
from .scanner import Gallery, MediaFile

log = logging.getLogger(__name__)

ASSETS_DIRNAME = "assets"
HASH_LENGTH = 10
INDEX_FILENAME = "index.html"

_HASHED_STATIC_FILES = ("gallery.css", "gallery.js")
_VERBATIM_STATIC_FILES = ("icons/play.svg",)


@dataclass(frozen=True)
class Asset:
    """One static asset emitted into output/assets/ with a content-hashed name."""

    logical: str            # e.g. "gallery.css"
    rel_output: str         # e.g. "assets/gallery.abc1234567.css" (posix, relative to output root)


class Renderer:
    """Render gallery pages and copy hashed static assets."""

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
        for logical in _HASHED_STATIC_FILES:
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
        for logical in _VERBATIM_STATIC_FILES:
            src = static_root.joinpath(logical)
            data = src.read_bytes()
            target = assets_dir / logical
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            result[logical] = Asset(
                logical=logical,
                rel_output=f"{ASSETS_DIRNAME}/{logical}",
            )
        self._assets = result
        return result

    @property
    def assets(self) -> dict[str, Asset]:
        return self._assets

    # --- rendering ------------------------------------------------------

    def render_gallery(
        self,
        gallery: Gallery,
        exif: dict[str, dict] | None = None,
    ) -> Path:
        out_path = gallery.output_dir / INDEX_FILENAME
        page_dir = out_path.parent
        exif_map = exif or {}
        ctx = {
            "site_title": self.config.title,
            "gallery": gallery,
            "is_root": not str(gallery.rel_path),
            "breadcrumbs": self._breadcrumbs(gallery, page_dir),
            "subgalleries": [
                self._subgallery_card(sg, page_dir) for sg in gallery.subgalleries
            ],
            "items": [
                self._gallery_item(m, page_dir, exif_map.get(m.slug))
                for m in gallery.media
            ],
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
        for logical in _HASHED_STATIC_FILES:
            asset = self._assets[logical]
            absolute = self.config.output / asset.rel_output
            short = logical.rsplit(".", 1)[-1]
            out[short] = self._rel(absolute, page_dir)
        return out

    def _breadcrumbs(self, gallery: Gallery, page_dir: Path) -> list[dict]:
        """Return [{name, href}] — last entry has href=None (current page)."""
        crumbs = gallery.breadcrumbs or [(gallery.name, gallery.rel_path)]
        web_root = self.config.output
        out: list[dict] = []
        last = len(crumbs) - 1
        for i, (name, rel) in enumerate(crumbs):
            if i == last:
                out.append({"name": name, "href": None})
                continue
            target = web_root / rel / INDEX_FILENAME if str(rel) else web_root / INDEX_FILENAME
            out.append({"name": name, "href": self._rel(target, page_dir)})
        return out

    def _subgallery_card(self, sg: Gallery, page_dir: Path) -> dict:
        target = sg.output_dir / INDEX_FILENAME
        cover_thumb = (
            self._rel(sg.cover_file.output_thumb, page_dir)
            if sg.cover_file is not None
            else None
        )
        return {
            "name": sg.name,
            "slug": sg.slug,
            "href": self._rel(target, page_dir),
            "cover_thumb": cover_thumb,
            "count": sg.count,
            "subcount": sg.subcount,
        }

    def _gallery_item(
        self,
        media: MediaFile,
        page_dir: Path,
        exif: dict | None = None,
    ) -> dict:
        original_abs = self.config.output / media.original_rel if str(media.original_rel) else None
        original_href = self._rel(original_abs, page_dir) if original_abs is not None else None
        if media.is_image:
            if media.output_full is not None:
                src_href = self._rel(media.output_full, page_dir)
            else:
                src_href = original_href
        else:
            src_href = None
        item: dict[str, object] = {
            "kind": media.kind,
            "name": media.source.name,
            "slug": media.slug,
            "thumb": self._rel(media.output_thumb, page_dir),
        }
        if src_href is not None:
            item["src"] = src_href
        if original_href is not None:
            item["original"] = original_href
        if media.output_mp4 is not None:
            item["mp4"] = self._rel(media.output_mp4, page_dir)
        if media.output_webm is not None:
            item["webm"] = self._rel(media.output_webm, page_dir)
        if media.is_video and media.output_mp4 is None and media.output_webm is None:
            ext = media.source.suffix.lower()
            if ext == ".mp4" and original_href is not None:
                item["mp4"] = original_href
            elif ext == ".webm" and original_href is not None:
                item["webm"] = original_href
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
