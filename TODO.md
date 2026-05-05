# simplegallery TODO

## Step 1 — Scaffold: config + CLI + entry point
- [ ] `pyproject.toml` — deps, entry point `simplegallery=simplegallery.__main__:main`
- [ ] `src/simplegallery/config.py` — `Config` dataclass, load env vars, defaults
- [ ] `src/simplegallery/cli.py` — argparse: `--source`, `--output`, `--title`, `--watch`, `--workers`
- [ ] `src/simplegallery/__main__.py` — parse args → build Config → call builder or watcher

## Step 2 — Scanner + cache
- [ ] `src/simplegallery/scanner.py` — `MediaFile`, `Gallery` dataclasses; `DirectoryScanner.scan()` — top-level subdirs only, split image/video by ext, derive output paths, set cover_file
- [ ] `src/simplegallery/cache.py` — `BuildCache` — JSON at `<output>/.gallery_cache.json`; `is_stale()` (mtime+size+missing outputs); `mark_done()`; atomic save; prune deleted sources + orphan outputs

## Step 3 — Renderer + stub templates
- [ ] `src/simplegallery/renderer.py` — Jinja2 `PackageLoader`; `render_index()`; `render_gallery()`; copy `static/` → `output/assets/` each build; correct relative asset paths per depth
- [ ] `src/simplegallery/templates/base.html.j2` — shared head, asset links
- [ ] `src/simplegallery/templates/index.html.j2` — grid of gallery cards (cover thumb, name, count)
- [ ] `src/simplegallery/templates/gallery.html.j2` — `<figure data-exif data-src data-mp4 data-webm>` per item
- [ ] `src/simplegallery/builder.py` — `GalleryBuilder.build_all()` skeleton (scanner → renderer, no processing yet)

## Step 4 — Image processor
- [ ] `src/simplegallery/image_processor.py`
  - `generate_thumbnail()` — wand, auto-orient, crop-fill 400×300, WebP q=80
  - `generate_full()` — wand, auto-orient, JPEG q=92, strip GPS keep camera tags
  - `extract_exif()` — wand primary, `exifread` fallback; return dict of display tags
- [ ] Wire into `builder.py` — `ThreadPoolExecutor(workers)`, `cache.is_stale()` guard, embed EXIF JSON on `<figure>`

## Step 5 — Frontend
- [ ] `static/gallery.css` — CSS Grid `auto-fill minmax(200px,1fr)`, lightbox overlay `position:fixed`, `@media (max-width:768px)`
- [ ] `static/gallery.js` — IIFE; `GalleryGrid`, `Lightbox`, `ExifPanel` classes
  - Lightbox DOM injection, open/close/nav
  - `data-src` (image) or `data-mp4`/`data-webm` (video) loading
  - Preload ±1 neighbors
  - Keyboard: arrows + Escape
  - Touch swipe: `|Δx|>50px` and `|Δx|>|Δy|`
  - Focus trap (save/restore `activeElement`)
  - ExifPanel: parse `data-exif` JSON → `<dt>/<dd>`, toggle via `(i)` button; mobile slide-up
- [ ] `static/icons/play.svg` — play button overlay for video thumbs

## Step 6 — Video processor
- [ ] `src/simplegallery/video_processor.py`
  - `probe()` — ffprobe JSON → `VideoInfo` (width, height, duration, codec, has_audio)
  - `generate_thumbnail()` — seek to `min(1.0, duration*0.1)`, pipe frame → wand → WebP
  - `transcode_mp4()` — libx264 CRF23, preset slow, AAC 128k, faststart, even-dim scale
  - `transcode_webm()` — libvpx-vp9 CRF33 b:v 0, libopus 96k; skip audio if `has_audio=False`
- [ ] Wire into `builder.py`

## Step 7 — Docker
- [ ] `Dockerfile` — python:3.12-alpine, `apk add --no-cache imagemagick imagemagick-dev libheif-dev libwebp-dev tiff-dev ffmpeg`, pip install, VOLUME, ENTRYPOINT
- [ ] `docker/imagemagick-policy.xml` — raise memory cap to 2GiB, allow all formats
- [ ] `docker-compose.yml` — source `:ro` mount, output mount, env vars with defaults, `restart: unless-stopped`

## Step 8 — Watcher
- [ ] `src/simplegallery/watcher.py` — watchdog `FileSystemEventHandler`; thread-safe dirty-slug set; debounced `threading.Timer` (default 2s) → `builder.build_galleries(dirty_slugs)` + re-render index; `WatcherService.start()` blocks on `observer.join()`
- [ ] Wire `--watch` flag in `__main__.py` → `WatcherService`

## Step 9 — Polish + verification
- [ ] Per-file error handling — log error + skip, don't abort whole build
- [ ] `docker compose up` smoke test — 2+ source subdirs, images, short video
- [ ] Verify: index lists galleries, thumbs render, lightbox opens, arrows navigate, EXIF shows
- [ ] Mobile viewport (Chrome DevTools) — swipe works, EXIF slides up
- [ ] Modify source file → only affected gallery rebuilds
- [ ] Video: lightbox shows HTML5 player (poster + MP4 + WebM sources)
- [ ] Delete source subdir → output gallery removed on next build
