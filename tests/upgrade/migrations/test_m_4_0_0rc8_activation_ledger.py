"""The ledger migration ``4.0.0rc8_activation_ledger`` (WP08 T043/T046-T048, FR-003/FR-004, NFR-001/NFR-002).

Every read of
a legacy surface before the move happens inside the upgrade scope, as the
shipped runner does it.

Covered: every ``ledger_migration`` fixture shape (data-model.md §8), the
divergence and legacy-deny refusals with byte identity of every file, the
idempotent re-run, crash recovery at each step boundary, the bundle re-stamp,
the migration class and its manifest entry, and the empty-write no-op.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from ruamel.yaml import YAML

from charter.activation import activation_ledger as seam
from charter.activation.activation_ledger import (
    LedgerMigrationRefused,
    apply_ledger_migration,
    plan_ledger_migration,
    prepare_ledger_write,
)
from charter.activation.charter_yaml_io import apply_yaml_write
from charter.activation.pack_context import PackContext
from charter.activation.synthesizer.manifest import MANIFEST_PATH, SynthesisManifest, finalize_manifest, load_yaml
from charter.activation.synthesizer.synthesize_pipeline import canonical_yaml
from charter.bundle import compute_bundle_content_hash
from charter.offering.artifact_kinds import ArtifactKind
from kernel.activation_ledger_store import activation_ledger_path, legacy_activation_scope
from specify_cli.upgrade.ledger import MigrationLedger
from specify_cli.upgrade.manifest import load_order_manifest
from specify_cli.upgrade.metadata import ProjectMetadata
from specify_cli.upgrade.migrations.base import MigrationStateUnreadableError
from specify_cli.upgrade.migrations.m_4_0_0rc8_activation_ledger import ActivationLedgerMigration
from specify_cli.upgrade.runner import MigrationRunner

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SAFE = YAML(typ="safe")
_POINTER = ".kittify/charter/charter.yaml"
_CONFIG_HEAD = "# project config\nvcs:\n  type: git\n"
_CHARTER_HEAD = '# authored charter\nschema_version: "2.0.0"\ngovernance:\n  testing: {}\n'
_MIGRATION_ID = "4.0.0rc8_activation_ledger"


# --------------------------------------------------------------------------- #
# Fixture builder
# --------------------------------------------------------------------------- #


def _project(
    root: Path,
    *,
    charter: str | None = None,
    config: str = "",
    ledger: str | None = None,
    pointer: bool = True,
    manifest: bool = False,
) -> Path:
    """A project with the given legacy surfaces (raw YAML text appended after a fixed head)."""
    kittify = root / ".kittify"
    (kittify / "charter").mkdir(parents=True, exist_ok=True)
    pointer_line = f"charter: {_POINTER}\n" if pointer else ""
    (kittify / "config.yaml").write_text(_CONFIG_HEAD + pointer_line + config, encoding="utf-8")
    if charter is not None:
        (kittify / "charter" / "charter.yaml").write_text(_CHARTER_HEAD + charter, encoding="utf-8")
    if ledger is not None:
        activation_ledger_path(root).write_text(ledger, encoding="utf-8")
    if manifest:
        (kittify / "charter" / "charter.md").write_text("# Charter\n", encoding="utf-8")
        stamped = finalize_manifest(
            SynthesisManifest(
                created_at="2026-10-19T00:00:00Z",
                run_id="01TESTRUN",
                adapter_id="project-direct-write",
                adapter_version="1",
                synthesizer_version="1",
                manifest_hash="0" * 64,
                built_in_only=False,
                bundle_content_hash=compute_bundle_content_hash(root),
            )
        )
        (root / MANIFEST_PATH).write_text(canonical_yaml(stamped.model_dump(mode="python")).decode("utf-8"), encoding="utf-8")
    return root


def _files(root: Path) -> dict[str, bytes]:
    """Every file under ``.kittify`` (relative path -> bytes)."""
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in sorted((root / ".kittify").rglob("*")) if path.is_file()}


def _yaml(path: Path) -> dict[str, Any]:
    return dict(_SAFE.load(path.read_text(encoding="utf-8")) or {})


def _config(root: Path) -> dict[str, Any]:
    return _yaml(root / ".kittify" / "config.yaml")


def _charter(root: Path) -> dict[str, Any]:
    return _yaml(root / _POINTER)


def _ledger(root: Path) -> dict[str, Any]:
    return _yaml(activation_ledger_path(root))


def _migrate(root: Path) -> tuple[Path, ...]:
    return apply_ledger_migration(root, plan_ledger_migration(root))


_KINDS = tuple(kind for kind in ArtifactKind if kind.activatable)


def _effective(root: Path) -> tuple[Any, ...]:
    ctx = PackContext.from_config(root)
    return (ctx.activated_mission_types, tuple(ctx.allow_for(kind) for kind in _KINDS))


# --------------------------------------------------------------------------- #
# Moves (fixture shapes)
# --------------------------------------------------------------------------- #

_ACTIVATION = "activated_directives: []\nactivated_tactics:\n- T\nmission_type_activations:\n- software-dev\n"
_EXPECTED = {"activated_directives": [], "activated_tactics": ["T"], "mission_type_activations": ["software-dev"]}


def test_pointer_charter_yaml_moves_verbatim_and_keeps_effective_sets(tmp_path: Path) -> None:
    root = _project(tmp_path, charter=_ACTIVATION + "catalog: {}\n")
    with legacy_activation_scope(root):
        before = _effective(root)

    written = _migrate(root)

    assert _ledger(root) == _EXPECTED
    charter_text = (root / _POINTER).read_text(encoding="utf-8")
    assert "# authored charter" in charter_text
    assert set(_charter(root)) == {"schema_version", "governance", "catalog"}
    assert activation_ledger_path(root) in written
    assert _effective(root) == before


def test_no_pointer_config_yaml_moves(tmp_path: Path) -> None:
    root = _project(tmp_path, pointer=False, config=_ACTIVATION)
    with legacy_activation_scope(root):
        before = _effective(root)

    _migrate(root)

    assert _ledger(root) == _EXPECTED
    assert _config(root) == {"vcs": {"type": "git"}}
    assert (root / ".kittify" / "config.yaml").read_text(encoding="utf-8").startswith("# project config\n")
    assert _effective(root) == before


def test_leftover_config_copy_equal_to_the_authority_is_removed(tmp_path: Path) -> None:
    root = _project(tmp_path, charter="mission_type_activations:\n- research\n- software-dev\n", config="mission_type_activations:\n- software-dev\n- research\n")

    plan = plan_ledger_migration(root)
    assert [(move.key, move.source.name) for move in plan.moves] == [
        ("mission_type_activations", "charter.yaml"),
        ("mission_type_activations", "config.yaml"),
    ]
    _migrate(root)

    assert _ledger(root) == {"mission_type_activations": ["research", "software-dev"]}
    assert "mission_type_activations" not in _config(root)
    assert "mission_type_activations" not in _charter(root)
    assert _config(root)["charter"] == _POINTER


def test_spellings_and_duplicates_move_verbatim(tmp_path: Path) -> None:
    root = _project(tmp_path, charter="activated_procedures:\n- PROC_CANVAS_REVIEW\n- canvas-review\n- canvas-review\n")
    _migrate(root)
    assert _ledger(root) == {"activated_procedures": ["PROC_CANVAS_REVIEW", "canvas-review", "canvas-review"]}


def test_existing_ledger_with_equal_legacy_keys_strips_them(tmp_path: Path) -> None:
    """Re-run after a crash (P9): the ledger already holds the keys; the copies go."""
    root = _project(tmp_path, charter="activated_tactics:\n- T\n", config="activated_tactics:\n- T\n", ledger="activated_tactics:\n- T\n")
    ledger_before = activation_ledger_path(root).read_bytes()

    _migrate(root)

    assert activation_ledger_path(root).read_bytes() == ledger_before
    assert "activated_tactics" not in _charter(root)
    assert "activated_tactics" not in _config(root)


def test_null_valued_legacy_key_is_stripped_without_a_ledger_value(tmp_path: Path) -> None:
    root = _project(tmp_path, charter="activated_tactics:\nactivated_directives:\n- D\n")
    _migrate(root)
    assert _ledger(root) == {"activated_directives": ["D"]}
    assert "activated_tactics" not in _charter(root)


# --------------------------------------------------------------------------- #
# Refusals (FR-004, NFR-001): nothing written, every file byte-identical
# --------------------------------------------------------------------------- #


_REFUSALS: dict[str, tuple[dict[str, Any], str, str, tuple[str, ...]]] = {
    "copy-differs": (
        {"charter": "activated_tactics:\n- T\n", "config": "activated_tactics:\n- U\n"},
        "activated_tactics",
        "divergent",
        ("charter.yaml", "config.yaml"),
    ),
    "stray-copy-authority-lacks-key": (
        {"charter": "catalog: {}\n", "config": "activated_tactics:\n- T\n"},
        "activated_tactics",
        "divergent",
        ("charter.yaml", "config.yaml"),
    ),
    "ledger-differs": (
        {"charter": "activated_tactics:\n- T\n", "config": "activated_tactics:\n- T\n", "ledger": "activated_tactics:\n- U\n"},
        "activated_tactics",
        "divergent",
        ("charter.yaml", "activation.yaml"),
    ),
    "ledger-lacks-key": (
        {"charter": "activated_tactics:\n- T\n", "ledger": "activated_directives: []\n"},
        "activated_tactics",
        "divergent",
        ("charter.yaml", "activation.yaml"),
    ),
    "three-state-empty-vs-absent": (
        {"charter": "activated_tactics: []\n", "config": "activated_tactics:\n"},
        "activated_tactics",
        "divergent",
        ("charter.yaml", "config.yaml"),
    ),
    "legacy-deny-key": (
        {"charter": "activated_tactics:\n- T\ndeactivated_tactics:\n- X\n"},
        "deactivated_tactics",
        "legacy_deny_key",
        ("charter.yaml",),
    ),
    "legacy-deny-key-in-copy": (
        {"charter": "activated_tactics:\n- T\n", "config": "deactivated_directives: []\n"},
        "deactivated_directives",
        "legacy_deny_key",
        ("config.yaml",),
    ),
}


@pytest.mark.parametrize("case", sorted(_REFUSALS))
def test_refusal_names_key_and_files_and_writes_nothing(tmp_path: Path, case: str) -> None:
    surfaces, key, reason, names = _REFUSALS[case]
    root = _project(tmp_path, manifest=True, **surfaces)
    before = _files(root)

    plan = plan_ledger_migration(root)

    assert plan.refusal is not None
    assert (plan.refusal.key, plan.refusal.reason) == (key, reason)
    assert tuple(path.name for path in plan.refusal.files) == names
    assert key in plan.refusal.message
    with pytest.raises(LedgerMigrationRefused) as caught:
        apply_ledger_migration(root, plan)
    assert caught.value.refusal == plan.refusal
    assert "Nothing was written" in caught.value.body
    assert _files(root) == before


# --------------------------------------------------------------------------- #
# Idempotency (NFR-002) and the bundle re-stamp
# --------------------------------------------------------------------------- #

_MOVING_SHAPES: dict[str, dict[str, Any]] = {
    "pointer": {"charter": _ACTIVATION},
    "no-pointer": {"pointer": False, "config": _ACTIVATION},
    "equal-copy": {"charter": "activated_tactics:\n- T\n", "config": "activated_tactics:\n- T\n"},
    "existing-ledger": {"charter": "activated_tactics:\n- T\n", "ledger": "activated_tactics:\n- T\n"},
}


@pytest.mark.parametrize("shape", sorted(_MOVING_SHAPES))
def test_second_run_changes_zero_bytes(tmp_path: Path, shape: str) -> None:
    root = _project(tmp_path, manifest=True, **_MOVING_SHAPES[shape])
    _migrate(root)
    after_first = _files(root)

    plan = plan_ledger_migration(root)

    assert plan.noop
    assert plan.moves == ()
    assert apply_ledger_migration(root, plan) == ()
    assert _files(root) == after_first
    assert ActivationLedgerMigration().detect(root) is False


def test_bundle_hash_is_restamped_after_the_move(tmp_path: Path) -> None:
    root = _project(tmp_path, charter=_ACTIVATION, manifest=True)
    stale = load_yaml(root / MANIFEST_PATH).bundle_content_hash

    _migrate(root)

    stamped = load_yaml(root / MANIFEST_PATH).bundle_content_hash
    assert stamped == compute_bundle_content_hash(root)
    assert stamped != stale


def test_a_project_without_legacy_keys_is_a_noop(tmp_path: Path) -> None:
    root = _project(tmp_path, charter="catalog: {}\n")
    before = _files(root)
    plan = plan_ledger_migration(root)
    assert plan.noop and plan.refusal is None
    assert apply_ledger_migration(root, plan) == ()
    assert _files(root) == before
    assert not activation_ledger_path(root).exists()


def test_apply_refuses_a_stale_plan(tmp_path: Path) -> None:
    root = _project(tmp_path, charter="activated_tactics:\n- T\n")
    plan = plan_ledger_migration(root)
    (root / _POINTER).write_text(_CHARTER_HEAD + "activated_tactics:\n- U\n", encoding="utf-8")
    with pytest.raises(ValueError, match="precondition_changed"):
        apply_ledger_migration(root, plan)
    assert not activation_ledger_path(root).exists()


def test_a_dangling_pointer_fails_closed(tmp_path: Path) -> None:
    root = _project(tmp_path)
    with pytest.raises(seam.ActiveCharterConfigError) as caught:
        plan_ledger_migration(root)
    assert "does not exist" in caught.value.body


def test_a_non_list_legacy_value_fails_closed(tmp_path: Path) -> None:
    root = _project(tmp_path, charter="activated_tactics: T\n")
    with pytest.raises(seam.ActiveCharterConfigError) as caught:
        plan_ledger_migration(root)
    assert "must be a list" in caught.value.body


# --------------------------------------------------------------------------- #
# Crash recovery (T043.2 / T048)
# --------------------------------------------------------------------------- #


def _crash_after_write(calls: int) -> Callable[[Any], bool]:
    """``apply_yaml_write`` that performs its *calls*-th real write, then raises."""
    done = {"n": 0}

    def _write(prepared: Any) -> bool:
        changed = apply_yaml_write(prepared)
        done["n"] += 1
        if done["n"] == calls:
            raise RuntimeError("injected crash")
        return changed

    return _write


def _stamp_then_crash(real: Callable[..., Any]) -> Callable[..., Any]:
    def _stamp(*args: Any, **kwargs: Any) -> Any:
        real(*args, **kwargs)
        raise RuntimeError("injected crash")

    return _stamp


_CRASH_SHAPE: dict[str, Any] = {"charter": _ACTIVATION, "config": "mission_type_activations:\n- software-dev\n", "manifest": True}
_BOUNDARIES = ("after-ledger-write", "after-manifest-stamp", "after-charter-strip", "after-config-strip")


@pytest.mark.parametrize("boundary", _BOUNDARIES)
def test_rerun_after_a_crash_reaches_the_uninterrupted_end_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, boundary: str) -> None:
    """Order (a) ledger write, (b) stamp the manifest with the stripped charter.yaml's hash, (c)/(d) strips.

    A crash anywhere before the last strip leaves a legacy key, so ``detect()``
    stays True and the re-run finishes; the stamp is never a recovery trigger.
    """
    reference = _project(tmp_path / "reference", **_CRASH_SHAPE)
    _migrate(reference)
    crashed = _project(tmp_path / "crashed", **_CRASH_SHAPE)

    with monkeypatch.context() as patch:
        if boundary == "after-manifest-stamp":
            patch.setattr(seam, "_stamp_manifest", _stamp_then_crash(seam._stamp_manifest))
        else:
            patch.setattr(seam, "apply_yaml_write", _crash_after_write(_BOUNDARIES.index(boundary) or 1))
        with pytest.raises(RuntimeError, match="injected crash"):
            _migrate(crashed)

    migration = ActivationLedgerMigration()
    assert migration.detect(crashed) is (boundary != "after-config-strip")
    result = migration.apply(crashed)
    assert result.success, result.errors

    assert _files(crashed) == _files(reference)
    assert migration.detect(crashed) is False


def test_the_manifest_is_stamped_before_charter_yaml_is_stripped(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _project(tmp_path, **_CRASH_SHAPE)
    stamped_while_keys_present: list[bool] = []
    real = seam._stamp_manifest

    def _stamp(*args: Any, **kwargs: Any) -> Any:
        stamped_while_keys_present.append("activated_tactics" in _charter(root))
        return real(*args, **kwargs)

    monkeypatch.setattr(seam, "_stamp_manifest", _stamp)
    _migrate(root)
    assert stamped_while_keys_present == [True]
    assert load_yaml(root / MANIFEST_PATH).bundle_content_hash == compute_bundle_content_hash(root)


def test_a_lagging_stamp_on_a_ledger_project_is_not_the_migrations_business(tmp_path: Path) -> None:
    """No lag heuristic (review cycle 1): a hand-edit after synthesis stays visible as stale."""
    root = _project(tmp_path, charter="catalog: {}\n", ledger="activated_tactics:\n- T\n", manifest=True)
    with (root / _POINTER).open("a", encoding="utf-8") as handle:
        handle.write("# hand edit after synthesis\n")
    before = _files(root)
    assert load_yaml(root / MANIFEST_PATH).bundle_content_hash != compute_bundle_content_hash(root)

    plan = plan_ledger_migration(root)

    assert plan.noop
    assert ActivationLedgerMigration().detect(root) is False
    assert apply_ledger_migration(root, plan) == ()
    assert _files(root) == before


# --------------------------------------------------------------------------- #
# The migration class and its manifest entry (T047)
# --------------------------------------------------------------------------- #


def test_migration_identity_and_flags() -> None:
    migration = ActivationLedgerMigration()
    assert migration.migration_id == _MIGRATION_ID
    assert migration.target_version == "4.0.0rc8"
    assert ActivationLedgerMigration.clone_local_effect is False
    assert ActivationLedgerMigration.runs_first is False
    assert ActivationLedgerMigration.runs_on_worktrees is False


def test_manifest_entry_follows_the_project_intent_rename() -> None:
    """The move runs after the #6443 rename, so the stems it rewrites are what reach the ledger."""
    order = load_order_manifest()
    assert order.index("4.0.0rc7_track_charter_pack_yaml") < order.index(_MIGRATION_ID)
    assert order[order.index("4.0.0rc8_project_intent_directive_rename") + 1] == _MIGRATION_ID


