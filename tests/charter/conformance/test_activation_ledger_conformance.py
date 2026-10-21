"""Runner of the activation-ledger conformance table (WP10: FR-015, FR-024, data-model.md section 8).

``activation_ledger_cases.yaml`` is the corpus: plain data that spec-kitty-charter
and open-packs port. This runner turns each row into calls on core's activation
API inside a ``tmp_path`` project seeded through ``tests/_factories/activation_ledger.py``
and asserts exactly the row's ``expect`` mapping. An ``expect`` key the section's
adapter does not observe fails the row, which keeps the table honest.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from charter.activation.action_governance_bundle import resolve_action_governance_bundle
from charter.activation.activation_engine import RequiredArtifactDeactivationError, UnknownActivationIdError, promote_activations
from charter.activation.activation_ledger import DENY_KEYS, allow_key
from charter.activation.active_charter_service_builder import build_active_charter_service
from charter.activation.api import ActiveCharterConfigError, IdentityIndex, apply_ledger_migration, plan_ledger_migration
from charter.activation.cascade import CascadeScope, ReferencedArtifact, cascade_activation_targets
from charter.activation.invocation_context import ProjectContext
from charter.activation.org_pack_discovery import read_org_required_provenance
from charter.activation.pack_context import PackContext
from charter.activation.pack_manager import ActiveCharterManager, resolve_activation_write_target
from charter.activation.preset_application import apply_preset_plan, plan_preset_application
from charter.offering.artifact_kinds import ArtifactKind
from charter.offering.drg.models import DRGEdge, DRGGraph, DRGNode, NodeKind, Relation
from kernel.activation_ledger_store import activation_ledger_path
from specify_cli.cli.commands.charter import charter_app
from tests._factories.activation_ledger import read_activation_ledger, seed_activation_ledger

pytestmark = [pytest.mark.fast]

CASES_FILE = Path(__file__).with_name("activation_ledger_cases.yaml")
SCHEMA = "activation-ledger-conformance/1"
SECTIONS = ("effective_set", "identity", "readers", "cascade", "deactivation", "ledger_migration")
REGISTER_DOC = Path(__file__).resolve().parents[3] / "docs" / "architecture" / "activation-ledger-and-charter-contract.md"

#: The open rows of the divergence register (doc name -> table id). Aligned rows are not here.
REGISTER_OPEN_ROWS: Mapping[str, str] = {
    "Required on read": "required-on-read",
    "Write-time floor": "write-time-floor",
    "Preset `--force`": "preset-force-clears-exclusions",
    "Unknown deny keys": "unknown-deny-key-preserved",
    "Stale required deny": "stale-required-deny-inert",
    "Languages": "languages-authored-vs-derived",
    "Id spelling": "id-spelling",
    "Unknown token": "unknown-token",
}
#: Charter #125 aligned the contract's select/deactivate with core (R8, 1:1): never a divergence.
ALIGNED_OPERATIONS = ("activate", "deactivate", "select")
DIVERGENCE_FIELDS = frozenset({"id", "core", "contract", "status", "ruling", "cases"})

_RUNNER = CliRunner()
_CHARTER_POINTER = Path(".kittify", "charter", "charter.yaml")
_CONFIG = Path(".kittify", "config.yaml")
_SURFACE_FILES: Mapping[str, Path] = {"charter_yaml": _CHARTER_POINTER, "config_yaml": _CONFIG}
_STILL_ACTIVE = re.compile(r"Cascade: ([\w-]+)/(\S+): still active \(no allow-list")
_SKIPPED_REQUIRED = re.compile(r"Cascade: ([\w-]+)/(\S+): skipped \(required by ([^)]+)\)")


def load_cases() -> dict[str, Any]:
    """The conformance table, parsed (plain YAML)."""
    loaded: dict[str, Any] = yaml.safe_load(CASES_FILE.read_text(encoding="utf-8"))
    return loaded


CASES = load_cases()


def _rows(section: str) -> list[Any]:
    return [pytest.param(row, id=row["id"]) for row in CASES[section]]


def _all_cases() -> Iterator[dict[str, Any]]:
    for section in SECTIONS:
        yield from CASES[section]


# --------------------------------------------------------------------------- #
# Project fixture (ledger-seeded through the factory)
# --------------------------------------------------------------------------- #


def _write_yaml(path: Path, data: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(dict(data), sort_keys=False) if data else "{}\n", encoding="utf-8")


def _config_text(required: Mapping[str, Any]) -> str:
    if not required:
        return "{}\n"
    lines = ["charter_packs:", "  org:", "    packs:"]
    for name in required:
        lines += [f"      - name: {name}", f"        local_path: org-packs/{name}"]
    return "\n".join(lines) + "\n"


def _seed_ledger(root: Path, ledger: Mapping[str, Any]) -> None:
    """Known keys through the factory's guarded writer; an unknown deny key verbatim (the writer refuses it)."""
    known = {key: value for key, value in ledger.items() if not key.startswith("deactivated_") or key in DENY_KEYS}
    seed_activation_ledger(root, **known)
    unknown = {key: value for key, value in ledger.items() if key not in known}
    if unknown:
        path = activation_ledger_path(root)
        current = read_activation_ledger(root)
        _write_yaml(path, {**current, **unknown})


