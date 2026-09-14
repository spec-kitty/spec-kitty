"""Tests for m_unify_charter_activation (WP07, T023/T024/T025, FR-006/FR-007).

All tests call ``detect()``/``can_apply()``/``apply()`` directly on a
``UnifyCharterActivationMigration`` instance (not the upgrade pipeline), so
the ``target_version`` guard never interferes.

Fixtures are **constructed synthetic** projects, not the live repository:
the squad measured that this repo's own ``answers.yaml``/``config.yaml`` pair
has *zero* reverse skew today (config is a strict superset for every kind
except directives, which are exact 25-vs-25 parity differing only in ID
form). T025 requires a project with a genuine answers-only directive AND
answers-only paradigm to prove the zero-drop promotion path, so every test
here builds its own ``.kittify`` tree from real built-in artifact ids
(``010-specification-fidelity-requirement`` / ``DIRECTIVE_010``,
``domain-driven-design``) rather than mirroring this repo's own config.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.activation.pack_context import PackContext
from specify_cli.upgrade.migrations.m_unify_charter_activation import (
    UnifyCharterActivationMigration,
    load_default_pack_ids,
    resolve_selected_id_to_stem,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

# Real built-in artifacts used across fixtures (must exist in this repo's own
# doctrine tree — resolve_doctrine_root() is never mocked in this file, it
# always resolves the real packaged/dev doctrine content, matching the WP01
# test style).
_DIRECTIVE_010_STEM = "010-specification-fidelity-requirement"
_DIRECTIVE_010_CANONICAL = "DIRECTIVE_010"
_PARADIGM_DDD = "domain-driven-design"  # config stem == canonical id for paradigms
_MALFORMED_ID = "999-does-not-exist-anywhere"


def _yaml_safe() -> YAML:
    return YAML(typ="safe")


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _load(path: Path) -> dict:
    data = _yaml_safe().load(path.read_text(encoding="utf-8")) if path.exists() else {}
    return data or {}


def _kittify_config(tmp_path: Path) -> Path:
    return tmp_path / ".kittify" / "config.yaml"


def _answers_path(tmp_path: Path) -> Path:
    return tmp_path / ".kittify" / "charter" / "interview" / "answers.yaml"


# ---------------------------------------------------------------------------
# detect() / can_apply()
# ---------------------------------------------------------------------------


def test_detect_false_when_config_absent(tmp_path: Path) -> None:
    _write(_answers_path(tmp_path), f"selected_directives:\n  - {_DIRECTIVE_010_CANONICAL}\n")
    m = UnifyCharterActivationMigration()
    assert m.detect(tmp_path) is False


def test_detect_false_when_answers_absent(tmp_path: Path) -> None:
    _write(_kittify_config(tmp_path), "activated_directives: []\n")
    m = UnifyCharterActivationMigration()
    assert m.detect(tmp_path) is False


def test_detect_false_when_no_skew(tmp_path: Path) -> None:
    """Answers and config already agree (post ID-form normalization) — nothing to promote."""
    _write(
        _kittify_config(tmp_path),
        f"activated_directives:\n  - {_DIRECTIVE_010_STEM}\n",
    )
    _write(
        _answers_path(tmp_path),
        f"selected_directives:\n  - {_DIRECTIVE_010_CANONICAL}\n",
    )
    m = UnifyCharterActivationMigration()
    assert m.detect(tmp_path) is False, (
        "Same directive in canonical form (answers) vs stem form (config) is "
        "exact parity, not a skew — must not be misdetected as answers-only."
    )


def test_detect_true_on_answers_only_directive_and_paradigm(tmp_path: Path) -> None:
    """T025 constructed synthetic skew: detect() sees the promotable set."""
    _write(_kittify_config(tmp_path), "activated_directives:\n  - 001-architectural-integrity-standard\n")
    _write(
        _answers_path(tmp_path),
        "selected_directives:\n"
        "  - 001-architectural-integrity-standard\n"
        f"  - {_DIRECTIVE_010_CANONICAL}\n"
        f"selected_paradigms:\n  - {_PARADIGM_DDD}\n",
    )
    m = UnifyCharterActivationMigration()
    assert m.detect(tmp_path) is True


def test_can_apply_mirrors_detect(tmp_path: Path) -> None:
    m = UnifyCharterActivationMigration()
    ok, reason = m.can_apply(tmp_path)
    assert ok is False
    assert reason

    _write(_kittify_config(tmp_path), "activated_directives: []\n")
    _write(_answers_path(tmp_path), f"selected_directives:\n  - {_DIRECTIVE_010_CANONICAL}\n")
    ok2, reason2 = m.can_apply(tmp_path)
    assert ok2 is True
    assert reason2 == ""


# ---------------------------------------------------------------------------
# apply() — T025 zero-drop promotion (directive + paradigm)
# ---------------------------------------------------------------------------


def test_apply_promotes_answers_only_directive_and_paradigm_zero_drop(tmp_path: Path) -> None:
    """The T025 fixture: an answers-only directive AND paradigm are both promoted, nothing dropped."""
    _write(
        _kittify_config(tmp_path),
        "activated_directives:\n  - 001-architectural-integrity-standard\n"
        "activated_paradigms:\n  - structured-prompt-driven-development\n",
    )
    _write(
        _answers_path(tmp_path),
        "selected_directives:\n"
        "  - 001-architectural-integrity-standard\n"
        f"  - {_DIRECTIVE_010_CANONICAL}\n"  # answers-only, canonical form
        "selected_paradigms:\n"
        "  - structured-prompt-driven-development\n"
        f"  - {_PARADIGM_DDD}\n",  # answers-only
    )

    m = UnifyCharterActivationMigration()
    result = m.apply(tmp_path)

    assert result.success is True
    data = _load(_kittify_config(tmp_path))

    # Zero drop: the pre-existing entries survive.
    assert "001-architectural-integrity-standard" in data["activated_directives"]
    assert "structured-prompt-driven-development" in data["activated_paradigms"]
    # Both answers-only artefacts promoted (directive resolved canonical -> stem).
    assert _DIRECTIVE_010_STEM in data["activated_directives"]
    assert _PARADIGM_DDD in data["activated_paradigms"]
    assert len(data["activated_directives"]) == 2
    assert len(data["activated_paradigms"]) == 2


def test_apply_dry_run_writes_nothing(tmp_path: Path) -> None:
    config_path = _kittify_config(tmp_path)
    _write(config_path, "activated_directives:\n  - 001-architectural-integrity-standard\n")
    _write(_answers_path(tmp_path), f"selected_directives:\n  - {_DIRECTIVE_010_CANONICAL}\n")
    before = config_path.read_bytes()

    m = UnifyCharterActivationMigration()
    result = m.apply(tmp_path, dry_run=True)

    assert result.success is True
    assert config_path.read_bytes() == before


def test_apply_is_idempotent(tmp_path: Path) -> None:
    _write(_kittify_config(tmp_path), "activated_directives:\n  - 001-architectural-integrity-standard\n")
    _write(_answers_path(tmp_path), f"selected_directives:\n  - {_DIRECTIVE_010_CANONICAL}\n")

    m = UnifyCharterActivationMigration()
    first = m.apply(tmp_path)
    assert first.success is True
    second = m.apply(tmp_path)
    assert second.success is True

    data = _load(_kittify_config(tmp_path))
    assert data["activated_directives"].count(_DIRECTIVE_010_STEM) == 1


def test_apply_no_op_when_nothing_to_promote(tmp_path: Path) -> None:
    _write(_kittify_config(tmp_path), f"activated_directives:\n  - {_DIRECTIVE_010_STEM}\n")
    _write(_answers_path(tmp_path), f"selected_directives:\n  - {_DIRECTIVE_010_CANONICAL}\n")

    m = UnifyCharterActivationMigration()
    result = m.apply(tmp_path)

    assert result.success is True
    assert result.changes_made == ["No answers-only selections to promote"]


def test_apply_no_op_when_config_absent(tmp_path: Path) -> None:
    _write(_answers_path(tmp_path), f"selected_directives:\n  - {_DIRECTIVE_010_CANONICAL}\n")
    m = UnifyCharterActivationMigration()
    result = m.apply(tmp_path)
    assert result.success is True
    assert "config.yaml" in result.changes_made[0]


def test_apply_no_op_when_answers_absent(tmp_path: Path) -> None:
    _write(_kittify_config(tmp_path), "activated_directives: []\n")
    m = UnifyCharterActivationMigration()
    result = m.apply(tmp_path)
    assert result.success is True
    assert "answers.yaml" in result.changes_made[0]


def test_apply_reports_unresolved_id_without_failing(tmp_path: Path) -> None:
    """A malformed/stale answers id is skipped (warned), not dropped silently or fatal."""
    _write(_kittify_config(tmp_path), "activated_directives:\n  - 001-architectural-integrity-standard\n")
    _write(
        _answers_path(tmp_path),
        f"selected_directives:\n  - 001-architectural-integrity-standard\n  - {_MALFORMED_ID}\n",
    )

    m = UnifyCharterActivationMigration()
    result = m.apply(tmp_path)

    assert result.success is True
    assert any(_MALFORMED_ID in w for w in result.warnings)


# ---------------------------------------------------------------------------
# LAND-BLOCKER — absent-key built-in preservation at the real call site
# ---------------------------------------------------------------------------


def test_apply_absent_key_preserves_real_builtins_not_bare_list(tmp_path: Path) -> None:
    """Reviewer caveat: promoting into an absent activated_directives key must
    materialize the REAL shipped built-in set (from packs/default.yaml via
    load_default_pack_ids()), not just the newly-promoted answers-only id.

    Regression guard for the exact WP06 LAND-BLOCKER, exercised through this
    migration's real call site (not the primitive in isolation).
    """
    # No 'activated_directives' key at all in config.yaml (absent-key state).
    _write(_kittify_config(tmp_path), "vcs:\n  type: git\n")
    _write(_answers_path(tmp_path), f"selected_directives:\n  - {_DIRECTIVE_010_CANONICAL}\n")

    m = UnifyCharterActivationMigration()
    result = m.apply(tmp_path)
    assert result.success is True

    data = _load(_kittify_config(tmp_path))
    committed = data["activated_directives"]

    real_builtins = load_default_pack_ids().get("activated_directives", [])
    assert real_builtins, "sanity: packs/default.yaml must ship a non-empty built-in directive set"
    assert committed != [_DIRECTIVE_010_STEM], (
        "must not collapse to a bare list containing only the promoted id"
    )
    assert set(real_builtins).issubset(set(committed))
    assert _DIRECTIVE_010_STEM in committed

    # Cross-check via the real three-state resolver (PackContext), matching
    # the WP06 primitive test's own regression style.
    ctx = PackContext.from_config(tmp_path)
    assert ctx.activated_directives is not None
    for builtin_id in real_builtins:
        assert builtin_id in ctx.activated_directives
    assert _DIRECTIVE_010_STEM in ctx.activated_directives


# ---------------------------------------------------------------------------
# resolve_selected_id_to_stem / load_default_pack_ids — unit coverage
# ---------------------------------------------------------------------------


def test_resolve_selected_id_to_stem_already_stem() -> None:
    from charter.activation.catalog import resolve_doctrine_root
    from charter.offering.artifact_kinds import ArtifactKind

    doctrine_root = resolve_doctrine_root()
    stem = resolve_selected_id_to_stem(
        ArtifactKind.DIRECTIVE, _DIRECTIVE_010_STEM, doctrine_root=doctrine_root
    )
    assert stem == _DIRECTIVE_010_STEM


def test_resolve_selected_id_to_stem_canonical_form() -> None:
    from charter.activation.catalog import resolve_doctrine_root
    from charter.offering.artifact_kinds import ArtifactKind

    doctrine_root = resolve_doctrine_root()
    stem = resolve_selected_id_to_stem(
        ArtifactKind.DIRECTIVE, _DIRECTIVE_010_CANONICAL, doctrine_root=doctrine_root
    )
    assert stem == _DIRECTIVE_010_STEM


def test_resolve_selected_id_to_stem_unresolvable_returns_none() -> None:
    from charter.activation.catalog import resolve_doctrine_root
    from charter.offering.artifact_kinds import ArtifactKind

    doctrine_root = resolve_doctrine_root()
    stem = resolve_selected_id_to_stem(
        ArtifactKind.DIRECTIVE, _MALFORMED_ID, doctrine_root=doctrine_root
    )
    assert stem is None


def test_load_default_pack_ids_matches_shipped_default_yaml() -> None:
    ids = load_default_pack_ids()
    assert "activated_directives" in ids
    assert _DIRECTIVE_010_STEM in ids["activated_directives"]
    assert "activated_paradigms" in ids
    assert _PARADIGM_DDD in ids["activated_paradigms"]


# ---------------------------------------------------------------------------
# charter.activation.default_pack.load_default_pack_activation_ids — shared-loader
# coverage (squad finding #2530: org_charter.py's ``_load_default_pack_ids``
# and this migration's ``load_default_pack_ids`` were near-identical
# independent readers of the same ``src/charter/activation/packs/default.yaml`` file;
# both now delegate to this one canonical charter-layer helper).
# ---------------------------------------------------------------------------


def test_load_default_pack_ids_is_a_pure_reexport_of_shared_helper() -> None:
    """This migration's public ``load_default_pack_ids`` name is kept for
    backward compatibility (``interview.py`` and this file both import it
    from here) but must carry no independent implementation — it must
    delegate to the shared ``charter.activation.default_pack`` loader verbatim."""
    from charter.activation.default_pack import load_default_pack_activation_ids

    assert load_default_pack_ids() == load_default_pack_activation_ids()


def test_load_default_pack_activation_ids_returns_real_per_kind_builtin_stems() -> None:
    """The shared helper returns the real per-kind built-in stem sets from
    the shipped ``src/charter/activation/packs/default.yaml`` — every one of the 8
    charter activation kinds ships a non-empty built-in set, and spot-checked
    ids are the config-stem form (not the canonical ``id:`` form)."""
    from charter.activation.default_pack import load_default_pack_activation_ids

    ids = load_default_pack_activation_ids()

    for kind_key in (
        "activated_directives",
        "activated_tactics",
        "activated_styleguides",
        "activated_toolguides",
        "activated_paradigms",
        "activated_procedures",
        "activated_agent_profiles",
        "activated_mission_step_contracts",
    ):
        assert kind_key in ids and ids[kind_key], (
            f"shipped default.yaml must ship a non-empty built-in set for {kind_key}"
        )

    assert _DIRECTIVE_010_STEM in ids["activated_directives"]
    assert _DIRECTIVE_010_CANONICAL not in ids["activated_directives"], (
        "default.yaml ships config-stem ids, not canonical id: form"
    )
    assert _PARADIGM_DDD in ids["activated_paradigms"]


def test_load_default_pack_activation_ids_missing_file_returns_empty(tmp_path: Path) -> None:
    """An absent ``packs/default.yaml`` under the supplied root degrades to
    ``{}`` rather than raising -- callers treat that as "no real default
    available" (see the WP06 absent-key LAND-BLOCKER note)."""
    from charter.activation.default_pack import load_default_pack_activation_ids

    assert load_default_pack_activation_ids(charter_pkg_root=tmp_path) == {}


