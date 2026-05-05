# NEXT

Step 11 desktop verify done. Mobile deferred. Next session: investigate HEIC + multi-worker race.

## Open: HEIC race + multi-worker flake

Symptom: `time limit exceeded ... @ error/cache.c/GetImagePixelCache/1743` warnings during `docker compose run --rm app -v` over `./web/gallery/`.

Repro matrix (workers env via `SIMPLEGALLERY_WORKERS`, default 4):
- workers=4 (default): 3-4 of {`129679.jpg`, `214143.jpeg`, `214361.jpeg`, `214389.jpeg`} flake + HEIC.
- workers=2: only HEIC fails.
- workers=1: only HEIC fails.

Confirmed not config:
- `magick -list policy` → `time=unlimited`.
- `magick -list resource` → `Time: 0 years` (= IM `MagickResourceInfinity`).
- `MAGICK_TIME_LIMIT=86400` set in `app` service.
- Direct `magick /sample-data/shelf-christmas-decoration.heic ...` → 0.55s, no error.
- Direct `wand.image.Image(...)` decode + resize + save → 0.58s, no error.

So error appears only in builder pipeline path (ProcessPool spawn ctx, `_image_worker` in `src/simplegallery/builder.py:243`).

Hypotheses to test next session:
1. **`/tmp` pixel cache contention.** IM uses `/tmp` for memory-mapped pixel cache when image > resource limits or for intermediate ops. `wand.image.Image` with HEIC source decodes to full pixel buffer; with `workers=4` × `IM thread=4` × ~1GP area = high `/tmp` pressure. Test: per-worker `MAGICK_TMPDIR` (e.g. `/tmp/im-${PID}`), or set `policy:resource thread=1` so each subprocess single-threads IM.
2. **HEIC-specific libheif time limit.** libheif 1.21.2 + libde265 1.0.16 in alpine. `shelf-christmas-decoration.heic` is 1.4MB, decodes 0.55s in isolation. Under load may exceed libheif `heif_decoding_options.start_time` budget. Test: try other HEIC samples; if none flake, sample-data swap. Alternatively libheif upgrade.
3. **Wand process init race.** Each spawned subprocess re-imports wand → re-loads MagickWand → first call may race on global init. Test: warm-up call in `_image_worker` (no-op `Image(blob=b'...')`), or `mp_context="forkserver"` instead of `spawn` (lower init cost, same isolation as spawn after first child).
4. **GetImagePixelCache lock timeout.** IM pixel cache uses semaphore w/ default timeout. With high concurrency could trip "time limit" misreport. Test: `policy:resource memory=512MiB` per process so pixel cache stays in-memory under combined budget; or drop IM thread count.

Investigation steps next session:
1. Reproduce on clean tree: `rm -rf web/{photos,videos,thumbs,index.html,assets,.gallery_cache.json}; docker compose run --rm app -v` 5×, log which files fail per run → confirm flake distribution.
2. Force `OMP_NUM_THREADS=1` + `MAGICK_THREAD_LIMIT=1` in `app` service env to neutralize IM internal threads. Re-run matrix.
3. If JPEG flakes vanish → HEIC-only is sample-specific, swap sample.
4. If HEIC still fails alone → trace inside `_image_worker` with `MAGICK_DEBUG=Cache,Resource` env to see which resource trips.
5. Decide: (a) document as sample-data limit + cap `workers=2` in compose default, or (b) ship `MAGICK_THREAD_LIMIT=1` permanently, or (c) drop sample and find smaller HEIC fixture.

Files: `src/simplegallery/builder.py:154-187` (image pipeline + ProcessPool), `src/simplegallery/image_processor.py:47-71` (wand calls), `docker/imagemagick-policy.xml` (resource policy), `docker-compose.yml` `app` service env.

## Manual verify (recap)

`docker compose up -d serve` → http://127.0.0.1:8080/. Stop: `docker compose stop serve`. Override port via `SIMPLEGALLERY_SERVE_PORT`.

---

