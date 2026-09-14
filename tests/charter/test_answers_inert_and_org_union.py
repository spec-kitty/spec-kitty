"""WP04 (T014/T015/T016): answers-inert + org-feeder union regression tests.

``org_charter.apply_org_charter_to_interview`` used to mutate only
``interview_data.selected_<kind>``, which fed the charter compiler before
WP02. Once the compiler switched to reading ``config.activated_*``
exclusively (WP02, FR-003), that mutation became inert -- org-required
artefacts would silently stop reaching the compiled reference set unless the
same ids were ALSO promoted into ``.kittify/config.yaml``.

This module pins:

- **T014**: every ``required_<kind>`` (all 8 kinds -- not just directives/
  paradigms) unions into ``config.activated_<kind>`` via
  :func:`charter.activation.activation_engine.promote_activations`, including the
  absent-key LAND-BLOCKER (promoting into a previously-absent key must
  preserve every built-in id, never write a bare restrictive list).
- **T015 (SC-004)**: editing ``interview.selected_*`` (the answers surface)
  without touching ``config.activated_*`` has NO effect on the compiled
  reference set -- answers are retired as an activation source.
- **T016**: the promotion writes ONLY ``.kittify/config.yaml`` -- never
  ``governance.yaml`` (the third ledger ``charter.offering.selected_*`` reads) or any
  file :func:`charter.offering.spdd_reasons.activation.is_spdd_reasons_active`
  consults.
"""

from __future__ import annotations

import dataclasses
import textwrap
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from charter.activation.compiler import compile_charter
from charter.activation.interview import CharterInterview, default_interview
from charter.activation.pack_context import PackContext
from charter.offering.service import DoctrineService
from specify_cli.doctrine.org_charter import (
    REQUIRED_KIND_FIELDS,
    apply_org_charter_to_interview,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast, pytest.mark.doctrine]

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PACK_PATH = REPO_ROOT / "src" / "charter" / "activation" / "packs" / "default.yaml"


def _safe_yaml() -> YAML:
    y = YAML(typ="safe")
    return y


def _roundtrip_yaml() -> YAML:
    y = YAML()
    y.preserve_quotes = True
    return y


class _Interview:
    """Minimal interview shape declaring every Mission B selection field.

    Mirrors ``tests/specify_cli/doctrine/test_org_charter_union.py`` -- a
    real :class:`CharterInterview` is a frozen dataclass that only declares
    ``selected_paradigms``/``selected_directives``/``selected_tactics``, so
    it cannot even receive the other 5 kinds' ``selected_<kind>`` mutation
    (the ``AttributeError``/``TypeError`` guard in
    ``apply_org_charter_to_interview`` skips it). This shape exercises the
    full 8-kind union path exactly like the interactive interview loop's
    pre-WP01 legacy fallback.
    """

    def __init__(self) -> None:
        self.answers: dict[str, str] = {}
        for kind in REQUIRED_KIND_FIELDS:
            setattr(self, f"selected_{kind}", [])


def _write_org_charter(pack_dir: Path, body: str) -> None:
    pack_dir.mkdir(parents=True, exist_ok=True)
    (pack_dir / "org-charter.yaml").write_text(textwrap.dedent(body).strip() + "\n", encoding="utf-8")


def _write_consumer_config(
    consumer: Path,
    packs: list[tuple[str, Path]],
    *,
    preseed: dict[str, list[str]] | None = None,
) -> Path:
    """Write ``.kittify/config.yaml`` with an org-pack registry entry and
    optional pre-existing ``activated_<kind>`` lists."""
    config_dir = consumer / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    lines = ["doctrine:", "  org:", "    packs:"]
    for name, path in packs:
        lines.append(f"      - name: {name}")
        lines.append(f"        local_path: {path}")
    for key, ids in (preseed or {}).items():
        lines.append(f"{key}:")
        for artifact_id in ids:
            lines.append(f"  - {artifact_id}")
    config_path = config_dir / "config.yaml"
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return config_path


