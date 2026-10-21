"""``charter activate`` and the deny-list (WP04 review cycle 1: FR-008, FR-009, FR-013, NFR-001).

Ledger-seeded.
Drives the manager's activation-side deny glue: the stored stem is cleared for
a declared id, an absent list is materialised without the denied id, a
present-list round trip leaves no deny key, and a deny list plus an
unreadable declared org pack refuses with every activation file
byte-identical (after a same-fixture positive control). Also pins the
cascade-child branches of ``charter deactivate`` and the empty-ledger write
guard.
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any, cast

import pytest
from click.testing import Result
from typer.testing import CliRunner

from charter.activation.activation_ledger import ActiveCharterConfigError
from charter.activation.invocation_context import ProjectContext
from charter.activation.pack_manager import ActivationResult, ActiveCharterManager, _save_ledger
from kernel.activation_ledger_store import activation_ledger_path
from specify_cli.cli.commands.charter import charter_app
from specify_cli.cli.commands.charter import deactivate as deactivate_module
from tests._factories.activation_ledger import read_activation_ledger, seed_activation_ledger

pytestmark = [pytest.mark.fast]

_RUNNER = CliRunner()
_A = "001-architectural-integrity-standard"
_D = "003-decision-documentation-requirement"
_OTHER = "010-specification-fidelity-requirement"
_ACTIVATION_FILES = (Path(".kittify", "config.yaml"), Path(".kittify", "charter", "charter.yaml"), Path(".kittify", "charter", "activation.yaml"))


def _project(tmp_path: Path, *, pack_body: str | None = None, **ledger: list[str]) -> Path:
    lines: list[str] = []
    if pack_body is not None:
        pack = tmp_path / "org-packs" / "acme"
        pack.mkdir(parents=True)
        (pack / "org-charter.yaml").write_text(textwrap.dedent(pack_body).lstrip(), encoding="utf-8")
        lines = ["charter_packs:", "  org:", "    packs:", "      - name: acme", "        local_path: org-packs/acme"]
    (tmp_path / ".kittify").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".kittify" / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    seed_activation_ledger(tmp_path, mission_type_activations=["software-dev"], **ledger)
    return tmp_path


def _charter(root: Path, *args: str) -> Result:
    return _RUNNER.invoke(charter_app, [args[0], "--repo-root", str(root), "--no-compile", *args[1:]])


def _snapshot(root: Path) -> dict[Path, bytes | None]:
    return {rel: (root / rel).read_bytes() if (root / rel).exists() else None for rel in _ACTIVATION_FILES}


# --------------------------------------------------------------------------- #
# Activation clears an exclusion (FR-008)
# --------------------------------------------------------------------------- #


def test_a_declared_id_round_trip_clears_the_stored_stem(tmp_path: Path) -> None:
    root = _project(tmp_path)
    assert _charter(root, "deactivate", "directive", "DIRECTIVE_003").exit_code == 0
    assert read_activation_ledger(root)["deactivated_directives"] == [_D]

    result = _charter(root, "activate", "directive", "DIRECTIVE_003")

    assert result.exit_code == 0, result.output
    ledger = read_activation_ledger(root)
    assert "deactivated_directives" not in ledger
    assert "activated_directives" not in ledger  # "absent = all" stays absent (D-09)
    assert f"Cleared the exclusion of '{_D}'" in " ".join(result.output.split())


def test_materialising_an_absent_list_leaves_out_the_denied_id(tmp_path: Path) -> None:
    root = _project(tmp_path, deactivated_directives=[_D])

    result = _charter(root, "activate", "directive", _A)

    assert result.exit_code == 0, result.output
    ledger = read_activation_ledger(root)
    assert _A in ledger["activated_directives"]
    assert _OTHER in ledger["activated_directives"]  # the rest of the effective set is preserved (#4253)
    assert _D not in ledger["activated_directives"]
    assert ledger["deactivated_directives"] == [_D]


def test_a_present_list_round_trip_leaves_no_deny_key(tmp_path: Path) -> None:
    root = _project(tmp_path, activated_directives=[_A, _D])
    assert _charter(root, "deactivate", "directive", _D).exit_code == 0
    assert read_activation_ledger(root)["activated_directives"] == [_A]

    result = _charter(root, "activate", "directive", _D)

    assert result.exit_code == 0, result.output
    ledger = read_activation_ledger(root)
    assert ledger["activated_directives"] == [_A, _D]
    assert "deactivated_directives" not in ledger


# --------------------------------------------------------------------------- #
# The activate-side strict floor read (FR-013, NFR-001)
# --------------------------------------------------------------------------- #

_ACME = "schema_version: 1\nrequired_tactics: [adversarial-qa-handoff]\n"


def _corrupt_after_a_positive_control(tmp_path: Path) -> Path:
    root = _project(tmp_path, pack_body=_ACME, deactivated_directives=[_D])
    control = _charter(root, "activate", "directive", _A)  # reads the floor (a deny list exists) and succeeds
    assert control.exit_code == 0, control.output
    assert _A in read_activation_ledger(root)["activated_directives"]
    (root / "org-packs" / "acme" / "org-charter.yaml").write_text("required_tactics: [unclosed\n", encoding="utf-8")
    return root


def test_activate_with_a_deny_list_refuses_on_an_unreadable_org_pack(tmp_path: Path) -> None:
    root = _corrupt_after_a_positive_control(tmp_path)
    before = _snapshot(root)

    result = _charter(root, "activate", "directive", _OTHER)

    assert result.exit_code != 0
    assert "acme" in result.output
    assert _snapshot(root) == before


def test_the_manager_refuses_through_the_strict_floor_read(tmp_path: Path) -> None:
    root = _corrupt_after_a_positive_control(tmp_path)
    before = _snapshot(root)

    with pytest.raises(ActiveCharterConfigError) as excinfo:
        ActiveCharterManager().activate(ProjectContext(repo_root=root), "directive", _OTHER)

    assert "org required floor cannot be read" in excinfo.value.body
    assert _snapshot(root) == before


# --------------------------------------------------------------------------- #
# Cascade-child branches of charter deactivate
# --------------------------------------------------------------------------- #


class _FakeManager:
    def __init__(self, *, raises: Exception | None = None, deactivated: list[str] | None = None) -> None:
        self.raises = raises
        self.deactivated = deactivated or []
        self.calls: list[dict[str, Any]] = []

    def deactivate(self, ctx: ProjectContext, kind: str, artifact_id: str, **kwargs: Any) -> ActivationResult:
        self.calls.append({"kind": kind, "artifact_id": artifact_id, **kwargs})
        if self.raises is not None:
            raise self.raises
        return ActivationResult(deactivated=list(self.deactivated))


def _child(manager: _FakeManager, kind: str, config_id: str, capsys: pytest.CaptureFixture[str], tmp_path: Path) -> str:
    deactivate_module._cascade_child(
        cast(ActiveCharterManager, manager),  # a structural stand-in for ActiveCharterManager.deactivate
        ProjectContext(repo_root=tmp_path),
        kind,
        config_id,
        layer_roots=None,
        source_id="parent",
        allow_absent=False,
    )
    return " ".join(capsys.readouterr().out.split())


def test_a_cascade_child_that_cannot_be_deactivated_is_warned_about(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    manager = _FakeManager(raises=ValueError("boom"))

    out = _child(manager, "tactic", "t1", capsys, tmp_path)

    assert "could not cascade-deactivate tactic/t1: boom" in out
    assert manager.calls[0]["record_exclusion"] is False


def test_a_cascade_child_agent_profile_carries_the_mission_binding_warning(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(deactivate_module, "mission_default_profile_warning", lambda profile_id: f"{profile_id} is a mission default")
    manager = _FakeManager(deactivated=["researcher-robbie"])

    out = _child(manager, "agent-profile", "researcher-robbie", capsys, tmp_path)

    assert "Cascade-deactivated: agent-profile/researcher-robbie" in out
    assert "researcher-robbie is a mission default" in out


def test_a_cascade_child_already_off_the_list_prints_nothing(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert _child(_FakeManager(deactivated=[]), "tactic", "t1", capsys, tmp_path) == ""


def test_active_urns_skips_an_allow_id_with_no_drg_node(tmp_path: Path) -> None:
    root = _project(tmp_path, activated_directives=[_A, "no-such-directive"], deactivated_tactics=["adversarial-qa-handoff"])
    graph_urns = frozenset({"tactic:adversarial-qa-handoff", "tactic:other-tactic"})

    urns = deactivate_module._active_urns(ActiveCharterManager(), ProjectContext(repo_root=root), None, None, graph_urns)

    assert "directive:DIRECTIVE_001" in urns
    assert not [urn for urn in urns if "no-such-directive" in urn]
    assert "tactic:other-tactic" in urns  # absent "all" kind: every graph node of the kind
    assert "tactic:adversarial-qa-handoff" not in urns  # less the denied ids


# --------------------------------------------------------------------------- #
# The empty-ledger write guard (carry-forward from WP03)
# --------------------------------------------------------------------------- #


def test_an_empty_write_on_a_fresh_project_creates_no_ledger(tmp_path: Path) -> None:
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.yaml").write_text("{}\n", encoding="utf-8")

    _save_ledger(activation_ledger_path(tmp_path), {}, repo_root=tmp_path)

    assert not activation_ledger_path(tmp_path).exists()


def test_an_empty_write_on_an_existing_ledger_still_empties_it(tmp_path: Path) -> None:
    root = _project(tmp_path)

    _save_ledger(activation_ledger_path(root), {}, repo_root=root)

    assert activation_ledger_path(root).read_text(encoding="utf-8") == "{}\n"


# --------------------------------------------------------------------------- #
# F2/F4: the deny is read only through the activation ledger seam
# --------------------------------------------------------------------------- #


def _unmigrated(tmp_path: Path) -> Path:
    (tmp_path / ".kittify").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".kittify" / "config.yaml").write_text(f"mission_type_activations:\n- software-dev\ndeactivated_directives:\n- {_D}\n", encoding="utf-8")
    return tmp_path


def _legacy_config(root: Path) -> dict[str, Any]:
    from ruamel.yaml import YAML

    return cast(dict[str, Any], YAML(typ="safe").load((root / ".kittify" / "config.yaml").read_text(encoding="utf-8")))


def test_activate_on_an_unmigrated_project_never_applies_a_legacy_deny_key(tmp_path: Path) -> None:
    """F2 (FR-017): materialising an absent list keeps the id a hand-written legacy deny key names."""
    root = _unmigrated(tmp_path)

    ActiveCharterManager().activate(ProjectContext(repo_root=root), "directive", _A)

    config = _legacy_config(root)
    assert _D in config["activated_directives"]
    assert config["deactivated_directives"] == [_D]
    assert not activation_ledger_path(root).exists()


def test_activate_of_the_id_a_legacy_deny_key_names_writes_the_allow_list_only(tmp_path: Path) -> None:
    """F2: the legacy deny key is not the activation's to clear; the allow-only write goes through."""
    root = _unmigrated(tmp_path)

    ActiveCharterManager().activate(ProjectContext(repo_root=root), "directive", _D)

    config = _legacy_config(root)
    assert _D in config["activated_directives"]
    assert config["deactivated_directives"] == [_D]


def test_active_urns_keeps_an_org_required_id_a_stale_deny_names(tmp_path: Path) -> None:
    """F4 (FR-012, C-005): the cascade's active set subtracts the effective deny, never a required id."""
    root = _project(
        tmp_path,
        pack_body="schema_version: 1\norg_name: Acme\nrequired_tactics:\n  - adversarial-qa-handoff\n",
        deactivated_tactics=["adversarial-qa-handoff"],
    )
    graph_urns = frozenset({"tactic:adversarial-qa-handoff", "tactic:other-tactic"})

    urns = deactivate_module._active_urns(ActiveCharterManager(), ProjectContext(repo_root=root), None, [root / "org-packs" / "acme"], graph_urns)

    assert "tactic:adversarial-qa-handoff" in urns