def build_project(root: Path, *, required: Mapping[str, Any], ledger: Mapping[str, Any]) -> Path:
    """A project with the org packs *required* declares and the ledger *ledger*."""
    for name, lists in required.items():
        body = {"schema_version": 1, "org_name": name.title(), **lists}
        _write_yaml(root / "org-packs" / name / "org-charter.yaml", body)
    (root / ".kittify").mkdir(parents=True, exist_ok=True)
    (root / _CONFIG).write_text(_config_text(required), encoding="utf-8")
    _seed_ledger(root, ledger)
    return root


def assert_expected(row: Mapping[str, Any], observed: Mapping[str, Any]) -> None:
    """Exactly the row's ``expect``; an expect key the adapter did not observe fails the row."""
    expect: Mapping[str, Any] = row["expect"]
    unknown = sorted(set(expect) - set(observed))
    assert not unknown, f"{row['id']}: expect keys this section does not observe: {unknown}"
    assert {key: observed[key] for key in expect} == dict(expect), row["id"]


# --------------------------------------------------------------------------- #
# Adapters, one per section
# --------------------------------------------------------------------------- #


def _promote_required(root: Path, kind: ArtifactKind) -> list[str]:
    """The write-time floor: promote the org-required stems into the kind's allow list."""
    key = allow_key(kind)
    floor = sorted(read_org_required_provenance(root, kind, strict=True))
    target, data, save = resolve_activation_write_target(root)
    promote_activations({key: floor}, config_path=target, config_data=data, save=save, effective_sets={})
    return list(read_activation_ledger(root).get(key) or [])


def observe_effective_set(row: Mapping[str, Any], root: Path) -> dict[str, Any]:
    """``effective_set`` and ``identity``: ``PackContext.effective_ids`` over the row's available ids."""
    build_project(root, required=row.get("required", {}), ledger=row["ledger"])
    kind = ArtifactKind(row["kind"])
    observed: dict[str, Any] = {}
    if row.get("promote_required"):
        observed["allow_after"] = _promote_required(root, kind)
    observed["effective"] = sorted(PackContext.from_config(root).effective_ids(kind, frozenset(row["available"])))
    return observed


def _served_by_bundle(root: Path, kind: ArtifactKind, artifact_id: str) -> bool:
    bundle = resolve_action_governance_bundle(root, action="implement", mission_type="software-dev", feature_dir=None)
    if kind is ArtifactKind.TACTIC:
        return artifact_id in bundle.tactic_ids
    return f"{kind.value}:{artifact_id}" in {node.urn for node in bundle.merged.nodes}


def _served_by_service(root: Path, kind: ArtifactKind, artifact_id: str) -> bool:
    service = build_active_charter_service(root)
    catalogue = service.tactics if kind is ArtifactKind.TACTIC else service.agent_profiles
    return artifact_id in catalogue


_READERS: Mapping[str, Callable[[Path, ArtifactKind, str], bool]] = {
    "action_bundle": _served_by_bundle,
    "charter_service": _served_by_service,
}


def observe_reader(row: Mapping[str, Any], root: Path) -> dict[str, Any]:
    build_project(root, required={}, ledger=row["ledger"])
    return {"served": _READERS[row["reader"]](root, ArtifactKind(row["kind"]), row["artifact_id"])}


def _graph(edges: list[list[str]]) -> DRGGraph:
    urns = sorted({urn for source, target, _relation in edges for urn in (source, target)})
    return DRGGraph(
        schema_version="1.0",
        generated_at="2026-10-20T00:00:00Z",
        generated_by="activation-ledger-conformance",
        nodes=[DRGNode(urn=urn, kind=NodeKind(urn.partition(":")[0])) for urn in urns],
        edges=[DRGEdge(source=source, target=target, relation=Relation(relation)) for source, target, relation in edges],
    )


