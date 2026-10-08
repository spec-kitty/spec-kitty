"""Parity gate: ``doctor charter-packs`` and the built-in-override gate share ONE policy loader.

SC-005 / FR-013 (#5767). The consumer allowlist, each pack's own sanction and the
consumer's revocations are combined in exactly one place,
``charter.offering.drg.override_policy``. This module proves that the doctor
collector and ``test_builtin_override_policy.py`` both reach a verdict through it:

1. structurally: the collector and the gate both call the shared loader and
   adjudicator and never parse a ``replaceable-builtins`` file themselves (AST,
   with a non-vacuity self-test);
2. behaviourally: on a two-pack fixture the collector's verdicts equal the gate's recipe;
3. structurally: both paths merge with ``project=None``, so neither lets a project node
   mask an org override.
"""

from __future__ import annotations

import ast
from pathlib import Path
from textwrap import dedent

import pytest

from charter.offering.drg.models import DRGGraph

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COLLECTOR = _REPO_ROOT / "src" / "specify_cli" / "cli" / "commands" / "_charter_pack_collect.py"
_GATE = Path(__file__).resolve().parent / "test_builtin_override_policy.py"

_REQUIRED_CALLS = frozenset({"load_effective_override_policy", "adjudicate_overrides"})
#: Parsers a consumer of the shared loader must never reach for directly.
_FORBIDDEN_CALLS = frozenset({"load_replaceable_builtins", "load_pack_sanction", "_load_consumer_policy", "safe_load"})


def _call_name(node: ast.Call) -> str | None:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _called_names(source: str) -> set[str]:
    return {name for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Call) and (name := _call_name(node))}


def _merge_calls_without_project_none(source: str) -> tuple[int, list[int]]:
    """Return ``(merge call count, line numbers of calls NOT passing project=None)``."""
    total = 0
    offenders: list[int] = []
    for node in ast.walk(ast.parse(source)):
        if not (isinstance(node, ast.Call) and _call_name(node) == "merge_three_layers"):
            continue
        total += 1
        keywords = {kw.arg: kw.value for kw in node.keywords}
        project = keywords.get("project")
        if not (isinstance(project, ast.Constant) and project.value is None):
            offenders.append(node.lineno)
    return total, offenders


@pytest.mark.parametrize("path", [_COLLECTOR, _GATE], ids=["collector", "gate"])
def test_consumer_uses_shared_loader_and_never_parses_sanction_files(path: Path) -> None:
    called = _called_names(path.read_text(encoding="utf-8"))

    assert called >= _REQUIRED_CALLS, f"{path.name} must call {sorted(_REQUIRED_CALLS - called)}"
    assert not (_FORBIDDEN_CALLS & called), f"{path.name} parses a sanction file itself: {sorted(_FORBIDDEN_CALLS & called)}"


def test_walker_is_not_vacuous() -> None:
    """The walker flags a synthetic source that parses the file itself and misses the loader."""
    synthetic = dedent(
        """
        import yaml

        def adjudicate(repo_root):
            return yaml.safe_load((repo_root / "replaceable-builtins.yaml").read_text())
        """
    )

    called = _called_names(synthetic)

    assert _FORBIDDEN_CALLS & called == {"safe_load"}
    assert not called >= _REQUIRED_CALLS
    total, offenders = _merge_calls_without_project_none("merge_three_layers(built_in=b, org_fragments=f, project=p)")
    assert (total, offenders) == (1, [1])


def _write_pack(root: Path, name: str, node_id: str, sanction: str | None) -> Path:
    pack = root / name
    (pack / "drg").mkdir(parents=True)
    (pack / "directives").mkdir()
    (pack / "drg" / "fragment.yaml").write_text(
        dedent(
            f"""\
            pack_name: {name}
            source_kind: local_path
            source_ref: {name}
            layer_index: 1
            provenance_marker: org
            nodes:
              - id: {node_id}
                kind: directives
                title: Override
                body_path: directives/{node_id}.directive.yaml
            edges: []
            """
        )
    )
    (pack / "directives" / f"{node_id}.directive.yaml").write_text(
        f"id: {node_id}\ntype: directive\ntitle: Override\nbody: |\n  Fixture.\nseverity: binding\nstatus: active\n"
    )
    if sanction is not None:
        (pack / "replaceable-builtins.yaml").write_text(sanction)
    return pack