def test_detect_and_dry_run_write_nothing(tmp_path: Path) -> None:
    root = _project(tmp_path, charter=_ACTIVATION)
    before = _files(root)
    migration = ActivationLedgerMigration()

    assert migration.detect(root) is True
    assert migration.can_apply(root) == (True, "")
    result = migration.apply(root, dry_run=True)

    assert result.success
    assert any("activated_tactics" in change for change in result.changes_made)
    assert _files(root) == before


def test_migration_apply_moves_and_reports(tmp_path: Path) -> None:
    root = _project(tmp_path, charter=_ACTIVATION)
    result = ActivationLedgerMigration().apply(root)
    assert result.success, result.errors
    assert _ledger(root) == _EXPECTED
    assert any("activation.yaml" in change for change in result.changes_made)


def test_migration_refusal_is_a_failure_and_writes_nothing(tmp_path: Path) -> None:
    root = _project(tmp_path, charter="activated_tactics:\n- T\n", config="activated_tactics:\n- U\n")
    before = _files(root)
    result = ActivationLedgerMigration().apply(root)
    assert not result.success
    assert "activated_tactics" in result.errors[0]
    assert _files(root) == before


def test_detect_raises_unreadable_on_a_malformed_surface(tmp_path: Path) -> None:
    root = _project(tmp_path, charter="activated_tactics: T\n")
    with pytest.raises(MigrationStateUnreadableError):
        ActivationLedgerMigration().detect(root)


