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
- [x] `src/simplegallery/renderer.py` — Jinja2 `PackageLoader`; `render_index()`; `render_gallery()`; copy `static/` → `output/assets/` each build with content-hash filenames (`gallery.<hash>.css`, `gallery.<hash>.js`); correct relative asset paths per depth
- [x] `src/simplegallery/templates/base.html.j2` — shared head, hashed asset links
- [x] `src/simplegallery/templates/index.html.j2` — grid of gallery cards (cover thumb, name, count)
- [x] `src/simplegallery/templates/gallery.html.j2` — `<figure data-exif data-src data-mp4 data-webm>` per item
- [x] `src/simplegallery/builder.py` — `GalleryBuilder.build_all()` skeleton (scanner → renderer, no processing yet)
- [x] `tests/test_renderer.py` — render to tmpdir; assert files exist, hashed asset names referenced, depth-correct relative paths
- [x] Stub `src/simplegallery/static/gallery.css` + `gallery.js` (full content lands in Step 5)

## Step 4 — Image processor
- [x] `src/simplegallery/image_processor.py`
  - `generate_thumbnail()` — wand, auto-orient, crop-fill 400×300, WebP q=80
  - `generate_full()` — wand, auto-orient, JPEG q=92, strip GPS keep camera tags
  - `extract_exif()` — wand primary, `exifread` fallback; humanized display dict
  - HEIC/HEIF input supported via wand (imagemagick libheif)
- [x] Wire into `builder.py` — `ThreadPoolExecutor(workers)`, `cache.is_stale()` guard, per-image try/except, EXIF JSON on `<figure data-exif>`
- [x] Tests use `sample-data/` (gitignored, not committed) mounted at `/sample-data` via `test`/`shell` services; `SIMPLEGALLERY_SAMPLE_DATA` env var, skip when missing
- [x] `tests/test_image_processor.py` — thumb dims/format, full dims/format, EXIF dict shape, GPS stripped, HEIC thumb + full

## Step 5 — Frontend
- [x] `static/gallery.css` — CSS Grid `auto-fill minmax(200px,1fr)`, lightbox overlay `position:fixed`, `@media (max-width:768px)`, EXIF side rail desktop / slide-up sheet mobile, play badge for video thumbs
- [x] `static/gallery.js` — IIFE; `GalleryGrid`, `Lightbox`, `ExifPanel` classes
  - Lightbox DOM injection, open/close/nav
  - `data-src` (image) or `data-mp4`/`data-webm` (video) loading
  - Preload ±1 neighbors
  - Keyboard: arrows + Escape
  - Touch swipe: `|Δx|>50px` and `|Δx|>|Δy|`
  - Focus trap (save/restore `activeElement`)
  - ExifPanel: parse `data-exif` JSON → `<dt>/<dd>`, toggle via `(i)` button; mobile slide-up
- [x] `static/icons/play.svg` — play button overlay for video thumbs (verbatim copy at `assets/icons/play.svg`, referenced by CSS `background-image`)
- [x] Accessibility — `alt` on thumb `<img>` from filename; `aria-label` on lightbox prev/next/close/info; `(i)` is real `<button>`; lightbox `role="dialog"` + `aria-modal="true"`
- [x] `tests/test_frontend_assets.py` — packaged asset payload + `copy_assets` emits CSS/JS/icons

## Step 6 — Video processor
- [x] `src/simplegallery/video_processor.py`
  - `probe()` — ffprobe JSON → `VideoInfo` (width, height, duration, codec, has_audio)
  - `generate_thumbnail()` — seek to `min(1.0, duration*0.1)`, pipe frame → wand → WebP
  - `transcode_mp4()` — libx264 CRF23, preset slow, AAC 128k, faststart, even-dim scale
  - `transcode_webm()` — libvpx-vp9 CRF33 b:v 0, libopus 96k; skip audio if `has_audio=False`
- [x] Wire into `builder.py`
- [x] Test fixture clip generated at runtime via `ffmpeg -f lavfi testsrc/sine` (session-scoped, no committed binary)
- [x] `tests/test_video_processor.py` — `probe()` returns expected fields; thumb generated; mp4 + webm produced; transcode tests marked `@pytest.mark.slow`

## Step 7 — Docker
- [x] `Dockerfile` — `python:3.12-alpine`, `apk add --no-cache imagemagick imagemagick-dev libheif-dev libwebp-dev tiff-dev ffmpeg`, pip install (incl. `pytest`), VOLUME, ENTRYPOINT
- [x] `docker/imagemagick-policy.xml` — raise memory cap to 2GiB, allow all formats
- [x] `docker-compose.yml`
  - `app` service — source `:ro` mount, output mount, env vars with defaults, `restart: unless-stopped`
  - `test` service — same image, command `pytest -v`, mounts `src/` + `tests/`, no restart
  - `shell` service — interactive sh for ad-hoc checks (added per CLAUDE.md no-host-Python rule)

