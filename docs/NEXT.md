# NEXT

Step 16 (CI + slim runtime image) landed. Step 11 mobile-viewport carry-over verified by user — closed out.

## What landed this batch

- `.github/workflows/test.yml` — push (main) / PR triggers, `docker/setup-buildx-action@v3`, `docker compose --profile dev build test` + `docker compose run --rm test`.
- `Dockerfile` split into `base` → `builder` → `runtime` / `dev` stages. Runtime carries no compilers or `-dev` headers; deps are `pip install --prefix=/install`-ed in builder and `COPY --from=builder /install /usr/local`-ed into runtime. Dev stage retains build deps + editable install + tests.
- Base sets `MAGICK_HOME=/usr` and creates unversioned `libMagick{Wand,Core}-7.Q16HDRI.so` symlinks — required because musl `ctypes.util.find_library` returns `None` without gcc, so wand needs `MAGICK_HOME` + the unversioned `.so` to resolve.
- `docker-compose.yml` — `app` builds with `target: runtime` (image tag `simplegallery:runtime`); `test` + `shell` build with `target: dev` (`simplegallery:dev`).
- Image sizes: `simplegallery:runtime` **200 MB** (was 493 MB, ~60% cut), `simplegallery:dev` 505 MB.
- Mobile-viewport lightbox (Step 11 carry-over: swipe + EXIF slide-up + hash routing on touch) verified by user.

## Next batch

Repo is feature-complete for the original scope. Open candidates if a new batch is desired:

1. **Publish** — push to `github.com/hnsk/simplegallery`, tag `v0.1.0`, `python -m build` + `twine upload` to PyPI (image already production-shaped). Requires user to provide remote + PyPI creds.
2. **GHCR image publish** — extend CI workflow to also build + push `simplegallery:runtime` to `ghcr.io/hnsk/simplegallery` on tag.
3. **Sample-data CI tests** — gate the currently-skipped EXIF/HEIC cases behind a CI fixture pack (committed under `tests/fixtures/` or fetched at job start).

## How to reproduce

- Build runtime: `docker compose build app`
- Build dev (test/shell): `docker compose --profile dev build test`
- Tests: `docker compose run --rm test`
- Smoke: `docker compose run --rm app -v`
- Browse: `docker compose --profile dev up -d serve` → http://127.0.0.1:8080/
- CI locally: `act -j test` (or push to a branch and let GitHub run it).

---

## Earlier context (kept for reference)

Step 15 (sort UI + compact HTML) landed. `Gallery.mtime` recursive max-mtime per gallery. Renderer uses `trim_blocks=True, lstrip_blocks=True`; templates rewritten compact. New `<aside class="gallery-controls">` per page with `Sort by [name|date]` + `Order [asc|desc]`; defaults `name asc`. `data-name` + `data-mtime` (epoch seconds) on figures + subgallery cards. `gallery.js` `GalleryControls` reorders DOM in place; `GalleryGrid.refreshItems()` rebuilds the `items` array (and lightbox order). Click handler resolves index by `figure.dataset.slug`. Suite: 115 pass, 1 skip.

Step 14 (pre-publish cleanup) — `pyproject.toml` polished (keywords, classifiers, urls, author). `__main__.py` deduped. `cli.parse_args` wrapper removed. Builder collapsed into single `build_all(dirty_rels=None)`. `Renderer.copy_assets` unified. Dev logs moved under `docs/`. `tests/test_smoke.py` folded into `test_config.py`. `--debounce` CLI flag added.

Step 13 (shareable lightbox links) — every figure carries `id="m-{slug}"` + `data-slug`; thumb sits inside `<a class="gallery-link" href="{full|original|video}">` so right-click "copy link" / middle-click / "open in new tab" all yield the full-size media URL. Lightbox drives `location.hash`; deep links `…/page#m-slug` auto-open and back-button closes.

Step 11 HEIC + multi-worker flake resolved via `docker/imagemagick-policy.xml` — removed bogus `time` policy line + dropped IM thread count to 1 (process pool already provides parallelism).
