# NEXT

Step 2 — Scanner + cache.

Create:
- `src/simplegallery/slugify.py` — `slugify(name)` → ascii, lowercase, hyphenated, collision-safe.
- `src/simplegallery/scanner.py` — `MediaFile`, `Gallery` dataclasses (incl. `slug`); `DirectoryScanner.scan()` — top-level subdirs only, split image/video by ext, derive output paths via slug, set `cover_file`.
- `src/simplegallery/cache.py` — `BuildCache` — JSON at `<output>/.gallery_cache.json`; `is_stale()` (mtime+size+missing outputs); `mark_done()`; atomic save; prune deleted sources + orphan outputs.
- `tests/test_slugify.py` — ascii/unicode/collision cases.
- `tests/test_scanner.py` — tmp source tree, assert image/video split, slug mapping, cover selection.
- `tests/test_cache.py` — stale detection, prune, atomic save.

Constraints:
- No host Python. Tests must wait for Step 7 Docker, or add a temporary `shell`/`test` service early if validation needed sooner — ask user before adding.
- After Step 2: update TODO.md + NEXT.md, commit, then Step 3 (renderer + templates).

Status of Step 1: complete. `pyproject.toml`, `src/simplegallery/{__init__,config,cli,__main__}.py` written. Not yet executed (host run forbidden by CLAUDE.md).
