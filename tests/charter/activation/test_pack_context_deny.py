"""``PackContext`` carries the effective deny and the membership accessors (WP05: FR-006, NFR-003, D-06).

Every fixture is ledger-seeded. Absence assertions follow a positive control on the
same fixture shape.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

import charter.activation.pack_context as pack_context_module
from charter.activation.activation_ledger import ActiveCharterConfigError, DenySet
from charter.activation.pack_context import PackContext
from charter.offering.artifact_kinds import ArtifactKind
from kernel.activation_ledger_store import activation_ledger_path
from specify_cli.cli.commands.charter import charter_app
from tests._factories.activation_ledger import read_activation_ledger, seed_activation_ledger

pytestmark = [pytest.mark.fast]

_RUNNER = CliRunner()
_A = "001-architectural-integrity-standard"
_D = "003-decision-documentation-requirement"
_OTHER = "010-specification-fidelity-requirement"
_TACTIC = "acceptance-test-first"


def _project(tmp_path: Path, *, config: str = "", **ledger: list[str]) -> Path:
    (tmp_path / ".kittify").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".kittify" / "config.yaml").write_text(textwrap.dedent(config).lstrip() or "{}\n", encoding="utf-8")
    seed_activation_ledger(tmp_path, mission_type_activations=["software-dev"], **ledger)
    return tmp_path


def test_denied_defaults_to_empty() -> None:
    ctx = PackContext(activated_kinds=frozenset(), activated_mission_types=frozenset(), pack_roots=(), org_pack_names=(), repo_root=Path("."))

    assert ctx.denied == ()
    assert ctx.denied_for(ArtifactKind.DIRECTIVE) == DenySet.EMPTY
    assert ctx.deactivated_urns == frozenset()


def test_from_config_records_the_deny_per_plural_sorted(tmp_path: Path) -> None:
    ctx = PackContext.from_config(_project(tmp_path, deactivated_tactics=[_TACTIC], deactivated_directives=[_D]))

    assert [plural for plural, _ in ctx.denied] == ["directives", "tactics"]
    assert not ctx.denied_for(ArtifactKind.TACTIC).admits(_TACTIC)
    assert not ctx.denied_for(ArtifactKind.DIRECTIVE).admits("DIRECTIVE_003")
    assert ctx.denied_for(ArtifactKind.PARADIGM) == DenySet.EMPTY
    assert ctx.deactivated_urns == frozenset({"directive:DIRECTIVE_003", f"tactic:{_TACTIC}"})


def test_admits_under_an_absent_all_list_needs_the_token_available(tmp_path: Path) -> None:
    ctx = PackContext.from_config(_project(tmp_path, deactivated_directives=[_D]))
    available = frozenset({_A, _D})

    assert ctx.admits(ArtifactKind.DIRECTIVE, _A, available=available)
    assert not ctx.admits(ArtifactKind.DIRECTIVE, _D, available=available)
    assert not ctx.admits(ArtifactKind.DIRECTIVE, "not-available", available=available)
    assert ctx.effective_ids(ArtifactKind.DIRECTIVE, available) == frozenset({_A})


def test_admits_under_a_present_list_reads_the_netted_list(tmp_path: Path) -> None:
    ctx = PackContext.from_config(_project(tmp_path, activated_directives=[_A, _D], deactivated_directives=[_D]))

    assert ctx.allow_for(ArtifactKind.DIRECTIVE) == frozenset({_A})
    assert ctx.admits(ArtifactKind.DIRECTIVE, _A, available=frozenset())
    assert not ctx.admits(ArtifactKind.DIRECTIVE, _D, available=frozenset({_D}))
    assert not ctx.admits(ArtifactKind.DIRECTIVE, _OTHER, available=frozenset({_OTHER}))


def test_admits_under_an_absent_required_list_admits_nothing_beyond_the_floor() -> None:
    ctx = PackContext(activated_kinds=frozenset(), activated_mission_types=frozenset(), pack_roots=(), org_pack_names=(), repo_root=Path("."))

    assert not ctx.admits(ArtifactKind.SKILL, "s", available=frozenset({"s"}))
    assert ctx.admits(ArtifactKind.TACTIC, "t", available=frozenset({"t"}))


def test_absent_lists_stay_none(tmp_path: Path) -> None:
    ctx = PackContext.from_config(_project(tmp_path, deactivated_directives=[_D]))

    assert ctx.allow_for(ArtifactKind.DIRECTIVE) is None
    assert ctx.allow_for(ArtifactKind.TACTIC) is None


def test_pack_context_stays_hashable_and_comparable(tmp_path: Path) -> None:
    root = _project(tmp_path, deactivated_directives=[_D])
    first, second = PackContext.from_config(root), PackContext.from_config(root)

    assert first == second
    assert hash(first) == hash(second)
    assert {first: 1}[second] == 1
    assert first != PackContext.from_config(_project(tmp_path / "other"))


def test_no_floor_read_without_a_deny_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-003: the strict floor reader runs only for a non-empty deny list."""
    calls: list[ArtifactKind] = []
    real = pack_context_module.read_org_required_tokens

    def spy(repo_root: Path, kind: ArtifactKind, *, strict: bool) -> object:
        calls.append(kind)
        return real(repo_root, kind, strict=strict)

    monkeypatch.setattr(pack_context_module, "read_org_required_tokens", spy)
    PackContext.from_config(_project(tmp_path / "plain", activated_directives=[_A]))
    assert calls == []

    PackContext.from_config(_project(tmp_path / "denied", deactivated_tactics=[_TACTIC]))
    assert calls == [ArtifactKind.TACTIC]


