# NEXT

Step 14 (pre-publish cleanup) all but CI + optional Dockerfile split done.

## What landed this batch

- `pyproject.toml` polished — added `keywords`, `classifiers`, `[project.urls]` (homepage / repo / issues at https://github.com/hnsk/simplegallery). Author corrected to `Hannu Ylitalo <hannu@ylitalo.eu>`.
- `__main__.py` cleaned — dropped stale `try/except ImportError: "not yet implemented (Step N)"` scaffolding for `GalleryBuilder` / `WatcherService`. Top-level imports, direct calls.
- `cli.parse_args` wrapper removed — `__main__.main` and tests call `build_parser().parse_args(argv)` directly.
- Builder deduped — `build_tree()` + `build_galleries()` collapsed into one `GalleryBuilder.build_all(dirty_rels=None)`. None/empty → full build; non-empty → scoped partial rebuild via the existing `_is_dirty_or_descendant` / `_is_ancestor_of_dirty` partition. Watcher (`watcher.py:196`) + `tests/test_builder_tree.py` + `tests/test_watcher.py` mocks updated.
- `Renderer.copy_assets` unified — `_HASHED_STATIC_FILES` / `_VERBATIM_STATIC_FILES` replaced by `_STATIC_FILES = ((logical, hashed), …)` with a single loop branching on `hashed`.
- Dev logs relocated — `TODO.md` + `NEXT.md` moved under `docs/` so they don't leak into the sdist as user docs.
- Test cleanup — `tests/test_smoke.py` folded into `tests/test_config.py` (`test_version_present`, `test_cli_overrides_config`, `test_default_log_level_info`); legacy `--source` / `--output` guard test dropped.
- `--debounce` CLI flag added (float seconds, only meaningful with `--watch`); env `SIMPLEGALLERY_DEBOUNCE` still honored.

Repo state: feature-complete through Step 13 + Step 14 cleanup. Suite passes 111 + 1 skip in docker. CI workflow + multi-stage Dockerfile remain as the only deferred Step 14 items.

## Next batch

1. **CI** — `.github/workflows/test.yml` running `docker compose run --rm test` on push/PR. Sample-data-dependent tests skip cleanly when the volume is missing, so CI is straightforward.
2. **Dockerfile split (optional)** — builder + runtime stages so production image drops `[dev]` extras. Defer until image size is an actual concern.
3. **Publish prep** — `python -m build` smoke inside the container, then PyPI upload once GitHub URL hosts an actual repo.

## How to reproduce

- Build: `docker compose build app`
- Tests: `docker compose run --rm test`
- Smoke: `docker compose run --rm app -v` over `./web/gallery/`
- Browse: `docker compose --profile dev up -d serve` → http://127.0.0.1:8080/

---

## Earlier context (kept for reference)

Step 13 (shareable lightbox links) landed: every figure carries `id="m-{slug}"` + `data-slug`; the thumb sits inside `<a class="gallery-link" href="{full|original|video}">` so right-click "copy link" / middle-click / "open in new tab" all yield the full-size media URL. Left-click still opens the lightbox (JS `preventDefault` on plain primary click; modifier keys + non-primary clicks fall through to the browser). Lightbox now drives `location.hash`: pushState on first open, replaceState on prev/next, history.back on close, popstate resyncs (so deep links `…/page#m-slug` auto-open and back-button closes). On close the previously-shown figure is scrolled into view via `scrollIntoView({block:'nearest'})`.

Stale orphan dirs from prior builds (`web/<sub>/video/`) are not touched by `cache.prune` because the matching cache entries still resolve to the same active sources; rewriting them just shrinks the recorded outputs list. Manual cleanup of `web/` (preserve `web/gallery/`) recovers the disk space.

Mobile-viewport lightbox verify (Step 11 carry-over — swipe + EXIF slide-up sheet + hash routing on touch) still deferred. Pick up after Step 14 if relevant before publishing.

Step 11 HEIC + multi-worker flake resolved: `docker/imagemagick-policy.xml` had `<policy domain="resource" name="time" value="unlimited"/>`; ImageMagick 7.1.2 parses that as `0 seconds`, tripping immediate `time limit exceeded` at `error/cache.c/GetImagePixelCache/1743` on slow decodes. Fix: removed bogus `time` policy line + dropped `thread=4` → `thread=1` (process pool already provides parallelism; nested IM threads = oversubscription).