def _scope(value: str | list[str]) -> CascadeScope:
    if value == "all":
        return CascadeScope.all()
    return CascadeScope(kinds=frozenset(ArtifactKind(kind) for kind in value))


def _reference(ref: ReferencedArtifact) -> dict[str, Any]:
    return {"id": ref.artifact_id, "via_requires": ref.via_requires, "required_by": list(ref.required_by)}


def observe_cascade(row: Mapping[str, Any], _root: Path) -> dict[str, Any]:
    result = cascade_activation_targets(
        _graph(row["graph"]["edges"]),
        row["source"],
        _scope(row["scope"]),
        deactivated_urns=frozenset(row["deactivated"]),
        include_deactivated=row["include_deactivated"],
    )
    return {
        "activated": {kind: sorted(ids) for kind, ids in result.activated.items()},
        "skipped_by_scope": {kind: sorted(ids) for kind, ids in result.skipped_by_scope.items()},
        "skipped_deactivated": {kind: [_reference(ref) for ref in refs] for kind, refs in result.skipped_deactivated.items()},
        "unreached_behind_deactivated": {kind: sorted(ids) for kind, ids in result.unreached_behind_deactivated.items()},
    }


def _refusal(exc: Exception) -> dict[str, Any]:
    if isinstance(exc, RequiredArtifactDeactivationError):
        return {"reason": exc.reason, "packs": sorted(entry.pack for entry in exc.requiring), "policy_key": exc.policy_key}
    return {"reason": "unknown"}


def _deactivate(row: Mapping[str, Any], root: Path) -> dict[str, Any]:
    token = ArtifactKind(row["kind"]).operator_token
    observed: dict[str, Any] = {"refused": None, "deactivated": []}
    try:
        observed["deactivated"] = ActiveCharterManager().deactivate(ProjectContext(repo_root=root), token, row["artifact_id"]).deactivated
    except (RequiredArtifactDeactivationError, UnknownActivationIdError) as exc:
        observed["refused"] = _refusal(exc)
    return observed


def _children(output: str) -> dict[str, list[dict[str, Any]]]:
    """The cascade children the CLI reports (``charter deactivate --cascade`` renders them only).

    The row names the children it pins in ``artifacts``; every other reported child is left out.
    """
    flat = " ".join(output.split())
    children: dict[str, list[dict[str, Any]]] = {}
    for token, child in _STILL_ACTIVE.findall(flat):
        children.setdefault(ArtifactKind.from_operator_token(token).value, []).append({"id": child, "state": "still-active-no-allow-list"})
    for token, child, packs in _SKIPPED_REQUIRED.findall(flat):
        entry = {"id": child, "state": "skipped-required", "packs": sorted(pack.strip() for pack in packs.split(","))}
        children.setdefault(ArtifactKind.from_operator_token(token).value, []).append(entry)
    return children


def _cascade_deactivate(row: Mapping[str, Any], root: Path) -> dict[str, Any]:
    token = ArtifactKind(row["kind"]).operator_token
    args = ["deactivate", "--repo-root", str(root), "--no-compile", "--cascade", "all", token, row["artifact_id"]]
    result = _RUNNER.invoke(charter_app, args)
    assert result.exit_code == 0, result.output
    named = {entry["stem"] for entry in row["artifacts"]} - {row["artifact_id"]}
    children = {kind: [child for child in found if child["id"] in named] for kind, found in _children(result.output).items()}
    return {"children": {kind: found for kind, found in children.items() if found}}


def _deny_mapping(root: Path) -> dict[str, Any]:
    return {key: value for key, value in read_activation_ledger(root).items() if key.startswith("deactivated_")}


def _preset(row: Mapping[str, Any], root: Path) -> dict[str, Any]:
    force = row["op"] == "preset_force"
    outcome = apply_preset_plan(root, plan_preset_application(root, "built-in", row["preset"]), force=force)
    return {"cleared": outcome.cleared, "kept_deactivated": outcome.kept_deactivated, "deny_after": _deny_mapping(root)}


_DEACTIVATION_OPS: Mapping[str, Callable[[Mapping[str, Any], Path], dict[str, Any]]] = {
    "deactivate": _deactivate,
    "cascade_deactivate": _cascade_deactivate,
    "preset": _preset,
    "preset_force": _preset,
}


def observe_deactivation(row: Mapping[str, Any], root: Path) -> dict[str, Any]:
    build_project(root, required=row.get("required", {}), ledger=row["ledger"])
    observed = _DEACTIVATION_OPS[row["op"]](row, root)
    observed["ledger_after"] = read_activation_ledger(root)
    return observed