def test_a_malformed_ledger_fails_closed(tmp_path: Path) -> None:
    root = _project(tmp_path)
    activation_ledger_path(root).write_text("deactivated_directives: not-a-list\n", encoding="utf-8")

    with pytest.raises(ActiveCharterConfigError):
        PackContext.from_config(root)


def test_an_unreadable_floor_fails_closed_only_when_a_deny_list_exists(tmp_path: Path) -> None:
    config = """
        charter_packs:
          org:
            packs:
              - name: gone
                local_path: org-packs/gone
    """
    plain = _project(tmp_path / "plain", config=config)
    assert PackContext.from_config(plain).denied == ()  # positive control: no deny, no floor read

    denied = _project(tmp_path / "denied", config=config, deactivated_directives=[_D])
    with pytest.raises(ActiveCharterConfigError) as raised:
        PackContext.from_config(denied)
    assert "org required floor cannot be read" in raised.value.body


def test_writers_derive_from_the_ledger_not_the_netted_context(tmp_path: Path) -> None:
    """Netting affects reads only: a hand-edited id and a denied id in the allow list survive an activation."""
    root = _project(tmp_path, activated_directives=[_A, _D, "hand-edited-unknown"], deactivated_directives=[_D])
    assert PackContext.from_config(root).allow_for(ArtifactKind.DIRECTIVE) == frozenset({_A, "hand-edited-unknown"})

    result = _RUNNER.invoke(charter_app, ["activate", "--repo-root", str(root), "--no-compile", "directive", _OTHER])

    assert result.exit_code == 0, result.output
    ledger = read_activation_ledger(root)
    assert {_A, _D, "hand-edited-unknown", _OTHER} <= set(ledger["activated_directives"])
    assert ledger["deactivated_directives"] == [_D]


def test_with_allow_lists_replaces_only_the_named_sets_and_keeps_every_other_field() -> None:
    """F6: the typed replacement the resynthesis preflight uses keeps the deny and every unnamed field."""
    deny = (("directives", DenySet(frozenset({_D}))),)
    ctx = PackContext(
        activated_kinds=frozenset({"directives"}),
        activated_mission_types=frozenset({"software-dev"}),
        pack_roots=(Path("builtin"),),
        org_pack_names=("acme",),
        repo_root=Path("."),
        activated_tactics=frozenset({_TACTIC}),
        activated_skills=frozenset(),
        denied=deny,
    )

    assert ctx.with_allow_lists({}) == ctx  # every field carried over, none dropped
    replaced = ctx.with_allow_lists({"activated_directives": frozenset({_A})})

    assert replaced.allow_for(ArtifactKind.DIRECTIVE) == frozenset({_A})
    assert replaced.allow_for(ArtifactKind.TACTIC) == frozenset({_TACTIC})
    assert replaced.allow_for(ArtifactKind.SKILL) == frozenset()
    assert replaced.denied == deny
    with pytest.raises(ValueError, match="Not a per-kind activation key"):
        ctx.with_allow_lists({"mission_type_activations": frozenset()})
