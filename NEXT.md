# NEXT

Step 10 in progress — `/web` web-root layout with originals served directly + recursive galleries.

Completed substeps:
1. **Config** — done. `Config(web_root, gallery_subdir)`; `source`/`output` derived. Env: `SIMPLEGALLERY_WEB`, `SIMPLEGALLERY_GALLERY_SUBDIR`. CLI: `--web`, `--gallery-subdir` added; legacy `--source`/`--output` kept transitionally. Reserved-name set + `direct_image_extensions` introduced. Tests in `tests/test_config.py`.
2. **Scanner** — done. New `DirectoryScanner.scan_tree()` returns recursive root `Gallery` (or `None`). `Gallery` gains `subgalleries`/`rel_path`/`breadcrumbs`/`subcount`/`walk()`. Reserved root-level names skipped + warned only at depth 0. Empty branches pruned. `MediaFile` gains `transcode_needed` + `original_rel`; tree-mode emits `output_full` only when transcode needed (HEIC/TIFF). Legacy flat `scan()` still works for builder/renderer/watcher until their substeps. Tests in `tests/test_scanner_tree.py` (15 cases).
3. **Cache** — done. `BuildCache(output, reserved_root_names=...)`; builder threads `Config.reserved_root_names` through. `prune` rewritten: walks galleries via `Gallery.walk()`, removes only cache-tracked orphan files, then rmdirs empty ancestor dirs upward, stopping at `output` and reserved top-levels (`gallery/`, `assets/`). Untracked dirs/files left alone. Tests rewritten in `tests/test_cache.py` (12 pass).
4. **Image processor** — done. Builder `_process_images` no longer asserts `output_full is not None`; it passes `media.output_full` through (which is `None` for direct-served formats in tree mode). `_image_worker` skips `generate_full` when full is `None`. Module docstring documents GPS-stays for direct-served originals (we only strip on the HEIC/TIFF JPEG derivative). New worker gate tests in `tests/test_image_processor.py`.
5. **Builder** — done. `GalleryBuilder.build_tree()` full-build entrypoint: `scanner.scan_tree()` → DFS-walk root → cache prune over `Gallery.walk()` → `copy_assets()` → image+video pools collected across the whole tree → `render_gallery()` once per non-empty gallery (root included). `build_all()` aliases `build_tree()`. Tests in `tests/test_builder_tree.py` (9 cases).
6. **Renderer + templates** — done. `Renderer.render_gallery` is now the only page entrypoint (root + nested both use `gallery.html.j2`). `render_index` / `_index_entry` / `index.html.j2` removed. New `_breadcrumbs.html.j2` partial driven by renderer-prepared `breadcrumbs` ctx (each entry `{name, href}`; the last entry has `href=None` and renders as `<span aria-current="page">`). Subgallery cards inlined above the media grid in `gallery.html.j2`: cover thumb if `sg.cover_file` exists, otherwise text-only (`subgallery-card--text` class for substep 10.7 styling); each card shows `count` own items plus `subcount` direct subgalleries. Lightbox `data-src` resolves to `media.output_full` (JPEG derivative) when a transcode happened, otherwise to `web_root / media.original_rel` relative to `page_dir` so browser-friendly originals are served directly. `data-original` is emitted on every figure (image + video) so the upcoming download button has something to grab. Builder `_build` legacy flat path deleted; `build_galleries(names, rebuild_index)` retains its signature for the watcher but routes to `build_tree()` until substep 10.8 reintroduces per-dir dirty propagation. Tests rewritten in `tests/test_renderer.py` (13 tree-mode cases). Suite: 115 pass, 1 skip (no-EXIF sample); the two pre-Step-10 sample-data flakes were green this run.

Goal recap:
- Single mount: `/web`. User originals at `/web/<gallery_subdir>/` (default `gallery/`). Output (HTML + assets + thumbs + transcoded derivatives) at `/web/`.
- We own `/web/` root. User content outside `<gallery_subdir>/` = user error (skipped/ignored).
- Browser-friendly formats (jpg/jpeg/png/webp/gif/avif) → reference original directly as `data-src`; no full-size duplicate.
- HEIC/HEIF/TIFF → generate JPEG derivative for inline view, keep original downloadable via lightbox download button.
- Galleries nest arbitrarily. Each dir = its own page. Page layout: breadcrumbs → subgallery cards (own count + non-recursive subcount) → media grid. Empty galleries (no own media + no non-empty subs) skipped. Galleries with subs but no own media render text-only (no cover thumb).
- Reserved names at source root: `<gallery_subdir>`, `assets`, `index.html` — skip + warn on collision.

Decisions locked:
1. Cover for gallery with no own images: text only (no recursive cover).
2. Breadcrumbs: yes, on every gallery page.
3. Empty galleries: skip.
4. Subgallery card shows own media count + non-recursive subgallery count.
5. We own `/web/` root; user-supplied content lives only inside `<gallery_subdir>/`.

Next substep: **Frontend (10.7)** — wire the lightbox download button to the new `data-original` attribute (anchor with `download` attr). Style the new subgallery card grid (`.subgallery-grid`, `.subgallery-card`, `.subgallery-card--text`) and the breadcrumb nav (`nav.breadcrumbs > ol > li`). The renderer already emits `data-original` on every figure (image + video) and a `subgallery-card--text` class when there is no cover thumb, so this is purely CSS + a small JS addition to the lightbox. Update `tests/test_frontend_assets.py` if we add new selectors worth pinning.

Order of attack:
1. ~~Config (env + dataclass).~~ done
2. ~~Scanner (recursive, new `Gallery` shape, reserved names, transcode_needed flag on `MediaFile`).~~ done
3. ~~Cache (path-keyed verified; recursive-aware prune; reserved roots).~~ done
4. ~~Image processor (skip `generate_full` when not transcode_needed).~~ done
5. ~~Builder (DFS walk).~~ done
6. ~~Renderer + templates (breadcrumbs, subgallery cards, original href, download data, drop separate index template).~~ done
7. Frontend (download button + subgallery + breadcrumb styling).
8. Watcher (per-dir dirty propagation under new layout).
9. CLI/`__main__` (drop legacy `--source`/`--output`).
10. docker-compose.yml.
11. Tests rewritten.
12. Smoke build over nested sample tree.

Per substep: update TODO.md + NEXT.md + commit.

How to reproduce so far:
- Build: `docker compose build app`
- Tests: `docker compose run --rm test` (115 pass, 1 skip)
- Smoke (current pre-Step-10 layout): `docker compose run --rm app -v` (will be replaced with `/web` layout in Step 10).
