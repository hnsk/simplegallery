# NEXT

Step 2 — Scanner + cache.

Status:
- Step 0 done.
- Step 1 done. CLI smoke (`docker compose run --rm app --help`) verified.
- Step 7 done early (out of TODO order, user-approved). `simplegallery:dev` image builds; `docker compose run --rm test` passes 3 smoke tests. Test service mounts `src/` + `tests/` so iteration does not need rebuild.

Create:
- `src/simplegallery/slugify.py` — `slugify(name)` → ascii, lowercase, hyphenated, collision-safe.
- `src/simplegallery/scanner.py` — `MediaFile`, `Gallery` dataclasses (incl. `slug`); `DirectoryScanner.scan()` — top-level subdirs only, split image/video by ext, derive output paths via slug, set `cover_file`.
- `src/simplegallery/cache.py` — `BuildCache` — JSON at `<output>/.gallery_cache.json`; `is_stale()` (mtime+size+missing outputs); `mark_done()`; atomic save; prune deleted sources + orphan outputs.
- `tests/test_slugify.py` — ascii/unicode/collision cases.
- `tests/test_scanner.py` — tmp source tree, assert image/video split, slug mapping, cover selection.
- `tests/test_cache.py` — stale detection, prune, atomic save.

How to run during Step 2:
- Tests: `docker compose run --rm test`
- Ad-hoc shell: `docker compose run --rm shell`

After Step 2: update TODO.md + NEXT.md, commit, then Step 3 (renderer + templates).