def test_load_default_pack_activation_ids_filters_non_list_values(tmp_path: Path) -> None:
    """Only list-valued top-level keys are returned -- a scalar/mapping key
    (e.g. a future ``schema_version:`` entry) is silently excluded rather
    than raising, matching the pre-dedup behaviour of both original readers."""
    from charter.activation.default_pack import load_default_pack_activation_ids

    packs_dir = tmp_path / "packs"
    packs_dir.mkdir(parents=True)
    (packs_dir / "default.yaml").write_text(
        "schema_version: 1\n"
        "activated_directives:\n"
        "  - 001-architectural-integrity-standard\n",
        encoding="utf-8",
    )

    ids = load_default_pack_activation_ids(charter_pkg_root=tmp_path)

    assert ids == {"activated_directives": ["001-architectural-integrity-standard"]}


def test_ambiguous_answer_is_reported_without_dropping_resolvable_sibling(monkeypatch: pytest.MonkeyPatch) -> None:
    from charter.activation.catalog import resolve_doctrine_root
    from charter.activation.kind_vocabulary import ArtifactKind, UnrepresentableDirectiveIdError
    from specify_cli.upgrade.migrations import m_unify_charter_activation as migration

    original = migration.resolve_selected_id_to_stem

    def resolve_with_ambiguity(kind: ArtifactKind, raw_id: str, *, doctrine_root: Path) -> str | None:
        if raw_id == "AMBIGUOUS-POLICY":
            raise UnrepresentableDirectiveIdError("Ambiguous policy filename")
        return original(kind, raw_id, doctrine_root=doctrine_root)

    monkeypatch.setattr(migration, "resolve_selected_id_to_stem", resolve_with_ambiguity)
    stems, unresolved = migration._answers_only_ids_for_kind(
        ArtifactKind.DIRECTIVE,
        answers_data={"selected_directives": ["AMBIGUOUS-POLICY", _DIRECTIVE_010_CANONICAL]},
        config_data={"activated_directives": []},
        doctrine_root=resolve_doctrine_root(),
    )
    assert stems == [_DIRECTIVE_010_STEM]
    assert unresolved == ["AMBIGUOUS-POLICY"]
