"""Stem → canonical parity guard for ``config.activated_*`` (WP01, C-006, FR-001).

C-006 requires that every ``config.activated_*`` slug-stem normalizes to a
canonical DRG URN node ID *exactly* as the live ``ActiveCharterService``/DRG
resolution does, and that a stem which cannot be resolved is **rejected**
(raises), never silently dropped. A silent drop would remove the artefact
*and* its entire transitive closure (tactics → styleguides → toolguides →
procedures) from the compiled reference set + graph, invisibly.

This module:

- **T001/T002**: confirms ``charter.activation.kind_vocabulary.resolve_artifact_urn`` is
  the correct stem→canonical resolver (reject-not-drop via
  ``UnknownArtifactIdError``) — no new resolver logic is introduced here; this
  is a reuse-and-pin, not a reimplementation (see module docstring history in
  ``kind_vocabulary.py``).
- **T003**: a data-driven fixture that round-trips *every one* of the
  ``activated_directives`` slug-stems declared in this repository's own
  activation store against the real built-in doctrine tree, plus a
  spot-check of one activated entry from each of the other five activatable
  kinds (tactic, toolguide, procedure, paradigm, styleguide). Both numbered
  (``DIRECTIVE_NNN``) and slug-hub (``USE_C4_MODEL_TECHNIQUES``) canonical id
  forms are accepted.
- **T004**: non-vacuity — a deliberately malformed/unresolvable stem is
  rejected (proves the guard actually bites and is not inert).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.activation.catalog import resolve_offering_root
from charter.activation.kind_vocabulary import (
    UnknownArtifactIdError,
    resolve_artifact_urn,
    resolve_config_id,
)
from charter.offering.artifact_kinds import ArtifactKind

pytestmark = [pytest.mark.unit]

#: Deliberately malformed/unresolvable stems for the non-vacuity check (T004).
#: None of these correspond to a real built-in directive config stem.
_MALFORMED_DIRECTIVE_STEMS = [
    "999-does-not-exist-anywhere",
    "not-a-numbered-directive-at-all",
    "",
]


def _find_repo_root() -> Path:
    """Walk up from this file until a directory containing ``pyproject.toml``.

    Duplicated (not imported) from ``tests/charter/conftest.py``'s private
    ``_find_repo_root`` because :func:`pytest.mark.parametrize` needs the
    directive stem list at collection time, before any fixture (including
    the session-scoped ``repo_root`` fixture) has run.
    """
    candidate = Path(__file__).resolve().parent
    while candidate != candidate.parent:
        if (candidate / "pyproject.toml").exists():
            return candidate
        candidate = candidate.parent
    raise RuntimeError("Could not find repo root (no pyproject.toml found in any parent directory)")


def _load_config(repo_root: Path) -> dict[str, object]:
    """Load the *resolved activation store* (WP07/T036 repoint, FR-017).

    Activation lives in the store resolved through the ``.kittify/config.yaml``
    ``charter:`` pointer — ``charter.yaml`` when the pointer is present (the
    migrated state), else the legacy config.yaml. The retired config.yaml
    ``activated_*`` mirror is no longer consulted. The function name is kept
    for call-site stability; every consumer reads ``activated_*`` keys.
    """
    from charter.activation.pack_context import resolve_charter_yaml_pointer

    yaml = YAML(typ="safe")
    config_path = repo_root / ".kittify" / "config.yaml"
    config_data = yaml.load(config_path.read_text(encoding="utf-8"))
    assert isinstance(config_data, dict)
    charter_path = resolve_charter_yaml_pointer(repo_root, config_data)
    if charter_path is None:
        return config_data
    store = yaml.load(charter_path.read_text(encoding="utf-8"))
    assert isinstance(store, dict)
    return store


@pytest.fixture(scope="module")
def doctrine_root() -> Path:
    return resolve_offering_root()


@pytest.fixture(scope="module")
def activated_directive_stems(repo_root: Path) -> list[str]:
    """Every slug-stem in this repo's own ``config.activated_directives``."""
    config = _load_config(repo_root)
    stems = config.get("activated_directives")
    assert isinstance(stems, list)
    assert stems, "expected config.activated_directives to be non-empty"
    return [str(stem) for stem in stems]


# --------------------------------------------------------------------------- #
# T001/T002 — resolve_artifact_urn is the stem→canonical, reject-not-drop
# resolver (pin, not reimplementation).
# --------------------------------------------------------------------------- #


def test_resolve_artifact_urn_is_reject_not_drop_on_unresolvable_stem(
    doctrine_root: Path,
) -> None:
    """An unresolvable stem raises — it is never silently skipped (C-006)."""
    with pytest.raises(UnknownArtifactIdError):
        resolve_artifact_urn(
            ArtifactKind.DIRECTIVE,
            "999-does-not-exist-anywhere",
            doctrine_root=doctrine_root,
        )


