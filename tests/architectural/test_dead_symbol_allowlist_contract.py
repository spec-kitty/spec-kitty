"""FR-009 ATDD contract pins for the dead-symbol ``(module, name)`` allowlist re-key (#5346).

These tests are the executable acceptance contract of
``kitty-specs/test-suite-remediation-01M3SSDW/contracts/dead-symbol-allowlist.md``
§3, rows **M1, M7, M8 and M11** (IC-09):

* **M1**: a body edit of an allowlisted, still-dead symbol costs 0 allowlist
  edits (FR-009 / NFR-003 / SC-003). It inverts ``bite_g``'s body-edit arm.
* **M7**: a rename is reported (stale GONE for the old name, offender for the new
  one), never silently passed (spec Edge Case 5).
* **M8**: a move is reported with a "probably moved to" hint, plus the offender
  at the new home. It supersedes ``bite_b`` and ``bite_j``'s relocation arm.
* **M11**: authority parse. The gate reads the allowlist file it is given, over
  the real session-cached corpus, not a cached copy.

The tests target the *contract surface* WP11/WP12 implemented, never today's
internals (no ``SymbolKey``, body hash or key tier appears here):
``_dead_symbol_allowlist.{load_allowlist, DeadSymbolKey, StaleVerdict,
ALLOWLIST_PATH}`` and ``test_no_dead_symbols.{_evaluate_allowlist,
_real_tree_inputs}``.
"""

from __future__ import annotations

import ast
import copy
from pathlib import Path
from typing import Any

import pytest
import yaml

from tests.architectural import _dead_symbol_allowlist as allowlist_mod
from tests.architectural import test_no_dead_symbols as gate
from tests.architectural._symbol_key import CorpusModule

pytestmark = [pytest.mark.architectural]

_FIXTURE_CATEGORY = "category_contract_test"
_FIXTURE_RATIONALE = "ATDD contract fixture"
_FIXTURE_ISSUE = "#5346"
_BOGUS_NAME = "DefinitelyNotARealSymbol5346"


def _write_allowlist(tmp_path: Path, entries: list[tuple[str, str]], filename: str = "allowlist.yaml") -> Path:
    """Write a minimal schema-v1 allowlist (data-model §1) with one fixture category."""
    document = {
        "schema_version": 1,
        "categories": {_FIXTURE_CATEGORY: {"rationale": _FIXTURE_RATIONALE, "requires_issue": False}},
        "entries": [{"module": module, "name": name, "category": _FIXTURE_CATEGORY} for module, name in entries],
        "widened_grandfathered_470": {"rationale": _FIXTURE_RATIONALE, "issue": _FIXTURE_ISSUE, "entries": []},
    }
    path = tmp_path / filename
    path.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
    return path


def _static_all(tree: ast.Module) -> frozenset[str]:
    """The literal ``__all__ = [...]`` of a synthetic module (empty if absent)."""
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
            return frozenset(ast.literal_eval(node.value))
    return frozenset()


def _synthetic_corpus(modules: dict[str, str]) -> tuple[dict[str, frozenset[str]], dict[str, CorpusModule]]:
    """Build ``(all_literal_decls, corpus)`` from ``{dotted_module: source}``.

    The synthetic modules are plain (non-package) modules, so the containing
    package is the dotted parent (``pkg.m`` -> ``pkg``).
    """
    all_literal_decls: dict[str, frozenset[str]] = {}
    corpus: dict[str, CorpusModule] = {}
    for dotted, source in modules.items():
        tree = ast.parse(source)
        corpus[dotted] = CorpusModule(tree=tree, source=source, containing_pkg=dotted.rpartition(".")[0])
        declared = _static_all(tree)
        if declared:
            all_literal_decls[dotted] = declared
    return all_literal_decls, corpus


def _findings_for(result: Any, key: Any) -> list[Any]:
    """The stale findings of an ``AllowlistEvaluation`` for one ``DeadSymbolKey``."""
    return [finding for finding in result.stale if finding.key == key]


