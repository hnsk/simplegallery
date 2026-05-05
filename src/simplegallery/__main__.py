"""simplegallery entry point."""

from __future__ import annotations

import logging
import sys

from .builder import GalleryBuilder
from .cli import apply_args, build_parser
from .config import Config
from .watcher import WatcherService

log = logging.getLogger("simplegallery")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = apply_args(Config.from_env(), args)
    logging.basicConfig(
        level=config.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        stream=sys.stdout,
    )
    log.debug("config: %s", config)

    if config.watch:
        WatcherService(config).start()
        return 0
    GalleryBuilder(config).build_all()
    return 0


if __name__ == "__main__":
    sys.exit(main())
