"""WP06 contract tests for the in-mission meta-reader sweep (FR-009 / SC-004).

These tests pin the **observable contract** of each inline ``json.loads`` read in
``agent/mission.py`` that WP06 routes through the canonical
``mission_metadata.load_meta`` authority.  The behavioral form (DECISION 7) is
mandatory: feed a *malformed* ``meta.json`` through each converted site's
pre-existing entry point (the module helper that owns the read) and assert the
read **degrades per the canonical reader's contract** -- never a raw
``json.JSONDecodeError``.

A source-grep / module-source count is explicitly rejected (DECISION 7): it
proves only that the text changed, not that the canonical contract holds at the
site.  We assert the **consuming helper's return value**, never the internal
``load_meta`` call-graph (CT4 / D036).

Two in-mission sites (the only ones in scope; the ~53-site #2100 backlog is
deferred; a third, the ``pr_bound`` write-back reader, was deleted as dead code):

- ``_read_feature_meta`` (was ``json.loads`` + ``except (JSONDecodeError,
  OSError): return {}``) -> silent-empty contract (c): missing/malformed -> ``{}``.
- ``_read_meta_for_emission`` (was the inline finalize-tasks event-emission
  read, ``except (JSONDecodeError, OSError): warn``) -> silent-none contract:
  missing/malformed -> ``None``.

Each site has a missing/malformed/valid cell.  The malformed cell is the
mutation-killer: the old inline ``json.loads`` raised ``JSONDecodeError`` on a
truncated file; the canonical reader absorbs it to the site's sentinel.

Production-shaped identity (testing-principles -- never a short placeholder)::

    ULID: 01KVTVZSQ7XB2M9K4D8N3FZ0YT  (26 chars)
    mid8: 01KVTVZS                       (8 chars)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from specify_cli.mission_metadata import META_FILENAME, write_meta

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_MISSION_ID = "01KVTVZSQ7XB2M9K4D8N3FZ0YT"
_MID8 = _MISSION_ID[:8]  # "01KVTVZS"
_MISSION_SLUG = f"write-surface-coherence-{_MID8}"


def _valid_meta() -> dict[str, Any]:
    """A complete, production-shaped meta.json mapping."""
    return {
        "mission_id": _MISSION_ID,
        "mission_number": None,
        "slug": _MISSION_SLUG,
        "mission_slug": _MISSION_SLUG,
        "friendly_name": "Write-Surface Coherence",
        "mission_type": "software-dev",
        "target_branch": "feat/write-surface-coherence",
        "created_at": "2026-06-23T19:28:09+00:00",
    }


def _seed_valid(feature_dir: Path) -> dict[str, Any]:
    """Write a valid meta.json via the production write seam; return its dict."""
    meta = _valid_meta()
    write_meta(feature_dir, meta)
    return meta


def _seed_malformed(feature_dir: Path) -> None:
    """Write a genuinely un-parseable meta.json (truncated JSON, not empty).

    ``{"a":`` is truncated JSON that ``json.loads`` cannot parse -- this is the
    malformed arm, the mutation-killer.  The old inline ``json.loads`` raised
    ``json.JSONDecodeError`` here; the canonical reader absorbs it.
    """
    (feature_dir / META_FILENAME).write_text('{"a":', encoding="utf-8")


# ===========================================================================
# Site 1: _read_feature_meta -> load_meta_or_empty (silent-empty contract c)
# ===========================================================================


def test_read_feature_meta_returns_empty_on_missing(tmp_path: Path) -> None:
    """Missing meta.json -> {} (contract c, missing arm)."""
    from specify_cli.cli.commands.agent.mission import _read_feature_meta

    assert _read_feature_meta(tmp_path) == {}


def test_read_feature_meta_returns_empty_on_malformed(tmp_path: Path) -> None:
    """Malformed meta.json -> {} -- never raises (contract c, malformed arm).

    Mutation-killer: the old inline ``json.loads`` raised ``JSONDecodeError``;
    the canonical reader degrades to ``{}``.
    """
    _seed_malformed(tmp_path)
    from specify_cli.cli.commands.agent.mission import _read_feature_meta

    assert _read_feature_meta(tmp_path) == {}


def test_read_feature_meta_returns_dict_on_valid(tmp_path: Path) -> None:
    """A valid meta.json returns the parsed mapping (positive control)."""
    expected = _seed_valid(tmp_path)
    from specify_cli.cli.commands.agent.mission import _read_feature_meta

    assert _read_feature_meta(tmp_path) == expected


# ===========================================================================
# Site 2: _read_meta_for_emission -> load_meta(..., on_malformed="none")
#
# The finalize-tasks event-emission read tolerates a missing/malformed meta by
# leaving ``meta = None`` (and warning at the call site).  Contract: missing or
# malformed -> None; valid -> dict.
# ===========================================================================


def test_read_meta_for_emission_returns_none_on_missing(tmp_path: Path) -> None:
    """Missing meta.json -> None (skip emission)."""
    from specify_cli.cli.commands.agent.mission import _read_meta_for_emission

    assert _read_meta_for_emission(tmp_path) is None


def test_read_meta_for_emission_returns_none_on_malformed(tmp_path: Path) -> None:
    """Malformed meta.json -> None -- never raises (mutation-killer).

    The old inline ``json.loads`` raised ``JSONDecodeError`` (caught + warned);
    the canonical reader degrades to ``None`` under ``on_malformed="none"``.
    """
    _seed_malformed(tmp_path)
    from specify_cli.cli.commands.agent.mission import _read_meta_for_emission

    assert _read_meta_for_emission(tmp_path) is None


def test_read_meta_for_emission_returns_dict_on_valid(tmp_path: Path) -> None:
    """A valid meta.json returns the parsed mapping (positive control)."""
    expected = _seed_valid(tmp_path)
    from specify_cli.cli.commands.agent.mission import _read_meta_for_emission

    assert _read_meta_for_emission(tmp_path) == expected
