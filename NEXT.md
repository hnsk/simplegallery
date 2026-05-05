# NEXT

Step 3 — Renderer + stub templates.

Status:
- Step 0 done.
- Step 1 done. CLI smoke (`docker compose run --rm app --help`) verified.
- Step 2 done. `slugify`, `DirectoryScanner` (Gallery/MediaFile dataclasses with per-file output paths), `BuildCache` (JSON, atomic save, stale checks, prune).
- Step 7 done early (out of TODO order, user-approved). `simplegallery:dev` image builds; `docker compose run --rm test` passes 34 tests.

Create:
- `src/simplegallery/renderer.py` — Jinja2 `PackageLoader`; `render_index(galleries)`; `render_gallery(gallery)`; copy `static/` → `output/assets/` with content-hashed filenames (`gallery.<hash>.css`, `gallery.<hash>.js`); compute correct relative asset paths per render depth.
- `src/simplegallery/templates/base.html.j2` — shared `<head>`, hashed asset links via context vars.
- `src/simplegallery/templates/index.html.j2` — grid of gallery cards (cover thumb, name, count).
- `src/simplegallery/templates/gallery.html.j2` — `<figure data-exif data-src data-mp4 data-webm>` per item.
- `src/simplegallery/builder.py` — `GalleryBuilder.build_all()` skeleton: scan → prune cache → render index + galleries (no media processing yet).
- Stub `src/simplegallery/static/gallery.css` + `gallery.js` so the renderer has assets to hash and copy (full content lands in Step 5).
- `tests/test_renderer.py` — render to tmpdir; assert files exist, hashed asset names referenced, depth-correct relative paths.

How to run during Step 3:
- Tests: `docker compose run --rm test`
- Ad-hoc shell: `docker compose run --rm shell`
- Build smoke (after wiring builder): `docker compose run --rm app` with a sample `./source/` tree.

After Step 3: update TODO.md + NEXT.md, commit, then Step 4 (image processor).
