"""Build cache: skip work when source files are unchanged and outputs exist."""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .scanner import Gallery, MediaFile

log = logging.getLogger(__name__)

CACHE_FILENAME = ".gallery_cache.json"
CACHE_VERSION = 1
_MTIME_TOL = 1e-6


@dataclass
class _Entry:
    size: int
    mtime: float
    outputs: list[str]  # relative to output dir, posix-style

    def to_json(self) -> dict:
        return {"size": self.size, "mtime": self.mtime, "outputs": list(self.outputs)}

    @classmethod
    def from_json(cls, data: dict) -> "_Entry":
        return cls(
            size=int(data["size"]),
            mtime=float(data["mtime"]),
            outputs=list(data.get("outputs", [])),
        )


class BuildCache:
    """Per-source-file record of size/mtime + emitted output paths."""

    def __init__(
        self,
        output: Path,
        reserved_root_names: Iterable[str] = (),
    ) -> None:
        self.output = output
        self.path = output / CACHE_FILENAME
        # Top-level names under ``output`` that prune must never traverse into
        # or remove (e.g. ``gallery`` user originals, ``assets`` build output).
        self.reserved_root_names: frozenset[str] = frozenset(reserved_root_names)
        self._entries: dict[str, _Entry] = {}

    def load(self) -> None:
        self._entries = {}
        if not self.path.is_file():
            return
        try:
            data = json.loads(self.path.read_text())
        except (OSError, ValueError) as exc:
            log.warning("cache unreadable, ignoring: %s (%s)", self.path, exc)
            return
        if not isinstance(data, dict) or data.get("version") != CACHE_VERSION:
            log.info("cache version mismatch, discarding")
            return
        entries = data.get("entries", {})
        if not isinstance(entries, dict):
            return
        for key, value in entries.items():
            try:
                self._entries[key] = _Entry.from_json(value)
            except (KeyError, TypeError, ValueError):
                continue

    def is_stale(self, media: MediaFile) -> bool:
        key = self._key(media.source)
        entry = self._entries.get(key)
        if entry is None:
            return True
        if entry.size != media.size:
            return True
        if abs(entry.mtime - media.mtime) > _MTIME_TOL:
            return True
        for rel in entry.outputs:
            if not (self.output / rel).exists():
                return True
        return False

    def mark_done(self, media: MediaFile) -> None:
        outputs = [self._rel(p) for p in media.output_paths()]
        self._entries[self._key(media.source)] = _Entry(
            size=media.size, mtime=media.mtime, outputs=outputs
        )

    def save(self) -> None:
        """Atomic write: tmp file in same dir → fsync → os.replace."""
        self.output.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        payload = {
            "version": CACHE_VERSION,
            "entries": {k: v.to_json() for k, v in self._entries.items()},
        }
        with tmp.open("w") as fh:
            json.dump(payload, fh, indent=2, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.path)

    def prune(self, galleries: Iterable[Gallery]) -> list[Path]:
        """Drop stale cache entries and unlink the orphan output files they
        owned. Then rmdir empty ancestor directories left behind, stopping at
        ``output`` itself or any reserved top-level name.

        Galleries may be passed as a flat list or as roots of a nested tree;
        ``Gallery.walk()`` is used to traverse descendants. We never delete
        files/dirs the cache did not record as ours, so user-managed paths
        (originals under ``gallery/``, files in ``assets/``, top-level
        ``index.html``) are left untouched.

        Returns the list of paths removed (for logging/testing).
        """
        flat: list[Gallery] = []
        for g in galleries:
            flat.extend(g.walk())

        active_sources = {self._key(m.source) for g in flat for m in g.media}
        expected_outputs = {
            self._rel(p) for g in flat for m in g.media for p in m.output_paths()
        }

        removed: list[Path] = []
        parents_to_check: set[Path] = set()

        for key in list(self._entries):
            if key in active_sources:
                continue
            entry = self._entries.pop(key)
            for rel in entry.outputs:
                if rel in expected_outputs:
                    continue
                target = self.output / rel
                if not target.exists() or not target.is_file():
                    continue
                try:
                    target.unlink()
                    removed.append(target)
                    parents_to_check.add(target.parent)
                except OSError as exc:
                    log.warning("could not remove orphan output %s: %s", target, exc)

        reserved_dirs = {self.output / name for name in self.reserved_root_names}
        for parent in parents_to_check:
            self._rmdir_upward(parent, reserved_dirs, removed)

        return removed

    def _rmdir_upward(
        self, start: Path, reserved: set[Path], removed: list[Path]
    ) -> None:
        """Remove ``start`` and each empty parent until we hit ``output``,
        a reserved top-level dir, or a non-empty / missing dir.
        """
        cur = start
        while True:
            if cur == self.output:
                return
            if cur in reserved:
                return
            if not cur.is_dir():
                return
            try:
                next(cur.iterdir())
                return  # not empty
            except StopIteration:
                pass
            except OSError:
                return
            try:
                cur.rmdir()
            except OSError:
                return
            removed.append(cur)
            cur = cur.parent

    @staticmethod
    def _key(source: Path) -> str:
        return str(source)

    def _rel(self, path: Path) -> str:
        try:
            return path.relative_to(self.output).as_posix()
        except ValueError:
            return path.as_posix()
