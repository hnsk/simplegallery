"""BuildCache: stale detection, mark_done, atomic save, prune."""

from __future__ import annotations

import json
from pathlib import Path

from simplegallery.cache import CACHE_FILENAME, CACHE_VERSION, BuildCache, _Entry
from simplegallery.scanner import Gallery, MediaFile


def _make_image(src_dir: Path, output: Path, slug: str = "img", name: str = "img.jpg") -> MediaFile:
    src = src_dir / name
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(b"data")
    stat = src.stat()
    return MediaFile(
        source=src,
        kind="image",
        slug=slug,
        size=stat.st_size,
        mtime=stat.st_mtime,
        output_thumb=output / "g" / "thumbs" / f"{slug}.webp",
        output_full=output / "g" / "full" / f"{slug}.jpg",
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


def test_prune_removes_orphan_outputs_and_dirs(tmp_path: Path) -> None:
    out = tmp_path / "output"
    cache = BuildCache(out)

    keeper = _make_image(tmp_path / "s", out, slug="keep", name="keep.jpg")
    dropped = _make_image(tmp_path / "s", out, slug="gone", name="gone.jpg")
    _emit(keeper)
    _emit(dropped)
    cache.mark_done(keeper)
    cache.mark_done(dropped)

    # active gallery contains only keeper; an orphan dir also exists
    active = Gallery(
        name="g",
        slug="g",
        source_dir=tmp_path / "s",
        output_dir=out / "g",
        images=[keeper],
        cover_file=keeper,
    )
    orphan_dir = out / "old-gallery"
    orphan_dir.mkdir()
    (orphan_dir / "thumbs").mkdir()
    (orphan_dir / "thumbs" / "junk.webp").write_bytes(b"x")

    # keep an "assets" dir to confirm it's not pruned
    (out / "assets").mkdir()
    (out / "assets" / "gallery.css").write_bytes(b"x")

    removed = cache.prune([active])

    # dropped file outputs gone
    assert dropped.output_thumb is not None
    assert not dropped.output_thumb.exists()
    assert not dropped.output_full.exists()
    # orphan dir gone
    assert not orphan_dir.exists()
    # keeper outputs preserved
    assert keeper.output_thumb.exists()
    assert keeper.output_full.exists()
    # assets dir preserved
    assert (out / "assets" / "gallery.css").exists()
    # entry removed from cache
    assert cache.is_stale(dropped) is True
    assert cache.is_stale(keeper) is False
    assert any(orphan_dir == p for p in removed)


def test_prune_keeps_outputs_shared_with_active_files(tmp_path: Path) -> None:
    """A stale entry whose outputs are still claimed by an active file must not delete them."""
    out = tmp_path / "output"
    cache = BuildCache(out)
    media = _make_image(tmp_path / "s", out, slug="img", name="img.jpg")
    _emit(media)
    cache.mark_done(media)
    assert media.output_full is not None

    # Inject a ghost entry that reuses the same output relative path.
    cache._entries["/ghost/src.jpg"] = _Entry(
        size=1,
        mtime=0.0,
        outputs=[media.output_full.relative_to(out).as_posix()],
    )

    gallery = Gallery(
        name="g",
        slug="g",
        source_dir=tmp_path / "s",
        output_dir=out / "g",
        images=[media],
        cover_file=media,
    )
    cache.prune([gallery])
    assert media.output_full.exists()
