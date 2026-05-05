"""Step 1 smoke tests: package imports + CLI parses."""

from __future__ import annotations

import logging

from simplegallery import __version__
from simplegallery.cli import apply_args, parse_args
from simplegallery.config import Config


def test_version_present() -> None:
    assert __version__


def test_cli_overrides_config() -> None:
    ns = parse_args(
        [
            "--source",
            "/tmp/s",
            "--output",
            "/tmp/o",
            "--title",
            "Hello",
            "--watch",
            "--workers",
            "8",
            "-vv",
        ]
    )
    cfg = apply_args(Config.from_env(), ns)
    assert str(cfg.source) == "/tmp/s"
    assert str(cfg.output) == "/tmp/o"
    assert cfg.title == "Hello"
    assert cfg.watch is True
    assert cfg.workers == 8
    assert cfg.log_level == logging.DEBUG


def test_default_log_level_info() -> None:
    ns = parse_args([])
    cfg = apply_args(Config.from_env(), ns)
    assert cfg.log_level == logging.INFO
