# simplegallery

Static photo and video gallery generator. Point it at a directory of media, get a recursive HTML site with thumbnails, lightbox, EXIF, and video transcodes.

- Recursive: every subdirectory becomes its own gallery page with breadcrumbs and subgallery cards.
- Browser-friendly originals (jpg/jpeg/png/webp/gif/avif, mp4/webm) served directly — no re-encode.
- HEIC/HEIF/TIFF and camera RAW (NEF/CR2/CR3/ARW/RAF/DNG/...) transcoded to full-resolution JPEG for inline view; original kept and downloadable from the lightbox.
- Other video containers (mov/m4v/mkv/avi) transcoded to MP4 (H.264) + WebM (VP9).
- Single content-hashed CSS/JS bundle. No client-side framework.
- Lightbox with keyboard nav, swipe, EXIF panel, deep links (`#m-<slug>`), download button.
- Incremental rebuilds via mtime/size cache; optional `--watch` mode rebuilds the affected gallery on filesystem changes.
- All build, test, and ad-hoc tooling runs inside Docker — no host Python required.

## Layout

A single mount, `/web`, owns both inputs and outputs:

```
/web/
├── gallery/                    # user originals (subdir name configurable)
│   ├── cover.jpg
│   ├── photos/
│   │   ├── a.jpg
│   │   └── macro/b.heic
│   ├── raws/d.NEF
│   └── videos/c.mov
├── index.html                  # generated
├── assets/                     # generated (hashed CSS/JS + icons)
├── thumbs/                     # generated thumbnails for root media
├── photos/
│   ├── index.html
│   ├── thumbs/
│   ├── full/                   # JPEG derivatives (HEIC/TIFF/RAW only)
│   └── macro/{index.html,thumbs/,full/}
└── videos/{index.html,thumbs/,video/}
```

Names reserved at the web root: `assets`, `index.html`, and the gallery subdir (default `gallery`). Other content placed at the root will be left alone.

## Usage

### Watch mode (default)

```sh
docker compose up
```

Runs `app` with `--watch -v`: initial full build, then debounced rebuilds on filesystem changes under `/web/gallery/`. Default mount: `./web/` → `/web/` (override with `SIMPLEGALLERY_WEB`).

### One-shot build

```sh
docker compose run --rm app -v
```

### Browse the result

Dev-only services live behind the `dev` profile so `docker compose up` keeps the runtime stack to just `app`:

```sh
docker compose --profile dev up -d serve   # http://127.0.0.1:8080/
docker compose --profile dev stop serve
```

Override the port with `SIMPLEGALLERY_SERVE_PORT`. `docker compose run --rm <svc>` starts a profiled service without activating the profile.

### Tests

```sh
docker compose run --rm test
```

Image and video processor tests need real media at `./sample-data/` (gitignored); they skip when missing.

## Configuration

CLI flags override env vars override defaults.

| Flag | Env | Default | Purpose |
|------|-----|---------|---------|
| `--web` | `SIMPLEGALLERY_WEB` | `/web` | Web root mount |
| `--gallery-subdir` | `SIMPLEGALLERY_GALLERY_SUBDIR` | `gallery` | Source subdir under web root |
| `--title` | `SIMPLEGALLERY_TITLE` | `Gallery` | Site title |
| `--watch` | `SIMPLEGALLERY_WATCH` | `0` | Watch + incremental rebuild |
| `--workers` | `SIMPLEGALLERY_WORKERS` | `4` | Parallel media workers |
| `-v` / `-vv` | `SIMPLEGALLERY_LOG_LEVEL` | `INFO` | Log verbosity |
|  | `SIMPLEGALLERY_DEBOUNCE` | `2.0` | Watch debounce seconds |

`MAGICK_TIME_LIMIT=86400` is set on the `app`/`test`/`shell` services to disable ImageMagick's per-image deadline.

## Privacy

`generate_full` strips EXIF GPS tags from the JPEG derivatives it produces (HEIC/HEIF/TIFF, camera RAW). Browser-friendly originals (jpg/png/webp/gif/avif) are served directly from `<gallery_subdir>/` and **retain any GPS tags** they carry; the original RAW/HEIC/TIFF files remain downloadable from the lightbox and are likewise unmodified. Strip GPS upstream if that matters for the source set.

## License

MIT — see [LICENSE](LICENSE).
