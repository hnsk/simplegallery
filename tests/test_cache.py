"""BuildCache: stale detection, mark_done, atomic save, prune."""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

from simplegallery.cache import CACHE_FILENAME, CACHE_VERSION, BuildCache, _Entry
from simplegallery.scanner import Gallery, MediaFile


def _make_image(
    src_dir: Path,
    output: Path,
    slug: str = "img",
    name: str = "img.jpg",
    rel: str = "g",
) -> MediaFile:
    """Build a MediaFile whose outputs live at ``output/<rel>/{thumbs,full}/``.

    The ``rel`` segment mirrors the recursive web-root layout where each
    gallery's outputs sit beside its source rel-path. Use ``rel=""`` for the
    web-root gallery itself.
    """
    src = src_dir / name
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(b"data")
    stat = src.stat()
    out_base = output / rel if rel else output
    return MediaFile(
        source=src,
        kind="image",
        slug=slug,
        size=stat.st_size,
        mtime=stat.st_mtime,
        output_thumb=out_base / "thumbs" / f"{slug}.webp",
        output_full=out_base / "full" / f"{slug}.jpg",
    )


def _gallery(
    output: Path,
    *,
    name: str = "g",
    slug: str = "g",
    rel: str = "",
    images: list[MediaFile] | None = None,
    subgalleries: list[Gallery] | None = None,
) -> Gallery:
    images = images or []
    out_dir = output / rel if rel else output
    return Gallery(
        name=name,
        slug=slug,
        source_dir=output / "src" / rel if rel else output / "src",
        output_dir=out_dir,
        images=images,
        cover_file=images[0] if images else None,
        rel_path=PurePosixPath(rel) if rel else PurePosixPath(),
        subgalleries=subgalleries or [],
    )


def _emit(media: MediaFile, content: bytes = b"out") -> None:
    for p in media.output_paths():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(content)


def test_is_stale_when_unknown(tmp_path: Path) -> None:
    out = tmp_path / "output"
    cache = BuildCache(out)
    media = _make_image(tmp_path / "s", out)
    assert cache.is_stale(media) is True


def test_mark_done_clears_stale(tmp_path: Path) -> None:
    out = tmp_path / "output"
    cache = BuildCache(out)
    media = _make_image(tmp_path / "s", out)
    _emit(media)
    cache.mark_done(media)
    assert cache.is_stale(media) is False


def test_size_change_marks_stale(tmp_path: Path) -> None:
    out = tmp_path / "output"
    cache = BuildCache(out)
    media = _make_image(tmp_path / "s", out)
    _emit(media)
    cache.mark_done(media)
    bigger = MediaFile(
        source=media.source,
        kind=media.kind,
        slug=media.slug,
        size=media.size + 1,
        mtime=media.mtime,
        output_thumb=media.output_thumb,
        output_full=media.output_full,
    )
    assert cache.is_stale(bigger) is True


def test_mtime_change_marks_stale(tmp_path: Path) -> None:
    out = tmp_path / "output"
    cache = BuildCache(out)
    media = _make_image(tmp_path / "s", out)
    _emit(media)
    cache.mark_done(media)
    newer = MediaFile(
        source=media.source,
        kind=media.kind,
        slug=media.slug,
        size=media.size,
        mtime=media.mtime + 5,
        output_thumb=media.output_thumb,
        output_full=media.output_full,
    )
    assert cache.is_stale(newer) is True


def test_missing_output_marks_stale(tmp_path: Path) -> None:
    out = tmp_path / "output"
    cache = BuildCache(out)
    media = _make_image(tmp_path / "s", out)
    _emit(media)
    cache.mark_done(media)
    assert media.output_full is not None
    media.output_full.unlink()
    assert cache.is_stale(media) is True


def test_save_is_atomic_and_roundtrips(tmp_path: Path) -> None:
    out = tmp_path / "output"
    cache = BuildCache(out)
    media = _make_image(tmp_path / "s", out)
    _emit(media)
    cache.mark_done(media)
    cache.save()
    assert (out / CACHE_FILENAME).is_file()
    # tmp must not linger
    leftover = list(out.glob(f"{CACHE_FILENAME}.tmp"))
    assert leftover == []
    raw = json.loads((out / CACHE_FILENAME).read_text())
    assert raw["version"] == CACHE_VERSION
    assert str(media.source) in raw["entries"]

    reloaded = BuildCache(out)
    reloaded.load()
    assert reloaded.is_stale(media) is False


def test_load_ignores_missing_file(tmp_path: Path) -> None:
    cache = BuildCache(tmp_path / "output")
    cache.load()  # must not raise


def test_load_discards_wrong_version(tmp_path: Path) -> None:
    out = tmp_path / "output"
    out.mkdir()
    (out / CACHE_FILENAME).write_text(json.dumps({"version": 999, "entries": {"x": {}}}))
    cache = BuildCache(out)
    cache.load()
    media = _make_image(tmp_path / "s", out)
    _emit(media)
    assert cache.is_stale(media) is True


