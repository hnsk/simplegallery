"""Filesystem watcher: rebuild affected galleries on source changes.

Dirty unit is the POSIX source-dir rel path under ``config.source`` of the
changed file/dir. A file event marks the file's parent dir; a dir event marks
the dir itself. ``""`` denotes the source root. Builder ancestor propagation
is responsible for re-rendering parent pages — the handler only emits leaves.
"""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable

from watchdog.events import (
    EVENT_TYPE_CLOSED_NO_WRITE,
    EVENT_TYPE_OPENED,
    DirCreatedEvent,
    DirDeletedEvent,
    DirMovedEvent,
    FileSystemEvent,
    FileSystemEventHandler,
)
from watchdog.observers import Observer

_IGNORED_EVENT_TYPES = frozenset({EVENT_TYPE_OPENED, EVENT_TYPE_CLOSED_NO_WRITE})

from .builder import GalleryBuilder
from .config import Config

log = logging.getLogger(__name__)


FlushCallback = Callable[[set[str]], None]


class GalleryEventHandler(FileSystemEventHandler):
    """Translate watchdog events into a debounced dirty-rels flush."""

    def __init__(
        self,
        source: Path,
        debounce_seconds: float,
        on_flush: FlushCallback,
    ) -> None:
        super().__init__()
        try:
            self.source = source.resolve()
        except OSError:
            self.source = source
        self.debounce_seconds = max(0.0, float(debounce_seconds))
        self._on_flush = on_flush
        self._lock = threading.Lock()
        self._dirty_rels: set[str] = set()
        self._timer: threading.Timer | None = None

    # --- watchdog hook --------------------------------------------------

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.event_type in _IGNORED_EVENT_TYPES:
            return
        is_dir = isinstance(event, (DirCreatedEvent, DirDeletedEvent, DirMovedEvent))
        rels: set[str] = set()

        src_rel = self._rel_for_event(getattr(event, "src_path", None), is_dir_event=is_dir)
        if src_rel is not None:
            rels.add(src_rel)

        dest_path = getattr(event, "dest_path", None)
        if dest_path and isinstance(event, DirMovedEvent):
            dest_rel = self._rel_for_event(dest_path, is_dir_event=True)
            if dest_rel is not None:
                rels.add(dest_rel)

        if not rels:
            return

        with self._lock:
            self._dirty_rels.update(rels)
            self._reset_timer_locked()

    # --- internals ------------------------------------------------------

    def _rel_for_event(self, raw: str | None, *, is_dir_event: bool) -> str | None:
        """POSIX rel path of the source-dir whose page is affected.

        For a file event: parent dir relative to ``source``.
        For a dir event: the dir itself relative to ``source``.

        Returns ``None`` for events outside ``source`` or under any hidden
        component (path part starting with ``.``).
        """
        if not raw:
            return None
        path = Path(raw)
        try:
            resolved = path.resolve()
            rel = resolved.relative_to(self.source)
        except (ValueError, OSError):
            try:
                rel = path.relative_to(self.source)
            except ValueError:
                return None
        parts = rel.parts
        if not parts:
            # Event on source root itself — treat as root dir change.
            return "" if is_dir_event else None
        if any(p.startswith(".") for p in parts):
            return None
        dir_parts = parts if is_dir_event else parts[:-1]
        return "/".join(dir_parts)

    def _reset_timer_locked(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        if self.debounce_seconds <= 0:
            # fire after releasing lock
            threading.Thread(target=self._fire, daemon=True).start()
            return
        self._timer = threading.Timer(self.debounce_seconds, self._fire)
        self._timer.daemon = True
        self._timer.start()

    def _fire(self) -> None:
        with self._lock:
            rels = self._dirty_rels
            self._dirty_rels = set()
            self._timer = None
        if not rels:
            return
        try:
            self._on_flush(rels)
        except Exception:
            log.exception("rebuild callback failed")

    # --- test helpers ---------------------------------------------------

    def flush_now(self) -> None:
        """Cancel pending timer and fire immediately. Test-only."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
        self._fire()

    @property
    def pending(self) -> set[str]:
        with self._lock:
            return set(self._dirty_rels)


class WatcherService:
    """Run an initial build, then watch source for changes and rebuild."""

    def __init__(
        self,
        config: Config,
        builder: GalleryBuilder | None = None,
    ) -> None:
        self.config = config
        self.builder = builder or GalleryBuilder(config)
        self.handler = GalleryEventHandler(
            source=config.source,
            debounce_seconds=config.debounce_seconds,
            on_flush=self._rebuild,
        )
        self._observer: Observer | None = None

    def start(self) -> None:
        log.info("initial build")
        self.builder.build_all()
        observer = Observer()
        observer.schedule(self.handler, str(self.config.source), recursive=True)
        observer.start()
        self._observer = observer
        log.info(
            "watching %s (debounce=%.2fs)",
            self.config.source,
            self.config.debounce_seconds,
        )
        try:
            observer.join()
        except KeyboardInterrupt:
            self.stop()

    def stop(self) -> None:
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None

    def _rebuild(self, dirty_rels: set[str]) -> None:
        log.info("rebuild triggered: dirty=%s", sorted(dirty_rels) or "[]")
        self.builder.build_all(dirty_rels)
