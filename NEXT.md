# NEXT

Step 10 in progress — `/web` web-root layout with originals served directly + recursive galleries.

Completed substeps:
1. **Config** — done. `Config(web_root, gallery_subdir)`; `source`/`output` derived. Env: `SIMPLEGALLERY_WEB`, `SIMPLEGALLERY_GALLERY_SUBDIR`. CLI: `--web`, `--gallery-subdir` added; legacy `--source`/`--output` kept transitionally. Reserved-name set + `direct_image_extensions` introduced. Tests in `tests/test_config.py`.
2. **Scanner** — done. New `DirectoryScanner.scan_tree()` returns recursive root `Gallery` (or `None`). `Gallery` gains `subgalleries`/`rel_path`/`breadcrumbs`/`subcount`/`walk()`. Reserved root-level names skipped + warned only at depth 0. Empty branches pruned. `MediaFile` gains `transcode_needed` + `original_rel`; tree-mode emits `output_full` only when transcode needed (HEIC/TIFF). Legacy flat `scan()` still works for builder/renderer/watcher until their substeps. Tests in `tests/test_scanner_tree.py` (15 cases).
3. **Cache** — done. `BuildCache(output, reserved_root_names=...)`; builder threads `Config.reserved_root_names` through. `prune` rewritten: walks galleries via `Gallery.walk()`, removes only cache-tracked orphan files, then rmdirs empty ancestor dirs upward, stopping at `output` and reserved top-levels (`gallery/`, `assets/`). Untracked dirs/files left alone. Tests rewritten in `tests/test_cache.py` (12 pass): nested-layout prune, untracked-orphan preservation, reserved-root collapse guard, shared-output protection.
4. **Image processor** — done. Builder `_process_images` no longer asserts `output_full is not None`; it passes `media.output_full` through (which is `None` for direct-served formats in tree mode). `_image_worker` skips `generate_full` when full is `None` — the original is referenced as `data-src` instead. Legacy flat scan still emits `output_full` for every image so existing renderer/builder/watcher tests keep passing during transition. `image_processor` module docstring documents GPS-stays for direct-served originals (we only strip on the HEIC/TIFF JPEG derivative). New worker gate tests in `tests/test_image_processor.py`. Suite: 97 pass; 2 pre-existing sample-data flakes (`129679.jpg` time-limit, `shelf-christmas-decoration.heic`).
5. **Builder** — done. `GalleryBuilder.build_tree()` is the new full-build entrypoint: `scanner.scan_tree()` → DFS-walk root → cache prune over `Gallery.walk()` → `copy_assets()` → image+video pools collected across the whole tree → `render_gallery()` once per non-empty gallery (root included). `build_all()` aliases `build_tree()`; the legacy `_build()` flat path stays alive only behind `build_galleries(names, …)` for the watcher until substep 10.8 migrates it. Empty trees still copy assets and prune so output is well-formed. Renderer/templates remain on the legacy shape; root currently renders through the existing `gallery.html.j2` (self-link back, empty grid for media-less roots) — that's fine; substep 10.6 rewrites the templates next. Tests: new `tests/test_builder_tree.py` (9 cases) and `test_renderer.py::test_builder_build_all_renders_index_and_each_gallery` updated to expect tree-mode `Trip A/index.html` paths. Suite: 106 pass; same 2 pre-existing sample-data flakes.

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

Next substep: **Renderer + templates (10.6)** — rewrite `gallery.html.j2` to be the single page template (root uses it too; drop `index.html.j2` and `Renderer.render_index`/`_index_entry`). Add a `_breadcrumbs.html.j2` partial driven by `gallery.breadcrumbs` (each ancestor link relative to current page_dir). Subgallery card grid above the media grid: cover thumb if `gallery.cover_file` (recursive cover when own gallery has no own media: per locked decision 1, skip — text-only); show `count` own + `subcount` non-recursive. Lightbox `data-src` becomes derivative-or-original — when `media.output_full is None` it points at `media.original_rel` (relative to page_dir). `data-original` always points at `media.original_rel` so the download button has something to grab. Renderer needs to compute `media.original_rel`-relative-to-page_dir; `web_root` is `config.output`, original lives at `web_root / original_rel`. Drop `render_index` from public API once template rewrite lands; renderer tests in `tests/test_renderer.py` need partial rewrite (the legacy assertions on `data-src="full/img1.jpg"` for plain jpg become `data-src="../gallery/Trip A/img1.jpg"`-style relative original paths under tree mode). Plan: add new tree-mode renderer tests alongside the legacy ones, then nuke the legacy ones once template lands.

Order of attack:
1. ~~Config (env + dataclass).~~ done
2. ~~Scanner (recursive, new `Gallery` shape, reserved names, transcode_needed flag on `MediaFile`).~~ done
3. ~~Cache (path-keyed verified; recursive-aware prune; reserved roots).~~ done
4. ~~Image processor (skip `generate_full` when not transcode_needed).~~ done
5. ~~Builder (DFS walk).~~ done
6. Renderer + templates (breadcrumbs, subgallery cards, original href, download button; drop separate index template).
7. Frontend (download button + subgallery + breadcrumb styling).
8. Watcher (per-dir dirty propagation under new layout).
9. CLI/`__main__` (drop legacy `--source`/`--output`).
10. docker-compose.yml.
11. Tests rewritten.
12. Smoke build over nested sample tree.

Per substep: update TODO.md + NEXT.md + commit.

How to reproduce so far:
- Build: `docker compose build app`
- Tests: `docker compose run --rm test` (106 pass; 2 known pre-Step-10 sample-data flakes on `129679.jpg` and `shelf-christmas-decoration.heic`)
- Smoke (current pre-Step-10 layout): `docker compose run --rm app -v` (will be replaced with `/web` layout in Step 10).