def test_a_refused_run_records_no_success_so_it_retries(tmp_path: Path) -> None:
    root = _project(tmp_path, charter="activated_tactics:\n- T\n", config="activated_tactics:\n- U\n")
    runner = MigrationRunner(root)
    metadata = runner._create_initial_metadata("4.0.0rc7")
    migration = ActivationLedgerMigration()

    _result, status = runner._apply_migration(migration, metadata, dry_run=False)

    assert status == "failed"
    results = {record.result for record in MigrationLedger(root).read_all() if record.id == _MIGRATION_ID}
    assert "success" not in results
    assert isinstance(metadata, ProjectMetadata)


# --------------------------------------------------------------------------- #
# Empty writes are a no-op (T048 carry-forward)
# --------------------------------------------------------------------------- #


def test_an_empty_ledger_write_on_a_fresh_project_creates_no_file(tmp_path: Path) -> None:
    prepared = prepare_ledger_write(tmp_path, {})
    assert prepared.changed is False
    assert apply_yaml_write(prepared) is False
    assert not activation_ledger_path(tmp_path).exists()


def test_an_emptying_write_of_an_existing_ledger_still_leaves_a_mapping(tmp_path: Path) -> None:
    ledger = activation_ledger_path(tmp_path)
    ledger.parent.mkdir(parents=True)
    ledger.write_text("activated_tactics:\n- t\n", encoding="utf-8")
    apply_yaml_write(prepare_ledger_write(tmp_path, {}, remove=("activated_tactics",)))
    assert ledger.read_text(encoding="utf-8") == "{}\n"


