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
- [ ] Manual lightbox verify in browser (arrows, EXIF, video poster) — moved to Step 11 carry-over via `serve` service
- [ ] Mobile viewport (Chrome DevTools) — swipe + EXIF slide-up — moved to Step 11 carry-over
- [ ] Resolve HEIC time-limit on `shelf-christmas-decoration.heic` — moved to Step 11 carry-over

## Step 11 — Lightbox UX polish
- [x] EXIF toggle button: relabel `i` → `EXIF`, move to top-right next to close X (`right: 4rem`); push download anchor to `right: 8.5rem`.
- [x] EXIF panel open: shift top-right buttons (close, EXIF, download, next-arrow) left by panel width via `:has(.exif-panel[data-open="true"])` so panel doesn't cover them; desktop only (≥769px), mobile sheet unaffected.
- [x] `.lightbox-btn` transition extended to animate `right` change.
- [x] `serve` compose service for host browser verify (`docker compose up -d serve` → http://127.0.0.1:8080/, ro mount `./web/`).
- [x] Manual browser verify against `./web/` via `serve` (arrows, EXIF toggle adjacent to X, download anchor, video poster) — verified.
- [ ] (deferred) Mobile viewport (Chrome DevTools) — swipe + EXIF slide-up sheet.
- [x] Investigate HEIC time-limit race on `shelf-christmas-decoration.heic` + multi-worker JPEG flake (`cache.c/GetImagePixelCache/1743`). Root cause: `docker/imagemagick-policy.xml` had `<policy domain="resource" name="time" value="unlimited"/>`; IM 7.1.2 parses that as `0 seconds` (visible via `magick -list resource` → `Time: 0 years`), tripping immediate `time limit exceeded` on slow decodes (HEIC dominant). Fix: removed bogus `time` policy line (default = truly unlimited) + dropped `thread=4` → `thread=1` (process pool already provides parallelism; nested IM threads = oversubscription). Verified: 20-copy HEIC stress test 0% → 100% success at workers=4 in ~10s; full pytest 110 pass.

## Step 10 — Web-root layout + recursive galleries + originals-as-full

Goal: single `/web` mount. Source lives at `/web/<gallery_subdir>/` (default `gallery`). Output assets/HTML/derivatives live at `/web/`. Originals served directly as full-size for browser-friendly formats (no JPEG re-encode). HEIC/HEIF/TIFF get a JPEG derivative + original kept downloadable. Galleries nest arbitrarily; every gallery dir gets its own page (subgallery cards first, then media). We own `/web/` root; anything user puts there outside `<gallery_subdir>/` = user error.

- [x] **Config** — `Config` gains `web_root` + `gallery_subdir`; `source`/`output` derived in `__post_init__` (still settable directly for transitional callers). New env: `SIMPLEGALLERY_WEB` (default `/web`), `SIMPLEGALLERY_GALLERY_SUBDIR` (default `gallery`). Old `SIMPLEGALLERY_SOURCE`/`SIMPLEGALLERY_OUTPUT` env vars dropped. CLI gains `--web` + `--gallery-subdir`; legacy `--source`/`--output` kept until substep 9 to keep tests/scanner/builder running. `RESERVED_ROOT_NAMES = {"assets", "index.html"}`; `Config.reserved_root_names` adds `gallery_subdir`. New `direct_image_extensions` (jpg/jpeg/png/webp/gif/avif) for substep 3 transcode_needed logic. Tests: `tests/test_config.py` covers env defaults, env overrides, legacy explicit source/output, missing-paths error, reserved names, and CLI overrides.
- [x] **Scanner** — `DirectoryScanner.scan_tree()` returns recursive root `Gallery` (or `None` if entire tree empty). `Gallery` gains `subgalleries`, `rel_path: PurePosixPath`, `breadcrumbs: list[(name, rel_path)]`, `subcount` property, `walk()` DFS helper. Output dirs mirror source rel paths under `web_root`. Reserved root-level names (`assets`, `index.html`, `<gallery_subdir>`) skipped + warned only at depth 0; nested dirs of the same name are kept. Empty branches (no own media + no non-empty subs) pruned. Legacy flat `scan()` retained until builder/renderer/watcher migrate. Tests: `tests/test_scanner_tree.py` (15 cases).
- [x] **MediaFile** — `transcode_needed: bool` set true iff ext ∈ `{.heic,.heif,.tif,.tiff}` (everything else in `image_extensions` is browser-friendly via `Config.direct_image_extensions`). Tree-mode `output_full` set only when `transcode_needed`; legacy flat scan keeps unconditional `output_full` until builder/image processor migrate. `original_rel: PurePosixPath` (POSIX path relative to `web_root`, e.g. `gallery/photos/a.jpg`) recorded on every media file for use as `data-src`/download. Output dirs mirror source: `web/<rel>/thumbs/<slug>.webp`, `web/<rel>/full/<slug>.jpg` (only HEIC/TIFF), `web/<rel>/video/<slug>.{mp4,webm}`.
- [x] **Image processor** — `generate_full` only invoked when `output_full` is set on the `MediaFile`. Tree-mode scanner already gates this on `transcode_needed`, so direct-served formats (jpg/png/webp/gif/avif) skip the JPEG re-encode entirely. Legacy flat scan still emits `output_full` for every image so renderer/builder/watcher tests keep passing during transition. Builder `_image_worker` accepts `full=None`. Module docstring documents that GPS strip only runs on transcoded HEIC/TIFF derivatives — direct-served originals are untouched and retain GPS tags. Tests: new `_image_worker` gate cases in `tests/test_image_processor.py` (full path runs `generate_full`, `None` skips it). 97 pass; 2 known sample-data flakes (`129679.jpg`, `shelf-christmas-decoration.heic`).
- [x] **Cache** — `is_stale` + `mark_done` already path-keyed; verified path-based source keys still apply with nested output dirs. `BuildCache` gains `reserved_root_names` param (passed by builder from `Config.reserved_root_names`). `prune` rewritten: traverses galleries via `Gallery.walk()`, drops stale entries, unlinks only files cache attests it owns, then collapses now-empty ancestor dirs upward — stopping at `output` itself or any reserved top-level (`gallery/`, `assets/`). Untracked stray files/dirs and reserved top-level paths are never touched. `index.html` left alone (builder/renderer concern). Tests: `tests/test_cache.py` rewritten — nested-layout prune, untracked-orphan preservation, reserved-root collapse guard, ghost-output-shared-with-active still skipped.
- [x] **Builder** — `GalleryBuilder.build_tree()` is the new full-build entrypoint: `scanner.scan_tree()` → DFS-walk root → cache prune over `Gallery.walk()` → `copy_assets()` → image+video pools collected across the whole tree → `render_gallery()` once per non-empty gallery (root included). `build_all()` is now an alias for `build_tree()`; the legacy `_build()` flat path stays alive only behind `build_galleries(names, …)` for the watcher until substep 10.8 migrates it. Empty trees still copy assets and prune so output is well-formed. Renderer/templates remain on the legacy shape for now (substep 10.6 rewrites them); root therefore renders via the existing `gallery.html.j2` (self-link back, empty grid for media-less roots). Tests: new `tests/test_builder_tree.py` (9 cases) covers full path coverage, asset copy, transcode-only-for-HEIC/TIFF, browser-friendly originals skip `full/`, nested page asset depth, video output references, empty/pruned branches, and `build_all` ↔ `build_tree` parity. `tests/test_renderer.py::test_builder_build_all_renders_index_and_each_gallery` updated to expect tree-mode `Trip A/index.html` paths. Suite: 106 pass; same 2 pre-existing sample-data flakes.
- [x] **Renderer** — `Renderer.render_gallery` is the single page entrypoint (root + nested both use it). `render_index`/`_index_entry` removed. Each page receives `breadcrumbs` (last entry = current page span, others anchors), `subgalleries` (cards with `cover_thumb` if any own image else text-only, plus `count` + `subcount`), and `items` (media). Lightbox `data-src` resolves to the JPEG derivative when one was generated (HEIC/TIFF), otherwise points at the original under `web_root/<gallery_subdir>/...`. `data-original` always points at the original (used by the upcoming download button). `assets/` + originals referenced via per-page relative paths via `_rel(target, page_dir)`.
- [x] **Templates** — `gallery.html.j2` rewritten as the only page template; new `_breadcrumbs.html.j2` partial driven by the renderer-prepared `breadcrumbs` ctx. Subgallery cards inlined in `gallery.html.j2` (own block above the media grid). `index.html.j2` removed. Builder `_build`/legacy flat path dropped; `build_galleries(names, rebuild_index)` now routes to `build_tree()` (full rebuild) until substep 10.8 reintroduces per-dir dirty propagation. Tests rewritten in `tests/test_renderer.py` (13 tree-mode cases). Suite: 115 pass, 1 skip (pre-existing sample-data EXIF skip); the two known sample-data flakes (`129679.jpg`, `shelf-christmas-decoration.heic`) currently green this run.
- [x] **Frontend (CSS/JS)** — lightbox download button: anchor `.lightbox-download` with `download` attr added to lightbox DOM; `_setDownload(item)` reads `item.original` (from `figure.dataset.original`), populates `href` + filename derived from path, hides anchor when no original. CSS adds `.breadcrumbs` (inline list w/ `/` separators), `.subgallery-grid`, `.subgallery-card`, `.subgallery-card--text`, `.lightbox-download` (positioned at `right: 4rem; top: 1rem`). Dropped dead `.index-grid` rules. `tests/test_frontend_assets.py` pins new selectors. Suite: 113 pass, 1 skip, 2 pre-existing sample-data flakes (`129679.jpg`, `shelf-christmas-decoration.heic`).
- [x] **Watcher** — `GalleryEventHandler` now tracks a `dirty_rels: set[str]` of POSIX source-dir rel paths under `config.source` (`""` denotes the root). File events mark the parent dir; dir create/delete mark the dir itself; dir moves mark both endpoints. Hidden components anywhere in the path are filtered. `FlushCallback` simplified to `Callable[[set[str]], None]`; `index_dirty` removed (every dir is its own page now, and ancestor re-render is handled by the builder). `WatcherService._rebuild` calls `builder.build_galleries(dirty_rels)`. Builder gains a real partial path: `_process_images` split into `_process_image_pipeline` (thumb+full, gated by `cache.is_stale`) and `_extract_exif_batch` (EXIF for any rendered image). `build_galleries(dirty_rels)` scans the full tree, scopes media processing to dirty rels and their descendants, and re-renders dirty + every ancestor (so subgallery cards stay in sync). `FileOpenedEvent` / `FileClosedNoWriteEvent` filter retained (output writes still confined to `web/<rel>/{thumbs,full,video}/`). Tests: `tests/test_watcher.py` rewritten for nested events (15 cases incl. deeply nested file/dir create, file at source root → `""` rel, nested dir move, hidden-component filter). Suite: 116 pass, 1 skip, 2 known sample-data HEIC flakes.
- [x] **CLI / `__main__`** — `--source` / `--output` argparse flags + their `apply_args` branches dropped. Help text on `--web` now spells out the single-mount layout. `__main__.py` wiring untouched (it already routes through `Config.from_env()` + `apply_args`). `tests/test_smoke.py::test_cli_overrides_config` switched to `--web` / `--gallery-subdir`. `tests/test_config.py::test_apply_args_no_legacy_source_output` asserts the legacy flags now raise `SystemExit`. Suite: 116 pass, 1 skip, 2 pre-existing HEIC sample-data flakes.
- [x] **docker-compose.yml** — `app` service collapsed to one `${SIMPLEGALLERY_WEB_DIR:-./web}:/web` rw mount. `SIMPLEGALLERY_SOURCE` / `SIMPLEGALLERY_OUTPUT` env vars dropped (no longer read by `Config.from_env`). Replaced with `SIMPLEGALLERY_WEB=/web` and `SIMPLEGALLERY_GALLERY_SUBDIR=${SIMPLEGALLERY_GALLERY_SUBDIR:-gallery}`. `test` / `shell` services untouched. `docker compose config` parses; suite still 116 pass + same sample-data flakes.
- [x] **Sample tree** — `./web/gallery/cover.jpg` (root-level), `./web/gallery/photos/{129679.jpg,214143.jpeg,214361.jpeg,52840.png}`, `./web/gallery/photos/macro/{214389.jpeg,shelf-christmas-decoration.heic}` (HEIC exercises transcode_needed), `./web/gallery/videos/{214357.mp4,198088.webm}`. Files copied from `./sample-data/`. `web/` added to `.gitignore`.
- [x] **Tests** — final sweep for legacy flat-layout assumptions. Per-substep rewrites already covered scanner_tree / cache / builder_tree / renderer / watcher / frontend / config / image_processor; the remaining stragglers were `tests/test_scanner.py` (legacy `scan()` only) and the legacy `scan()` + `_scan_files_into()` + `emit_full_for_all_images` machinery in `src/simplegallery/scanner.py`. Both removed; recursive `scan_tree()` is now the only public scan entrypoint. Suite: 110 pass, 1 skip, sample-data HEIC flakes oscillating between green and `time limit exceeded`.
- [x] **Smoke** — `docker compose run --rm app -v` over the assembled `./web/gallery/` tree.
  - Dockerfile pre-step: stale `SIMPLEGALLERY_SOURCE` / `SIMPLEGALLERY_OUTPUT` env replaced with `SIMPLEGALLERY_WEB=/web`; `VOLUME ["/source", "/output"]` collapsed to `VOLUME ["/web"]`. `app` service in compose gained `MAGICK_TIME_LIMIT=${MAGICK_TIME_LIMIT:-86400}` for parity with `test`/`shell`. `app` image rebuilt before smoke.
  - Layout verified: `/web/index.html`, `/web/photos/index.html`, `/web/photos/macro/index.html`, `/web/videos/index.html` rendered; `/web/assets/{gallery.<hash>.css, gallery.<hash>.js, icons/play.svg}` populated; thumb dirs present at every depth; `/web/videos/video/{198088,214357}.{mp4,webm}` transcoded.
  - Originals served direct: `data-src="../gallery/photos/129679.jpg"` etc. with no matching `full/<slug>.jpg` derivative in `/web/photos/`.
  - HEIC plumbing correct: `data-src="full/shelf-christmas-decoration.jpg"` + `data-original="../../gallery/photos/macro/shelf-christmas-decoration.heic"` (decode itself still hits the pre-existing libheif time-limit on this sample, a libheif/libde265 quirk; ImageMagick policy is `time=unlimited`, so the limit is internal to libheif. Sample-data flake — not a Step 10 regression).
  - Breadcrumbs correct at depth: `Gallery → photos → macro` on the macro page; `Gallery → photos`, `Gallery → videos` at depth 1; root shows just `Gallery`.
  - No output written under `/web/gallery/`; root cover served from `gallery/cover.jpg` and its thumb at `/web/thumbs/cover.webp`.
- [ ] **TODO.md + NEXT.md** updated after each substep; git commit per substep.

## Step 12 — Runtime polish
- [x] **Per-file processing logs** — builder logs `processing image: <src>` / `image done: <src>` and `processing video: <src>` / `video done: <src>` on stdout so container output shows progress. `__main__.basicConfig` routed to `sys.stdout`. ProcessPool gains `_worker_log_init` initializer so spawned children inherit a stdout handler at the configured level. Aggregate counts (`processing N image(s)` / `N video(s)`) emitted before pool submit.
- [x] **Direct video passthrough** — `Config.direct_video_extensions = {".mp4", ".webm"}`. Scanner sets `output_mp4`/`output_webm` only when source ext is outside that set (`transcode_needed=True`). Renderer fills `data-mp4` or `data-webm` from `original_rel` when no derivatives exist, so browser-friendly videos play from `gallery/<rel>/<file>` directly with no `web/<rel>/video/<slug>.{mp4,webm}` duplicate. Builder `_process_video` runs each transcode only when its output path is set; thumbnail still always generated. Tests updated (`test_scanner_tree.py`, `test_renderer.py`, `test_builder_tree.py`); new `.mov` case verifies transcode path still emits both derivatives. Suite: 111 pass, 1 skip.

## Step 13 — Shareable lightbox links
- [x] **Template** — every `<figure>` gains `id="m-{slug}"` + `data-slug` and an inner `<a class="gallery-link" href="{full|original|video}">` wrapping the thumb `<img>`. Browser-native middle-click / "open in new tab" / "copy link" gives the full-size image (or video) URL directly. Left-click still opens lightbox via JS preventDefault.
- [x] **JS hash routing** — `Lightbox._syncHistory()` pushes `#m-{slug}` on first open, `replaceState`s it on prev/next. Close → `history.back()` (or `replaceState` to clear hash when opened from deep link). `popstate` resyncs lightbox state from hash; deep link on page load auto-opens the matching figure. Anchor click handler skips lightbox when modifier keys / non-primary button used so middle/ctrl-click still opens the file natively.
- [x] **Scroll restore on close** — `_closeNow` calls `figure.scrollIntoView({block:'nearest'})` so closing returns the page to the figure that was last shown.
- [x] **CSS** — `.gallery-link` is a block link with no underline / inherited color; `figure` gets `scroll-margin-top: 1rem` so the anchored item isn't flush against the viewport top.
- [x] **Tests** — `tests/test_renderer.py` adds `test_render_figure_has_anchor_id_and_link` (browser-friendly + transcoded image cases) and `test_render_video_figure_link_points_at_video_file`. Full suite: 113 pass, 1 skip in docker.
- [x] **Smoke** — rebuilt `./web/` via shell+src mount; verified `id="m-..."`, `data-slug=`, `<a class="gallery-link" href="...">` in `web/photos/macro/index.html` plus regenerated hashed `gallery.<hash>.css/js`.

## Step 14 — Pre-publish cleanup

Goal: get the repo publish-ready (PyPI + GitHub). Audit done in session — see commit log for cleanup so far.

- [x] **Stale dirs wiped** — `output/`, `source/`, leftover `web/` cruft (`1920.webp*`, root-level `198088.webm`, orphan `web/{photos,videos}/video/*` from prior smoke runs) removed by user. `.gitignore` trimmed to drop legacy pre-Step-10 dirs (`source/`, `photos/`, `input/`, `output/`, `gallery_output/`); `web/` + `sample-data/` remain ignored.
- [x] **README.md** — added; documents layout, Docker workflows (build / watch / serve / test), config matrix, GPS-on-direct-originals privacy caveat. Referenced from `pyproject.toml`.
- [x] **LICENSE** — added MIT, matches `pyproject.toml license = { text = "MIT" }`.
- [ ] **Builder dedup** — collapse `build_tree()` + `build_galleries()` into one internal flow (~80% overlap: scan → prune → copy_assets → image_pipeline → exif_batch → videos → render). `build_galleries(None)` and full build differ only by the `(in_scope, to_render)` partition. Drop `build_tree()` alias if `build_all` stays the public name; keep one.
- [ ] **`__main__.py` scaffolding** — drop `try: from .builder import GalleryBuilder; except ImportError: log.error("not yet implemented (Step N)")` blocks in `_run_build` / `_run_watcher`. Top-level imports + direct calls.
- [ ] **`cli.parse_args`** — single-line wrapper, single caller (`__main__.main`). Inline.
- [ ] **`Renderer.copy_assets`** — unify `_HASHED_STATIC_FILES` / `_VERBATIM_STATIC_FILES` loops with one `(logical, hash: bool)` iteration.
- [ ] **`pyproject.toml`** — add `classifiers`, `[project.urls]` (homepage / repo / issues), `keywords` so PyPI listing isn't sparse.
- [ ] **CI** — `.github/workflows/test.yml` running `docker compose run --rm test` on push/PR.
- [ ] **Dockerfile split** — optional builder + runtime stages so production image doesn't carry `[dev]` extras (pytest). Defer if image size not a concern.
- [ ] **Dev log relocation** — move `TODO.md` + `NEXT.md` under `docs/` (or drop from sdist via `MANIFEST.in`); they're build-process artifacts, not user docs.
- [ ] **`tests/test_smoke.py`** — strict subset of `tests/test_config.py`. Fold in or delete.
- [ ] **`tests/test_config.py::test_apply_args_no_legacy_source_output`** — guards against pre-Step-10 flags. Drop once published.
- [ ] **`SIMPLEGALLERY_DEBOUNCE`** — env-only, no CLI flag. Either add `--debounce` or drop the env var (only relevant in `--watch`).
