"""URL-safe slug generation for gallery directory names."""

from __future__ import annotations

import re
import unicodedata
from typing import Iterable

_FALLBACK = "gallery"
_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_MULTI_HYPHEN = re.compile(r"-{2,}")


def slugify(name: str, taken: Iterable[str] | None = None) -> str:
    """Convert *name* to an ascii, lowercase, hyphenated slug.

    If *taken* is provided, the returned slug is guaranteed not to be in it.
    Pass a mutable set and add the result to it to track collisions across calls.
    """
    base = _base_slug(name)
    if taken is None:
        return base
    taken_set = taken if isinstance(taken, set) else set(taken)
    if base not in taken_set:
        return base
    n = 2
    while True:
        candidate = f"{base}-{n}"
        if candidate not in taken_set:
            return candidate
        n += 1


def _base_slug(name: str) -> str:
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_bytes = decomposed.encode("ascii", "ignore")
    text = ascii_bytes.decode("ascii").lower()
    text = _NON_ALNUM.sub("-", text)
    text = _MULTI_HYPHEN.sub("-", text)
    text = text.strip("-")
    return text or _FALLBACK
