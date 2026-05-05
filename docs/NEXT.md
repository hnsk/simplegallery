# NEXT

Step 15 (sort UI + compact HTML) landed.

## What landed this batch

- `Gallery.mtime` — scanner computes recursive max-mtime per gallery (own media + subgalleries) so subgallery cards expose a meaningful sort key.
- Renderer / templates — jinja env switched to `trim_blocks=True, lstrip_blocks=True`; `gallery.html.j2`, `_breadcrumbs.html.j2`, `base.html.j2` rewritten compact (no consecutive blank lines, single-line `<figure>` blocks).
- New per-page `<aside class="gallery-controls">` below the subgallery + media grids: `Sort by [name|date]` + `Order [asc|desc]`. Default `name asc` (matches scanner output, so initial order is unchanged).
- `data-name` + `data-mtime` (epoch seconds) added to every `<figure>` and every `.subgallery-card` for client-side sort.
- `gallery.js` — `GalleryControls` reorders DOM nodes of both `.subgallery-grid` and `.gallery-grid` in place; `GalleryGrid.refreshItems()` rebuilds the `items` array (and therefore lightbox prev/next order) from the current DOM order. Click handler now resolves index by `figure.dataset.slug` so post-sort clicks still open the correct lightbox slot.
- CSS — `.gallery-controls` flex layout with themed `<select>` styling.
- Tests — 4 new renderer cases (data-name + data-mtime on figures, on subgallery cards, sort controls + defaults, compact output) + frontend-asset hooks (`.gallery-controls`, `GalleryControls`, `gc-key`, `gc-order`). Suite: **115 pass, 1 skip** in docker.

## Next batch

1. **CI** — `.github/workflows/test.yml` running `docker compose run --rm test` on push/PR.
2. **Dockerfile split (optional)** — builder + runtime stages so production image drops `[dev]` extras.
3. **Mobile-viewport lightbox verify** — Step 11 carry-over (swipe + EXIF slide-up sheet + hash routing on touch).

## How to reproduce

- Build: `docker compose build app`
- Tests: `docker compose run --rm test`
- Smoke (uses installed package): `docker compose run --rm app -v`
- Smoke against fresh src (no rebuild): `docker compose run --rm shell -c "PYTHONPATH=/app/src python -m simplegallery -v"`
- Browse: `docker compose --profile dev up -d serve` → http://127.0.0.1:8080/

---

## Earlier context (kept for reference)

Step 14 (pre-publish cleanup) all but CI + optional Dockerfile split done. `pyproject.toml` polished (keywords, classifiers, urls, author). `__main__.py` deduped. `cli.parse_args` wrapper removed. Builder collapsed into single `build_all(dirty_rels=None)`. `Renderer.copy_assets` unified. Dev logs moved under `docs/`. `tests/test_smoke.py` folded into `test_config.py`. `--debounce` CLI flag added.

Step 13 (shareable lightbox links) — every figure carries `id="m-{slug}"` + `data-slug`; thumb sits inside `<a class="gallery-link" href="{full|original|video}">` so right-click "copy link" / middle-click / "open in new tab" all yield the full-size media URL. Lightbox drives `location.hash`; deep links `…/page#m-slug` auto-open and back-button closes.

Step 11 HEIC + multi-worker flake resolved via `docker/imagemagick-policy.xml` — removed bogus `time` policy line + dropped IM thread count to 1 (process pool already provides parallelism).