# --------------------------------------------------------------------------- #
# Pre-PR fix round (F3, F5, F8, F9)
# --------------------------------------------------------------------------- #


def test_the_manifest_is_restamped_when_only_config_yaml_moves(tmp_path: Path) -> None:
    """F3 (FR-003): the ledger is in the bundle hash, so writing it restamps the manifest even with no charter.yaml strip."""
    root = _project(tmp_path, charter="catalog: {}\n", config="activated_tactics:\n- T\n", pointer=False, manifest=True)

    _migrate(root)

    assert _ledger(root) == {"activated_tactics": ["T"]}
    assert load_yaml(root / MANIFEST_PATH).bundle_content_hash == compute_bundle_content_hash(root)


@pytest.mark.parametrize("text", ["schema_version: 1\nbogus_field: [\n", "bogus_field: 1\n"], ids=["broken-yaml", "schema-invalid"])
def test_a_malformed_manifest_refuses_before_any_write(tmp_path: Path, text: str) -> None:
    """F8: the synthesis manifest is validated in the plan phase; the refusal names it and nothing is written."""
    root = _project(tmp_path, charter=_ACTIVATION, manifest=True)
    (root / MANIFEST_PATH).write_text(text, encoding="utf-8")
    before = _files(root)

    with pytest.raises(seam.ActiveCharterConfigError) as caught:
        _migrate(root)

    assert str(MANIFEST_PATH) in caught.value.body
    assert _files(root) == before
    assert not activation_ledger_path(root).exists()