def _write_all_kinds_empty_config(consumer: Path) -> Path:
    """Explicit ``[]`` for every kind -- narrows away "all built-ins active"
    so a leaked answers-sourced id would be observable (mirrors
    ``tests/charter/test_activate_resolves_no_answers_edit.py``'s fixture).
    """
    config_dir = consumer / ".kittify"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.yaml"
    config_path.write_text(
        "activated_directives: []\n"
        "activated_tactics: []\n"
        "activated_styleguides: []\n"
        "activated_toolguides: []\n"
        "activated_paradigms: []\n"
        "activated_procedures: []\n"
        "activated_agent_profiles: []\n"
        "activated_mission_step_contracts: []\n"
        "mission_type_activations:\n"
        "  - software-dev\n",
        encoding="utf-8",
    )
    return config_path


def _read_config_yaml(consumer: Path) -> dict:
    text = (consumer / ".kittify" / "config.yaml").read_text(encoding="utf-8")
    data = _safe_yaml().load(text)
    return data or {}


def _compile(project_root: Path, interview: CharterInterview):
    pack_context = PackContext.from_config(project_root)
    doctrine_service = DoctrineService()
    return compile_charter(
        mission=interview.mission,
        interview=interview,
        repo_root=project_root,
        doctrine_service=doctrine_service,
        pack_context=pack_context,
    )


# ---------------------------------------------------------------------------
# T014 -- org required_<kind> promoted into config.activated_<kind>
# ---------------------------------------------------------------------------


class TestOrgRequiredPromotedIntoConfig:
    """``apply_org_charter_to_interview`` writes ``config.yaml`` directly,
    for all 8 :data:`REQUIRED_KIND_FIELDS` kinds -- not just roots."""

    @pytest.mark.parametrize("kind", list(REQUIRED_KIND_FIELDS))
    def test_required_kind_promoted_into_config_activated(self, kind: str, tmp_path: Path) -> None:
        pack = tmp_path / "pack"
        _write_org_charter(
            pack,
            f"""
            schema_version: "1"
            org_name: "ATDD"
            required_{kind}:
              - org-required-1
            """,
        )
        consumer = tmp_path / "consumer"
        consumer.mkdir()
        yaml_key = f"activated_{kind}"
        _write_consumer_config(consumer, [("pack", pack)], preseed={yaml_key: ["project-pinned"]})

        interview = _Interview()
        messages = apply_org_charter_to_interview(interview, consumer)

        written = _read_config_yaml(consumer).get(yaml_key)
        assert written == ["project-pinned", "org-required-1"], f"required_{kind} must union into config.{yaml_key} (append-only, config-authority write path)"
        assert any(yaml_key in m for m in messages), f"apply_org_charter_to_interview must disclose the config-authority promotion for {yaml_key}"

    def test_promotion_is_idempotent_on_repeated_calls(self, tmp_path: Path) -> None:
        pack = tmp_path / "pack"
        _write_org_charter(
            pack,
            """
            schema_version: "1"
            required_directives:
              - org-required-directive
            """,
        )
        consumer = tmp_path / "consumer"
        consumer.mkdir()
        _write_consumer_config(
            consumer,
            [("pack", pack)],
            preseed={"activated_directives": ["project-pinned"]},
        )

        apply_org_charter_to_interview(_Interview(), consumer)
        apply_org_charter_to_interview(_Interview(), consumer)

        written = _read_config_yaml(consumer)["activated_directives"]
        assert written == ["project-pinned", "org-required-directive"], "re-running the org union twice must not duplicate the promoted id"

    def test_promotion_into_absent_config_key_preserves_builtins(self, tmp_path: Path) -> None:
        """LAND-BLOCKER guard (WP06): promoting ``required_directives`` into a
        previously-absent ``activated_directives`` key must NOT write a bare
        ``[org-required-directive]`` list -- it must materialize every
        built-in directive first (the real shipped default pack), preserving
        the absent-key "all built-ins active" three-state contract
        :meth:`charter.activation.pack_context.PackContext.from_config` depends on.
        """
        pack = tmp_path / "pack"
        _write_org_charter(
            pack,
            """
            schema_version: "1"
            required_directives:
              - org-required-directive
            """,
        )
        consumer = tmp_path / "consumer"
        consumer.mkdir()
        # No activated_<kind> keys at all -- the absent-key state under
        # test. ``mission_type_activations`` is preseeded (an unrelated
        # key) purely so the later ``PackContext.from_config`` round-trip
        # below doesn't hard-fail (WP04, C-A1) -- it has no bearing on the
        # absent-key ``activated_directives`` builtin-preservation
        # assertion this test exists to pin.
        _write_consumer_config(
            consumer,
            [("pack", pack)],
            preseed={"mission_type_activations": ["software-dev"]},
        )

        apply_org_charter_to_interview(_Interview(), consumer)

        written = _read_config_yaml(consumer).get("activated_directives")
        assert written is not None, "promotion into an absent key must materialize a list, not leave it absent"

        # Real built-in directive ids, loaded independently of the production
        # code under test, straight from the shipped pack -- this assertion
        # does not just restate the implementation.
        default_pack_raw = _safe_yaml().load(DEFAULT_PACK_PATH.read_text(encoding="utf-8"))
        builtin_directives = list(default_pack_raw["activated_directives"])
        assert len(builtin_directives) >= 15, "fixture assumption: the shipped default pack ships a real directive set"

        assert set(builtin_directives).issubset(set(written)), (
            "promoting an org-required directive into an absent config key must "
            "preserve every built-in directive -- dropping them would silently "
            "disable the project's baseline governance"
        )
        assert "org-required-directive" in written
        assert len(written) == len(builtin_directives) + 1, "the committed list must be exactly the built-ins plus the promoted id -- never a bare restrictive list"

        ctx = PackContext.from_config(consumer)
        assert ctx.activated_directives is not None
        assert "org-required-directive" in ctx.activated_directives
        for builtin_id in builtin_directives:
            assert builtin_id in ctx.activated_directives


