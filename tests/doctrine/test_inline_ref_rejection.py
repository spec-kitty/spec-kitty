"""Negative-fixture suite asserting the per-kind validators reject any YAML
that still carries forbidden inline reference fields.

Covers the contract in
``kitty-specs/excise-doctrine-curation-and-inline-references-01KP54J6/contracts/validator-rejection-error.schema.json``.

The migration hint emitted by :class:`InlineReferenceRejectedError` must
match the schema's regex pattern::

    ^Remove .+ from YAML; add edge \\{source: .+, target: .+, relation: requires\\}
     to packs/built-in/<kind>.graph.yaml$

The trailing path is the per-kind DRG fragment for the *source* artifact's
kind -- the file the operator actually has to open. Naming the pre-#2680
monolith sent them to a path that is not on disk (mission
``doctrine-silence-guards-01KYFV7Q`` WP07, FR-008); mission
``relocate-builtin-doctrine-packs-01KYT87F`` then moved the shipped fragments
from ``src/charter/offering/`` to ``packs/built-in/``, so the followable path is now
under the pack root.

The hint uses the actual ``DRGEdge`` schema (``source``/``target``/``relation``)
and the ``requires`` relation -- the ``Relation`` enum does not contain
``uses``, so the earlier ``kind: uses`` text pointed operators at an
impossible edit.

Eight cases total: 7 per-kind top-level fixtures + 1 procedures step-level
fixture.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import pytest

from charter.offering.agent_profiles.validation import reject_agent_profile_inline_refs
from charter.offering.directives.validation import reject_directive_inline_refs
from charter.offering.paradigms.validation import reject_paradigm_inline_refs
from charter.offering.procedures.validation import reject_procedure_inline_refs
from charter.offering.shared.exceptions import InlineReferenceRejectedError
from charter.offering.styleguides.validation import reject_styleguide_inline_refs
from charter.offering.tactics.validation import reject_tactic_inline_refs
from charter.offering.toolguides.validation import reject_toolguide_inline_refs

#: Matches ``migration_hint`` per the JSON schema.

pytestmark = [pytest.mark.doctrine, pytest.mark.fast]

HINT_PATTERN = re.compile(
    r"^Remove .+ from YAML; add edge "
    r"\{source: .+, target: .+, relation: requires\} "
    r"to packs/built-in/[a-z_]+\.graph\.yaml$"
)

#: Registry of (reject_fn, artifact_kind, sample_data_factory) entries for each
#: per-kind validator plus the procedures step-level case.


def _make_data_with_field(artifact_id: str, forbidden_field: str) -> dict[str, Any]:
    return {"id": artifact_id, forbidden_field: ["target-1", "target-2"]}


@pytest.mark.parametrize(
    "reject_fn, artifact_kind, forbidden_field",
    [
        (reject_directive_inline_refs, "directive", "tactic_refs"),
        (reject_tactic_inline_refs, "tactic", "paradigm_refs"),
        (reject_procedure_inline_refs, "procedure", "applies_to"),
        (reject_paradigm_inline_refs, "paradigm", "tactic_refs"),
        (reject_styleguide_inline_refs, "styleguide", "applies_to"),
        (reject_toolguide_inline_refs, "toolguide", "tactic_refs"),
        (reject_agent_profile_inline_refs, "agent_profile", "applies_to"),
    ],
)
def test_top_level_inline_ref_is_rejected(
    reject_fn: Any,
    artifact_kind: str,
    forbidden_field: str,
    tmp_path: Any,
) -> None:
    """Every per-kind validator rejects top-level inline reference fields
    with a structured :class:`InlineReferenceRejectedError`."""
    artifact_id = f"sample-{artifact_kind}"
    data = _make_data_with_field(artifact_id, forbidden_field)
    file_path = str(tmp_path / f"{artifact_id}.{artifact_kind}.yaml")

    with pytest.raises(InlineReferenceRejectedError) as excinfo:
        reject_fn(data, file_path=file_path)

    err = excinfo.value
    assert err.file_path == file_path
    assert err.forbidden_field == forbidden_field
    assert err.artifact_kind == artifact_kind
    assert HINT_PATTERN.match(err.migration_hint), (
        f"migration_hint {err.migration_hint!r} does not match schema regex"
    )
    # The hint embeds the artifact id so operators can locate the source quickly.
    assert f"{artifact_kind}:{artifact_id}" in err.migration_hint


def test_procedure_step_level_tactic_refs_rejected(tmp_path: Any) -> None:
    """A procedure YAML with ``steps[i].tactic_refs`` must be rejected with a
    structured error (FR-008 step-level scan requirement).

    Without this scan, step-level ``tactic_refs`` would fall through to
    Pydantic's generic ``extra_forbidden`` error -- valid rejection but
    missing the migration hint the spec requires.
    """
    data: dict[str, Any] = {
        "id": "my-procedure",
        "steps": [
            {"title": "step-0", "body": "..."},
            {"title": "step-1", "tactic_refs": ["tactic-a"]},
        ],
    }
    file_path = str(tmp_path / "my-procedure.procedure.yaml")

    with pytest.raises(InlineReferenceRejectedError) as excinfo:
        reject_procedure_inline_refs(data, file_path=file_path)

    err = excinfo.value
    assert err.artifact_kind == "procedure"
    assert err.forbidden_field == "tactic_refs"
    assert err.file_path == file_path
    assert HINT_PATTERN.match(err.migration_hint), (
        f"migration_hint {err.migration_hint!r} does not match schema regex"
    )
    assert "procedure:my-procedure" in err.migration_hint


def test_procedure_step_level_paradigm_refs_rejected(tmp_path: Any) -> None:
    """Step-level ``paradigm_refs`` is also rejected with the structured error."""
    data: dict[str, Any] = {
        "id": "my-procedure",
        "steps": [{"title": "s0", "paradigm_refs": ["p1"]}],
    }
    with pytest.raises(InlineReferenceRejectedError) as excinfo:
        reject_procedure_inline_refs(
            data, file_path=str(tmp_path / "p.procedure.yaml")
        )
    assert excinfo.value.forbidden_field == "paradigm_refs"


def test_clean_payload_passes_without_raising(tmp_path: Any) -> None:
    """A YAML without any forbidden inline fields does not raise."""
    data: dict[str, Any] = {"id": "clean-directive", "summary": "no inline refs"}
    reject_directive_inline_refs(
        data, file_path=str(tmp_path / "clean.directive.yaml")
    )


def test_all_three_forbidden_fields_are_flagged() -> None:
    """Verify each of the three forbidden field names is rejected on at
    least one per-kind validator, satisfying the schema enum coverage."""
    flagged: set[str] = set()
    for data, reject_fn in [
        ({"id": "a", "tactic_refs": ["x"]}, reject_directive_inline_refs),
        ({"id": "b", "paradigm_refs": ["y"]}, reject_tactic_inline_refs),
        ({"id": "c", "applies_to": ["z"]}, reject_styleguide_inline_refs),
    ]:
        try:
            reject_fn(data, file_path="/nonexistent/fake.yaml")
        except InlineReferenceRejectedError as err:
            flagged.add(err.forbidden_field)
    assert flagged == {"tactic_refs", "paradigm_refs", "applies_to"}


# ---------------------------------------------------------------------------
# Integration tests: the live repository ``_load`` paths must raise
# :class:`InlineReferenceRejectedError`, not silently warn with a generic
# Pydantic ``extra_forbidden``. Closes FR-008 Scenario 4 ("The loader does
# not silently ignore the field.").
# ---------------------------------------------------------------------------


def _write_yaml(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_directive_repository_rejects_project_inline_refs(tmp_path: Path) -> None:
    """Loading a project directive that carries ``applies_to:`` must raise
    :class:`InlineReferenceRejectedError` at _load time, not warn.
    """
    from charter.offering.directives.repository import DirectiveRepository

    project_dir = tmp_path / "directives"
    _write_yaml(
        project_dir / "my-directive.directive.yaml",
        "id: MY-DIRECTIVE\ntitle: demo\nintent: demo intent\napplies_to: [software-dev]\n",
    )

    with pytest.raises(InlineReferenceRejectedError) as excinfo:
        DirectiveRepository(
            built_in_dir=tmp_path / "nonexistent_shipped",
            project_dir=project_dir,
        )
    err = excinfo.value
    assert err.artifact_kind == "directive"
    assert err.forbidden_field == "applies_to"
    assert HINT_PATTERN.match(err.migration_hint)


def test_tactic_repository_rejects_shipped_inline_refs(tmp_path: Path) -> None:
    """Shipped tactics with forbidden inline refs must raise at load time."""
    from charter.offering.tactics.repository import TacticRepository

    built_in_dir = tmp_path / "tactics_shipped"
    _write_yaml(
        built_in_dir / "bad.tactic.yaml",
        "id: bad-tactic\nname: bad\npurpose: test\nparadigm_refs: [p1]\n",
    )

    with pytest.raises(InlineReferenceRejectedError) as excinfo:
        TacticRepository(built_in_dir=built_in_dir, project_dir=None)
    assert excinfo.value.artifact_kind == "tactic"
    assert excinfo.value.forbidden_field == "paradigm_refs"


def test_paradigm_repository_rejects_inline_refs(tmp_path: Path) -> None:
    from charter.offering.paradigms.repository import ParadigmRepository

    built_in_dir = tmp_path / "paradigms_shipped"
    _write_yaml(
        built_in_dir / "bad.paradigm.yaml",
        "id: bad-paradigm\nname: bad\nsummary: test\ntactic_refs: [t1]\n",
    )

    with pytest.raises(InlineReferenceRejectedError) as excinfo:
        ParadigmRepository(built_in_dir=built_in_dir, project_dir=None)
    assert excinfo.value.artifact_kind == "paradigm"
    assert excinfo.value.forbidden_field == "tactic_refs"


def test_styleguide_repository_rejects_inline_refs(tmp_path: Path) -> None:
    from charter.offering.styleguides.repository import StyleguideRepository

    built_in_dir = tmp_path / "styleguides_shipped"
    _write_yaml(
        built_in_dir / "bad.styleguide.yaml",
        "id: bad-style\ntitle: bad\nprinciples: [x]\napplies_to: [y]\n",
    )

    with pytest.raises(InlineReferenceRejectedError) as excinfo:
        StyleguideRepository(built_in_dir=built_in_dir, project_dir=None)
    assert excinfo.value.artifact_kind == "styleguide"
    assert excinfo.value.forbidden_field == "applies_to"


def test_toolguide_repository_rejects_inline_refs(tmp_path: Path) -> None:
    from charter.offering.toolguides.repository import ToolguideRepository

    built_in_dir = tmp_path / "toolguides_shipped"
    _write_yaml(
        built_in_dir / "bad.toolguide.yaml",
        "id: bad-tool\ntitle: bad\nsummary: x\ntactic_refs: [t1]\n",
    )

    with pytest.raises(InlineReferenceRejectedError) as excinfo:
        ToolguideRepository(built_in_dir=built_in_dir, project_dir=None)
    assert excinfo.value.artifact_kind == "toolguide"
    assert excinfo.value.forbidden_field == "tactic_refs"


def test_procedure_repository_rejects_top_level_inline_refs(tmp_path: Path) -> None:
    from charter.offering.procedures.repository import ProcedureRepository

    built_in_dir = tmp_path / "procedures_shipped"
    _write_yaml(
        built_in_dir / "bad.procedure.yaml",
        "id: bad-proc\nname: bad\npurpose: x\nsteps: []\napplies_to: [y]\n",
    )

    with pytest.raises(InlineReferenceRejectedError) as excinfo:
        ProcedureRepository(built_in_dir=built_in_dir, project_dir=None)
    assert excinfo.value.artifact_kind == "procedure"
    assert excinfo.value.forbidden_field == "applies_to"


def test_procedure_repository_rejects_step_level_inline_refs(tmp_path: Path) -> None:
    """FR-008 step-level scan: ``steps[*].tactic_refs`` rejected with the
    structured :class:`InlineReferenceRejectedError`, not Pydantic's generic
    ``extra_forbidden`` warning.
    """
    from charter.offering.procedures.repository import ProcedureRepository

    built_in_dir = tmp_path / "procedures_shipped"
    _write_yaml(
        built_in_dir / "bad-step.procedure.yaml",
        "id: bad-step-proc\n"
        "name: bad-step\n"
        "purpose: x\n"
        "steps:\n"
        "  - title: step-0\n"
        "    body: ok\n"
        "  - title: step-1\n"
        "    tactic_refs: [t1]\n",
    )

    with pytest.raises(InlineReferenceRejectedError) as excinfo:
        ProcedureRepository(built_in_dir=built_in_dir, project_dir=None)
    err = excinfo.value
    assert err.artifact_kind == "procedure"
    assert err.forbidden_field == "tactic_refs"
    assert HINT_PATTERN.match(err.migration_hint)


def test_agent_profile_repository_surfaces_inline_refs_as_skip(tmp_path: Path) -> None:
    """Agent-profile inline-ref rejection is a *surfaced skip*, not a raise (WP01).

    Unlike the other doctrine repositories (which still propagate the raise so
    the author fixes the YAML), the agent-profile loader catches the inline-ref
    rejection in ``_load_layer`` and records it via ``skipped_profiles()`` so
    valid sibling profiles keep loading and the doctor ``doctor charter-packs`` health
    surface can report ``healthy=false`` without blanking the surface (#1584
    false-healthy class). A general caller never silently returns a wrong/empty
    result — the skip is loud and carries the readable error (operator
    preference: loud over hidden).
    """
    from charter.offering.agent_profiles.repository import AgentProfileRepository

    built_in_dir = tmp_path / "agent_profiles_shipped"
    # agent profile YAMLs use kebab-case keys; the rejection scan is for
    # extra top-level fields, so ``applies_to`` is unambiguous.
    _write_yaml(
        built_in_dir / "bad.agent.yaml",
        "profile-id: bad-profile\n"
        "role: implementer\n"
        "applies_to: [software-dev]\n",
    )

    # The constructor no longer raises; the invalid profile becomes a skip.
    repo = AgentProfileRepository(built_in_dir=built_in_dir, project_dir=None)

    skipped = repo.skipped_profiles()
    bad = [s for s in skipped if s.path.endswith("bad.agent.yaml")]
    assert bad, "inline-ref profile must be surfaced as a skip"
    skip = bad[0]
    # The load-layer skip has the YAML in hand, so profile_id is populated.
    assert skip.profile_id == "bad-profile"
    # The error summary names the forbidden field + a migration hint.
    assert "applies_to" in skip.error_summary
    assert "graph.yaml" in skip.error_summary
    # The invalid profile is not loaded as a usable profile.
    assert repo.get("bad-profile") is None