def test_collector_and_gate_recipe_reach_identical_verdicts(tmp_path: Path) -> None:
    """Pack A sanctions its own override; pack B's override is unsanctioned."""
    from charter.activation.drg_activation import load_org_drg
    from charter.drg import load_built_in_graph
    from charter.offering.drg.merge import merge_three_layers
    from charter.offering.drg.override_policy import (
        adjudicate_overrides,
        configured_pack_names,
        find_overridden_builtins,
        load_effective_override_policy,
        pack_roots_from_fragments,
    )
    from specify_cli.cli.commands._charter_pack_collect import _collect_org_layer_data

    pack_a = _write_pack(tmp_path, "pack-a", "DIRECTIVE_001", "replaceable_builtins:\n  - urn: directive:DIRECTIVE_001\n    reason: pack A replaces it\n")
    pack_b = _write_pack(tmp_path, "pack-b", "DIRECTIVE_003", None)
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.yaml").write_text(
        f'charter_packs:\n  org:\n    packs:\n      - name: pack-a\n        local_path: "{pack_a}"\n      - name: pack-b\n        local_path: "{pack_b}"\n'
    )

    collected = _collect_org_layer_data(tmp_path)

    fragments = load_org_drg(tmp_path)
    built_in = load_built_in_graph()
    merged = merge_three_layers(built_in=built_in, org_fragments=fragments, project=None)
    roots = pack_roots_from_fragments(fragments, tmp_path)
    effective = load_effective_override_policy(tmp_path, roots, configured_pack_names=configured_pack_names(tmp_path, roots))
    verdict = adjudicate_overrides(find_overridden_builtins(merged, frozenset(n.urn for n in built_in.nodes)), effective)

    sanctioned = collected.get("sanctioned_overrides")
    unsanctioned = collected.get("unsanctioned_overrides")
    assert isinstance(sanctioned, list) and isinstance(unsanctioned, list)
    assert [(s["urn"], s["pack"], s["source"], s["reason"]) for s in sanctioned] == [(s.urn, s.pack, s.source, s.reason) for s in verdict.sanctioned]
    assert [(u["urn"], u["why"]) for u in unsanctioned] == [(u.urn, u.why) for u in verdict.unsanctioned]
    assert [s.urn for s in verdict.sanctioned] == ["directive:DIRECTIVE_001"]
    assert [u.urn for u in verdict.unsanctioned] == ["directive:DIRECTIVE_003"]


def test_collector_and_gate_merge_with_project_none() -> None:
    for path in (_COLLECTOR, _GATE):
        total, offenders = _merge_calls_without_project_none(path.read_text(encoding="utf-8"))
        assert total >= 1, f"{path.name}: no merge_three_layers call found (vacuous)"
        assert offenders == [], f"{path.name}: merge_three_layers without project=None at lines {offenders}"


def test_collector_and_gate_recipe_report_identical_policy_errors(tmp_path: Path) -> None:
    """An unknown revoked pack yields the same revocation error in both paths.

    Both resolve "configured" through the one ``configured_pack_names`` helper, so a
    configured pack is never reported unknown by one and known by the other.
    """
    from charter.activation.drg_activation import load_org_drg
    from charter.offering.drg.override_policy import (
        configured_pack_names,
        load_effective_override_policy,
        pack_roots_from_fragments,
    )
    from specify_cli.cli.commands._charter_pack_collect import _adjudicate_with_policy, _collect_org_layer_data

    pack_a = _write_pack(tmp_path, "pack-a", "DIRECTIVE_001", None)
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.yaml").write_text(f'charter_packs:\n  org:\n    packs:\n      - name: pack-a\n        local_path: "{pack_a}"\n')
    (tmp_path / ".kittify" / "doctrine").mkdir()
    (tmp_path / ".kittify" / "doctrine" / "replaceable-builtins.yaml").write_text("revoked_pack_sanctions:\n  - pack: pack-a\n  - pack: ghost-pack\n")

    fragments = load_org_drg(tmp_path)
    roots = pack_roots_from_fragments(fragments, tmp_path)
    gate = load_effective_override_policy(tmp_path, roots, configured_pack_names=configured_pack_names(tmp_path, roots))
    collector = _adjudicate_with_policy(_empty_graph(), frozenset(), tmp_path, fragments).effective
    collected = _collect_org_layer_data(tmp_path)

    assert gate.revocation_errors and any("ghost-pack" in e for e in gate.revocation_errors)
    assert not any("pack-a" in e for e in gate.revocation_errors)
    assert collector.revocation_errors == gate.revocation_errors
    assert collector.pack_errors == gate.pack_errors
    assert collector.consumer_error == gate.consumer_error
    errors = collected.get("errors")
    assert isinstance(errors, list) and all(e in errors for e in gate.revocation_errors)


def _empty_graph() -> DRGGraph:
    return DRGGraph(schema_version="1.0", generated_at="2026-06-01T00:00:00Z", generated_by="unit-test", nodes=[], edges=[])
