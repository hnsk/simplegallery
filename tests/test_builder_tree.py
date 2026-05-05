"""GalleryBuilder.build_tree(): recursive build over the web-root layout."""

from __future__ import annotations

from pathlib import Path

import pytest

from simplegallery.builder import GalleryBuilder
from simplegallery.config import Config
from simplegallery.renderer import ASSETS_DIRNAME


def _touch(path: Path, content: bytes = b"x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


@pytest.fixture
def web(tmp_path: Path) -> Path:
    """web/gallery/ tree exercising root media, nested subs, and HEIC transcode."""
    web = tmp_path / "web"
    g = web / "gallery"
    _touch(g / "cover.jpg")
    _touch(g / "photos" / "a.heic")
    _touch(g / "photos" / "a.jpg")
    _touch(g / "photos" / "macro" / "close.png")
    _touch(g / "photos" / "macro" / "tilt.tif")
    _touch(g / "videos" / "clip.mp4")
    return web


@pytest.fixture
def cfg(web: Path) -> Config:
    return Config(web_root=web, title="Site")


def test_build_tree_renders_root_and_every_non_empty_subgallery(cfg: Config) -> None:
    rendered = GalleryBuilder(cfg).build_tree()
    rel = {p.relative_to(cfg.output).as_posix() for p in rendered}
    assert rel == {
        "index.html",
        "photos/index.html",
        "photos/macro/index.html",
        "videos/index.html",
    }


def test_build_tree_copies_assets(cfg: Config) -> None:
    GalleryBuilder(cfg).build_tree()
    assert (cfg.output / ASSETS_DIRNAME).is_dir()


def test_build_tree_root_uses_gallery_template_with_site_title(cfg: Config) -> None:
    GalleryBuilder(cfg).build_tree()
    html = (cfg.output / "index.html").read_text(encoding="utf-8")
    assert "Site" in html
    assert 'data-gallery="site"' in html


def test_build_tree_heic_emits_full_jpeg_path_only_for_transcoded(cfg: Config) -> None:
    """HEIC → ``photos/full/a.jpg`` referenced as data-src; jpg has no data-src."""
    GalleryBuilder(cfg).build_tree()
    html = (cfg.output / "photos" / "index.html").read_text(encoding="utf-8")
    # HEIC sorted before jpg by name.lower(); takes slug "a", reserves "full/a.jpg".
    assert 'data-src="full/a.jpg"' in html
    # The jpg gets slug "a-2" but no transcode → no full/<slug>.jpg → no data-src
    # for that figure. Verify the thumb is referenced and no full path exists for it.
    assert 'data-thumb="thumbs/a-2.webp"' in html
    assert "full/a-2.jpg" not in html


def test_build_tree_nested_page_uses_gallery_relative_paths(cfg: Config) -> None:
    GalleryBuilder(cfg).build_tree()
    html = (cfg.output / "photos" / "macro" / "index.html").read_text(encoding="utf-8")
    # close.png is browser-friendly: thumb only, no data-src.
    assert 'data-thumb="thumbs/close.webp"' in html
    # tilt.tif transcodes: full path under macro/full/
    assert 'data-src="full/tilt.jpg"' in html
    # asset link climbs two dirs up
    assert 'href="../../assets/' in html


def test_build_tree_video_outputs_referenced(cfg: Config) -> None:
    GalleryBuilder(cfg).build_tree()
    html = (cfg.output / "videos" / "index.html").read_text(encoding="utf-8")
    assert 'data-mp4="video/clip.mp4"' in html
    assert 'data-webm="video/clip.webm"' in html


def test_build_tree_empty_tree_returns_no_pages(tmp_path: Path) -> None:
    web = tmp_path / "web"
    (web / "gallery").mkdir(parents=True)
    cfg = Config(web_root=web)
    rendered = GalleryBuilder(cfg).build_tree()
    assert rendered == []
    # Assets are still copied so the (empty) output dir is well-formed.
    assert (cfg.output / ASSETS_DIRNAME).is_dir()


def test_build_tree_skips_empty_branches(tmp_path: Path) -> None:
    web = tmp_path / "web"
    _touch(web / "gallery" / "photos" / "a.jpg")
    (web / "gallery" / "deserted").mkdir()
    cfg = Config(web_root=web)
    rendered = GalleryBuilder(cfg).build_tree()
    rel = {p.relative_to(cfg.output).as_posix() for p in rendered}
    assert "deserted/index.html" not in rel
    assert "photos/index.html" in rel


def test_build_all_alias_calls_build_tree(cfg: Config) -> None:
    a = GalleryBuilder(cfg).build_all()
    b = GalleryBuilder(cfg).build_tree()
    assert {p.relative_to(cfg.output).as_posix() for p in a} == {
        p.relative_to(cfg.output).as_posix() for p in b
    }
