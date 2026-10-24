import hashlib

import pytest

from hallx.canonical import CANONICALIZATION_VERSION, canonicalize
from hallx.errors import SourceMapError


def test_canonicalization_version_is_pinned() -> None:
    assert CANONICALIZATION_VERSION == "nfkc-ws-v1"


def test_whitespace_and_nfkc_canonicalization() -> None:
    document = canonicalize("Ａ\tcorp\n\n policy  ")
    assert document.text == "A corp policy "
    assert document.sha256 == hashlib.sha256(document.text.encode("utf-8")).hexdigest()
    assert document.to_original_span(0, 1) == (0, 1)
    assert document.to_original_span(2, 6) == (2, 6)
    assert document.to_original_span(6, 7) == (6, 9)
    assert document.to_original_span(7, 13) == (9, 15)
    assert document.to_original_span(13, 14) == (15, 17)


def test_nfkc_expansion_maps_to_one_original_character() -> None:
    document = canonicalize("ﬀ")
    assert document.text == "ff"
    assert document.to_original_span(0, 2) == (0, 1)
    assert document.original_span_to_canonical(0, 1) == (0, 2)


def test_source_map_span_and_failure() -> None:
    document = canonicalize("a  b")
    assert document.text == "a b"
    assert document.to_original_span(2, 3) == (3, 4)
    assert document.original_span_to_canonical(3, 4) == (2, 3)
    with pytest.raises(SourceMapError):
        document.to_original_span(0, 0)
    with pytest.raises(SourceMapError):
        document.to_original_span(0, 99)
    with pytest.raises(SourceMapError):
        document.original_span_to_canonical(1, 2)
