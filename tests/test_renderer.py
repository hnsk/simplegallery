"""Renderer: hashed asset copy, tree-mode pages, breadcrumbs, subgallery cards."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from simplegallery.builder import GalleryBuilder
from simplegallery.config import Config
from simplegallery.renderer import ASSETS_DIRNAME, Renderer
from simplegallery.scanner import DirectoryScanner


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
    _touch(g / "videos" / "clip.mp4")
    return web


@pytest.fixture
def cfg(web: Path) -> Config:
    return Config(web_root=web, title="My Gallery")


def test_copy_assets_emits_hashed_files(cfg: Config) -> None:
    cfg.output.mkdir(parents=True, exist_ok=True)
    renderer = Renderer(cfg)
    assets = renderer.copy_assets()

    assets_dir = cfg.output / ASSETS_DIRNAME
    assert assets_dir.is_dir()
    css_path = cfg.output / assets["gallery.css"].rel_output
    js_path = cfg.output / assets["gallery.js"].rel_output
    assert css_path.is_file()
    assert js_path.is_file()
    assert re.fullmatch(r"gallery\.[a-f0-9]{10}\.css", css_path.name)
    assert re.fullmatch(r"gallery\.[a-f0-9]{10}\.js", js_path.name)


def test_copy_assets_is_deterministic(cfg: Config) -> None:
    cfg.output.mkdir(parents=True, exist_ok=True)
    a1 = Renderer(cfg).copy_assets()
    a2 = Renderer(cfg).copy_assets()
    assert a1["gallery.css"].rel_output == a2["gallery.css"].rel_output
    assert a1["gallery.js"].rel_output == a2["gallery.js"].rel_output


def test_render_root_page_uses_root_relative_assets(cfg: Config) -> None:
    root = DirectoryScanner(cfg).scan_tree()
    assert root is not None
    cfg.output.mkdir(parents=True, exist_ok=True)
    renderer = Renderer(cfg)
    assets = renderer.copy_assets()
    out = renderer.render_gallery(root)

    html = out.read_text(encoding="utf-8")
    assert f'href="{assets["gallery.css"].rel_output}"' in html
    assert f'src="{assets["gallery.js"].rel_output}"' in html
    assert "My Gallery" in html


def test_render_root_breadcrumb_is_current_only(cfg: Config) -> None:
    root = DirectoryScanner(cfg).scan_tree()
    assert root is not None
    cfg.output.mkdir(parents=True, exist_ok=True)
    renderer = Renderer(cfg)
    renderer.copy_assets()
    out = renderer.render_gallery(root)

    html = out.read_text(encoding="utf-8")
    assert '<nav class="breadcrumbs"' in html
    # root crumb is current page → span, not anchor
    assert '<span aria-current="page">My Gallery</span>' in html


def test_render_nested_breadcrumb_links_back_to_ancestors(cfg: Config) -> None:
    root = DirectoryScanner(cfg).scan_tree()
    assert root is not None
    photos = next(g for g in root.subgalleries if g.name == "photos")
    macro = photos.subgalleries[0]
    cfg.output.mkdir(parents=True, exist_ok=True)
    renderer = Renderer(cfg)
    renderer.copy_assets()
    out = renderer.render_gallery(macro)

    html = out.read_text(encoding="utf-8")
    # ancestors are anchors, current is a span
    assert 'href="../../index.html">My Gallery</a>' in html
    assert 'href="../index.html">photos</a>' in html
    assert '<span aria-current="page">macro</span>' in html


def test_render_root_subgallery_cards_show_counts(cfg: Config) -> None:
    root = DirectoryScanner(cfg).scan_tree()
    assert root is not None
    cfg.output.mkdir(parents=True, exist_ok=True)
    renderer = Renderer(cfg)
    renderer.copy_assets()
    out = renderer.render_gallery(root)

    html = out.read_text(encoding="utf-8")
    # root has photos + videos as subgalleries
    assert 'href="photos/index.html"' in html
    assert 'href="videos/index.html"' in html
    # photos has 2 own items + 1 sub (macro)
    assert "2 items · 1 subgallery" in html
    # videos has 1 own item, no subs
    assert "1 item</p>" in html


def test_render_text_only_subgallery_card_when_no_own_media(tmp_path: Path) -> None:
    """A subgallery with only nested children renders without a cover thumb."""
    web = tmp_path / "web"
    _touch(web / "gallery" / "year" / "trip" / "img.jpg")
    cfg = Config(web_root=web, title="Site")
    root = DirectoryScanner(cfg).scan_tree()
    assert root is not None
    cfg.output.mkdir(parents=True, exist_ok=True)
    renderer = Renderer(cfg)
    renderer.copy_assets()
    out = renderer.render_gallery(root)

    html = out.read_text(encoding="utf-8")
    assert "subgallery-card--text" in html
    # no <img> inside the year card
    assert 'src="year/' not in html


def test_render_browser_friendly_image_uses_original_for_data_src(cfg: Config) -> None:
    root = DirectoryScanner(cfg).scan_tree()
    assert root is not None
    photos = next(g for g in root.subgalleries if g.name == "photos")
    cfg.output.mkdir(parents=True, exist_ok=True)
    renderer = Renderer(cfg)
    renderer.copy_assets()
    out = renderer.render_gallery(photos)

    html = out.read_text(encoding="utf-8")
    # a.jpg (browser-friendly) → data-src points at original under gallery/photos/
    # NB: heic sorts before jpg under name.lower(); jpg gets slug "a-2".
    assert 'data-thumb="thumbs/a-2.webp"' in html
    assert 'data-src="../gallery/photos/a.jpg"' in html
    # data-original always points at the original
    assert 'data-original="../gallery/photos/a.jpg"' in html


def test_render_transcoded_image_uses_derivative_for_data_src(cfg: Config) -> None:
    root = DirectoryScanner(cfg).scan_tree()
    assert root is not None
    photos = next(g for g in root.subgalleries if g.name == "photos")
    cfg.output.mkdir(parents=True, exist_ok=True)
    renderer = Renderer(cfg)
    renderer.copy_assets()
    out = renderer.render_gallery(photos)

    html = out.read_text(encoding="utf-8")
    # a.heic → derivative full/a.jpg as data-src; data-original keeps .heic
    assert 'data-src="full/a.jpg"' in html
    assert 'data-original="../gallery/photos/a.heic"' in html


def test_render_figure_has_anchor_id_and_link(cfg: Config) -> None:
    root = DirectoryScanner(cfg).scan_tree()
    assert root is not None
    photos = next(g for g in root.subgalleries if g.name == "photos")
    cfg.output.mkdir(parents=True, exist_ok=True)
    renderer = Renderer(cfg)
    renderer.copy_assets()
    out = renderer.render_gallery(photos)

    html = out.read_text(encoding="utf-8")
    # figure carries a slug-based id for deep linking
    assert 'id="m-a"' in html
    assert 'data-slug="a"' in html
    # browser-friendly jpg gets slug "a-2"; figure linked to its full URL
    assert 'id="m-a-2"' in html
    assert '<a class="gallery-link" href="../gallery/photos/a.jpg"' in html
    # heic transcoded → link points at derivative full/a.jpg
    assert '<a class="gallery-link" href="full/a.jpg"' in html


def test_render_video_figure_link_points_at_video_file(cfg: Config) -> None:
    root = DirectoryScanner(cfg).scan_tree()
    assert root is not None
    videos = next(g for g in root.subgalleries if g.name == "videos")
    cfg.output.mkdir(parents=True, exist_ok=True)
    renderer = Renderer(cfg)
    renderer.copy_assets()
    out = renderer.render_gallery(videos)

    html = out.read_text(encoding="utf-8")
    assert '<a class="gallery-link" href="../gallery/videos/clip.mp4"' in html


def test_render_video_data_original_points_at_source(cfg: Config) -> None:
    root = DirectoryScanner(cfg).scan_tree()
    assert root is not None
    videos = next(g for g in root.subgalleries if g.name == "videos")
    cfg.output.mkdir(parents=True, exist_ok=True)
    renderer = Renderer(cfg)
    renderer.copy_assets()
    out = renderer.render_gallery(videos)

    html = out.read_text(encoding="utf-8")
    # Browser-friendly mp4 is played from the original; no separate derivatives.
    assert 'data-mp4="../gallery/videos/clip.mp4"' in html
    assert "data-webm=" not in html
    assert 'data-original="../gallery/videos/clip.mp4"' in html


def test_render_nested_page_climbs_two_dirs_for_assets(cfg: Config) -> None:
    root = DirectoryScanner(cfg).scan_tree()
    assert root is not None
    photos = next(g for g in root.subgalleries if g.name == "photos")
    macro = photos.subgalleries[0]
    cfg.output.mkdir(parents=True, exist_ok=True)
    renderer = Renderer(cfg)
    assets = renderer.copy_assets()
    out = renderer.render_gallery(macro)

    html = out.read_text(encoding="utf-8")
    assert f'href="../../{assets["gallery.css"].rel_output}"' in html
    assert f'src="../../{assets["gallery.js"].rel_output}"' in html


def test_builder_build_all_renders_root_and_each_gallery(cfg: Config) -> None:
    rendered = GalleryBuilder(cfg).build_all()
    rel = {p.relative_to(cfg.output).as_posix() for p in rendered}
    assert rel == {
        "index.html",
        "photos/index.html",
        "photos/macro/index.html",
        "videos/index.html",
    }
    assert (cfg.output / ASSETS_DIRNAME).is_dir()


def test_render_emits_data_mtime_and_data_name(cfg: Config) -> None:
    root = DirectoryScanner(cfg).scan_tree()
    assert root is not None
    photos = next(g for g in root.subgalleries if g.name == "photos")
    cfg.output.mkdir(parents=True, exist_ok=True)
    renderer = Renderer(cfg)
    renderer.copy_assets()
    out = renderer.render_gallery(photos)

    html = out.read_text(encoding="utf-8")
    # figure carries data-name + data-mtime for client-side sorting
    assert 'data-name="a.heic"' in html
    assert 'data-name="a.jpg"' in html
    assert re.search(r'data-mtime="\d+"', html)


def test_render_root_subgallery_cards_have_sort_data(cfg: Config) -> None:
    root = DirectoryScanner(cfg).scan_tree()
    assert root is not None
    cfg.output.mkdir(parents=True, exist_ok=True)
    renderer = Renderer(cfg)
    renderer.copy_assets()
    out = renderer.render_gallery(root)

    html = out.read_text(encoding="utf-8")
    assert 'data-name="photos"' in html
    assert 'data-name="videos"' in html
    # subgallery card includes a numeric data-mtime
    assert re.search(r'class="subgallery-card[^"]*"[^>]*data-mtime="\d+"', html)


def test_render_emits_sort_controls(cfg: Config) -> None:
    root = DirectoryScanner(cfg).scan_tree()
    assert root is not None
    cfg.output.mkdir(parents=True, exist_ok=True)
    renderer = Renderer(cfg)
    renderer.copy_assets()
    out = renderer.render_gallery(root)

    html = out.read_text(encoding="utf-8")
    assert 'class="gallery-controls"' in html
    assert 'class="gc-key"' in html and 'class="gc-order"' in html
    assert 'value="name" selected' in html
    assert 'value="asc" selected' in html
    assert 'value="date"' in html and 'value="desc"' in html


def test_render_html_is_compact(cfg: Config) -> None:
    """trim_blocks + lstrip_blocks should yield no consecutive blank lines."""
    root = DirectoryScanner(cfg).scan_tree()
    assert root is not None
    cfg.output.mkdir(parents=True, exist_ok=True)
    renderer = Renderer(cfg)
    renderer.copy_assets()
    out = renderer.render_gallery(root)

    html = out.read_text(encoding="utf-8")
    assert "\n\n" not in html, "expected no blank lines in compact output"


def test_render_before_copy_assets_raises(cfg: Config) -> None:
    root = DirectoryScanner(cfg).scan_tree()
    assert root is not None
    cfg.output.mkdir(parents=True, exist_ok=True)
    renderer = Renderer(cfg)
    with pytest.raises(RuntimeError):
        renderer.render_gallery(root)
