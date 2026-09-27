"""Site-E (merge-driver ``meta.json`` blob) diagnosability under WP04.

``specify_cli.merge.drivers._load_json_object`` routes its decode through the public L2 reader
``parse_meta_file`` (``on_malformed="raise"``) so a corrupt merge-blob
``meta.json`` fails LOUD and NAMED — an ``EventLogMergeError`` carrying the path —
instead of the pre-routing bare, unnamed ``json.JSONDecodeError`` (mission
``meta-json-fail-closed-routing-01KZPJ1F`` / site E / FR-005 / C-010). The benign
contracts are preserved: an empty/whitespace-only blob yields ``{}`` and a valid
object round-trips unchanged; a non-object top level stays an
``EventLogMergeError``.

Site E is a plain on-disk ``Path`` (git materializes the ``%O``/``%A``/``%B``
merge inputs as sibling temp files), so these are pure on-disk unit assertions —
no ``git_repo`` fixture, no skip.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from specify_cli.merge.drivers import _load_json_object
from specify_cli.status import EventLogMergeError

pytestmark = pytest.mark.fast


def test_corrupt_meta_blob_fails_loud_and_names_path(tmp_path: Path) -> None:
    """A malformed blob raises a NAMED ``EventLogMergeError`` that names the path.

    Red-first proof: pre-routing, ``_load_json_object`` let a bare
    ``json.JSONDecodeError`` escape here (unnamed, NOT an ``EventLogMergeError``);
    routing site E through ``parse_meta_file(on_malformed="raise")`` and
    translating the failure to ``EventLogMergeError(path)`` is what turns this
    green.
    """
    blob = tmp_path / "meta.json"
    blob.write_text("{ not valid json", encoding="utf-8")
    with pytest.raises(EventLogMergeError, match=re.escape(str(blob))):
        _load_json_object(blob)


def test_non_object_blob_raises_named_merge_error(tmp_path: Path) -> None:
    """A JSON array (non-object) top level stays an ``EventLogMergeError`` (preserved)."""
    blob = tmp_path / "meta.json"
    blob.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(EventLogMergeError, match="not a JSON object"):
        _load_json_object(blob)


def test_whitespace_only_blob_is_benign_empty(tmp_path: Path) -> None:
    """Empty/whitespace-only content short-circuits to ``{}`` (C-010, preserved)."""
    blob = tmp_path / "meta.json"
    blob.write_text("   \n\t", encoding="utf-8")
    assert _load_json_object(blob) == {}


def test_valid_object_blob_round_trips_unchanged(tmp_path: Path) -> None:
    """A valid object decodes to the same mapping (FR-005, behavior-preserving)."""
    blob = tmp_path / "meta.json"
    payload: dict[str, object] = {
        "mission_slug": "m",
        "mission_number": 7,
        "nested": {"k": [1, 2]},
    }
    blob.write_text(json.dumps(payload), encoding="utf-8")
    assert _load_json_object(blob) == payload
