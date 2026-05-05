# NEXT

Full-resolution RAW landed. Step 17 (camera RAW support) + Step 16 (CI + slim
runtime image) + Step 11 mobile-viewport carry-over already closed.

## What landed this batch

- `_DCRAW_EMU_ARGS` dropped `-h` (half-size demosaic). RAW JPEG derivatives
  now carry the sensor's full pixel count: Nikon D800 7378×4924 (~36 MP),
  Sony A7R II 7968×5320 (~42 MP), Fuji X100S 4934×3296, Canon 1D Mk IV
  4916×3272. Derivative file sizes grew correspondingly (e.g. A7R II
  3.3 MB → 12 MB).
- Decode cost: per-file ~3.5× slower than half-size (4 RAW at workers=4:
  ~7 s vs ~2 s wall clock; full pipeline incl. EXIF + render: ~38 s vs
  ~2 s when nothing else needs work). Below the predicted ~10× because the
  TIFF write + JPEG re-encode dominate over libraw's demosaic step.
- Module docstring + `_DCRAW_EMU_ARGS` comment reworded to reflect full-res
  intent. No API or config surface changes.
- Tests unchanged (no dim assertions in the RAW fixture cases — they only
  check thumb shape, JPEG output, and GPS strip). Suite: 129 pass, 1 skip.
- Smoke: re-ran `docker compose run --rm app -v` over `./web/gallery/raws/`
  against a freshly rebuilt `simplegallery:runtime`; verified pixel dims via
  `identify` on the four `web/raws/full/*.jpg` outputs.

## Earlier batch — Step 17 (camera RAW support)

- `RAW_IMAGE_EXTENSIONS` module constant in `config.py` covering all common
  camera RAW containers (NEF, NRW, CR2, CR3, CRW, ARW, SRF, SR2, RAF, ORF,
  RW2, PEF, PTX, SRW, DNG, RWL, 3FR, IIQ, X3F, DCR, KDC, MRW, MEF, ERF,
  RAW). Merged into `Config.image_extensions` default; intentionally absent
  from `direct_image_extensions` so the scanner flags `transcode_needed=True`
  — RAWs go through the same JPEG-derivative path as HEIC, with the original
  kept under `<gallery_subdir>/` for download.
- `image_processor._open_image()` context manager dispatches RAW reads
  through `dcraw_emu -T -w -Z -` (libraw-tools): full-resolution, white-
  balanced sRGB TIFF on stdout, parsed by wand as a TIFF blob. Non-RAW
  formats stay on the existing `Image(filename=…)` path. EXIF for RAW skips
  wand (no IM decoder) and goes through `exifread`, which reads the TIFF
  tags off the RAW container.
- Dockerfile `base` adds `libraw libraw-tools` (~2.7 MiB). Alpine has no
  `dcraw` package and no IM RAW coder; the libraw CLI is the lightest path
  that actually decodes NEF/CR2/ARW/RAF/etc.
- `tests/test_image_processor.py` parametrized `raw_sample` fixture (NEF /
  CR2 / ARW / RAF) covers thumbnail decode, full → JPEG, and GPS strip.

## Why dcraw_emu rather than format-hint or `dcraw` (Step 17 background)

The first attempt forced `FORMAT:path` so IM would dispatch the correct
coder for TIFF-magic-mimicking RAW containers (NEF/CR2/ARW/DNG). That fixed
the wrong-coder problem but exposed a deeper one: Alpine's IM build advertises
`raw` in DELEGATES yet ships no actual camera-RAW coder (only `raw.so` for
raw RGB samples). Result: every RAW format failed with `MissingDelegateError`.
Alpine has no `dcraw` package either; only `libraw-tools` (~187 KiB) provides
`dcraw_emu`. Shelling out to it returns a TIFF blob wand reads natively, no
delegate XML or coder shim required.

## Next batch

Repo is feature-complete for the original scope plus full-res RAW. Open
candidates if a new batch is desired:

1. **Publish** — push to `github.com/hnsk/simplegallery`, tag `v0.1.0`,
   `python -m build` + `twine upload` to PyPI (image already production-
   shaped). Requires user to provide remote + PyPI creds.
2. **GHCR image publish** — extend CI workflow to also build + push
   `simplegallery:runtime` to `ghcr.io/hnsk/simplegallery` on tag.
3. **Sample-data CI tests** — gate the currently-skipped EXIF/HEIC/RAW
   cases behind a CI fixture pack (committed under `tests/fixtures/` or
   fetched at job start).
4. **Mobile viewport verify** — Step 11 carry-over (Chrome DevTools swipe +
   EXIF slide-up sheet). Manual browser check, not yet performed.

## How to reproduce

- Build runtime: `docker compose build app`
- Build dev (test/shell): `docker compose --profile dev build test`
- Tests: `docker compose run --rm test`
- Smoke: `docker compose run --rm app -v`
- Browse: `docker compose --profile dev up -d serve` → http://127.0.0.1:8080/
- CI locally: `act -j test` (or push to a branch and let GitHub run it).

---

## Earlier context (kept for reference)

Step 16 (CI + slim runtime image) landed. `.github/workflows/test.yml` runs
`docker compose --profile dev build test` + `docker compose run --rm test`
on push/PR. Dockerfile split into `base` → `builder` → `runtime` / `dev`;
runtime image 200 MB (was 493 MB), dev 505 MB. `MAGICK_HOME=/usr` +
unversioned `libMagick{Wand,Core}-7.Q16HDRI.so` symlinks needed because musl
`ctypes.util.find_library` returns `None` without gcc.

Step 15 (sort UI + compact HTML) — `Gallery.mtime` recursive max-mtime.
Renderer uses `trim_blocks=True, lstrip_blocks=True`; templates compact. New
`<aside class="gallery-controls">` per page with `Sort by [name|date]` +
`Order [asc|desc]`; defaults `name asc`. `data-name` + `data-mtime` (epoch
seconds) on figures + subgallery cards.

Step 13 (shareable lightbox links) — every figure carries `id="m-{slug}"` +
`data-slug`; thumb sits inside `<a class="gallery-link" href="…">`. Lightbox
drives `location.hash`; deep links `…/page#m-slug` auto-open and back-button
closes.

Step 11 HEIC + multi-worker flake resolved via `docker/imagemagick-policy.xml`
— removed bogus `time` policy line + dropped IM thread count to 1 (process
pool already provides parallelism).
