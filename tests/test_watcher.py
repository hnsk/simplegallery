"""Watcher: dirty-rel tracking, debounce coalescing, nested events."""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Iterable

import pytest
from watchdog.events import (
    DirCreatedEvent,
    DirDeletedEvent,
    DirMovedEvent,
    FileClosedNoWriteEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileOpenedEvent,
)

from simplegallery.watcher import GalleryEventHandler


class _Recorder:
    """Capture dirty-rel flush invocations."""

    def __init__(self) -> None:
        self.calls: list[set[str]] = []
        self.event = threading.Event()

    def __call__(self, dirty_rels: set[str]) -> None:
        self.calls.append(set(dirty_rels))
        self.event.set()

    def wait(self, timeout: float = 1.0) -> bool:
        return self.event.wait(timeout)


def _handler(source: Path, debounce: float, recorder: _Recorder) -> GalleryEventHandler:
    return GalleryEventHandler(source=source, debounce_seconds=debounce, on_flush=recorder)


def _send(handler: GalleryEventHandler, events: Iterable) -> None:
    for ev in events:
        handler.dispatch(ev)


@pytest.fixture
def src(tmp_path: Path) -> Path:
    s = tmp_path / "source"
    (s / "alpha").mkdir(parents=True)
    (s / "beta").mkdir(parents=True)
    (s / "alpha" / "macro").mkdir()
    return s


def test_file_event_marks_parent_dir_rel(src: Path) -> None:
    rec = _Recorder()
    h = _handler(src, debounce=0.05, recorder=rec)
    h.dispatch(FileModifiedEvent(str(src / "alpha" / "img.jpg")))
    assert rec.wait(1.0)
    assert rec.calls[-1] == {"alpha"}


def test_deeply_nested_file_event_marks_leaf_rel(src: Path) -> None:
    rec = _Recorder()
    h = _handler(src, debounce=0.05, recorder=rec)
    h.dispatch(FileCreatedEvent(str(src / "alpha" / "macro" / "close.png")))
    assert rec.wait(1.0)
    assert rec.calls[-1] == {"alpha/macro"}


def test_file_at_source_root_marks_root_rel(src: Path) -> None:
    rec = _Recorder()
    h = _handler(src, debounce=0.05, recorder=rec)
    h.dispatch(FileCreatedEvent(str(src / "loose.jpg")))
    assert rec.wait(1.0)
    assert rec.calls[-1] == {""}


def test_dir_create_marks_dir_rel(src: Path) -> None:
    rec = _Recorder()
    h = _handler(src, debounce=0.05, recorder=rec)
    h.dispatch(DirCreatedEvent(str(src / "gamma")))
    assert rec.wait(1.0)
    assert rec.calls[-1] == {"gamma"}


def test_nested_dir_create_marks_full_rel(src: Path) -> None:
    rec = _Recorder()
    h = _handler(src, debounce=0.05, recorder=rec)
    h.dispatch(DirCreatedEvent(str(src / "alpha" / "ultra")))
    assert rec.wait(1.0)
    assert rec.calls[-1] == {"alpha/ultra"}


def test_dir_delete_marks_dir_rel(src: Path) -> None:
    rec = _Recorder()
    h = _handler(src, debounce=0.05, recorder=rec)
    h.dispatch(DirDeletedEvent(str(src / "alpha")))
    assert rec.wait(1.0)
    assert rec.calls[-1] == {"alpha"}


def test_dir_move_tracks_both_endpoints(src: Path) -> None:
    rec = _Recorder()
    h = _handler(src, debounce=0.05, recorder=rec)
    h.dispatch(DirMovedEvent(str(src / "alpha"), str(src / "alpha-renamed")))
    assert rec.wait(1.0)
    assert rec.calls[-1] == {"alpha", "alpha-renamed"}