def test_m1_body_edit_of_allowlisted_dead_symbol_stays_green(tmp_path: Path) -> None:
    """M1 (FR-009 / NFR-003 / SC-003): a body edit of an allowlisted dead symbol costs 0 edits.

    Every body below is a code-token edit of the same dead ``pkg.m::Baz`` (a
    constant change and a structural ``def`` change), each of which changes the
    runtime content hash. The ``(module, name)`` entry must exempt all of them.
    The positive control on the same fixture proves the probe sees the dead
    symbol when it is not exempted, so an evaluator that ignored the corpus or
    the allowlist could not pass this test.
    """
    allowlist = allowlist_mod.load_allowlist(_write_allowlist(tmp_path, [("pkg.m", "Baz")]))
    control = allowlist_mod.load_allowlist(_write_allowlist(tmp_path, [("pkg.m", "Other")], filename="control.yaml"))

    bodies = (
        "Baz = 1\n",
        "Baz = 2\n",
        "def Baz(x: int) -> int:\n    return x + 1\n",
        "def Baz(x: int) -> int:\n    return x + 2\n",
    )
    for body in bodies:
        decls, corpus = _synthetic_corpus({"pkg.m": '__all__ = ["Baz"]\n' + body})

        result = gate._evaluate_allowlist(decls, {}, set(), corpus, allowlist)
        assert result.offenders == [], f"body {body!r}: an allowlisted dead symbol became an offender"
        assert result.stale == [], f"body {body!r}: the (module, name) entry went stale on a body edit"

        unexempted = gate._evaluate_allowlist(decls, {}, set(), corpus, control)
        assert unexempted.offenders == ["pkg.m::Baz"], f"body {body!r}: positive control -- the probe did not see the unexempted dead symbol"


def test_m7_rename_reports_gone_and_new_offender(tmp_path: Path) -> None:
    """M7 (spec Edge Case 5): a rename ``Old`` -> ``New`` is reported, never silently passed."""
    allowlist = allowlist_mod.load_allowlist(_write_allowlist(tmp_path, [("pkg.m", "Old")]))
    decls, corpus = _synthetic_corpus({"pkg.m": '__all__ = ["New"]\nNew = 1\n'})

    result = gate._evaluate_allowlist(decls, {}, set(), corpus, allowlist)

    assert result.offenders == ["pkg.m::New"]
    assert len(result.stale) == 1, [finding.render() for finding in result.stale]
    (finding,) = result.stale
    assert finding.key == allowlist_mod.DeadSymbolKey("pkg.m", "Old")
    assert finding.verdict == allowlist_mod.StaleVerdict.GONE
    assert "probably moved" not in finding.hint, "no offender named `Old` exists, so no move hint may be given"


def test_m8_move_reports_gone_with_moved_hint_and_new_offender(tmp_path: Path) -> None:
    """M8 (spec Edge Case 5): a move ``pkg.a::N`` -> ``pkg.b::N`` is reported with a hint.

    ``pkg.a::Other`` is allowlisted too, so the offender list stays focused on
    the moved symbol. Supersedes ``bite_b`` and ``bite_j``'s relocation arm.
    """
    allowlist = allowlist_mod.load_allowlist(_write_allowlist(tmp_path, [("pkg.a", "N"), ("pkg.a", "Other")]))
    decls, corpus = _synthetic_corpus(
        {
            "pkg.a": '__all__ = ["Other"]\nOther = 1\n',
            "pkg.b": '__all__ = ["N"]\nN = 1\n',
        }
    )

    result = gate._evaluate_allowlist(decls, {}, set(), corpus, allowlist)

    assert result.offenders == ["pkg.b::N"]
    assert len(result.stale) == 1, [finding.render() for finding in result.stale]
    (finding,) = result.stale
    assert finding.key == allowlist_mod.DeadSymbolKey("pkg.a", "N")
    assert finding.verdict == allowlist_mod.StaleVerdict.GONE
    assert "probably moved to `pkg.b`" in finding.hint
    rendered = finding.render()
    assert rendered.startswith("pkg.a::N [GONE] "), rendered
    assert "probably moved to `pkg.b`" in rendered


