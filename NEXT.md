# NEXT

Step 6 done. Next: Step 8 (watcher).

Status:
- Steps 0–5 done.
- Step 6 done. `src/simplegallery/video_processor.py` — `VideoInfo` dataclass; `probe()` (ffprobe JSON, picks video stream + duration fallback to format); `generate_thumbnail()` (ffmpeg seek `min(1.0, dur*0.1)` → PNG pipe → Wand WebP q=80); `transcode_mp4()` (libx264 CRF23 preset slow, AAC 128k, +faststart, `scale=trunc(iw/2)*2:trunc(ih/2)*2`, `-an` if `has_audio=False`); `transcode_webm()` (libvpx-vp9 CRF33 b:v 0, row-mt, libopus 96k, same scale/audio rules); `VideoProcessingError` for ffmpeg failures. Wired into `GalleryBuilder._process_videos` (ThreadPoolExecutor, `cache.is_stale` guard, per-video try/except). 9 video tests pass — fixtures generated via `ffmpeg -f lavfi testsrc/sine` at session scope (no committed binary). Transcode tests marked `@pytest.mark.slow`.
- Step 7 done early.

Known issue (pre-existing, NOT Step 6):
- `tests/test_image_processor.py::test_heic_thumbnail_decodes` still fails with `wand.exceptions.ResourceLimitError: time limit exceeded` on `/sample-data/shelf-christmas-decoration.heic`. ImageMagick policy already `time = unlimited` in `docker/imagemagick-policy.xml`. Likely pixel-cache time limit ignoring policy or libheif/threading regression. Try `MAGICK_TIME_LIMIT=0` env var on `app`/`test`/`shell` services next session — env vars override policy in IM. Or substitute another HEIC sample. Unrelated to Step 6 video work.

Next steps:
- Step 8 (watcher) — `src/simplegallery/watcher.py`: watchdog `FileSystemEventHandler`, debounced (`config.debounce_seconds`) rebuild, thread-safe dirty-slug set, handle `DirCreated/Deleted/Moved` on top-level subdirs (rebuild index, prune slugs); `WatcherService.start()` blocks on `observer.join()`. Wire `--watch` in `__main__.py` → `WatcherService`. `tests/test_watcher.py` — handler unit tests (file event → dirty slug; dir create/delete → index dirty; debounce coalesces bursts).
- Step 9 — polish (per-file error handling already partial; broader smoke + mobile checks).

How to verify Step 6 in browser:
- Drop sample mp4/webm into `./source/<gallery>/`, then `docker compose run --rm app`.
- Open `output/<gallery>/index.html`. Click video thumb → lightbox should show HTML5 player with poster + MP4 + WebM sources.