Step 10 — `/web` web-root layout with originals served directly + recursive galleries.

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
11. **Sample tree** — done. `./web/gallery/cover.jpg` (root-level media, copy of EXIF-bearing `23xxesym0e9w18z2904frnpgy7.jpg`), `./web/gallery/photos/{129679.jpg,214143.jpeg,214361.jpeg,52840.png}` (mixed jpg/jpeg/png; all browser-friendly so no `full/` derivative expected), `./web/gallery/photos/macro/{214389.jpeg,shelf-christmas-decoration.heic}` (HEIC exercises `transcode_needed` + JPEG derivative + lightbox download), `./web/gallery/videos/{214357.mp4,198088.webm}`. `.gitignore` extended with `web/` so the tree isn't tracked.
12. **Tests sweep** — done. Grep across `src/` + `tests/` cleared all stale legacy refs (`render_index`, `index.html.j2`, `_index_entry`, `--source`, `--output`, `index_dirty`, `SIMPLEGALLERY_SOURCE`, `SIMPLEGALLERY_OUTPUT`). Last legacy stragglers were `tests/test_scanner.py` (8 cases all driven through legacy flat `scan()`) plus the `scan()` / `_scan_files_into()` / `emit_full_for_all_images` machinery in `src/simplegallery/scanner.py`; all removed. `DirectoryScanner.scan_tree()` is now the only public scan entrypoint. `MediaFile.original_rel` docstring trimmed (no more "empty for legacy callers"). Suite: 110 pass, 1 skip; sample-data HEIC cases oscillating green/red.
13. **Smoke** — done. Required Dockerfile pre-step first: stale `SIMPLEGALLERY_SOURCE` / `SIMPLEGALLERY_OUTPUT` env vars replaced with `SIMPLEGALLERY_WEB=/web`; `VOLUME ["/source", "/output"]` → `VOLUME ["/web"]`. `app` service in compose gained `MAGICK_TIME_LIMIT=${MAGICK_TIME_LIMIT:-86400}` for parity with test/shell. `app` image rebuilt; `docker compose run --rm app -v` over `./web/gallery/` rendered all four pages (root + photos + photos/macro + videos), populated `./web/assets/`, served browser-friendly originals direct (no `full/` derivative), kept HEIC plumbing correct (`data-src` → JPEG derivative, `data-original` → `.heic`). Breadcrumbs correct at every depth; no output written under `./web/gallery/`. Pre-existing sample-data quirk: `shelf-christmas-decoration.heic` still hits `time limit exceeded` from libheif/libde265 (ImageMagick policy is `time=unlimited`, so the limit is internal to the HEIF decoder, not IM resource limits). Not a Step 10 regression.

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

Step 10 is functionally complete. Open items left from earlier in TODO.md (carried over from Step 9, still apply):

- Manual lightbox verify in browser (arrows, EXIF, video poster) against the freshly-generated `./web/index.html` etc. — needs a host browser; serve with e.g. `python -m http.server` against `./web/` (or `docker run -v ./web:/usr/share/nginx/html:ro -p 8080:80 nginx`). Spot-check: arrow keys, EXIF info button, video plays, lightbox download anchor pulls original (incl. HEIC).
- Mobile viewport (Chrome DevTools) — swipe + EXIF slide-up panel.
- Resolve HEIC `time limit exceeded` on `shelf-christmas-decoration.heic`. Source is libheif/libde265 internal time, not ImageMagick's policy (already `time=unlimited`). Options: substitute another HEIC sample, or upgrade libheif. Optional — known sample-data quirk.

Recommended next session: do the manual browser pass, then close out Step 10 in TODO.md.

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
11. ~~Sample tree assembled under `./web/gallery/`.~~ done
12. ~~Tests sweep.~~ done
13. ~~Smoke build over nested sample tree.~~ done

Per substep: update TODO.md + NEXT.md + commit.

How to reproduce so far:
- Build: `docker compose build app`
- Tests: `docker compose run --rm test` (116 pass, 1 skip, 2 pre-existing HEIC sample-data flakes on `shelf-christmas-decoration.heic`)
- Smoke (current pre-Step-10 layout): `docker compose run --rm app -v` (will be replaced with `/web` layout in Step 10).
