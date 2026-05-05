# NEXT

Step 4 — Image processor.

Status:
- Step 0 done.
- Step 1 done.
- Step 2 done.
- Step 3 done. `Renderer` (PackageLoader, content-hashed `assets/gallery.<hash>.{css,js}`, depth-correct relative paths via `posixpath.relpath`), `base.html.j2` / `index.html.j2` / `gallery.html.j2`, stub `static/gallery.{css,js}`, `GalleryBuilder.build_all()` skeleton (scan → cache prune → copy_assets → render index + galleries → save cache). 40 tests pass (`docker compose run --rm test`).
- Step 7 done early. `simplegallery:dev` image + `app`/`test`/`shell` services.

Create:
- `src/simplegallery/image_processor.py`
  - `generate_thumbnail(src, dst)` — wand: auto-orient, crop-fill 400×300, WebP q=80
  - `generate_full(src, dst)` — wand: auto-orient, JPEG q=92, strip GPS, keep camera tags
  - `extract_exif(src) -> dict` — wand primary, `exifread` fallback; return display-tag dict
  - HEIC/HEIF input via wand (libheif from base image)
- Wire into `builder.py`:
  - `ThreadPoolExecutor(max_workers=config.workers)` over images
  - Per-image: skip when `cache.is_stale(media)` is False; on success `cache.mark_done(media)`
  - Embed EXIF JSON on `<figure data-exif='...'>` (renderer already passes `item["exif"]` through; populate it from `extract_exif()` in builder; use `renderer.serialize_exif()` helper)
  - Per-file try/except → log + skip, never abort whole build
- `tests/fixtures/` — small JPEG + small HEIC sample (commit them — small fixtures, not user data; outside `sample-data/`)
- `tests/test_image_processor.py`
  - thumb is 400×300, WebP, auto-oriented
  - full is JPEG ≤ orig dims, q≈92
  - `extract_exif()` returns expected camera tags
  - GPS keys stripped from full output
  - HEIC fixture decodes (covers libheif wiring)

How to run during Step 4:
- Tests: `docker compose run --rm test`
- Slow image processing iteration: `docker compose run --rm shell` then `python -c ...`
- End-to-end smoke: `docker compose run --rm app` after dropping samples in `./source/<gallery>/`

After Step 4: update TODO.md + NEXT.md, commit, then Step 5 (frontend CSS + JS — replaces stubs).
