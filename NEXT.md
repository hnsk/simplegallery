# NEXT

Step 5 — Frontend (CSS + JS replaces stubs).

Status:
- Step 0 done.
- Step 1 done.
- Step 2 done.
- Step 3 done.
- Step 4 done. `image_processor.py` (Wand: auto-orient, 400×300 crop-fill WebP@80, JPEG@92 with GPS stripped; EXIF read via Wand → `exifread` fallback, humanized to Camera/Lens/Date/Exposure/Aperture/ISO/FocalLength). Builder wires `ThreadPoolExecutor(workers)`, per-image `cache.is_stale()` skip, per-image try/except, populates `data-exif` JSON via `Renderer.render_gallery(gallery, exif=...)`. Tests pull from gitignored `sample-data/` (mounted at `/sample-data` ro in `test`/`shell` services); skip when fixtures absent. 47 passed, 1 skipped (`docker compose run --rm test`).
- Step 7 done early.

Create / replace:
- `src/simplegallery/static/gallery.css`
  - CSS Grid `auto-fill minmax(200px,1fr)`
  - Lightbox overlay `position:fixed`, dark backdrop, centered media
  - EXIF panel: side rail desktop, slide-up sheet on `@media (max-width:768px)`
  - Play badge for video thumbs
- `src/simplegallery/static/gallery.js` (IIFE, no deps)
  - `GalleryGrid` — click figure → open Lightbox
  - `Lightbox` — DOM injection, open/close/nav, focus trap (save/restore `activeElement`), `role="dialog"`, `aria-modal="true"`, prev/next/close buttons with `aria-label`, keyboard arrows + Escape, touch swipe `|Δx|>50 && |Δx|>|Δy|`, ±1 neighbor preload
  - Image branch loads `data-src`; video branch builds `<video>` with `data-mp4` + `data-webm` sources, poster=`data-thumb`
  - `ExifPanel` — `(i)` `<button>`; parse `data-exif` JSON → `<dl>/<dt>/<dd>` rows
- `src/simplegallery/static/icons/play.svg` — play badge for video thumbs
- Renderer: alt text on thumb img already from filename. Lightbox markup is JS-injected — no template change.

Tests:
- `tests/test_frontend_assets.py`
  - asset files present in package
  - `gallery.css` / `gallery.js` non-empty, contain expected hooks (`.gallery-grid`, `Lightbox`, `data-exif`)
  - copy_assets emits all (incl. `icons/play.svg`)

How to run during Step 5:
- Tests: `docker compose run --rm test`
- Smoke: `docker compose run --rm app` after dropping sample images into `./source/<gallery>/`, then open `output/index.html` in a browser
- Mobile check: Chrome DevTools device emulation

After Step 5: update TODO.md + NEXT.md, commit, then Step 6 (video processor) or Step 8 (watcher).
