"""Config + CLI overrides for the web_root layout."""

from __future__ import annotations

from pathlib import Path

import pytest

from simplegallery.cli import apply_args, build_parser
from simplegallery.config import DEFAULT_GALLERY_SUBDIR, RESERVED_ROOT_NAMES, Config


def _parse(argv: list[str]):
    return build_parser().parse_args(argv)


def test_from_env_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in (
        "SIMPLEGALLERY_WEB",
        "SIMPLEGALLERY_GALLERY_SUBDIR",
        "SIMPLEGALLERY_TITLE",
        "SIMPLEGALLERY_WATCH",
        "SIMPLEGALLERY_WORKERS",
        "SIMPLEGALLERY_DEBOUNCE",
        "SIMPLEGALLERY_LOG_LEVEL",
    ):
        monkeypatch.delenv(var, raising=False)

    cfg = Config.from_env()
    assert cfg.web_root == Path("/web")
    assert cfg.gallery_subdir == DEFAULT_GALLERY_SUBDIR
    assert cfg.source == Path("/web") / DEFAULT_GALLERY_SUBDIR
    assert cfg.output == Path("/web")
    assert cfg.title == "Gallery"
    assert cfg.watch is False
    assert cfg.workers == 4


def test_from_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIMPLEGALLERY_WEB", "/srv/site")
    monkeypatch.setenv("SIMPLEGALLERY_GALLERY_SUBDIR", "media")
    monkeypatch.setenv("SIMPLEGALLERY_TITLE", "Mine")
    monkeypatch.setenv("SIMPLEGALLERY_WORKERS", "8")
    monkeypatch.setenv("SIMPLEGALLERY_WATCH", "1")
    monkeypatch.setenv("SIMPLEGALLERY_DEBOUNCE", "0.5")

    cfg = Config.from_env()
    assert cfg.web_root == Path("/srv/site")
    assert cfg.gallery_subdir == "media"
    assert cfg.source == Path("/srv/site/media")
    assert cfg.output == Path("/srv/site")
    assert cfg.title == "Mine"
    assert cfg.watch is True
    assert cfg.workers == 8
    assert cfg.debounce_seconds == 0.5


def test_explicit_source_output_still_supported(tmp_path: Path) -> None:
    src = tmp_path / "src"
    out = tmp_path / "out"
    cfg = Config(source=src, output=out)
    assert cfg.web_root is None
    assert cfg.source == src
    assert cfg.output == out


def test_missing_web_and_paths_raises() -> None:
    with pytest.raises(ValueError):
        Config()


def test_reserved_root_names_includes_gallery_subdir() -> None:
    cfg = Config(web_root=Path("/web"))
    assert cfg.reserved_root_names == RESERVED_ROOT_NAMES | {"gallery"}

    cfg2 = Config(web_root=Path("/web"), gallery_subdir="media")
    assert cfg2.reserved_root_names == RESERVED_ROOT_NAMES | {"media"}


def test_apply_args_web_flag_derives_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SIMPLEGALLERY_WEB", raising=False)
    cfg = Config.from_env()
    args = _parse(["--web", "/tmp/site"])
    apply_args(cfg, args)
    assert cfg.web_root == Path("/tmp/site")
    assert cfg.source == Path("/tmp/site/gallery")
    assert cfg.output == Path("/tmp/site")


def test_apply_args_gallery_subdir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SIMPLEGALLERY_WEB", raising=False)
    cfg = Config.from_env()
    args = _parse(["--web", "/tmp/site", "--gallery-subdir", "pics"])
    apply_args(cfg, args)
    assert cfg.gallery_subdir == "pics"
    assert cfg.source == Path("/tmp/site/pics")


def test_apply_args_legacy_source_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SIMPLEGALLERY_WEB", raising=False)
    cfg = Config.from_env()
    args = _parse(["--source", "/a", "--output", "/b"])
    apply_args(cfg, args)
    assert cfg.source == Path("/a")
    assert cfg.output == Path("/b")