# ---------------------------------------------------------------------------
# #2529 -- org required_<kind> id-form normalization (canonical -> stem)
# ---------------------------------------------------------------------------


class TestOrgRequiredIdFormNormalizedBeforePromotion:
    """Squad finding #2529: ``config.activated_<kind>`` stores config/file-
    stem ids and the derivation (:mod:`charter.activation.compiler`,
    :func:`~charter.activation.kind_vocabulary.resolve_artifact_urn`) reads stems --
    promoting an org-required id in its natural canonical ``id:`` form
    (e.g. ``DIRECTIVE_001``) verbatim writes a value the derivation can never
    match, crashing even for a built-in org-required directive.
    ``_promote_org_required_to_config`` now normalizes every id to stem form
    first, via the same ``resolve_config_id``-based two-direction resolution
    ``m_unify_charter_activation.resolve_selected_id_to_stem`` uses for
    ``answers.selected_<kind>``.
    """

    _DIRECTIVE_001_STEM = "001-architectural-integrity-standard"
    _DIRECTIVE_001_CANONICAL = "DIRECTIVE_001"

    def test_canonical_form_required_directive_promoted_as_stem(self, tmp_path: Path) -> None:
        pack = tmp_path / "pack"
        _write_org_charter(
            pack,
            f"""
            schema_version: "1"
            org_name: "ATDD"
            required_directives:
              - {self._DIRECTIVE_001_CANONICAL}
            """,
        )
        consumer = tmp_path / "consumer"
        consumer.mkdir()
        # A non-empty pinned preseed avoids the YAML null-vs-empty-list
        # ambiguity (an explicitly-empty preseed round-trips as a null
        # scalar, which the absent-key LAND-BLOCKER safety materializes
        # every built-in for -- orthogonal to what this test pins down).
        # ``mission_type_activations`` is preseeded so the ``PackContext.
        # from_config`` round-trip below doesn't hard-fail (WP04, C-A1);
        # it is unrelated to the directive-stem-normalization behavior
        # under test.
        _write_consumer_config(
            consumer,
            [("pack", pack)],
            preseed={
                "activated_directives": ["project-pinned"],
                "mission_type_activations": ["software-dev"],
            },
        )

        apply_org_charter_to_interview(_Interview(), consumer)

        written = _read_config_yaml(consumer).get("activated_directives")
        assert written == ["project-pinned", self._DIRECTIVE_001_STEM], (
            "an org-required id written in its natural canonical form "
            "(DIRECTIVE_001) must be promoted into config.activated_directives "
            "in config-STEM form -- the form config.yaml stores and the "
            "derivation (resolve_artifact_urn) reads"
        )

        # Round-trips through the real activation surface the compiler
        # consumes -- proves this is not just a string-shape assertion.
        ctx = PackContext.from_config(consumer)
        assert ctx.activated_directives is not None
        assert self._DIRECTIVE_001_STEM in ctx.activated_directives
        assert self._DIRECTIVE_001_CANONICAL not in ctx.activated_directives

    def test_stem_form_required_directive_is_idempotent(self, tmp_path: Path) -> None:
        """Already-stem input round-trips unchanged -- normalization is a
        no-op on the common case, not a mandatory rewrite (idempotent)."""
        pack = tmp_path / "pack"
        _write_org_charter(
            pack,
            f"""
            schema_version: "1"
            required_directives:
              - {self._DIRECTIVE_001_STEM}
            """,
        )
        consumer = tmp_path / "consumer"
        consumer.mkdir()
        _write_consumer_config(consumer, [("pack", pack)], preseed={"activated_directives": ["project-pinned"]})

        apply_org_charter_to_interview(_Interview(), consumer)

        written = _read_config_yaml(consumer).get("activated_directives")
        assert written == ["project-pinned", self._DIRECTIVE_001_STEM]

    def test_legacy_declared_directive_id_remains_readable(self) -> None:
        """#4185: old raw-ID activations remain readable; new producers write stems."""
        from charter.activation.catalog import resolve_doctrine_root
        from charter.activation.kind_vocabulary import resolve_artifact_urn
        from charter.offering.artifact_kinds import ArtifactKind

        doctrine_root = resolve_doctrine_root()
        expected = f"directive:{self._DIRECTIVE_001_CANONICAL}"
        assert resolve_artifact_urn(ArtifactKind.DIRECTIVE, self._DIRECTIVE_001_CANONICAL, doctrine_root=doctrine_root) == expected
        assert resolve_artifact_urn(ArtifactKind.DIRECTIVE, self._DIRECTIVE_001_STEM, doctrine_root=doctrine_root) == expected

    def test_unresolvable_required_id_passes_through_verbatim(self, tmp_path: Path) -> None:
        """An id that resolves in neither direction (not a known stem NOR a
        known canonical id) is promoted unchanged rather than dropped -- a
        malformed/unknown org-required id must fail loudly downstream at
        derivation, not vanish silently during promotion."""
        pack = tmp_path / "pack"
        _write_org_charter(
            pack,
            """
            schema_version: "1"
            required_directives:
              - 999-does-not-exist-anywhere
            """,
        )
        consumer = tmp_path / "consumer"
        consumer.mkdir()
        _write_consumer_config(consumer, [("pack", pack)], preseed={"activated_directives": ["project-pinned"]})

        apply_org_charter_to_interview(_Interview(), consumer)

        written = _read_config_yaml(consumer).get("activated_directives")
        assert written == ["project-pinned", "999-does-not-exist-anywhere"]


