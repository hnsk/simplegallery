# NEXT

Step 5 done. Next: Step 6 (video processor) or Step 8 (watcher).

Status:
- Step 0 done.
- Step 1 done.
- Step 2 done.
- Step 3 done.
- Step 4 done.
- Step 5 done. `static/gallery.css` (grid, lightbox overlay, EXIF panel side-rail/slide-up mobile, play badge via `background-image: url(icons/play.svg)`); `static/gallery.js` (IIFE — `GalleryGrid` per `.gallery-grid[data-gallery]`, `Lightbox` injects `role="dialog"` + `aria-modal="true"` shell, ±1 image preload, keyboard arrows + Escape, touch swipe `|Δx|>50 && |Δx|>|Δy|`, focus trap, save/restore `activeElement`, image vs `<video>` source switch, `(i)` toggles `ExifPanel`); `static/icons/play.svg` copied verbatim at `assets/icons/play.svg` so hashed CSS can `url(icons/play.svg)`. Renderer split `_HASHED_STATIC_FILES` (css/js, sha256-hashed) vs `_VERBATIM_STATIC_FILES` (icons). 11 Step-5/Renderer tests pass (`docker compose run --rm test -v tests/test_frontend_assets.py tests/test_renderer.py`).
- Step 7 done early.

Known issue (pre-existing, NOT Step 5):
- `tests/test_image_processor.py::test_heic_thumbnail_decodes` and `test_heic_full_converts_to_jpeg` fail with `wand.exceptions.ResourceLimitError: time limit exceeded` on `/sample-data/shelf-christmas-decoration.heic`. ImageMagick `time` policy already `unlimited` in `docker/imagemagick-policy.xml`. Likely pixel-cache time limit or libheif/threading regression. Investigate in Step 6 or earlier — not introduced by Step 5 frontend work.

Next steps options:
- Step 6 (video processor) — `src/simplegallery/video_processor.py`: `probe()`, `generate_thumbnail()`, `transcode_mp4()`, `transcode_webm()`; wire into builder; `tests/test_video_processor.py` (mark transcode `@pytest.mark.slow`); short fixture mp4.
- Step 8 (watcher) — `src/simplegallery/watcher.py`: watchdog `FileSystemEventHandler`, debounced rebuild, dirty-slug set; wire `--watch`; `tests/test_watcher.py`.

How to verify Step 5 in browser:
- Drop sample images into `./source/<gallery>/`, then `docker compose run --rm app`.
- Open `output/index.html` in a browser. Check grid, click → lightbox, arrows/Escape, swipe, EXIF toggle, mobile viewport (Chrome DevTools).
