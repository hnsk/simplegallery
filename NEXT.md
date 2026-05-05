# NEXT

Step 9 mostly done — automated verification passes. Browser/mobile manual checks still pending.

Status:
- Steps 0–8 done.
- Step 9: per-file error handling, test suite, smoke test, watcher live test all green. Two real fixes landed this step:
  - `builder.py`: image pool switched from `ThreadPoolExecutor` → `ProcessPoolExecutor(mp_context=spawn)`. wand/ImageMagick is not thread-safe; concurrent thread access caused intermittent `time limit exceeded @ cache.c/GetImagePixelCache/1743` (misleading error from IM throttle path). New module-level `_image_worker` and `_exif_worker` are picklable.
  - `watcher.py`: filter `FileOpenedEvent` + `FileClosedNoWriteEvent` (`EVENT_TYPE_OPENED`, `EVENT_TYPE_CLOSED_NO_WRITE`). Without this, the build's own reads of `/source` triggered watchdog → infinite rebuild loop. Added `tests/test_watcher.py::test_read_only_open_close_events_ignored`.
- Test suite: 71 pass, 1 skip, 1 pre-existing flaky failure on `tests/test_image_processor.py::test_heic_thumbnail_decodes` against `/sample-data/shelf-christmas-decoration.heic`. Same error reproduces with `magick identify -verbose` against that file standalone — looks like libheif/IM 7.1.2-19 + that specific file. Other HEIC handling fine. Pre-existing per Step 8 NEXT.
- Smoke build (`/source/photos`, `/source/videos`): index + 2 gallery pages, 4/6 photo thumbs+full, 1 image in videos dir, 2 videos thumb+mp4+webm. `uC38zxx.jpeg` is a corrupt JPEG ("Application transferred too few scanlines") — per-file error handling skips it cleanly.
- Watcher live: tested file create, new subdir create, rename, delete. All trigger correct partial rebuild + cache prune.

Remaining for Step 9:
- Open `output/index.html` in a real browser; click into a gallery; verify lightbox arrows + Escape + (i) EXIF panel + video poster + HTML5 player.
- Chrome DevTools mobile viewport: swipe works, EXIF slides up from bottom.
- Decide on HEIC sample: substitute another file or document as sample-data quirk.

How to reproduce locally:
- Build: `docker compose build app`
- Tests: `docker compose run --rm test`
- Smoke: `docker compose run --rm app -v` (source pre-populated under `./source/`)
- Watch: `docker compose run --rm -d -e SIMPLEGALLERY_WATCH=1 -e SIMPLEGALLERY_DEBOUNCE=1.0 --name sg_watch app -v`; tail with `docker logs -f sg_watch`; modify `./source/<gallery>/`; stop with `docker stop sg_watch`.