# ---------------------------------------------------------------------------
# T015 -- SC-004: answers.selected_* is inert for activation
# ---------------------------------------------------------------------------


class TestAnswersInertForActivation:
    def test_editing_selected_fields_has_no_effect_on_compiled_reference_set(self, tmp_path: Path) -> None:
        _write_all_kinds_empty_config(tmp_path)
        base_interview = default_interview(mission="software-dev")

        edited_interview = dataclasses.replace(
            base_interview,
            selected_directives=[
                *base_interview.selected_directives,
                "010-specification-fidelity-requirement",
            ],
            selected_paradigms=[*base_interview.selected_paradigms, "domain-driven-design"],
            selected_tactics=[*base_interview.selected_tactics, "acceptance-test-first"],
        )
        # Sanity: the edit actually happened on the answers surface.
        assert edited_interview.selected_directives != base_interview.selected_directives

        compiled_before = _compile(tmp_path, base_interview)
        compiled_after = _compile(tmp_path, edited_interview)

        ids_before = {reference.id for reference in compiled_before.references}
        ids_after = {reference.id for reference in compiled_after.references}
        assert ids_before == ids_after, "editing answers.selected_* without a config.activated_* change must have NO effect on the compiled reference set (SC-004)"

        # The edited ids specifically must not have leaked into the
        # config-sourced selection the compiler actually renders.
        assert "010-specification-fidelity-requirement" not in compiled_after.selected_directives
        assert "domain-driven-design" not in compiled_after.selected_paradigms
        assert "acceptance-test-first" not in compiled_after.selected_tactics
        # selected_* on the CompiledCharter itself is config-sourced, so it is
        # identical between the two compiles regardless of the answers edit
        # (the markdown body embeds a compile timestamp, so it is NOT
        # compared here -- the id-set and selected_* equality already prove
        # SC-004 without that incidental noise).
        assert compiled_before.selected_directives == compiled_after.selected_directives
        assert compiled_before.selected_paradigms == compiled_after.selected_paradigms
        assert compiled_before.selected_tactics == compiled_after.selected_tactics

    def test_config_activated_change_does_affect_the_compiled_reference_set(self, tmp_path: Path) -> None:
        """Control case: the SAME interview, but a real ``config.yaml``
        change, DOES change the compiled set -- proves the previous test
        isn't vacuously true because compilation is insensitive to everything.
        """
        _write_all_kinds_empty_config(tmp_path)
        interview = default_interview(mission="software-dev")
        ids_before = {r.id for r in _compile(tmp_path, interview).references}

        yaml = _roundtrip_yaml()
        config_path = tmp_path / ".kittify" / "config.yaml"
        data = yaml.load(config_path.read_text(encoding="utf-8"))
        data["activated_directives"] = ["010-specification-fidelity-requirement"]
        with config_path.open("w", encoding="utf-8") as fh:
            yaml.dump(data, fh)

        ids_after = {r.id for r in _compile(tmp_path, interview).references}
        assert ids_after != ids_before, "a real config.activated_* change must change the compiled reference set"