# --------------------------------------------------------------------------- #
# T003 — full activated-directive parity fixture, driven by this repo's own
# .kittify/config.yaml (production-shaped data, not placeholders).
# --------------------------------------------------------------------------- #



def _directive_stems_for_parametrize() -> list[str]:
    """Read config.activated_directives eagerly for parametrize IDs.

    ``pytest.mark.parametrize`` needs its argument list at collection time,
    before fixtures run, so this re-reads the same config file the
    ``activated_directive_stems`` fixture reads. Both routes must produce the
    same stems; the behavioral round-trip below rejects unresolved drift
    without pinning a corpus cardinality.
    """
    config = _load_config(_find_repo_root())
    stems = config.get("activated_directives")
    assert isinstance(stems, list)
    return [str(stem) for stem in stems]


@pytest.mark.parametrize("stem", _directive_stems_for_parametrize())
def test_every_activated_directive_stem_round_trips_to_canonical_urn(
    stem: str, doctrine_root: Path
) -> None:
    """Every real ``config.activated_directives`` stem resolves and round-trips.

    Exercises the exact mapping the live derivation (WP02) must reproduce:
    stem -> canonical directive URN -> back to the same stem, with no manual
    answers.yaml involvement.

    The canonical id is *whatever form the directive artifact declares*: the
    numbered ``directive:DIRECTIVE_NNN`` form, or the UPPER_SNAKE slug form used
    by deliberately-named extensible hub directives (e.g.
    ``directive:USE_C4_MODEL_TECHNIQUES``,
    ``directive:RECONCILE_CHANGE_SCOPE_TENSIONS`` — the same established
    convention as ``DISCIPLINED_REFACTORING`` / ``USE_MUTATION_TESTING`` already
    in the graph). The round-trip below is the real bite; the URN shape check
    only pins that a *canonical* directive URN came back, not a particular id
    spelling.
    """
    urn = resolve_artifact_urn(ArtifactKind.DIRECTIVE, stem, doctrine_root=doctrine_root)
    assert re.fullmatch(
        r"directive:[A-Z][A-Z0-9_]+", urn
    ), f"expected a canonical directive URN, got {urn!r}"
    assert resolve_config_id(urn, doctrine_root=doctrine_root) == stem


@pytest.mark.parametrize(
    ("kind", "config_key"),
    [
        (ArtifactKind.TACTIC, "activated_tactics"),
        (ArtifactKind.TOOLGUIDE, "activated_toolguides"),
        (ArtifactKind.PROCEDURE, "activated_procedures"),
        (ArtifactKind.PARADIGM, "activated_paradigms"),
        (ArtifactKind.STYLEGUIDE, "activated_styleguides"),
    ],
)
def test_spot_check_one_activated_entry_per_other_kind_round_trips(
    kind: ArtifactKind, config_key: str, repo_root: Path, doctrine_root: Path
) -> None:
    """Spot-check: one real activated stem per remaining kind round-trips.

    T003 asks for a full sweep of directives (the kind implicated in the
    #2524 regression, C-006) plus a spot-check of the other activatable
    kinds — this is the spot-check half.
    """
    config = _load_config(repo_root)
    stems = config.get(config_key)
    if stems is None:
        # The key is absent here (the kind is unrestricted, e.g. after the #3732
        # cutover reset a stale released list): spot-check a shipped artifact.
        from charter.offering.pack_paths import built_in_root

        stems = sorted(path.name.split(".")[0] for path in (built_in_root() / kind.plural).glob(kind.glob_pattern))
    assert isinstance(stems, list)
    assert stems, f"expected config.{config_key} (or the built-in {kind.plural}) to be non-empty"
    stem = str(stems[0])

    urn = resolve_artifact_urn(kind, stem, doctrine_root=doctrine_root)
    assert urn.startswith(f"{kind.value}:")
    assert resolve_config_id(urn, doctrine_root=doctrine_root) == stem


# --------------------------------------------------------------------------- #
# T004 — non-vacuity: a deliberately malformed stem is rejected, proving the
# guard is not inert.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("malformed_stem", _MALFORMED_DIRECTIVE_STEMS)
def test_malformed_stem_is_rejected_not_silently_dropped(
    malformed_stem: str, doctrine_root: Path, activated_directive_stems: list[str]
) -> None:
    """A stem with no matching artefact raises — proving reject-not-drop bites.

    Non-vacuity per T004: this test would fail (no exception raised) if the
    resolver silently returned a sentinel/None or picked an unrelated
    artefact instead of raising. It also asserts the malformed stem is not
    coincidentally a real activated directive, so the negative case is
    genuinely negative.
    """
    assert malformed_stem not in activated_directive_stems
    with pytest.raises(UnknownArtifactIdError):
        resolve_artifact_urn(ArtifactKind.DIRECTIVE, malformed_stem, doctrine_root=doctrine_root)
