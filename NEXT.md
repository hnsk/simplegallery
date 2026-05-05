# NEXT

Step 14 (pre-publish cleanup) opened. First two items landed in commit `4855bd3`:

- `README.md` written (layout diagram, Docker workflow matrix, config table, GPS privacy caveat).
- `LICENSE` written (MIT, matches `pyproject.toml`).
- `.gitignore` trimmed: dropped legacy pre-Step-10 bind-mount dirs (`source/`, `photos/`, `input/`, `output/`, `gallery_output/`). Only `web/` + `sample-data/` remain ignored alongside the standard Python/editor cruft.
- Stale tree wiped by user: `output/`, `source/`, `web/gallery/1920.webp*`, root-level `web/gallery/198088.webm`, orphan transcoded outputs under `web/{photos,videos}/video/`.

Repo state: feature-complete through Step 13. Suite passes 113 + 1 skip in docker. README + LICENSE on disk. No PyPI metadata yet.

## Next batch (in priority order)

1. **`pyproject.toml` polish** — add `classifiers`, `[project.urls]` (homepage / repo / issues), `keywords`. Cheap, makes the PyPI listing usable.
2. **`__main__.py` + `cli.py` cleanup** — drop the stale `try/except ImportError: "not yet implemented (Step N)"` scaffolding in `_run_build` / `_run_watcher`; inline `cli.parse_args` (one-line wrapper, single caller). No behavior change; suite must stay green.
3. **Builder dedup** — collapse `build_tree()` + `build_galleries()` into one internal flow. ~80% overlap (scan → prune → copy_assets → image pipeline → exif batch → videos → render); only the `(in_scope, to_render)` partition differs. Cuts ~40 lines from `builder.py`. Pick one public entry point (`build_all` is what `__main__` + watcher already call).
4. **CI** — `.github/workflows/test.yml`: `docker compose run --rm test` on push + PR. Sample-data-dependent tests skip cleanly when the volume is missing, so CI is straightforward.
5. **Dev log relocation** — move `TODO.md` + `NEXT.md` to `docs/` or exclude from sdist via `MANIFEST.in`. They're build-process artifacts, not user docs.
6. **Misc cleanups** — fold `tests/test_smoke.py` into `tests/test_config.py`; drop `test_apply_args_no_legacy_source_output` (guards against retired flags); decide on `SIMPLEGALLERY_DEBOUNCE` (add `--debounce` flag or drop the env var); unify `Renderer.copy_assets` static-file loops.
7. **Optional** — Dockerfile split into builder + runtime stages so production image drops `[dev]` extras.

See `TODO.md` Step 14 for the full checklist.

## How to reproduce

- Build: `docker compose build app`
- Tests: `docker compose run --rm test`
- Smoke: `docker compose run --rm app -v` over `./web/gallery/`
- Browse: `docker compose up -d serve` → http://127.0.0.1:8080/

---

## Earlier context (kept for reference)

Step 13 (shareable lightbox links) landed: every figure carries `id="m-{slug}"` + `data-slug`; the thumb sits inside `<a class="gallery-link" href="{full|original|video}">` so right-click "copy link" / middle-click / "open in new tab" all yield the full-size media URL. Left-click still opens the lightbox (JS `preventDefault` on plain primary click; modifier keys + non-primary clicks fall through to the browser). Lightbox now drives `location.hash`: pushState on first open, replaceState on prev/next, history.back on close, popstate resyncs (so deep links `…/page#m-slug` auto-open and back-button closes). On close the previously-shown figure is scrolled into view via `scrollIntoView({block:'nearest'})`.

Stale orphan dirs from prior builds (`web/<sub>/video/`) are not touched by `cache.prune` because the matching cache entries still resolve to the same active sources; rewriting them just shrinks the recorded outputs list. Manual cleanup of `web/` (preserve `web/gallery/`) recovers the disk space.

Mobile-viewport lightbox verify (Step 11 carry-over — swipe + EXIF slide-up sheet + hash routing on touch) still deferred. Pick up after Step 14 if relevant before publishing.

Step 11 HEIC + multi-worker flake resolved: `docker/imagemagick-policy.xml` had `<policy domain="resource" name="time" value="unlimited"/>`; ImageMagick 7.1.2 parses that as `0 seconds`, tripping immediate `time limit exceeded` at `error/cache.c/GetImagePixelCache/1743` on slow decodes. Fix: removed bogus `time` policy line + dropped `thread=4` → `thread=1` (process pool already provides parallelism; nested IM threads = oversubscription).