def _write_surfaces(root: Path, surfaces: Mapping[str, Mapping[str, Any]]) -> None:
    (root / ".kittify").mkdir(parents=True, exist_ok=True)
    for name, data in surfaces.items():
        path = activation_ledger_path(root) if name == "ledger" else root / _SURFACE_FILES[name]
        _write_yaml(path, data)


def _keys_left(root: Path, surfaces: Mapping[str, Any]) -> dict[str, list[str]]:
    left: dict[str, list[str]] = {}
    for name in surfaces:
        if name in _SURFACE_FILES:
            loaded = yaml.safe_load((root / _SURFACE_FILES[name]).read_text(encoding="utf-8")) or {}
            left[name] = sorted(loaded)
    return left


def _ledger_or_none(root: Path) -> dict[str, Any] | None:
    return read_activation_ledger(root) if activation_ledger_path(root).is_file() else None


def observe_ledger_migration(row: Mapping[str, Any], root: Path) -> dict[str, Any]:
    _write_surfaces(root, row["surfaces"])
    try:
        plan = plan_ledger_migration(root)
    except ActiveCharterConfigError as exc:
        return {"error": "unknown_ledger_key" if "Unknown activation ledger key" in exc.body else exc.body}
    if plan.refusal is not None:
        return {"refused": {"key": plan.refusal.key, "reason": plan.refusal.reason}, "ledger": _ledger_or_none(root)}
    apply_ledger_migration(root, plan)
    return {"refused": None, "ledger": _ledger_or_none(root), "keys_left": _keys_left(root, row["surfaces"])}


# --------------------------------------------------------------------------- #
# The table, row by row
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("row", _rows("effective_set"))
def test_effective_set(row: dict[str, Any], tmp_path: Path) -> None:
    assert_expected(row, observe_effective_set(row, tmp_path))


@pytest.mark.parametrize("row", _rows("identity"))
def test_identity(row: dict[str, Any], tmp_path: Path) -> None:
    assert_expected(row, observe_effective_set(row, tmp_path))


@pytest.mark.parametrize("row", _rows("readers"))
def test_readers(row: dict[str, Any], tmp_path: Path) -> None:
    assert_expected(row, observe_reader(row, tmp_path))


@pytest.mark.parametrize("row", _rows("cascade"))
def test_cascade(row: dict[str, Any], tmp_path: Path) -> None:
    assert_expected(row, observe_cascade(row, tmp_path))


@pytest.mark.parametrize("row", _rows("deactivation"))
def test_deactivation(row: dict[str, Any], tmp_path: Path) -> None:
    assert_expected(row, observe_deactivation(row, tmp_path))


@pytest.mark.parametrize("row", _rows("ledger_migration"))
def test_ledger_migration(row: dict[str, Any], tmp_path: Path) -> None:
    assert_expected(row, observe_ledger_migration(row, tmp_path))


# --------------------------------------------------------------------------- #
# Meta: the table stays honest (T060.4)
# --------------------------------------------------------------------------- #


def test_schema_and_sections() -> None:
    assert CASES["schema"] == SCHEMA
    assert set(CASES) == {"schema", "divergences", *SECTIONS}
    for section in SECTIONS:
        assert CASES[section], f"section {section} has no row"


def test_row_ids_are_unique() -> None:
    ids = [row["id"] for row in _all_cases()]
    assert len(ids) == len(set(ids)), sorted({item for item in ids if ids.count(item) > 1})


def _listed_tokens(row: Mapping[str, Any]) -> set[str]:
    """Every artifact token a row names: ledger and surface lists, available ids, the target and graph URN tails."""
    tokens: set[str] = set(row.get("available", ()))
    mappings = [row.get("ledger") or {}, *(row.get("surfaces") or {}).values()]
    for mapping in mappings:
        for key, value in mapping.items():
            if key.startswith(("activated_", "deactivated_")) and key != "activated_kinds":
                tokens.update(value)
    if "artifact_id" in row:
        tokens.add(row["artifact_id"])
    for edge in (row.get("graph") or {}).get("edges", ()):
        tokens.update(urn.partition(":")[2] for urn in edge[:2])
    return tokens


def test_every_case_records_both_spellings() -> None:
    for row in _all_cases():
        artifacts = row["artifacts"]
        assert isinstance(artifacts, list), row["id"]
        for entry in artifacts:
            assert set(entry) == {"kind", "stem", "declared_id"}, row["id"]
            assert all(isinstance(entry[field], str) and entry[field] for field in entry), row["id"]
        spellings = {entry[field] for entry in artifacts for field in ("stem", "declared_id")}
        missing = sorted(_listed_tokens(row) - spellings)
        assert not missing, f"{row['id']}: tokens without an artifacts entry: {missing}"