## Step 8 — Watcher
- [x] `src/simplegallery/watcher.py` — watchdog `FileSystemEventHandler`; thread-safe dirty-name set + index-dirty flag; debounced `threading.Timer` (`config.debounce_seconds`) → `builder.build_galleries(dirty_names)`; handles `DirCreatedEvent` / `DirDeletedEvent` / `DirMovedEvent` on top-level subdirs (mark index dirty, both endpoints for moves); `WatcherService.start()` runs initial `build_all()` then blocks on `observer.join()`
- [x] `GalleryBuilder.build_galleries(names, rebuild_index=True)` — partial rebuild path; processes only galleries whose source-dir name is in the set; always re-renders index; cache prune still runs for orphan slugs
- [x] Wire `--watch` flag in `__main__.py` → `WatcherService` (already in place from Step 1 scaffold)
- [x] `tests/test_watcher.py` — handler unit tests: file event → dirty name; dir create/delete/move → index dirty; debounce coalesces bursts; events outside source / hidden top-level ignored; `WatcherService` end-to-end calls `build_galleries`

## Test fixtures
- `sample-data/` — real images (jpg/jpeg/png/heic) + videos (mp4/webm) for ad-hoc verification. Gitignored. Copy/rename into multiple `source/<gallery>/` subdirs to exercise scanner, slug collisions, image+video processors, and gallery output. Do not commit.

## Step 9 — Polish + verification
- [x] Per-file error handling — log error + skip, don't abort whole build (already in builder)
- [x] `docker compose run test` — 71 pass, 1 pre-existing flaky HEIC failure on `shelf-christmas-decoration.heic` (sample-data artifact, not regression)
- [x] Switched image processing from `ThreadPoolExecutor` → `ProcessPoolExecutor` (spawn ctx) — wand/IM not thread-safe; concurrent thread access caused intermittent `cache.c/GetImagePixelCache/1743` "time limit exceeded" misreports
- [x] Watcher: filter `FileOpenedEvent` + `FileClosedNoWriteEvent` — they fire when the build reads source files and caused infinite rebuild loop on Linux/WSL2
- [x] `docker compose up app` smoke test — 2 subdirs (`photos`, `videos`), 6 images + 2 videos + 1 image in videos dir; index + per-gallery pages render; thumbs/full/mp4/webm produced; corrupt JPEG (`uC38zxx.jpeg`) and HEIC fail per-file (handled gracefully)
- [x] Watcher live test — file drop → only affected gallery rebuilds; new subdir → `index_dirty=True` + scanned 3 galleries; rename → old slug pruned + new built; delete → slug pruned + index refresh
- [ ] Manual lightbox verify in browser (arrows, EXIF, video poster)
- [ ] Mobile viewport (Chrome DevTools) — swipe + EXIF slide-up
- [ ] Resolve HEIC time-limit on `shelf-christmas-decoration.heic` (substitute another HEIC sample, or accept as known sample-data quirk)

## Step 10 — Web-root layout + recursive galleries + originals-as-full

Goal: single `/web` mount. Source lives at `/web/<gallery_subdir>/` (default `gallery`). Output assets/HTML/derivatives live at `/web/`. Originals served directly as full-size for browser-friendly formats (no JPEG re-encode). HEIC/HEIF/TIFF get a JPEG derivative + original kept downloadable. Galleries nest arbitrarily; every gallery dir gets its own page (subgallery cards first, then media). We own `/web/` root; anything user puts there outside `<gallery_subdir>/` = user error.

