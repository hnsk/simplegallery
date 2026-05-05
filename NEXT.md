# NEXT

Step 10 begins — restructure to `/web` web-root layout with originals served directly + recursive galleries.

Goal recap:
- Single mount: `/web`. User originals at `/web/<gallery_subdir>/` (default `gallery/`). Output (HTML + assets + thumbs + transcoded derivatives) at `/web/`.
- We own `/web/` root. User content outside `<gallery_subdir>/` = user error (skipped/ignored).
- Browser-friendly formats (jpg/jpeg/png/webp/gif/avif) → reference original directly as `data-src`; no full-size duplicate.
- HEIC/HEIF/TIFF → generate JPEG derivative for inline view, keep original downloadable via lightbox download button.
- Galleries nest arbitrarily. Each dir = its own page. Page layout: breadcrumbs → subgallery cards (own count + non-recursive subcount) → media grid. Empty galleries (no own media + no non-empty subs) skipped. Galleries with subs but no own media render text-only (no cover thumb).
- Reserved names at source root: `<gallery_subdir>`, `assets`, `index.html` — skip + warn on collision.

Decisions locked in this conversation:
1. Cover for gallery with no own images: text only (no recursive cover).
2. Breadcrumbs: yes, on every gallery page.
3. Empty galleries: skip.
4. Subgallery card shows own media count + non-recursive subgallery count.
5. We own `/web/` root; user-supplied content lives only inside `<gallery_subdir>/`.

First substep: **Config + Scanner refactor** (recursive `Gallery` model with `rel_path`, `breadcrumbs`, `subgalleries`; reserved-name handling; `web_root`/`gallery_subdir`).

Order of attack:
1. Config (env + dataclass).
2. Scanner (recursive, new `Gallery` shape, reserved names, transcode_needed flag on `MediaFile`).
3. Cache (verify path-keyed still works; prune across nested output).
4. Image processor (skip `generate_full` when not transcode_needed).
5. Builder (DFS walk).
6. Renderer + templates (breadcrumbs, subgallery cards, original href, download button; drop separate index template).
7. Frontend (download button + subgallery + breadcrumb styling).
8. Watcher (per-dir dirty propagation under new layout).
9. CLI/`__main__` (`--web`, `--gallery-subdir`).
10. docker-compose.yml.
11. Tests rewritten.
12. Smoke build over nested sample tree.

Per substep: update TODO.md + NEXT.md + commit.

How to reproduce so far:
- Build: `docker compose build app`
- Tests: `docker compose run --rm test`
- Smoke (current pre-Step-10 layout): `docker compose run --rm app -v` (will be replaced with `/web` layout in Step 10).