def test_a_dangling_pointer_during_upgrade_names_the_pointer_not_upgrade(tmp_path: Path) -> None:
    """F9: the remedy is to fix or remove the ``charter:`` pointer, never to re-run the failing ``spec-kitty upgrade``."""
    root = _project(tmp_path)

    with pytest.raises(MigrationStateUnreadableError) as caught:
        ActivationLedgerMigration().detect(root)

    message = str(caught.value)
    assert "spec-kitty upgrade" not in message
    assert "charter:" in message and ".kittify/config.yaml" in message


def test_the_rename_then_the_move_succeeds_on_an_equal_leftover_copy(tmp_path: Path) -> None:
    """F5: the project-intent rename rewrites the authority's stem only; the equal leftover copy still moves."""
    from specify_cli.upgrade.migrations.m_4_0_0rc8_project_intent_directive_rename import ProjectIntentDirectiveRenameMigration

    legacy = "activated_directives:\n- 007-mission-type-scope-directive\n"
    root = _project(tmp_path, charter=legacy, config=legacy)

    renamed = ProjectIntentDirectiveRenameMigration().apply(root)
    assert renamed.success, renamed.errors
    authority = _charter(root)["activated_directives"]
    assert authority != ["007-mission-type-scope-directive"], "control: the rename rewrote the authority"

    moved = ActivationLedgerMigration().apply(root)

    assert moved.success, moved.errors
    assert _ledger(root) == {"activated_directives": authority}
    assert "activated_directives" not in _config(root)
    assert "activated_directives" not in _charter(root)
