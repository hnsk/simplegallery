"""CLI argument parsing for simplegallery."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .config import Config


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="simplegallery",
        description="Generate a static gallery site from photos and videos.",
    )
    parser.add_argument("--source", type=Path, help="Source directory of media subfolders.")
    parser.add_argument("--output", type=Path, help="Output directory for generated site.")
    parser.add_argument("--title", help="Site title.")
    parser.add_argument(
        "--watch",
        action="store_true",
        default=None,
        help="Watch source for changes and rebuild incrementally.",
    )
    parser.add_argument("--workers", type=int, help="Worker thread count for media processing.")
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase log verbosity (-v=INFO, -vv=DEBUG).",
    )
    return parser


def apply_args(config: Config, args: argparse.Namespace) -> Config:
    """Layer CLI overrides onto an env-derived Config."""
    if args.source is not None:
        config.source = args.source
    if args.output is not None:
        config.output = args.output
    if args.title is not None:
        config.title = args.title
    if args.watch is not None:
        config.watch = bool(args.watch)
    if args.workers is not None:
        config.workers = args.workers
    if args.verbose:
        config.log_level = logging.DEBUG if args.verbose >= 2 else logging.INFO
    return config


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    return build_parser().parse_args(argv)
