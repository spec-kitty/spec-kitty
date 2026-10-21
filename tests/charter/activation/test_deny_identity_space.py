"""Identity-space effective deny (WP05: FR-006, data-model.md §2 / §2.1, R4/R5).

``resolve_deny`` expands each ledger deny entry (a stem) into every spelling a
reader filters by -- the stem, the declared id and the DRG URN -- so a stem
deny subtracts a declared-id allow entry. ``_effective_deny`` subtracts the
required floor in the same space. The conformance-shaped rows of data-model.md
§2 are pinned here through :class:`PackContext`, each on a ledger-seeded
fixture with a positive control first (the id is in force before the deny).
"""

from __future__ import annotations

import ast
import textwrap
from pathlib import Path

import pytest

from charter.activation.activation_ledger import DenySet, _effective_deny, resolve_deny
from charter.activation.identity_index import IdentityIndex
from charter.activation.pack_context import PackContext
from charter.offering.artifact_kinds import ArtifactKind
from tests._factories.activation_ledger import seed_activation_ledger

pytestmark = [pytest.mark.fast]

_SRC_ACTIVATION = Path(__file__).resolve().parents[3] / "src" / "charter" / "activation"

#: Built-in directive stems and their declared ids.
_A = "001-architectural-integrity-standard"
_D = "003-decision-documentation-requirement"
_D_ID = "DIRECTIVE_003"
_OTHER = "010-specification-fidelity-requirement"


class _FakeIdentity:
    """Two directives known by stem and declared id; everything else unknown."""

    _IDS = {"canvas-review": "PROC_CANVAS_REVIEW", "keep": "KEEP"}

    def declared_id(self, kind: ArtifactKind, token: str) -> str | None:
        if token in self._IDS:
            return self._IDS[token]
        return token if token in self._IDS.values() else None

    def stem(self, kind: ArtifactKind, token: str) -> str | None:
        if token in self._IDS:
            return token
        return next((stem for stem, declared in self._IDS.items() if declared == token), None)


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")


def _project(tmp_path: Path, *, required: str | None = None, **ledger: list[str]) -> Path:
    """A ledger-seeded project; *required* is an org pack's ``required_*`` YAML block."""
    lines: list[str] = []
    if required is not None:
        _write(tmp_path / "org-packs" / "acme" / "org-charter.yaml", f"schema_version: 1\norg_name: Acme\n{textwrap.dedent(required)}")
        lines = ["charter_packs:", "  org:", "    packs:", "      - name: acme", "        local_path: org-packs/acme"]
    (tmp_path / ".kittify").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".kittify" / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    seed_activation_ledger(tmp_path, mission_type_activations=["software-dev"], **ledger)
    return tmp_path


# --------------------------------------------------------------------------- #
# DenySet / resolve_deny / _effective_deny
# --------------------------------------------------------------------------- #


def test_deny_set_refuses_every_spelling() -> None:
    deny = resolve_deny(ArtifactKind.PROCEDURE, ["canvas-review"], _FakeIdentity())

    assert deny == DenySet(frozenset({"canvas-review"}), frozenset({"PROC_CANVAS_REVIEW"}), frozenset({"procedure:PROC_CANVAS_REVIEW"}))
    for spelling in ("canvas-review", "PROC_CANVAS_REVIEW", "procedure:PROC_CANVAS_REVIEW"):
        assert not deny.admits(spelling)
    assert deny.admits("keep")
    assert deny.admits("KEEP")


def test_a_declared_id_deny_entry_resolves_to_its_stem() -> None:
    deny = resolve_deny(ArtifactKind.PROCEDURE, ["PROC_CANVAS_REVIEW"], _FakeIdentity())

    assert deny.stems == frozenset({"canvas-review"})
    assert not deny.admits("canvas-review")


def test_an_unknown_token_stays_a_stem_with_its_own_urn() -> None:
    deny = resolve_deny(ArtifactKind.MISSION_STEP_CONTRACT, ["software-dev/implement"], _FakeIdentity())

    assert deny.stems == frozenset({"software-dev/implement"})
    assert deny.declared_ids == frozenset()
    assert deny.urns == frozenset({"mission_step_contract:software-dev/implement"})
    assert not deny.admits("software-dev/implement")


def test_the_empty_deny_set_admits_everything_and_is_falsy() -> None:
    assert DenySet() == DenySet.EMPTY
    assert not DenySet.EMPTY
    assert DenySet.EMPTY.admits("anything")
    assert resolve_deny(ArtifactKind.TACTIC, [], _FakeIdentity()) == DenySet.EMPTY
    assert resolve_deny(ArtifactKind.TACTIC, ["x"], _FakeIdentity())