- [x] **Config** — `Config` gains `web_root` + `gallery_subdir`; `source`/`output` derived in `__post_init__` (still settable directly for transitional callers). New env: `SIMPLEGALLERY_WEB` (default `/web`), `SIMPLEGALLERY_GALLERY_SUBDIR` (default `gallery`). Old `SIMPLEGALLERY_SOURCE`/`SIMPLEGALLERY_OUTPUT` env vars dropped. CLI gains `--web` + `--gallery-subdir`; legacy `--source`/`--output` kept until substep 9 to keep tests/scanner/builder running. `RESERVED_ROOT_NAMES = {"assets", "index.html"}`; `Config.reserved_root_names` adds `gallery_subdir`. New `direct_image_extensions` (jpg/jpeg/png/webp/gif/avif) for substep 3 transcode_needed logic. Tests: `tests/test_config.py` covers env defaults, env overrides, legacy explicit source/output, missing-paths error, reserved names, and CLI overrides.
- [x] **Scanner** — `DirectoryScanner.scan_tree()` returns recursive root `Gallery` (or `None` if entire tree empty). `Gallery` gains `subgalleries`, `rel_path: PurePosixPath`, `breadcrumbs: list[(name, rel_path)]`, `subcount` property, `walk()` DFS helper. Output dirs mirror source rel paths under `web_root`. Reserved root-level names (`assets`, `index.html`, `<gallery_subdir>`) skipped + warned only at depth 0; nested dirs of the same name are kept. Empty branches (no own media + no non-empty subs) pruned. Legacy flat `scan()` retained until builder/renderer/watcher migrate. Tests: `tests/test_scanner_tree.py` (15 cases).
- [x] **MediaFile** — `transcode_needed: bool` set true iff ext ∈ `{.heic,.heif,.tif,.tiff}` (everything else in `image_extensions` is browser-friendly via `Config.direct_image_extensions`). Tree-mode `output_full` set only when `transcode_needed`; legacy flat scan keeps unconditional `output_full` until builder/image processor migrate. `original_rel: PurePosixPath` (POSIX path relative to `web_root`, e.g. `gallery/photos/a.jpg`) recorded on every media file for use as `data-src`/download. Output dirs mirror source: `web/<rel>/thumbs/<slug>.webp`, `web/<rel>/full/<slug>.jpg` (only HEIC/TIFF), `web/<rel>/video/<slug>.{mp4,webm}`.
- [ ] **Image processor** — `generate_full` only invoked when `transcode_needed`. EXIF strip stays for HEIC/TIFF derivative; original untouched (document GPS-stays for direct-served formats).
- [ ] **Cache** — `is_stale` + `mark_done` keyed by source path (already path-based, but verify after recursive change). `prune` walks recursive output tree; preserves `<gallery_subdir>/`, `assets/`, top-level `index.html`. Orphan dirs/files outside that set get removed only if cache says they were ours.
- [ ] **Renderer** — single `gallery.html.j2` (root gallery uses same template; no separate `index.html.j2`). Breadcrumbs partial. Subgallery card grid (cover thumb if any own image else text-only; show `count` own + `subcount` non-recursive). Media grid below. Lightbox `data-src` → derivative-or-original; `data-original` always points to original for download button. `assets/` + originals referenced via relative paths from each page.
- [ ] **Templates** — `gallery.html.j2` rewritten; new `_breadcrumbs.html.j2` partial; `_subgallery_card.html.j2` + `_media_item.html.j2` partials if cleaner. Drop `index.html.j2`.
- [ ] **Frontend (CSS/JS)** — lightbox download button (anchor with `download` attr → `data-original`); subgallery card styling; breadcrumb styling. Update `data-exif` shape unchanged.
- [ ] **Builder** — walk gallery tree (DFS). Process all media in tree (own pool batches). Render every gallery page. Skip empties.
- [ ] **Watcher** — dirty unit = source dir of changed file. Dir create/delete/move marks parent + new dir. Output writes still confined to `web/<rel>/{thumbs,full,video}/` so existing `FileOpenedEvent`/`FileClosedNoWriteEvent` filter remains; verify no loop with new layout.
- [ ] **CLI / `__main__`** — `--web` (replaces `--source`/`--output`), `--gallery-subdir`. Update help text.
- [ ] **docker-compose.yml** — single `${SIMPLEGALLERY_WEB_DIR:-./web}:/web` mount (rw). Drop `/source` + `/output`. Update `app` env: `SIMPLEGALLERY_WEB=/web`, `SIMPLEGALLERY_GALLERY_SUBDIR=gallery`. Test/shell services unchanged except sample-data path semantics.
- [ ] **Sample tree** — under `./web/gallery/` create nested example: `./web/gallery/photos/...`, `./web/gallery/photos/macro/...`, `./web/gallery/videos/...`, plus a root-level `./web/gallery/cover.jpg` to exercise media-at-root.
- [ ] **Tests** — rewrite scanner tests for recursive model + reserved-name collisions; cache prune across nested output; renderer tests for breadcrumbs + subgallery cards + original-href + transcode-only-when-needed; image processor unchanged but builder tests reflect new dir layout; watcher tests for nested dirty propagation; frontend asset test still valid.
- [ ] **Smoke** — `docker compose run --rm app -v` over nested sample. Verify originals served, HEIC derivative rendered, download button hits original, breadcrumbs correct at every depth, no output written into source dir.
- [ ] **TODO.md + NEXT.md** updated after each substep; git commit per substep.
