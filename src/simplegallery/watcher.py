"""Filesystem watcher: rebuild affected galleries on source changes."""

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


FlushCallback = Callable[[set[str], bool], None]


class GalleryEventHandler(FileSystemEventHandler):
    """Translate watchdog events into a debounced (dirty-names, index-dirty) flush."""

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
        self._dirty_names: set[str] = set()
        self._index_dirty = False
        self._timer: threading.Timer | None = None

    # --- watchdog hook --------------------------------------------------

    def on_any_event(self, event: FileSystemEvent) -> None:
        if event.event_type in _IGNORED_EVENT_TYPES:
            return
        names: set[str] = set()
        index_change = False

        top, is_top = self._top_level(getattr(event, "src_path", None))
        if top is not None:
            names.add(top)
            if is_top and isinstance(
                event, (DirCreatedEvent, DirDeletedEvent, DirMovedEvent)
            ):
                index_change = True

        dest = getattr(event, "dest_path", None)
        if dest:
            dtop, dis_top = self._top_level(dest)
            if dtop is not None:
                names.add(dtop)
                if dis_top and isinstance(event, DirMovedEvent):
                    index_change = True

        if not names and not index_change:
            return

        with self._lock:
            self._dirty_names.update(names)
            if index_change:
                self._index_dirty = True
            self._reset_timer_locked()

    # --- internals ------------------------------------------------------

    def _top_level(self, raw: str | None) -> tuple[str | None, bool]:
        """Return (top-level subdir name under source, True if path == that subdir)."""
        if not raw:
            return None, False
        path = Path(raw)
        try:
            resolved = path.resolve()
            rel = resolved.relative_to(self.source)
        except (ValueError, OSError):
            try:
                rel = path.relative_to(self.source)
            except ValueError:
                return None, False
        parts = rel.parts
        if not parts:
            return None, False
        top = parts[0]
        if top.startswith(".") or top in ("", "."):
            return None, False
        return top, len(parts) == 1

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
            names = self._dirty_names
            index_dirty = self._index_dirty
            self._dirty_names = set()
            self._index_dirty = False
            self._timer = None
        if not names and not index_dirty:
            return
        try:
            self._on_flush(names, index_dirty)
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
    def pending(self) -> tuple[set[str], bool]:
        with self._lock:
            return set(self._dirty_names), self._index_dirty


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
        log.info("watching %s (debounce=%.2fs)", self.config.source, self.config.debounce_seconds)
        try:
            observer.join()
        except KeyboardInterrupt:
            self.stop()

    def stop(self) -> None:
        if self._observer is not None:
            self._observer.stop()
            self._observer.join()
            self._observer = None

    def _rebuild(self, dirty_names: set[str], index_dirty: bool) -> None:
        log.info(
            "rebuild triggered: galleries=%s index_dirty=%s",
            sorted(dirty_names) or "[]",
            index_dirty,
        )
        self.builder.build_galleries(dirty_names if dirty_names else set(), rebuild_index=True)