def test_effective_deny_subtracts_the_floor_in_identity_space() -> None:
    """A floor spelled as the declared id still exempts the stem deny entry (R3/R4)."""
    deny = _effective_deny(ArtifactKind.PROCEDURE, ["canvas-review", "keep", "gone"], ["PROC_CANVAS_REVIEW"], _FakeIdentity())

    assert deny.admits("canvas-review")
    assert deny.admits("PROC_CANVAS_REVIEW")
    assert not deny.admits("keep")
    assert not deny.admits("gone")
    assert _effective_deny(ArtifactKind.PROCEDURE, ["keep"], ["keep"], _FakeIdentity()) == DenySet.EMPTY


def test_resolve_deny_against_the_real_index_maps_a_directive_stem() -> None:
    deny = resolve_deny(ArtifactKind.DIRECTIVE, [_D], IdentityIndex(org_roots=[]))

    assert deny.declared_ids == frozenset({_D_ID})
    assert deny.urns == frozenset({"directive:DIRECTIVE_003"})


# --------------------------------------------------------------------------- #
# data-model.md §2 conformance rows
# --------------------------------------------------------------------------- #


def _available(repo: Path) -> frozenset[str]:
    return frozenset(entry.stem for entry in IdentityIndex.build(repo)._table(ArtifactKind.DIRECTIVE).entries)


def test_row1_absent_all_minus_the_deny(tmp_path: Path) -> None:
    before = PackContext.from_config(_project(tmp_path / "before"))
    available = _available(tmp_path / "before")
    assert _D in before.effective_ids(ArtifactKind.DIRECTIVE, available)  # positive control

    after = PackContext.from_config(_project(tmp_path / "after", deactivated_directives=[_D]))
    assert after.effective_ids(ArtifactKind.DIRECTIVE, available) == available - {_D}


def test_row2_present_list_minus_the_deny(tmp_path: Path) -> None:
    ctx = PackContext.from_config(_project(tmp_path, activated_directives=[_A, _D], deactivated_directives=[_D]))

    assert ctx.allow_for(ArtifactKind.DIRECTIVE) == frozenset({_A})
    assert ctx.effective_ids(ArtifactKind.DIRECTIVE, {_A, _D, _OTHER}) == frozenset({_A})


def test_row3_empty_list_stays_empty(tmp_path: Path) -> None:
    ctx = PackContext.from_config(_project(tmp_path, activated_directives=[], deactivated_directives=[_D]))

    assert ctx.allow_for(ArtifactKind.DIRECTIVE) == frozenset()
    assert ctx.effective_ids(ArtifactKind.DIRECTIVE, {_A, _D}) == frozenset()


def test_row4_a_stale_deny_of_a_required_id_is_inert(tmp_path: Path) -> None:
    required = f"required_directives:\n  - {_D_ID}\n"
    ctx = PackContext.from_config(_project(tmp_path, required=required, deactivated_directives=[_D]))

    assert ctx.denied_for(ArtifactKind.DIRECTIVE) == DenySet.EMPTY
    assert ctx.effective_ids(ArtifactKind.DIRECTIVE, {_A, _D}) == frozenset({_A, _D})


def test_row5_skill_absent_required_keeps_the_floor_and_drops_the_denied(tmp_path: Path) -> None:
    required = "required_skills:\n  - floor-skill\n"
    ctx = PackContext.from_config(_project(tmp_path, required=required, deactivated_skills=["other-skill", "floor-skill"]))

    assert ctx.allow_for(ArtifactKind.SKILL) == frozenset({"floor-skill"})
    assert ctx.effective_ids(ArtifactKind.SKILL, {"floor-skill", "other-skill"}) == frozenset({"floor-skill"})


def test_row7_declared_id_allow_with_a_stem_deny_is_empty(tmp_path: Path) -> None:
    before = PackContext.from_config(_project(tmp_path / "before", activated_directives=[_D_ID]))
    assert before.allow_for(ArtifactKind.DIRECTIVE) == frozenset({_D_ID})  # positive control

    after = PackContext.from_config(_project(tmp_path / "after", activated_directives=[_D_ID], deactivated_directives=[_D]))
    assert after.allow_for(ArtifactKind.DIRECTIVE) == frozenset()
    assert after.effective_ids(ArtifactKind.DIRECTIVE, {_D_ID, _D}) == frozenset()


# --------------------------------------------------------------------------- #
# Single helper pin (T023.8)
# --------------------------------------------------------------------------- #


def _defined_functions(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.name for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}


