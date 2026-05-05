# NEXT

Step 8 done. Next: Step 9 (polish + verification).

Status:
- Steps 0–7 done.
- Step 8 done. `src/simplegallery/watcher.py` — `GalleryEventHandler(FileSystemEventHandler)` with thread-safe dirty-name set + `index_dirty` flag, `threading.Timer` debounce (`config.debounce_seconds`); on each event resolves top-level subdir under `source` (uses `Path.resolve()` with fallback for non-existent paths); `Dir{Created,Deleted,Moved}` on a top-level subdir flips `index_dirty`; `DirMovedEvent` records both src + dest names. `WatcherService.start()` runs initial `build_all()`, schedules recursive observer, blocks on `observer.join()` (KeyboardInterrupt → graceful stop). Builder gained `build_galleries(names, rebuild_index=True)` — always scans + prunes + copies assets, but processes only galleries whose `source_dir.name` is in `names`; index re-rendered when requested. `--watch` already wired in `__main__.py` from Step 1.
- Tests: `tests/test_watcher.py` — 10 cases (file/dir/move events, debounce coalesce, hidden top-level ignored, events outside source ignored, `flush_now` drains state, `WatcherService` end-to-end with fake builder). All 10 pass; full suite 66 pass.

Known issue (still pre-existing, NOT Step 8):
- `tests/test_image_processor.py::test_heic_full_converts_to_jpeg` and `test_heic_thumbnail_decodes` fail with `wand.exceptions.ResourceLimitError: time limit exceeded` on `/sample-data/shelf-christmas-decoration.heic`. ImageMagick policy already `time = unlimited` in `docker/imagemagick-policy.xml`. Try `MAGICK_TIME_LIMIT=0` env var on `app`/`test`/`shell` services next session, or substitute another HEIC sample.

Next steps:
- Step 9 — polish + verification:
  - Smoke test `docker compose up app` against `./source/` with 2+ subdirs (mix of images + a short video).
  - Manual lightbox verify (arrows, EXIF, video poster).
  - Mobile viewport (Chrome DevTools): swipe + EXIF slide-up.
  - Watcher live test: `docker compose run --rm app simplegallery --watch` (or set `SIMPLEGALLERY_WATCH=1`), drop a file → confirm only affected gallery re-renders and index refreshes when adding/removing a subdir.
  - Resolve HEIC time-limit issue (env var first).

How to verify Step 8 in browser / locally:
- `docker compose run --rm -e SIMPLEGALLERY_WATCH=1 app` (or pass `--watch`).
- In another shell, modify a file under `./source/<gallery>/` → expect debounced rebuild log and updated `output/<gallery>/index.html`.
- Create a new top-level subdir with media → expect index page refreshed with new card.
- Rename or delete a top-level subdir → expect cache prune + index refresh.
