"""simplegallery entry point."""

from __future__ import annotations

import logging
import sys

from .cli import apply_args, parse_args
from .config import Config

log = logging.getLogger("simplegallery")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = apply_args(Config.from_env(), args)
    logging.basicConfig(
        level=config.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    log.debug("config: %s", config)

    if config.watch:
        return _run_watcher(config)
    return _run_build(config)


def _run_build(config: Config) -> int:
    try:
        from .builder import GalleryBuilder
    except ImportError:
        log.error("builder not yet implemented (Step 3)")
        return 2
    GalleryBuilder(config).build_all()
    return 0


def _run_watcher(config: Config) -> int:
    try:
        from .watcher import WatcherService
    except ImportError:
        log.error("watcher not yet implemented (Step 8)")
        return 2
    WatcherService(config).start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