def _removable_entry(raw: dict[str, Any]) -> dict[str, Any]:
    """The first entry, by ``(module, name)``, whose category has >= 2 entries.

    Removing it can never leave a tombstone category (loader rule L9).
    """
    per_category: dict[str, int] = {}
    for entry in raw["entries"]:
        per_category[entry["category"]] = per_category.get(entry["category"], 0) + 1
    candidates = [entry for entry in raw["entries"] if per_category[entry["category"]] >= 2]
    assert candidates, "no category of the real allowlist has >= 2 entries -- M11(a) cannot pick an entry"
    return min(candidates, key=lambda entry: (entry["module"], entry["name"]))


def _bogus_entry(raw: dict[str, Any]) -> dict[str, Any]:
    """A schema-valid entry naming a symbol that exists nowhere, in an existing category."""
    category_id, category = sorted(raw["categories"].items())[0]
    entry: dict[str, Any] = {"module": "specify_cli", "name": _BOGUS_NAME, "category": category_id}
    if category.get("requires_issue") is True:
        entry["issue"] = _FIXTURE_ISSUE
    return entry


def test_m11_gate_reads_the_allowlist_file_it_is_given(tmp_path: Path) -> None:
    """M11 (authority parse): the gate reads the allowlist file it is given, over the real corpus.

    (a) A scratch copy with one live entry removed makes that symbol an
    offender. (b) A scratch copy with one bogus entry added reports that entry
    stale GONE. The control (the real file, unmodified) is clean, so (a) and
    (b) are caused by the edits alone.

    Cost: the real inputs come from the session-cached
    ``_real_tree_inputs()`` walk. Sharing a process with the gate adds no
    second walk, but under CI's ``-n auto --dist loadfile`` this file runs on
    its own xdist worker and pays one full walk there (about the gate's own
    walk cost). Kept in one test function so the walk happens once even if the
    lru cache is disturbed.
    """
    inputs = gate._real_tree_inputs()
    raw = yaml.safe_load(allowlist_mod.ALLOWLIST_PATH.read_text(encoding="utf-8"))

    def evaluate(allowlist: Any) -> Any:
        return gate._evaluate_allowlist(
            inputs.all_literal_decls,
            inputs.per_symbol,
            inputs.star_targets,
            inputs.corpus,
            allowlist,
            inputs.collision_index,
        )

    control = evaluate(allowlist_mod.load_allowlist())
    assert control.offenders == [], control.offenders
    assert control.stale == [], [finding.render() for finding in control.stale]

    # (a) Removed entry -> that symbol is an offender again.
    removed = _removable_entry(raw)
    without_entry = copy.deepcopy(raw)
    without_entry["entries"] = [e for e in without_entry["entries"] if (e["module"], e["name"]) != (removed["module"], removed["name"])]
    removed_path = tmp_path / "removed.yaml"
    removed_path.write_text(yaml.safe_dump(without_entry, sort_keys=False), encoding="utf-8")
    result_a = evaluate(allowlist_mod.load_allowlist(removed_path))
    assert f"{removed['module']}::{removed['name']}" in result_a.offenders

    # (b) Bogus entry -> stale GONE naming it.
    with_bogus = copy.deepcopy(raw)
    with_bogus["entries"].append(_bogus_entry(raw))
    bogus_path = tmp_path / "bogus.yaml"
    bogus_path.write_text(yaml.safe_dump(with_bogus, sort_keys=False), encoding="utf-8")
    result_b = evaluate(allowlist_mod.load_allowlist(bogus_path))
    bogus_findings = _findings_for(result_b, allowlist_mod.DeadSymbolKey("specify_cli", _BOGUS_NAME))
    assert [finding.verdict for finding in bogus_findings] == [allowlist_mod.StaleVerdict.GONE]
