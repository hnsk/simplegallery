# simplegallery TODO

## Step 0 — Project init
- [x] `.gitignore` — `__pycache__/`, `*.pyc`, `.gallery_cache.json`, `output/`, `.venv/`, `dist/`, `*.egg-info/`, `.pytest_cache/`
- [x] `NEXT.md` — seed with "next: Step 1 scaffold"
- [x] `git init` + initial commit

## Step 1 — Scaffold: config + CLI + entry point
- [x] `pyproject.toml` — runtime deps + dev deps (`pytest`); entry point `simplegallery=simplegallery.__main__:main`
- [x] `src/simplegallery/config.py` — `Config` dataclass (incl. `log_level`), load env vars, defaults
- [x] `src/simplegallery/cli.py` — argparse: `--source`, `--output`, `--title`, `--watch`, `--workers`, `--verbose/-v`
- [x] `src/simplegallery/__main__.py` — parse args → build Config → `logging.basicConfig(level=...)` → call builder or watcher

## Step 2 — Scanner + cache
- [x] `src/simplegallery/slugify.py` — `slugify(name)` → ascii, lowercase, hyphenated, collision-safe
- [x] `src/simplegallery/scanner.py` — `MediaFile`, `Gallery` dataclasses (incl. `slug`); `DirectoryScanner.scan()` — top-level subdirs only, split image/video by ext, derive output paths via slug, set cover_file
- [x] `src/simplegallery/cache.py` — `BuildCache` — JSON at `<output>/.gallery_cache.json`; `is_stale()` (mtime+size+missing outputs); `mark_done()`; atomic save; prune deleted sources + orphan outputs
- [x] `tests/test_slugify.py` — ascii/unicode/collision cases
- [x] `tests/test_scanner.py` — tmp source tree, assert image/video split, slug mapping, cover selection
- [x] `tests/test_cache.py` — stale detection, prune, atomic save

## Step 3 — Renderer + stub templates
- [ ] `src/simplegallery/renderer.py` — Jinja2 `PackageLoader`; `render_index()`; `render_gallery()`; copy `static/` → `output/assets/` each build with content-hash filenames (`gallery.<hash>.css`, `gallery.<hash>.js`); correct relative asset paths per depth
- [ ] `src/simplegallery/templates/base.html.j2` — shared head, hashed asset links
- [ ] `src/simplegallery/templates/index.html.j2` — grid of gallery cards (cover thumb, name, count)
- [ ] `src/simplegallery/templates/gallery.html.j2` — `<figure data-exif data-src data-mp4 data-webm>` per item
- [ ] `src/simplegallery/builder.py` — `GalleryBuilder.build_all()` skeleton (scanner → renderer, no processing yet)
- [ ] `tests/test_renderer.py` — render to tmpdir; assert files exist, hashed asset names referenced, depth-correct relative paths

## Step 4 — Image processor
- [ ] `src/simplegallery/image_processor.py`
  - `generate_thumbnail()` — wand, auto-orient, crop-fill 400×300, WebP q=80
  - `generate_full()` — wand, auto-orient, JPEG q=92, strip GPS keep camera tags
  - `extract_exif()` — wand primary, `exifread` fallback; return dict of display tags
  - HEIC/HEIF input supported via wand (imagemagick libheif)
- [ ] Wire into `builder.py` — `ThreadPoolExecutor(workers)`, `cache.is_stale()` guard, embed EXIF JSON on `<figure>`
- [ ] `tests/fixtures/` — small JPEG + HEIC sample
- [ ] `tests/test_image_processor.py` — thumb dims, full dims, EXIF dict, GPS stripped, HEIC decoded

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
- [ ] Accessibility — `alt` on thumb `<img>` from filename; `aria-label` on lightbox prev/next/close; `(i)` is real `<button>`; lightbox `role="dialog"` + `aria-modal="true"`

## Step 6 — Video processor
- [ ] `src/simplegallery/video_processor.py`
  - `probe()` — ffprobe JSON → `VideoInfo` (width, height, duration, codec, has_audio)
  - `generate_thumbnail()` — seek to `min(1.0, duration*0.1)`, pipe frame → wand → WebP
  - `transcode_mp4()` — libx264 CRF23, preset slow, AAC 128k, faststart, even-dim scale
  - `transcode_webm()` — libvpx-vp9 CRF33 b:v 0, libopus 96k; skip audio if `has_audio=False`
- [ ] Wire into `builder.py`
- [ ] `tests/fixtures/` — short sample mp4 (≤2s, low-res)
- [ ] `tests/test_video_processor.py` — `probe()` returns expected fields; thumb generated; mp4 + webm produced; transcode tests marked `@pytest.mark.slow`

## Step 7 — Docker
- [x] `Dockerfile` — `python:3.12-alpine`, `apk add --no-cache imagemagick imagemagick-dev libheif-dev libwebp-dev tiff-dev ffmpeg`, pip install (incl. `pytest`), VOLUME, ENTRYPOINT
- [x] `docker/imagemagick-policy.xml` — raise memory cap to 2GiB, allow all formats
- [x] `docker-compose.yml`
  - `app` service — source `:ro` mount, output mount, env vars with defaults, `restart: unless-stopped`
  - `test` service — same image, command `pytest -v`, mounts `src/` + `tests/`, no restart
  - `shell` service — interactive sh for ad-hoc checks (added per CLAUDE.md no-host-Python rule)

## Step 8 — Watcher
- [ ] `src/simplegallery/watcher.py` — watchdog `FileSystemEventHandler`; thread-safe dirty-slug set; debounced `threading.Timer` (default 2s) → `builder.build_galleries(dirty_slugs)` + re-render index; handles `DirCreatedEvent` / `DirDeletedEvent` / `DirMovedEvent` on top-level subdirs (rebuild index, prune removed slugs); `WatcherService.start()` blocks on `observer.join()`
- [ ] Wire `--watch` flag in `__main__.py` → `WatcherService`
- [ ] `tests/test_watcher.py` — handler unit tests: file event → dirty slug; dir create/delete → index dirty; debounce coalesces bursts

## Test fixtures
- `sample-data/` — real images (jpg/jpeg/png/heic) + videos (mp4/webm) for ad-hoc verification. Gitignored. Copy/rename into multiple `source/<gallery>/` subdirs to exercise scanner, slug collisions, image+video processors, and gallery output. Do not commit.

## Step 9 — Polish + verification
- [ ] Per-file error handling — log error + skip, don't abort whole build
- [ ] `docker compose run test` — all tests pass
- [ ] `docker compose up app` smoke test — 2+ source subdirs, images, short video
- [ ] Verify: index lists galleries, thumbs render, lightbox opens, arrows navigate, EXIF shows
- [ ] Mobile viewport (Chrome DevTools) — swipe works, EXIF slides up
- [ ] Modify source file → only affected gallery rebuilds
- [ ] Video: lightbox shows HTML5 player (poster + MP4 + WebM sources)
- [ ] Delete source subdir → output gallery removed on next build
- [ ] Rename source subdir → old slug pruned, new slug built