# ---------------------------------------------------------------------------
# T016 -- third ledger (governance.yaml charter.offering.selected_*) untouched
# ---------------------------------------------------------------------------


class TestThirdLedgerUntouched:
    """The org-union promotion (T014) writes ONLY ``.kittify/config.yaml``.

    ``governance.yaml`` (ledger C, read by
    :func:`charter.offering.spdd_reasons.activation.is_spdd_reasons_active`) is
    populated later by an unrelated pipeline stage (``charter generate`` /
    ``sync_charter``) -- this module must never create or edit it as a
    side effect of the interview pre-fill.
    """

    def test_apply_org_charter_does_not_touch_governance_yaml(self, tmp_path: Path) -> None:
        pack = tmp_path / "pack"
        _write_org_charter(
            pack,
            """
            schema_version: "1"
            required_directives:
              - org-required-directive
            required_styleguides:
              - org-required-styleguide
            """,
        )
        consumer = tmp_path / "consumer"
        consumer.mkdir()
        _write_consumer_config(consumer, [("pack", pack)])

        governance_path = consumer / ".kittify" / "charter" / "governance.yaml"
        answers_path = consumer / ".kittify" / "charter" / "interview" / "answers.yaml"

        apply_org_charter_to_interview(_Interview(), consumer)

        assert not governance_path.exists(), "apply_org_charter_to_interview must never write governance.yaml (the third ledger) -- only .kittify/config.yaml"
        assert not answers_path.exists(), "apply_org_charter_to_interview mutates an in-memory interview object only -- it must not write answers.yaml to disk"
