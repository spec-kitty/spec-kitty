"""``mission_dir_aliases``: the one authority for a Mission's directory names (#5651).

A coordination Mission whose primary directory is the bare slug keeps its coordination
directory under the composed ``<slug>-<mid8>`` name. The alias set pairs the two, exactly:

* the passed name is always in the set;
* the composed name is added only when the LITERAL primary directory's ``meta.json`` declares
  ``mid8`` or ``mission_id``;
* nothing is guessed from the slug's shape, nothing is prefix-matched, a handle is not
  canonicalised, and no input raises.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specify_cli.mission_metadata import OnMalformed
from specify_cli.missions._read_path_resolver import mission_dir_aliases

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_MID8 = "01M5651A"
_MISSION_ID = _MID8 + "0" * 18


def _write_meta(repo: Path, dir_name: str, meta: object) -> Path:
    directory = repo / "kitty-specs" / dir_name
    directory.mkdir(parents=True, exist_ok=True)
    text = meta if isinstance(meta, str) else json.dumps(meta)
    (directory / "meta.json").write_text(text, encoding="utf-8")
    return directory


def test_bare_slug_mission_gains_its_composed_coordination_name(tmp_path: Path) -> None:
    _write_meta(tmp_path, "bare-mission", {"mission_id": _MISSION_ID, "mid8": _MID8})

    assert mission_dir_aliases(tmp_path, "bare-mission") == frozenset({"bare-mission", f"bare-mission-{_MID8}"})


def test_the_mid8_is_derived_from_the_mission_id_when_mid8_is_not_recorded(tmp_path: Path) -> None:
    _write_meta(tmp_path, "bare-mission", {"mission_id": _MISSION_ID})

    assert mission_dir_aliases(tmp_path, "bare-mission") == frozenset({"bare-mission", f"bare-mission-{_MID8}"})


def test_a_recorded_mid8_alone_is_enough(tmp_path: Path) -> None:
    _write_meta(tmp_path, "bare-mission", {"mid8": _MID8})

    assert mission_dir_aliases(tmp_path, "bare-mission") == frozenset({"bare-mission", f"bare-mission-{_MID8}"})


def test_a_canonical_mission_yields_one_name_and_its_bare_stem_is_not_an_alias(tmp_path: Path) -> None:
    canonical = f"canonical-mission-{_MID8}"
    _write_meta(tmp_path, canonical, {"mission_id": _MISSION_ID, "mid8": _MID8})

    aliases = mission_dir_aliases(tmp_path, canonical)

    assert aliases == frozenset({canonical})
    assert "canonical-mission" not in aliases


def test_a_legacy_numeric_prefix_is_composed_verbatim_not_stripped(tmp_path: Path) -> None:
    _write_meta(tmp_path, "001-legacy-mission", {"mission_id": _MISSION_ID, "mid8": _MID8})

    assert mission_dir_aliases(tmp_path, "001-legacy-mission") == frozenset({"001-legacy-mission", f"001-legacy-mission-{_MID8}"})


def test_the_recorded_identity_wins_over_a_slug_tail_that_looks_like_an_identifier(tmp_path: Path) -> None:
    lookalike = "bare-mission-ABCDEFGH"
    _write_meta(tmp_path, lookalike, {"mission_id": _MISSION_ID, "mid8": _MID8})

    aliases = mission_dir_aliases(tmp_path, lookalike)

    assert aliases == frozenset({lookalike, f"{lookalike}-{_MID8}"})
    assert "bare-mission" not in aliases


@pytest.mark.parametrize(
    "meta",
    [{}, {"mission_slug": "bare-mission"}, {"mid8": ""}, {"mission_id": "short"}],
    ids=["empty-object", "no-identity", "empty-mid8", "short-mission-id"],
)
def test_unproven_identity_yields_the_single_name_set(tmp_path: Path, meta: dict[str, object]) -> None:
    _write_meta(tmp_path, "bare-mission", meta)

    assert mission_dir_aliases(tmp_path, "bare-mission") == frozenset({"bare-mission"})


def test_a_slug_that_merely_looks_like_it_ends_in_a_mid8_is_not_inferred_from(tmp_path: Path) -> None:
    """No recorded identity: the look-alike tail of the name is a guess, so no alias is added."""
    name = "bare-mission-ABCDEFGH"
    _write_meta(tmp_path, name, {"mission_slug": name})

    assert mission_dir_aliases(tmp_path, name) == frozenset({name})


def test_absent_metadata_yields_the_single_name_set(tmp_path: Path) -> None:
    (tmp_path / "kitty-specs" / "bare-mission").mkdir(parents=True)

    assert mission_dir_aliases(tmp_path, "bare-mission") == frozenset({"bare-mission"})


def test_a_missing_directory_yields_the_single_name_set(tmp_path: Path) -> None:
    assert mission_dir_aliases(tmp_path, "bare-mission") == frozenset({"bare-mission"})


@pytest.mark.parametrize("text", ["{not json", "[1, 2]", "", "null"], ids=["not-json", "not-an-object", "empty-file", "null"])
def test_corrupt_metadata_yields_the_single_name_set_without_raising(tmp_path: Path, text: str) -> None:
    _write_meta(tmp_path, "bare-mission", text)

    assert mission_dir_aliases(tmp_path, "bare-mission") == frozenset({"bare-mission"})


def test_unreadable_metadata_yields_the_single_name_set_without_raising(tmp_path: Path) -> None:
    """A ``meta.json`` that is a directory cannot be read; that is "no identity", not an error."""
    (tmp_path / "kitty-specs" / "bare-mission" / "meta.json").mkdir(parents=True)

    assert mission_dir_aliases(tmp_path, "bare-mission") == frozenset({"bare-mission"})


def test_a_bare_handle_for_a_composed_directory_mission_gains_no_alias(tmp_path: Path) -> None:
    """The handle is not canonicalised: ``kitty-specs/bare-mission/`` does not exist, so nothing is added."""
    _write_meta(tmp_path, f"bare-mission-{_MID8}", {"mission_id": _MISSION_ID, "mid8": _MID8})

    assert mission_dir_aliases(tmp_path, "bare-mission") == frozenset({"bare-mission"})


@pytest.mark.parametrize("slug", ["", "../x", "a/b", ".hidden", "ok slug", " padded", "../../etc"])
def test_a_slug_that_is_not_a_safe_path_segment_yields_the_single_name_set_without_raising(tmp_path: Path, slug: str) -> None:
    assert mission_dir_aliases(tmp_path, slug) == frozenset({slug})


@pytest.mark.parametrize(
    "recorded",
    [
        pytest.param({"mid8": "../x"}, id="mid8-traversal"),
        pytest.param({"mid8": "a/b"}, id="mid8-separator"),
        pytest.param({"mid8": "/../../etc"}, id="mid8-absolute-traversal"),
        pytest.param({"mid8": "  01M565"}, id="mid8-leading-spaces"),
        pytest.param({"mid8": "01M5651A "}, id="mid8-trailing-space"),
        pytest.param({"mid8": "01M5651A\n"}, id="mid8-trailing-newline"),
        pytest.param({"mid8": "   "}, id="mid8-blank"),
        pytest.param({"mission_id": "../../../etc/passwd"}, id="mission-id-traversal"),
        pytest.param({"mission_id": "  01M5651A" + "0" * 17}, id="mission-id-leading-spaces"),
        pytest.param({"mission_id": "01M5651\u00c9" + "0" * 18}, id="mission-id-non-ascii"),
    ],
)
def test_a_malformed_recorded_identity_yields_no_alias(tmp_path: Path, recorded: dict[str, object]) -> None:
    _write_meta(tmp_path, "bare-mission", recorded)

    assert mission_dir_aliases(tmp_path, "bare-mission") == frozenset({"bare-mission"})


def test_a_canonical_directory_whose_record_disagrees_with_its_tail_gains_the_recorded_composition(tmp_path: Path) -> None:
    """Recorded identity disposes (decision, review cycle 1).

    ``kitty-specs/foo-01ZZZZZZ`` with a recorded ``mid8`` of ``01M5651A`` can only arise from a
    hand-edited or corrupt ``meta.json`` (the directory is minted from the identity). Excluding it
    would need a guess from the slug's tail, which the alias never makes, so the recorded
    composition is added; it names a directory that does not exist and recognises nothing.
    """
    _write_meta(tmp_path, "foo-01ZZZZZZ", {"mission_id": _MISSION_ID, "mid8": _MID8})

    assert mission_dir_aliases(tmp_path, "foo-01ZZZZZZ") == frozenset({"foo-01ZZZZZZ", f"foo-01ZZZZZZ-{_MID8}"})


@pytest.mark.parametrize(
    "recorded",
    [
        pytest.param({"mid8": "01m5651a"}, id="lowercase-mid8"),
        pytest.param({"mid8": "01COORD0"}, id="non-crockford-mid8"),
        pytest.param({"mid8": "x"}, id="single-character-mid8"),
        pytest.param({"mid8": _MID8 + "0" * 18}, id="26-character-mid8"),
        pytest.param({"mid8": 7}, id="non-string-mid8"),
        pytest.param({"mission_id": "01m5651a" + "0" * 18}, id="lowercase-mission-id"),
        pytest.param({"mission_id": 12345678}, id="non-string-mission-id"),
        pytest.param({"mid8": _MID8, "mission_id": "01ZZZZZZ" + "0" * 18}, id="mid8-wins-over-mission-id"),
    ],
)
def test_the_alias_is_exactly_the_directory_name_the_real_composer_writes(tmp_path: Path, recorded: dict[str, object]) -> None:
    """No case, length or alphabet check: the alias follows the recorded identity byte for byte."""
    from specify_cli.coordination.surface_resolver import resolve_declared_mid8
    from specify_cli.missions._read_path_resolver import coord_feature_dir

    _write_meta(tmp_path, "bare-mission", recorded)
    composed = coord_feature_dir(tmp_path, "bare-mission", resolve_declared_mid8(recorded, "bare-mission")).name

    assert composed != "bare-mission"
    assert mission_dir_aliases(tmp_path, "bare-mission") == frozenset({"bare-mission", composed})


def test_a_recorded_mid8_is_not_stripped_because_the_composer_does_not_strip_it(tmp_path: Path) -> None:
    """``resolve_declared_mid8`` returns a truthy ``mid8`` verbatim; padded, it names an unsafe segment, so no alias."""
    from specify_cli.coordination.surface_resolver import resolve_declared_mid8

    recorded = {"mid8": " 01M5651A", "mission_id": _MISSION_ID}
    _write_meta(tmp_path, "bare-mission", recorded)

    assert resolve_declared_mid8(recorded, "bare-mission") == " 01M5651A"
    assert mission_dir_aliases(tmp_path, "bare-mission") == frozenset({"bare-mission"})


def test_the_literal_primary_directory_is_read_exactly_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.mission_metadata as mission_metadata

    _write_meta(tmp_path, "bare-mission", {"mission_id": _MISSION_ID, "mid8": _MID8})
    real_load_meta = mission_metadata.load_meta
    read_dirs: list[Path] = []

    def _counting_load_meta(feature_dir: Path, *, allow_missing: bool = True, on_malformed: OnMalformed = "raise") -> dict[str, Any] | None:
        read_dirs.append(feature_dir)
        return real_load_meta(feature_dir, allow_missing=allow_missing, on_malformed=on_malformed)

    monkeypatch.setattr(mission_metadata, "load_meta", _counting_load_meta)

    mission_dir_aliases(tmp_path, "bare-mission")

    assert read_dirs == [tmp_path / "kitty-specs" / "bare-mission"]
