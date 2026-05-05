"""Frontend assets: package payload + copy_assets emits CSS/JS/icons."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

import pytest

from simplegallery.config import Config
from simplegallery.renderer import ASSETS_DIRNAME, Renderer


PACKAGED = ("gallery.css", "gallery.js", "icons/play.svg")


def _read_static(rel: str) -> bytes:
    return resources.files("simplegallery").joinpath("static", rel).read_bytes()


@pytest.fixture
def cfg(tmp_path: Path) -> Config:
    src = tmp_path / "source"
    src.mkdir()
    return Config(source=src, output=tmp_path / "output", title="T")


def test_packaged_assets_present_and_nonempty() -> None:
    for rel in PACKAGED:
        data = _read_static(rel)
        assert data, f"{rel} should not be empty"


def test_css_contains_expected_hooks() -> None:
    css = _read_static("gallery.css").decode("utf-8")
    assert ".gallery-grid" in css
    assert ".lightbox" in css
    assert ".exif-panel" in css
    assert "@media (max-width: 768px)" in css
    assert "icons/play.svg" in css
    assert ".breadcrumbs" in css
    assert ".subgallery-grid" in css
    assert ".subgallery-card" in css
    assert ".subgallery-card--text" in css
    assert ".lightbox-download" in css
    assert ".gallery-controls" in css


def test_js_contains_expected_hooks() -> None:
    js = _read_static("gallery.js").decode("utf-8")
    assert "Lightbox" in js
    assert "GalleryGrid" in js
    assert "ExifPanel" in js
    assert "data-exif" in js or "dataset.exif" in js
    assert "ArrowLeft" in js and "ArrowRight" in js
    assert "Escape" in js
    assert 'role", "dialog"' in js
    assert "aria-modal" in js
    assert "lightbox-download" in js
    assert "dataset.original" in js or "data-original" in js
    assert "GalleryControls" in js
    assert "gc-key" in js and "gc-order" in js


def test_play_svg_is_svg() -> None:
    svg = _read_static("icons/play.svg")
    assert svg.lstrip().startswith(b"<svg")


def test_copy_assets_emits_css_js_and_play_icon(cfg: Config) -> None:
    cfg.output.mkdir(parents=True, exist_ok=True)
    renderer = Renderer(cfg)
    assets = renderer.copy_assets()

    assets_dir = cfg.output / ASSETS_DIRNAME
    assert assets_dir.is_dir()

    # css/js are hashed
    assert (cfg.output / assets["gallery.css"].rel_output).is_file()
    assert (cfg.output / assets["gallery.js"].rel_output).is_file()

    # play icon emitted verbatim at stable path
    icon_rel = assets["icons/play.svg"].rel_output
    assert icon_rel == f"{ASSETS_DIRNAME}/icons/play.svg"
    assert (cfg.output / icon_rel).is_file()
    assert (cfg.output / icon_rel).read_bytes() == _read_static("icons/play.svg")
