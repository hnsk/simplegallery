"""DirectoryScanner.scan_tree(): recursive Gallery model + new MediaFile fields."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest

from simplegallery.config import Config
from simplegallery.scanner import DirectoryScanner, Gallery


def _touch(path: Path, content: bytes = b"x") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


@pytest.fixture
def web(tmp_path: Path) -> Path:
    """Build a sample web tree:

    web/
      gallery/
        cover.jpg               # root-level media
        photos/
          a.jpg
          a.heic
          notes.txt             # ignored
          macro/
            close.png
            tilt.tif
        videos/
          clip.mp4
          poster.jpg
        empty/                  # gets pruned
        .hidden/                # gets pruned
        assets/                 # reserved name → skipped at source root
          junk.jpg
        index.html/             # reserved name → skipped at source root
          x.jpg
        gallery/                # reserved name (gallery_subdir) → skipped at source root
          y.jpg
    """
    web = tmp_path / "web"
    g = web / "gallery"
    _touch(g / "cover.jpg")
    _touch(g / "photos" / "a.jpg")
    _touch(g / "photos" / "a.heic")
    _touch(g / "photos" / "notes.txt")
    _touch(g / "photos" / "macro" / "close.png")
    _touch(g / "photos" / "macro" / "tilt.tif")
    _touch(g / "videos" / "clip.mp4")
    _touch(g / "videos" / "poster.jpg")
    (g / "empty").mkdir()
    _touch(g / ".hidden" / "h.jpg")
    _touch(g / "assets" / "junk.jpg")
    _touch(g / "index.html" / "x.jpg")
    _touch(g / "gallery" / "y.jpg")
    return web


def _config(web: Path) -> Config:
    return Config(web_root=web, title="Site")


def _names(galleries: list[Gallery]) -> list[str]:
    return [g.name for g in galleries]


def test_scan_tree_root_returned(web: Path) -> None:
    root = DirectoryScanner(_config(web)).scan_tree()
    assert root is not None
    assert root.rel_path == PurePosixPath()
    assert root.source_dir == web / "gallery"
    assert root.output_dir == web
    # root has cover.jpg as own media
    assert {m.source.name for m in root.images} == {"cover.jpg"}


def test_scan_tree_nested_subgalleries(web: Path) -> None:
    root = DirectoryScanner(_config(web)).scan_tree()
    assert root is not None
    sub_names = _names(root.subgalleries)
    # photos and videos kept; empty/.hidden/assets/index.html/gallery skipped
    assert sub_names == ["photos", "videos"]

    photos = next(g for g in root.subgalleries if g.name == "photos")
    assert photos.rel_path == PurePosixPath("photos")
    assert photos.output_dir == web / "photos"
    assert {m.source.name for m in photos.images} == {"a.jpg", "a.heic"}
    assert _names(photos.subgalleries) == ["macro"]

    macro = photos.subgalleries[0]
    assert macro.rel_path == PurePosixPath("photos/macro")
    assert macro.output_dir == web / "photos" / "macro"
    assert {m.source.name for m in macro.images} == {"close.png", "tilt.tif"}


def test_scan_tree_skips_reserved_root_names(web: Path) -> None:
    root = DirectoryScanner(_config(web)).scan_tree()
    assert root is not None
    sub_names = _names(root.subgalleries)
    for reserved in ("assets", "index.html", "gallery"):
        assert reserved not in sub_names


def test_scan_tree_reserved_only_at_root(tmp_path: Path) -> None:
    """`assets` is only reserved at the top-level source root, not when nested."""
    web = tmp_path / "web"
    _touch(web / "gallery" / "photos" / "assets" / "x.jpg")
    root = DirectoryScanner(_config(web)).scan_tree()
    assert root is not None
    photos = root.subgalleries[0]
    assert _names(photos.subgalleries) == ["assets"]


def test_scan_tree_transcode_needed(web: Path) -> None:
    root = DirectoryScanner(_config(web)).scan_tree()
    assert root is not None
    photos = next(g for g in root.subgalleries if g.name == "photos")
    by_name = {m.source.name: m for m in photos.images}
    assert by_name["a.jpg"].transcode_needed is False
    assert by_name["a.jpg"].output_full is None
    assert by_name["a.heic"].transcode_needed is True
    assert by_name["a.heic"].output_full == web / "photos" / "full" / "a.jpg"


def test_scan_tree_video_outputs(web: Path) -> None:
    root = DirectoryScanner(_config(web)).scan_tree()
    assert root is not None
    videos = next(g for g in root.subgalleries if g.name == "videos")
    clip = next(m for m in videos.videos if m.source.name == "clip.mp4")
    # mp4 is browser-friendly → no transcode, original is referenced directly
    assert clip.output_mp4 is None
    assert clip.output_webm is None
    assert clip.transcode_needed is False


def test_scan_tree_video_transcode_needed(tmp_path: Path) -> None:
    """Non-browser-friendly containers (.mov/.mkv/.avi) emit mp4+webm derivatives."""
    web = tmp_path / "web"
    _touch(web / "gallery" / "clips" / "raw.mov")
    root = DirectoryScanner(_config(web)).scan_tree()
    assert root is not None
    clips = next(g for g in root.subgalleries if g.name == "clips")
    raw = next(m for m in clips.videos if m.source.name == "raw.mov")
    assert raw.output_mp4 == web / "clips" / "video" / "raw.mp4"
    assert raw.output_webm == web / "clips" / "video" / "raw.webm"
    assert raw.transcode_needed is True


def test_scan_tree_original_rel_relative_to_web_root(web: Path) -> None:
    root = DirectoryScanner(_config(web)).scan_tree()
    assert root is not None
    cover = root.images[0]
    assert cover.original_rel == PurePosixPath("gallery/cover.jpg")
    photos = next(g for g in root.subgalleries if g.name == "photos")
    a = next(m for m in photos.images if m.source.name == "a.jpg")
    assert a.original_rel == PurePosixPath("gallery/photos/a.jpg")
    macro = photos.subgalleries[0]
    close = next(m for m in macro.images if m.source.name == "close.png")
    assert close.original_rel == PurePosixPath("gallery/photos/macro/close.png")


def test_scan_tree_breadcrumbs(web: Path) -> None:
    root = DirectoryScanner(_config(web)).scan_tree()
    assert root is not None
    assert root.breadcrumbs == [("Site", PurePosixPath())]
    photos = next(g for g in root.subgalleries if g.name == "photos")
    assert photos.breadcrumbs == [
        ("Site", PurePosixPath()),
        ("photos", PurePosixPath("photos")),
    ]
    macro = photos.subgalleries[0]
    assert macro.breadcrumbs == [
        ("Site", PurePosixPath()),
        ("photos", PurePosixPath("photos")),
        ("macro", PurePosixPath("photos/macro")),
    ]


def test_scan_tree_skips_empty_branches(tmp_path: Path) -> None:
    """A branch with no own media and no non-empty subs is pruned."""
    web = tmp_path / "web"
    _touch(web / "gallery" / "photos" / "a.jpg")
    (web / "gallery" / "deserted").mkdir()
    (web / "gallery" / "deserted" / "subdeserted").mkdir()
    root = DirectoryScanner(_config(web)).scan_tree()
    assert root is not None
    assert _names(root.subgalleries) == ["photos"]


def test_scan_tree_subgallery_with_only_subs_kept(tmp_path: Path) -> None:
    """A directory with no own media but a non-empty sub IS kept (text-only)."""
    web = tmp_path / "web"
    _touch(web / "gallery" / "year" / "trip" / "img.jpg")
    root = DirectoryScanner(_config(web)).scan_tree()
    assert root is not None
    year = next(g for g in root.subgalleries if g.name == "year")
    assert year.count == 0
    assert year.subcount == 1
    assert year.cover_file is None  # text-only card per spec


def test_scan_tree_returns_none_when_fully_empty(tmp_path: Path) -> None:
    web = tmp_path / "web"
    (web / "gallery").mkdir(parents=True)
    (web / "gallery" / "blank").mkdir()
    root = DirectoryScanner(_config(web)).scan_tree()
    assert root is None


def test_scan_tree_missing_source_returns_none(tmp_path: Path) -> None:
    cfg = Config(web_root=tmp_path / "nope")
    assert DirectoryScanner(cfg).scan_tree() is None


def test_scan_tree_walk_dfs(web: Path) -> None:
    root = DirectoryScanner(_config(web)).scan_tree()
    assert root is not None
    walked = root.walk()
    names = [g.name for g in walked]
    # pre-order DFS: root, photos, photos/macro, videos
    assert names == ["Site", "photos", "macro", "videos"]


def test_scan_tree_cover_file_first_image(web: Path) -> None:
    root = DirectoryScanner(_config(web)).scan_tree()
    assert root is not None
    photos = next(g for g in root.subgalleries if g.name == "photos")
    assert photos.cover_file is not None
    assert photos.cover_file.is_image


def test_scan_tree_cover_file_falls_back_to_video(tmp_path: Path) -> None:
    web = tmp_path / "web"
    _touch(web / "gallery" / "clips" / "v.mp4")
    root = DirectoryScanner(_config(web)).scan_tree()
    assert root is not None
    clips = root.subgalleries[0]
    assert clips.cover_file is not None
    assert clips.cover_file.is_video