def test_activation_ledger_owns_the_only_effective_deny_helper() -> None:
    owners = {
        (path.relative_to(_SRC_ACTIVATION).as_posix(), name)
        for path in sorted(_SRC_ACTIVATION.rglob("*.py"))
        for name in _defined_functions(path)
        if "effective_deny" in name
    }
    assert owners == {("activation_ledger.py", "_effective_deny")}
    assert "_effective_deny_stems" not in _defined_functions(_SRC_ACTIVATION / "activation_engine.py")


# --------------------------------------------------------------------------- #
# The read path's raw strict floor (NFR-003)
# --------------------------------------------------------------------------- #


def test_read_org_required_tokens_is_the_raw_strict_union(tmp_path: Path) -> None:
    from charter.activation.activation_ledger import ActiveCharterConfigError
    from charter.activation.org_pack_discovery import read_org_required_tokens

    root = _project(tmp_path, required=f"required_directives:\n  - {_D_ID}\n  - {_A}\n")
    assert read_org_required_tokens(root, ArtifactKind.DIRECTIVE, strict=True) == [_D_ID, _A]
    assert read_org_required_tokens(root, ArtifactKind.TACTIC, strict=True) == []

    _write(root / "org-packs" / "acme" / "org-charter.yaml", "required_directives: not-a-list\n")
    with pytest.raises(ActiveCharterConfigError):
        read_org_required_tokens(root, ArtifactKind.DIRECTIVE, strict=True)
    assert read_org_required_tokens(root, ArtifactKind.DIRECTIVE, strict=False) == []


def test_top_level_keys_reads_the_mapping_keys(tmp_path: Path) -> None:
    from kernel.activation_ledger_store import top_level_keys

    path = tmp_path / "doc.yaml"
    path.write_text("a: 1\ndeactivated_tactics: [x]\n", encoding="utf-8")
    assert top_level_keys(path) == frozenset({"a", "deactivated_tactics"})
    assert top_level_keys(tmp_path / "missing.yaml") == frozenset()


def test_a_legacy_surface_without_deny_keys_is_not_parsed_for_deny(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-003: the read path answers "no deny list" from the cached key probe on a legacy surface."""
    import charter.activation.pack_context as pack_context_module
    from charter.activation.activation_ledger import ledger_may_hold_deny
    from kernel.activation_ledger_store import legacy_activation_scope
    from tests._factories.activation_ledger import legacy_seed

    plain = tmp_path / "plain"
    legacy_seed(plain, activated_tactics=[_A])
    with_deny = tmp_path / "with-deny"
    legacy_seed(with_deny, deactivated_directives=[_D])
    ledger = _project(tmp_path / "ledger")

    loads: list[Path] = []
    real = pack_context_module.load_activation_ledger
    monkeypatch.setattr(pack_context_module, "load_activation_ledger", lambda root, **kw: loads.append(root) or real(root, **kw))
    with legacy_activation_scope(plain), legacy_activation_scope(with_deny):
        assert not ledger_may_hold_deny(plain)
        assert pack_context_module.load_denied(plain) == ()
        assert loads == []
        assert ledger_may_hold_deny(with_deny)  # positive control: a deny key sends the read through
        assert pack_context_module.load_denied(with_deny) == ()  # ...and a legacy deny key is never applied (hole 6)
        assert loads == [with_deny]
    assert ledger_may_hold_deny(ledger)


def test_read_and_write_floors_give_the_same_effective_deny(tmp_path: Path) -> None:
    """The read path (raw tokens) and the write path (provenance stems) agree through ``_effective_deny``."""
    from charter.activation.org_pack_discovery import read_org_required_provenance, read_org_required_tokens

    lines = ["charter_packs:", "  org:", "    packs:"]
    for name, required in (("acme", _D_ID), ("acme-two", _A)):
        _write(tmp_path / "org-packs" / name / "org-charter.yaml", f"schema_version: 1\nrequired_directives: [{required}]\n")
        lines += [f"      - name: {name}", f"        local_path: org-packs/{name}"]
    (tmp_path / ".kittify").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".kittify" / "config.yaml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    identity = IdentityIndex.build(tmp_path)
    for deny in ([_D, _A, _OTHER], [_D_ID, "DIRECTIVE_001", "DIRECTIVE_010"]):
        read = _effective_deny(ArtifactKind.DIRECTIVE, deny, read_org_required_tokens(tmp_path, ArtifactKind.DIRECTIVE, strict=True), identity)
        write = _effective_deny(ArtifactKind.DIRECTIVE, deny, read_org_required_provenance(tmp_path, ArtifactKind.DIRECTIVE, strict=True), identity)
        assert read == write
        assert read.declared_ids == frozenset({"DIRECTIVE_010"})


def test_the_engine_holds_no_raw_deny_subtraction() -> None:
    names = _defined_functions(_SRC_ACTIVATION / "activation_engine.py")
    assert "_promotion_denied" not in names
