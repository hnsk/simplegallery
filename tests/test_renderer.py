"""Renderer: hashed asset copy, depth-correct relative paths, page output."""

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
def src(tmp_path: Path) -> Path:
    s = tmp_path / "source"
    _touch(s / "Trip A" / "img1.jpg")
    _touch(s / "Trip A" / "img2.png")
    _touch(s / "Trip A" / "clip.mp4")
    _touch(s / "Trip B" / "movie.mov")
    return s


@pytest.fixture
def cfg(src: Path, tmp_path: Path) -> Config:
    return Config(source=src, output=tmp_path / "output", title="My Gallery")


def test_copy_assets_emits_hashed_files(cfg: Config) -> None:
    cfg.output.mkdir(parents=True, exist_ok=True)
    renderer = Renderer(cfg)
    assets = renderer.copy_assets()

    assets_dir = cfg.output / ASSETS_DIRNAME
    assert (assets_dir).is_dir()
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


def test_render_index_uses_root_relative_assets(cfg: Config) -> None:
    galleries = DirectoryScanner(cfg).scan()
    cfg.output.mkdir(parents=True, exist_ok=True)
    renderer = Renderer(cfg)
    assets = renderer.copy_assets()
    out = renderer.render_index(galleries)

    html = out.read_text(encoding="utf-8")
    expected_css = assets["gallery.css"].rel_output
    expected_js = assets["gallery.js"].rel_output
    assert f'href="{expected_css}"' in html
    assert f'src="{expected_js}"' in html
    assert "My Gallery" in html
    # gallery card links are <slug>/index.html (no leading "../")
    assert 'href="trip-a/index.html"' in html
    assert 'href="trip-b/index.html"' in html
    # cover thumbnails are root-relative
    assert "trip-a/thumbs/img1.webp" in html


def test_render_gallery_uses_depth_correct_relative_paths(cfg: Config) -> None:
    galleries = DirectoryScanner(cfg).scan()
    cfg.output.mkdir(parents=True, exist_ok=True)
    renderer = Renderer(cfg)
    assets = renderer.copy_assets()
    trip_a = next(g for g in galleries if g.slug == "trip-a")
    out = renderer.render_gallery(trip_a)

    html = out.read_text(encoding="utf-8")
    # asset is one dir up
    assert f'href="../{assets["gallery.css"].rel_output}"' in html
    assert f'src="../{assets["gallery.js"].rel_output}"' in html
    # back-link to index.html one level up
    assert 'href="../index.html"' in html
    # thumb references are gallery-relative (no slug prefix, no "../")
    assert 'data-thumb="thumbs/img1.webp"' in html
    assert 'data-src="full/img1.jpg"' in html
    assert 'data-mp4="video/clip.mp4"' in html
    assert 'data-webm="video/clip.webm"' in html


def test_builder_build_all_renders_index_and_each_gallery(cfg: Config) -> None:
    rendered = GalleryBuilder(cfg).build_all()
    rendered_set = {p.relative_to(cfg.output).as_posix() for p in rendered}
    assert "index.html" in rendered_set
    assert "trip-a/index.html" in rendered_set
    assert "trip-b/index.html" in rendered_set
    assert (cfg.output / ASSETS_DIRNAME).is_dir()


def test_render_before_copy_assets_raises(cfg: Config) -> None:
    cfg.output.mkdir(parents=True, exist_ok=True)
    renderer = Renderer(cfg)
    with pytest.raises(RuntimeError):
        renderer.render_index([])
