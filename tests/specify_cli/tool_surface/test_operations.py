"""Owner contract values: immutable observations, exact effects, no discovery."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, dataclass, replace
from hashlib import sha256  # noqa: TID251 - exact file-byte integrity fixtures, not charter semantic hashes.
from pathlib import Path
import subprocess
import sys

import pytest

from specify_cli.tool_surface.operations import (
    ApplyConsent,
    AssessmentInputs,
    Diagnostic,
    Disposition,
    FileState,
    InputObservation,
    OperationRoot,
    OwnerApplyResult,
    OwnerAssessment,
    OwnershipProof,
    PhysicalEffect,
    coalesce_effects,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _file(content: bytes = b"prepared", mode: int = 0o644) -> FileState:
    return FileState("file", sha256=sha256(content).hexdigest(), mode=mode)


def _effect(
    *, path: str = ".agents/skills/a/SKILL.md", action: str = "create", before: FileState = FileState("absent"), after: FileState | None = None
) -> PhysicalEffect:
    return PhysicalEffect(
        owner="commands",
        phase="surface_repair",
        root=OperationRoot("project", "project", Path("/project")),
        path=path,
        action=action,
        before=before,
        after=after if after is not None else _file(),
        reason="Missing managed command",
        ownership=(OwnershipProof("managed_path", "command catalog: exact a/SKILL.md"),),
        logical_owners=("codex",),
        surface_ids=("codex.a",),
    )


@pytest.mark.parametrize("path", ["", ".", "..", "../a", "a/../b", "/a", "C:/a", r"a\b", "a//b", "a/./b"])
def test_effect_rejects_non_normal_or_escaping_path(path: str) -> None:
    with pytest.raises(ValueError, match="relative path"):
        _effect(path=path)


@pytest.mark.parametrize(
    "action,before,after",
    [
        ("create", _file(), _file()),
        ("update", _file(), _file()),
        ("update", FileState("absent"), _file()),
        ("delete", FileState("absent"), FileState("absent")),
        ("replace", _file(), _file(b"other")),
        ("retarget", _file(), _file(b"other")),
        ("chmod", _file(), _file(b"other", 0o755)),
    ],
)
def test_action_requires_its_observable_transition(action: str, before: FileState, after: FileState) -> None:
    with pytest.raises(ValueError, match="action"):
        _effect(action=action, before=before, after=after)


@pytest.mark.parametrize(
    "action,before,after",
    [
        ("create", FileState("absent"), _file(mode=0o755)),
        ("create", FileState("absent"), FileState("directory", mode=0o755)),
        ("update", _file(), _file(b"other", 0o755)),
        ("delete", _file(), FileState("absent")),
        ("replace", FileState("symlink", target="../sentinel", mode=0o777), _file()),
        ("retarget", FileState("symlink", target="a", mode=0o777), FileState("symlink", target="b", mode=0o777)),
        ("chmod", _file(), _file(mode=0o755)),
    ],
)
def test_action_captures_one_net_transition(action: str, before: FileState, after: FileState) -> None:
    assert _effect(action=action, before=before, after=after).after == after


@pytest.mark.parametrize(
    "kind,digest,target,mode",
    [
        ("absent", None, None, 0o644),
        ("file", "not-a-hash", None, 0o644),
        ("file", "a" * 64, "other", 0o644),
        ("symlink", None, None, 0o777),
        ("directory", None, None, 4096),
        ("unknown", None, None, None),
    ],
)
def test_invalid_node_states_are_refused(kind: str, digest: str | None, target: str | None, mode: int | None) -> None:
    with pytest.raises(ValueError):
        FileState(kind, digest, target, mode)


@dataclass(frozen=True)
class _Prepared:
    rendered: bytes
    sampled_at: str


def test_assessment_retains_exact_preparation_and_observation() -> None:
    prepared = _Prepared(b'{"updated_at":"T1"}', "T1")
    observation = InputObservation("manifest", ("a" * 64, 123, "literal-link"))
    effect = _effect(after=_file(prepared.rendered))
    assessment = OwnerAssessment("commands", effect.root, effects=(effect,), prepared=prepared, inputs_fingerprint=(observation,))
    assert assessment.prepared is prepared
    assert assessment.inputs_fingerprint == (observation,)
    with pytest.raises(FrozenInstanceError):
        field_name = "complete"
        setattr(assessment, field_name, False)
    with pytest.raises(FrozenInstanceError):
        field_name = "sampled_at"
        setattr(prepared, field_name, "T2")


@pytest.mark.parametrize("payload", [[b"live"], {"config": []}, ([],), lambda: None])
def test_mutable_or_executable_owner_payload_is_refused(payload: object) -> None:
    with pytest.raises(TypeError, match="immutable"):
        OwnerAssessment("commands", _effect().root, prepared=payload)
    with pytest.raises(TypeError, match="immutable"):
        AssessmentInputs(_effect().root, projected=payload)


def test_mutable_nested_frozen_payload_is_refused() -> None:
    @dataclass(frozen=True)
    class Shell:
        live: list[str]

    with pytest.raises(TypeError, match="immutable"):
        InputObservation("config", Shell([]))


def test_empty_incomplete_assessment_is_not_successful_noop() -> None:
    diagnostic = Diagnostic("missing_provider", "commands", "error", "Required owner absent")
    assessment = OwnerAssessment("commands", _effect().root, complete=False, diagnostics=(diagnostic,))
    assert not assessment.complete
    assert not assessment.effects
    assert assessment.diagnostics == (diagnostic,)


def test_dedup_retains_all_owners_surfaces_and_proofs_under_permutation() -> None:
    codex = _effect()
    vibe = replace(codex, logical_owners=("vibe",), surface_ids=("vibe.a",), ownership=(OwnershipProof("manifest", "manifest:vibe:a"),))
    first = coalesce_effects((codex, vibe))
    assert first == coalesce_effects((vibe, codex))
    assert len(first) == 1
    assert first[0].logical_owners == ("codex", "vibe")
    assert first[0].surface_ids == ("codex.a", "vibe.a")
    assert set(first[0].ownership) == set(codex.ownership + vibe.ownership)


def test_id_excludes_clocks_absolute_fixture_root_and_prepared_hashes() -> None:
    effect = _effect()
    later = replace(effect, after=_file(b"T2"), root=replace(effect.root, path=Path("/other-fixture")))
    assert effect.id == later.id
    assert effect.after.sha256 != later.after.sha256


def test_alias_dedup_uses_supplied_root_identity_without_following_links(tmp_path: Path) -> None:
    sentinel = tmp_path / "sentinel"
    sentinel.mkdir()
    (tmp_path / "hostile").symlink_to(sentinel, target_is_directory=True)
    left = replace(_effect(), root=OperationRoot("left", "project", tmp_path), path="hostile/a")
    right = replace(left, root=OperationRoot("right", "project", sentinel), path="a")
    assert len(coalesce_effects((left, right))) == 2
    alias = replace(left, root=OperationRoot("alias", "project", tmp_path))
    assert coalesce_effects((left, alias)) == coalesce_effects((alias, left))
    assert len(coalesce_effects((left, alias))) == 1


@pytest.mark.parametrize("after,owner", [(_file(b"contradictory"), "commands"), (_file(mode=0o755), "commands"), (_file(), "other")])
def test_conflicting_destination_has_no_last_writer_wins(after: FileState, owner: str) -> None:
    effect = _effect()
    with pytest.raises(ValueError, match="conflict"):
        coalesce_effects((effect, replace(effect, after=after, owner=owner)))


def test_mode_kind_link_and_mtime_observations_remain_distinct() -> None:
    state = FileState("symlink", target="a", mode=0o777, mtime_ns=100)
    assert state != replace(state, target="b")
    assert state != replace(state, mode=0o755)
    assert state != replace(state, mtime_ns=101)
    assert state != _file()


def test_root_identity_cannot_hide_distinct_physical_destinations() -> None:
    effect = _effect()
    other = replace(effect, root=replace(effect.root, path=Path("/another-project")))
    with pytest.raises(ValueError, match="Root identity conflict"):
        coalesce_effects((effect, other))


def test_result_refuses_overlapping_or_false_precondition_success() -> None:
    with pytest.raises(ValueError):
        OwnerApplyResult("commands", succeeded=("a",), failed=("a",))
    with pytest.raises(ValueError):
        OwnerApplyResult("commands", outcome="precondition_changed", succeeded=("a",))


def test_dispositions_and_consent_are_not_effects() -> None:
    disposition = Disposition("commands", "project", "a", "consent_required", "Edited managed content")
    assessment = OwnerAssessment("commands", _effect().root, dispositions=(disposition,))
    assert not assessment.effects
    assert not ApplyConsent().automatic


@pytest.mark.parametrize(
    "outcome,succeeded,failed",
    [
        ("applied", (), ("a",)),
        ("failed", ("a",), ()),
        ("skipped", ("a",), ()),
    ],
)
def test_result_outcome_cannot_disagree_with_actual_ids(outcome: str, succeeded: tuple[str, ...], failed: tuple[str, ...]) -> None:
    with pytest.raises(ValueError):
        OwnerApplyResult("commands", succeeded=succeeded, failed=failed, outcome=outcome)


def test_value_import_does_not_discover_or_bootstrap_providers() -> None:
    code = """
import sys
import specify_cli.tool_surface.operations
assert 'specify_cli.tool_surface.providers._discovery' not in sys.modules
assert 'specify_cli.runtime.bootstrap' not in sys.modules
assert 'specify_cli.upgrade.runner' not in sys.modules
"""
    result = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
