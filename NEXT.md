# NEXT

Step 10 in progress — `/web` web-root layout with originals served directly + recursive galleries.

Completed substeps:

1. **Config** — done. `Config(web_root, gallery_subdir)`; `source`/`output` derived. Env: `SIMPLEGALLERY_WEB`, `SIMPLEGALLERY_GALLERY_SUBDIR`. CLI: `--web`, `--gallery-subdir` added; legacy `--source`/`--output` kept transitionally. Reserved-name set + `direct_image_extensions` introduced. Tests in `tests/test_config.py`.
2. **Scanner** — done. New `DirectoryScanner.scan_tree()` returns recursive root `Gallery` (or `None`). `Gallery` gains `subgalleries`/`rel_path`/`breadcrumbs`/`subcount`/`walk()`. Reserved root-level names skipped + warned only at depth 0. Empty branches pruned. `MediaFile` gains `transcode_needed` + `original_rel`; tree-mode emits `output_full` only when transcode needed (HEIC/TIFF). Legacy flat `scan()` still works for builder/renderer/watcher until their substeps. Tests in `tests/test_scanner_tree.py` (15 cases).
3. **Cache** — done. `BuildCache(output, reserved_root_names=...)`; builder threads `Config.reserved_root_names` through. `prune` rewritten: walks galleries via `Gallery.walk()`, removes only cache-tracked orphan files, then rmdirs empty ancestor dirs upward, stopping at `output` and reserved top-levels (`gallery/`, `assets/`). Untracked dirs/files left alone. Tests rewritten in `tests/test_cache.py` (12 pass).
4. **Image processor** — done. Builder `_process_images` no longer asserts `output_full is not None`; it passes `media.output_full` through (which is `None` for direct-served formats in tree mode). `_image_worker` skips `generate_full` when full is `None`. Module docstring documents GPS-stays for direct-served originals (we only strip on the HEIC/TIFF JPEG derivative). New worker gate tests in `tests/test_image_processor.py`.
5. **Builder** — done. `GalleryBuilder.build_tree()` full-build entrypoint: `scanner.scan_tree()` → DFS-walk root → cache prune over `Gallery.walk()` → `copy_assets()` → image+video pools collected across the whole tree → `render_gallery()` once per non-empty gallery (root included). `build_all()` aliases `build_tree()`. Tests in `tests/test_builder_tree.py` (9 cases).
6. **Renderer + templates** — done. `Renderer.render_gallery` is now the only page entrypoint (root + nested both use `gallery.html.j2`). `render_index` / `_index_entry` / `index.html.j2` removed. New `_breadcrumbs.html.j2` partial driven by renderer-prepared `breadcrumbs` ctx. Subgallery cards inlined above the media grid in `gallery.html.j2`. Lightbox `data-src` resolves to `media.output_full` (JPEG derivative) when a transcode happened, otherwise to `web_root / media.original_rel` relative to `page_dir`. `data-original` emitted on every figure. Tests rewritten in `tests/test_renderer.py` (13 tree-mode cases).
7. **Frontend (CSS/JS)** — done. JS: `Lightbox._build()` injects `<a class="lightbox-download" download hidden>↓</a>`. New `_setDownload(item)` populates `href` from `item.original` (read via `figure.dataset.original`) and sets the `download` attr to the basename derived from the URL. CSS: `.breadcrumbs`, `.subgallery-grid`, `.subgallery-card`, `.subgallery-card--text`, `.lightbox-download` added; dead `.index-grid` rules dropped. `tests/test_frontend_assets.py` pins all new selectors.
8. **Watcher** — done. `GalleryEventHandler` now tracks a `dirty_rels: set[str]` of POSIX source-dir rel paths under `config.source` (`""` denotes the root). File events mark the parent dir; dir create/delete mark the dir itself; dir moves mark both endpoints. Hidden components anywhere in the path are filtered. `FlushCallback` simplified to `Callable[[set[str]], None]`; `index_dirty` removed (every dir is its own page now, and ancestor re-render is handled by the builder). `WatcherService._rebuild` calls `builder.build_galleries(dirty_rels)`. Builder gains a real partial path: `_process_images` split into `_process_image_pipeline` (thumb+full, gated by `cache.is_stale`) and `_extract_exif_batch` (EXIF for any rendered image). `build_galleries(dirty_rels)` scans the full tree, scopes media processing to dirty rels and their descendants, and re-renders dirty + every ancestor (so subgallery cards stay in sync). Tests rewritten in `tests/test_watcher.py` (15 cases). Suite: 116 pass, 1 skip, 2 known sample-data HEIC flakes.
9. **CLI / `__main__`** — done. Legacy `--source` / `--output` argparse flags + their `apply_args` branches removed; help text on `--web` now describes the single-mount layout. `__main__.py` wiring unchanged (already routes through `Config.from_env()` + `apply_args`). `tests/test_smoke.py::test_cli_overrides_config` rewritten around `--web` / `--gallery-subdir`. `tests/test_config.py::test_apply_args_no_legacy_source_output` asserts the legacy flags now raise `SystemExit`. Suite: 116 pass, 1 skip, 2 pre-existing HEIC sample-data flakes.
10. **docker-compose.yml** — done. `app` service collapsed to a single `${SIMPLEGALLERY_WEB_DIR:-./web}:/web` rw bind. Dropped `SIMPLEGALLERY_SOURCE` / `SIMPLEGALLERY_OUTPUT` env vars (no longer read by `Config.from_env`); replaced with `SIMPLEGALLERY_WEB=/web` + `SIMPLEGALLERY_GALLERY_SUBDIR=${SIMPLEGALLERY_GALLERY_SUBDIR:-gallery}`. `test` / `shell` services untouched. `docker compose config` parses; `docker compose run --rm test` still 116 pass + sample-data HEIC flakes only.

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

Next substep: **Sample tree (10.11)** — under `./web/gallery/` create a nested example so the next smoke run exercises the full recursive path: `./web/gallery/photos/...`, `./web/gallery/photos/macro/...`, `./web/gallery/videos/...`, plus a root-level `./web/gallery/cover.jpg` to exercise media-at-root. Source: copy/rename from existing `./sample-data/` (already mounted on test/shell, gitignored, 1.6 GB). Goal here is purely to assemble the tree on disk — don't run the build yet (smoke is substep 10.13). Confirm `./web/` is gitignored (it should be already) before copying.

Order of attack:
1. ~~Config (env + dataclass).~~ done
2. ~~Scanner (recursive, new `Gallery` shape, reserved names, transcode_needed flag on `MediaFile`).~~ done
3. ~~Cache (path-keyed verified; recursive-aware prune; reserved roots).~~ done
4. ~~Image processor (skip `generate_full` when not transcode_needed).~~ done
5. ~~Builder (DFS walk).~~ done
6. ~~Renderer + templates (breadcrumbs, subgallery cards, original href, download data, drop separate index template).~~ done
7. ~~Frontend (download button + subgallery + breadcrumb styling).~~ done
8. ~~Watcher (per-dir dirty propagation under new layout).~~ done
9. ~~CLI/`__main__` (drop legacy `--source`/`--output`).~~ done
10. ~~docker-compose.yml.~~ done
11. Tests rewritten.
12. Smoke build over nested sample tree.

Per substep: update TODO.md + NEXT.md + commit.

How to reproduce so far:
- Build: `docker compose build app`
- Tests: `docker compose run --rm test` (116 pass, 1 skip, 2 pre-existing HEIC sample-data flakes on `shelf-christmas-decoration.heic`)
- Smoke (current pre-Step-10 layout): `docker compose run --rm app -v` (will be replaced with `/web` layout in Step 10).