def test_prune_removes_stale_outputs_in_nested_layout(tmp_path: Path) -> None:
    """Recursive web-root layout: orphan outputs nested under a subgallery
    rel-path get unlinked, and now-empty thumbs/full/<rel> dirs collapse up
    to (but not including) ``output`` and reserved roots."""
    web = tmp_path / "web"
    cache = BuildCache(web, reserved_root_names={"gallery", "assets"})

    keeper = _make_image(tmp_path / "src" / "photos", web, slug="keep", name="keep.jpg", rel="photos")
    dropped = _make_image(tmp_path / "src" / "photos" / "macro", web, slug="gone", name="gone.jpg", rel="photos/macro")
    _emit(keeper)
    _emit(dropped)
    cache.mark_done(keeper)
    cache.mark_done(dropped)

    # User-owned + build-owned sibling content that prune must never touch.
    (web / "gallery").mkdir()
    (web / "gallery" / "original.jpg").write_bytes(b"orig")
    (web / "assets").mkdir()
    (web / "assets" / "gallery.css").write_bytes(b"css")
    (web / "index.html").write_bytes(b"<html/>")
    # Untracked stray file outside cache: not ours, must be left alone.
    (web / "photos").mkdir(exist_ok=True)
    (web / "photos" / "stray.txt").write_bytes(b"hi")

    photos = _gallery(web, name="photos", slug="photos", rel="photos", images=[keeper])
    root = _gallery(web, name="root", slug="gallery", rel="", subgalleries=[photos])

    removed = cache.prune([root])

    # dropped media derivatives gone
    assert dropped.output_thumb is not None and not dropped.output_thumb.exists()
    assert dropped.output_full is not None and not dropped.output_full.exists()
    # empty thumbs/full + their macro/ parent collapsed
    assert not (web / "photos" / "macro" / "thumbs").exists()
    assert not (web / "photos" / "macro" / "full").exists()
    assert not (web / "photos" / "macro").exists()
    # keeper preserved
    assert keeper.output_thumb.exists()
    assert keeper.output_full.exists()
    # reserved + untracked content preserved
    assert (web / "gallery" / "original.jpg").exists()
    assert (web / "assets" / "gallery.css").exists()
    assert (web / "index.html").exists()
    assert (web / "photos" / "stray.txt").exists()
    # cache entry purged for dropped, kept for keeper
    assert cache.is_stale(dropped) is True
    assert cache.is_stale(keeper) is False
    # collapsed dirs reported as removed
    assert (web / "photos" / "macro") in removed


def test_prune_keeps_outputs_shared_with_active_files(tmp_path: Path) -> None:
    """A stale entry whose outputs are still claimed by an active file must not delete them."""
    web = tmp_path / "web"
    cache = BuildCache(web)
    media = _make_image(tmp_path / "src", web, slug="img", name="img.jpg", rel="g")
    _emit(media)
    cache.mark_done(media)
    assert media.output_full is not None

    # Ghost stale entry reusing the same output relative path.
    cache._entries["/ghost/src.jpg"] = _Entry(
        size=1,
        mtime=0.0,
        outputs=[media.output_full.relative_to(web).as_posix()],
    )

    gallery = _gallery(web, name="g", slug="g", rel="g", images=[media])
    cache.prune([gallery])
    assert media.output_full.exists()


def test_prune_does_not_touch_untracked_orphan_dir(tmp_path: Path) -> None:
    """Recursive layout: a stray dir that cache never recorded stays put.
    Only files cache attests it owns may be removed."""
    web = tmp_path / "web"
    cache = BuildCache(web, reserved_root_names={"gallery", "assets"})

    keeper = _make_image(tmp_path / "src", web, slug="keep", name="keep.jpg", rel="photos")
    _emit(keeper)
    cache.mark_done(keeper)

    untracked = web / "old-gallery" / "thumbs"
    untracked.mkdir(parents=True)
    (untracked / "junk.webp").write_bytes(b"x")

    photos = _gallery(web, name="photos", slug="photos", rel="photos", images=[keeper])
    root = _gallery(web, name="root", slug="gallery", rel="", subgalleries=[photos])

    cache.prune([root])

    # Untracked dir still present — we don't own it.
    assert (untracked / "junk.webp").exists()
    assert keeper.output_thumb.exists()


def test_prune_stops_at_reserved_root(tmp_path: Path) -> None:
    """Empty-dir collapse must not remove a reserved top-level dir even if
    it happens to be empty at prune time."""
    web = tmp_path / "web"
    cache = BuildCache(web, reserved_root_names={"gallery", "assets"})

    media = _make_image(tmp_path / "src", web, slug="x", name="x.jpg", rel="assets")
    _emit(media)
    cache.mark_done(media)

    # Drop the source out of active set so prune deletes media's outputs.
    cache.prune([])

    # Files removed; reserved 'assets' dir itself stays.
    assert not media.output_thumb.exists()
    assert (web / "assets").is_dir()