def test_nested_dir_move_tracks_both_endpoints(src: Path) -> None:
    rec = _Recorder()
    h = _handler(src, debounce=0.05, recorder=rec)
    h.dispatch(
        DirMovedEvent(str(src / "alpha" / "macro"), str(src / "beta" / "macro"))
    )
    assert rec.wait(1.0)
    assert rec.calls[-1] == {"alpha/macro", "beta/macro"}


def test_debounce_coalesces_burst(src: Path) -> None:
    rec = _Recorder()
    h = _handler(src, debounce=0.15, recorder=rec)
    burst = [
        FileCreatedEvent(str(src / "alpha" / f"img{i}.jpg")) for i in range(10)
    ] + [FileModifiedEvent(str(src / "beta" / "video.mp4"))]
    for ev in burst:
        h.dispatch(ev)
        time.sleep(0.005)
    assert rec.wait(1.0)
    time.sleep(0.2)  # ensure no follow-up
    assert len(rec.calls) == 1
    assert rec.calls[0] == {"alpha", "beta"}


def test_event_outside_source_ignored(src: Path, tmp_path: Path) -> None:
    rec = _Recorder()
    h = _handler(src, debounce=0.05, recorder=rec)
    other = tmp_path / "elsewhere"
    other.mkdir()
    h.dispatch(FileCreatedEvent(str(other / "foo.jpg")))
    assert not rec.wait(0.25), "no flush expected for events outside source"


def test_hidden_component_ignored(src: Path) -> None:
    rec = _Recorder()
    h = _handler(src, debounce=0.05, recorder=rec)
    hidden = src / ".cache"
    h.dispatch(FileCreatedEvent(str(hidden / "x.jpg")))
    h.dispatch(FileModifiedEvent(str(src / "alpha" / ".tmpfile")))
    h.dispatch(FileCreatedEvent(str(src / "alpha" / ".hidden" / "y.jpg")))
    assert not rec.wait(0.25)


def test_read_only_open_close_events_ignored(src: Path) -> None:
    """FileOpenedEvent / FileClosedNoWriteEvent fire when the build reads source files;
    they must not retrigger a rebuild or the watcher loops forever."""
    rec = _Recorder()
    h = _handler(src, debounce=0.05, recorder=rec)
    h.dispatch(FileOpenedEvent(str(src / "alpha" / "img.jpg")))
    h.dispatch(FileClosedNoWriteEvent(str(src / "alpha" / "img.jpg")))
    assert not rec.wait(0.25), "read-only opens must not trigger rebuild"


def test_flush_now_drains_state(src: Path) -> None:
    rec = _Recorder()
    h = _handler(src, debounce=5.0, recorder=rec)
    h.dispatch(FileModifiedEvent(str(src / "alpha" / "x.jpg")))
    h.flush_now()
    assert rec.calls and rec.calls[-1] == {"alpha"}
    assert h.pending == set()


def test_watcher_service_partial_rebuild(monkeypatch, src: Path, tmp_path: Path) -> None:
    """End-to-end: handler flush → builder.build_all called with dirty rels."""
    from simplegallery.config import Config
    from simplegallery.watcher import WatcherService

    cfg = Config(source=src, output=tmp_path / "output", debounce_seconds=0.05)

    class _FakeBuilder:
        def __init__(self) -> None:
            self.full_calls = 0
            self.partial_calls: list[set[str]] = []

        def build_all(self, dirty_rels=None) -> list[Path]:
            if dirty_rels is None:
                self.full_calls += 1
            else:
                self.partial_calls.append(set(dirty_rels))
            return []

    fake = _FakeBuilder()
    svc = WatcherService(cfg, builder=fake)
    # do not call start(); simulate a flush directly
    svc.handler.dispatch(FileModifiedEvent(str(src / "alpha" / "img.jpg")))
    svc.handler.dispatch(DirCreatedEvent(str(src / "alpha" / "ultra")))
    svc.handler.dispatch(DirCreatedEvent(str(src / "gamma")))
    svc.handler.flush_now()
    assert fake.partial_calls, "expected partial rebuild"
    assert fake.partial_calls[-1] == {"alpha", "alpha/ultra", "gamma"}