def test_recorded_spellings_match_the_identity_index(tmp_path: Path) -> None:
    """A built-in artifact carries its real declared id; a synthetic one (unknown to the index) has ``declared_id == stem``."""
    index = IdentityIndex.build(build_project(tmp_path, required={}, ledger={}))
    kinds = {kind.value: kind for kind in ArtifactKind}
    for row in _all_cases():
        for entry in row["artifacts"]:
            kind = kinds.get(entry["kind"])
            if kind is None:
                continue  # an unknown kind (the unknown-deny-key case): no index exists for it
            assert (index.declared_id(kind, entry["stem"]) or entry["stem"]) == entry["declared_id"], (row["id"], entry)


def test_divergences_cite_existing_cases() -> None:
    case_ids = {row["id"] for row in _all_cases()}
    for entry in CASES["divergences"]:
        assert set(entry) == DIVERGENCE_FIELDS, entry["id"]
        assert entry["cases"], entry["id"]
        assert set(entry["cases"]) <= case_ids, (entry["id"], sorted(set(entry["cases"]) - case_ids))


def test_no_aligned_operation_is_listed_as_a_divergence() -> None:
    for entry in CASES["divergences"]:
        assert entry["id"].split("-")[0] not in ALIGNED_OPERATIONS, entry["id"]


def _register_rows() -> dict[str, str]:
    """The divergence register of the architecture page: row name -> status cell."""
    text = REGISTER_DOC.read_text(encoding="utf-8")
    section = text.split("## Divergence register", 1)[1].split("\n## ", 1)[0]
    rows: dict[str, str] = {}
    for line in section.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) == 4 and cells[0] not in ("Divergence", "---"):
            rows[cells[0]] = cells[3]
    return rows


def test_divergences_mirror_the_open_rows_of_the_register() -> None:
    register = _register_rows()
    open_rows = {name for name, status in register.items() if "Aligned" not in status}
    assert open_rows == set(REGISTER_OPEN_ROWS), sorted(open_rows ^ set(REGISTER_OPEN_ROWS))
    assert {"Activate", "Deactivate"} <= set(register) - open_rows
    assert [entry["id"] for entry in CASES["divergences"]] == list(REGISTER_OPEN_ROWS.values())


def test_divergence_rulings_mirror_the_register() -> None:
    """A row the register rules carries that ruling in the corpus; a row it leaves open stays open."""
    register = _register_rows()
    by_id = {entry["id"]: entry for entry in CASES["divergences"]}
    for name, row_id in REGISTER_OPEN_ROWS.items():
        status_cell, entry = register[name], by_id[row_id]
        if status_cell.startswith("**Ruled"):
            assert entry["status"] in ("ruled", "logged"), row_id
            assert entry["ruling"], row_id
            numbered = re.match(r"\*\*Ruled (R\d+)\*\*", status_cell)
            if numbered:
                assert entry["ruling"].startswith(f"{numbered.group(1)}:"), (row_id, entry["ruling"])
        else:
            assert status_cell.startswith("Open"), (name, status_cell)
            assert (entry["status"], entry["ruling"]) == ("open", None), row_id


# --------------------------------------------------------------------------- #
# Non-vacuity (T063.4): with the deny forced empty, the effective-set rows fail
# --------------------------------------------------------------------------- #


def _rows_failing_without_deny(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> list[str]:
    real = PackContext.from_config

    def without_deny(_cls: type[PackContext], repo_root: Path) -> PackContext:
        return dataclasses.replace(real(repo_root), denied=())

    monkeypatch.setattr(PackContext, "from_config", classmethod(without_deny))
    failing: list[str] = []
    for index, row in enumerate([*CASES["effective_set"], *CASES["identity"]]):
        try:
            assert_expected(row, observe_effective_set(row, tmp_path / str(index)))
        except AssertionError:
            failing.append(row["id"])
    return failing


def test_a_forced_empty_deny_fails_the_effective_set_rows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    failing = _rows_failing_without_deny(monkeypatch, tmp_path)

    assert "absent-all-minus-deny" in failing, failing
    assert "unknown-token-kept-as-its-own-stem" in failing, failing


def test_the_fixture_yaml_is_plain_data() -> None:
    """No Python expression and no repository path except the legacy surface names (T059.3)."""
    text = CASES_FILE.read_text(encoding="utf-8")
    assert "!!python" not in text
    paths = set(re.findall(r"\.kittify/[\w./-]+", text))
    assert paths <= {_CHARTER_POINTER.as_posix()}, paths
