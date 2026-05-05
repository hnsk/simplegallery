"""Slugify: ascii lowercase, unicode strip, collision handling."""

from __future__ import annotations

import pytest

from simplegallery.slugify import slugify


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Hello World", "hello-world"),
        ("Already-slug", "already-slug"),
        ("  Trim  spaces  ", "trim-spaces"),
        ("Mixed_Case 123", "mixed-case-123"),
        ("multi  ---  hyphen", "multi-hyphen"),
        ("Café & Crème", "cafe-creme"),
        ("São Paulo", "sao-paulo"),
        ("北京", "gallery"),
        ("---", "gallery"),
        ("", "gallery"),
    ],
)
def test_base_slug(raw: str, expected: str) -> None:
    assert slugify(raw) == expected


def test_collision_appends_counter() -> None:
    taken: set[str] = set()
    a = slugify("Vacation", taken)
    taken.add(a)
    b = slugify("Vacation", taken)
    taken.add(b)
    c = slugify("vacation", taken)
    taken.add(c)
    assert (a, b, c) == ("vacation", "vacation-2", "vacation-3")


def test_collision_skips_existing_counter() -> None:
    taken = {"trip", "trip-2"}
    assert slugify("Trip", taken) == "trip-3"


def test_unicode_only_collisions_use_fallback() -> None:
    taken: set[str] = set()
    first = slugify("北京", taken)
    taken.add(first)
    second = slugify("東京", taken)
    assert first == "gallery"
    assert second == "gallery-2"
