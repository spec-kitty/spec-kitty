"""One authority for the mid8 a ``meta.json`` records (charter DIRECTIVE_044, #5751).

Two rules decided "which mid8 does this Mission declare" in more than one place:

* the cascade of ``surface_resolver.resolve_declared_mid8`` (recorded ``mid8``, else the
  recorded ``mission_id`` through the identity helper, else a heuristic read of the slug's
  tail) and the directory-alias authority ``mission_dir_aliases`` (the first two tiers
  only): both are now built on the one declared-only core ``_declared_mid8``;
* the rule ``mission close`` applies (``mid8``, else ``mission_id``'s first eight
  characters, whitespace stripped) and the retrospective postcondition's "has this Mission a
  recorded identity" check: both are now built on ``mission_metadata.recorded_mid8``.

The tables below pin the behaviour each caller had before the extraction, so a later change to
the core moves every caller together, and the ``co_names`` checks prove the callers really go
through the shared function rather than agreeing by coincidence.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.coordination.surface_resolver import resolve_declared_mid8
from specify_cli.mission_metadata import recorded_mid8
from specify_cli.missions._read_path_resolver import _declared_mid8, mission_dir_aliases
from specify_cli.post_merge import retrospective_terminus

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_ID = "01KX0000000000000000000000"
_METAS: list[dict[str, object]] = [
    {},
    {"mid8": "ABCD1234"},
    {"mid8": ""},
    {"mission_id": _ID},
    {"mission_id": "short"},
    {"mission_id": None},
    {"mid8": "ABCD1234", "mission_id": _ID},
]
_SLUGS = ["bare", "bare-01KX0000", "bare-ZZZZZZZZ", ""]


@pytest.mark.parametrize("meta", _METAS)
@pytest.mark.parametrize("slug", _SLUGS)
def test_the_cascade_is_the_declared_core_plus_the_slug_tail_heuristic(meta: dict[str, object], slug: str) -> None:
    from mission_runtime import mid8_from_slug

    declared = _declared_mid8(meta, slug)

    assert resolve_declared_mid8(meta, slug) == (declared or mid8_from_slug(slug))


def test_the_cascade_and_the_alias_authority_both_call_the_one_declared_core() -> None:
    assert "_declared_mid8" in resolve_declared_mid8.__code__.co_names
    assert "_declared_mid8" in mission_dir_aliases.__code__.co_names


@pytest.mark.parametrize(
    ("meta", "expected"),
    [
        ({}, ""),
        ({"mid8": " ABCD1234 "}, "ABCD1234"),
        ({"mid8": "   "}, ""),
        ({"mission_id": _ID}, "01KX0000"),
        ({"mission_id": f"  {_ID}  "}, "01KX0000"),
        ({"mission_id": "short"}, ""),
        ({"mission_id": 12345678}, "12345678"),
        ({"mid8": "ABCD1234", "mission_id": _ID}, "ABCD1234"),
    ],
)
def test_recorded_mid8_is_the_rule_mission_close_applies(meta: dict[str, object], expected: str) -> None:
    assert recorded_mid8(meta) == expected


@pytest.mark.parametrize("meta", _METAS + [{"mid8": "   "}, {"mission_id": f"  {_ID}  "}])
def test_mission_close_and_the_retrospective_postcondition_agree_on_a_recorded_identity(tmp_path: Path, meta: dict[str, object]) -> None:
    from specify_cli.cli.commands.mission_type import _read_mission_mid8

    (tmp_path / "meta.json").write_text(json.dumps(meta), encoding="utf-8")

    assert retrospective_terminus._has_recorded_identity(tmp_path) is bool(_read_mission_mid8(tmp_path / "meta.json"))
    assert _read_mission_mid8(tmp_path / "meta.json") == recorded_mid8(meta)


def test_both_callers_go_through_the_shared_rule() -> None:
    from specify_cli.cli.commands.mission_type import _read_mission_mid8

    assert "recorded_mid8" in _read_mission_mid8.__code__.co_names
    assert "recorded_mid8" in retrospective_terminus._has_recorded_identity.__code__.co_names
