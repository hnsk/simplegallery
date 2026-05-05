"""DirectoryScanner: gallery discovery, image/video split, slug, cover."""

from __future__ import annotations

from pathlib import Path

import pytest

from simplegallery.config import Config
from simplegallery.scanner import DirectoryScanner


def _config(source: Path, output: Path) -> Config:
    return Config(source=source, output=output)


def _touch(path: Path, content: bytes = b"x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    src = tmp_path / "source"
    _touch(src / "Trip A" / "img1.jpg")
    _touch(src / "Trip A" / "img2.PNG")
    _touch(src / "Trip A" / "clip.mp4")
    _touch(src / "Trip A" / "notes.txt")
    _touch(src / "Trip A" / ".DS_Store")
    _touch(src / "Trip B" / "movie.MOV")
    (src / "empty").mkdir()
    _touch(src / ".hidden" / "img.jpg")
    _touch(src / "loose.jpg")  # top-level file, not a gallery
    return src


def test_scan_lists_only_non_empty_subdirs(tree: Path, tmp_path: Path) -> None:
    out = tmp_path / "output"
    galleries = DirectoryScanner(_config(tree, out)).scan()
    names = {g.name for g in galleries}
    assert names == {"Trip A", "Trip B"}


def test_scan_splits_images_and_videos(tree: Path, tmp_path: Path) -> None:
    galleries = DirectoryScanner(_config(tree, tmp_path / "output")).scan()
    a = next(g for g in galleries if g.name == "Trip A")
    assert {m.source.name for m in a.images} == {"img1.jpg", "img2.PNG"}
    assert {m.source.name for m in a.videos} == {"clip.mp4"}
    assert a.count == 3


def test_cover_prefers_first_image(tree: Path, tmp_path: Path) -> None:
    galleries = DirectoryScanner(_config(tree, tmp_path / "output")).scan()
    a = next(g for g in galleries if g.name == "Trip A")
    assert a.cover_file is not None
    assert a.cover_file.is_image
    assert a.cover_file.source.name == "img1.jpg"


def test_cover_falls_back_to_video(tree: Path, tmp_path: Path) -> None:
    galleries = DirectoryScanner(_config(tree, tmp_path / "output")).scan()
    b = next(g for g in galleries if g.name == "Trip B")
    assert b.cover_file is not None
    assert b.cover_file.is_video


def test_output_paths_use_gallery_slug(tree: Path, tmp_path: Path) -> None:
    out = tmp_path / "output"
    galleries = DirectoryScanner(_config(tree, out)).scan()
    a = next(g for g in galleries if g.name == "Trip A")
    assert a.slug == "trip-a"
    assert a.output_dir == out / "trip-a"
    img = a.images[0]
    assert img.output_thumb == out / "trip-a" / "thumbs" / f"{img.slug}.webp"
    assert img.output_full == out / "trip-a" / "full" / f"{img.slug}.jpg"
    vid = a.videos[0]
    assert vid.output_mp4 == out / "trip-a" / "video" / f"{vid.slug}.mp4"
    assert vid.output_webm == out / "trip-a" / "video" / f"{vid.slug}.webm"


def test_gallery_slug_collisions(tmp_path: Path) -> None:
    src = tmp_path / "source"
    _touch(src / "Trip A" / "1.jpg")
    _touch(src / "trip a" / "1.jpg")
    _touch(src / "TRIP-A" / "1.jpg")
    galleries = DirectoryScanner(_config(src, tmp_path / "output")).scan()
    slugs = sorted(g.slug for g in galleries)
    assert slugs == ["trip-a", "trip-a-2", "trip-a-3"]


def test_file_slug_collisions(tmp_path: Path) -> None:
    src = tmp_path / "source"
    _touch(src / "g" / "Photo.jpg")
    _touch(src / "g" / "photo.jpeg")
    galleries = DirectoryScanner(_config(src, tmp_path / "output")).scan()
    g = galleries[0]
    slugs = sorted(m.slug for m in g.images)
    assert slugs == ["photo", "photo-2"]


def test_missing_source_returns_empty(tmp_path: Path) -> None:
    src = tmp_path / "nope"
    out = tmp_path / "output"
    assert DirectoryScanner(_config(src, out)).scan() == []
