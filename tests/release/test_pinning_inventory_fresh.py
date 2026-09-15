"""Freshness and completeness gate for the pinning-rule inventory (FR-010, SC-009).

Mission ``sonar-per-pr-coverage-reuse-01M2FR32`` WP06/T028. Contract:
``kitty-specs/sonar-per-pr-coverage-reuse-01M2FR32/contracts/gate-disposition-contract.md``.

    A rule that goes **red** when the topology changes is found by CI.
    A rule that goes **greener by deletion** is found by nobody.

``scripts/ci/derive_pinning_inventory.py`` enumerates every automated rule
gripping the retired duplicate-measurement job and writes
``tests/release/pinning_rule_inventory.json``. Without this module that artefact
is a transcribed table wearing a derivation's clothes: **"derived" is proven by
re-running, never asserted in prose** (SC-009), so the first test below
re-derives and diffs.

The other four close the ways a disposition record can be true-looking and
worthless:

* an entry with no disposition, or with a disposition outside the contract's
  vocabulary, or with an empty reason -- the "silently deleted" failure C-005
  names;
* a ``retire-as-moot`` record whose rule is in fact still in the tree, i.e. a
  retirement that was recorded but never performed;
* a ``relocate``/``rewrite`` record naming a successor that does not exist, i.e.
  a property claimed to have moved somewhere it did not;
* a ``relocate`` whose successor is the rule itself, which would make the word
  mean nothing.

Together these make the ledger *checkable against the tree* rather than merely
readable, which is the difference between a record and a claim.
"""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = [pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "scripts" / "ci" / "derive_pinning_inventory.py"
_ARTEFACT = _REPO_ROOT / "tests" / "release" / "pinning_rule_inventory.json"

#: A reason short enough to be a label rather than a justification is not one.
#: The contract requires a *stated reason*, and "moot" is not a reason.
_MIN_REASON_CHARS = 60


def _load_deriver() -> ModuleType:
    """Import the derivation script by path (``scripts/`` is not a package)."""
    spec = importlib.util.spec_from_file_location("derive_pinning_inventory", _SCRIPT)
    assert spec is not None and spec.loader is not None, f"cannot load {_SCRIPT}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _artefact() -> dict[str, object]:
    assert _ARTEFACT.exists(), (
        f"the derived pinning inventory is missing: {_ARTEFACT.relative_to(_REPO_ROOT)} — regenerate it with `python3 {_SCRIPT.relative_to(_REPO_ROOT)}`"
    )
    loaded = json.loads(_ARTEFACT.read_text(encoding="utf-8"))
    assert isinstance(loaded, dict)
    return loaded


def _entries(key: str) -> list[dict[str, object]]:
    rows = _artefact()[key]
    assert isinstance(rows, list) and rows, f"inventory section {key!r} is empty"
    return [row for row in rows if isinstance(row, dict)]


def _rule_exists(rule_id: str) -> bool:
    """Whether *rule_id* (``<relpath>::<scope>``) is still DEFINED in the tree.

    Defined, not merely mentioned. A plain substring search reports every
    retired rule as still present, because executing a disposition *writes its
    name down*: the record comment left where the rule was, and this module's
    own assertions below, both quote it. So the scope must match a definition
    -- a ``def``/``class`` header, or an assignment/annotation target -- and a
    dict-key scope (``NAME['key']``) must match a real key, not the prose
    around one.
    """
    relpath, _, scope = rule_id.partition("::")
    path = _REPO_ROOT / relpath
    if not path.exists():
        return False
    if scope.startswith("<"):
        return True
    text = path.read_text(encoding="utf-8")
    name, bracket, remainder = scope.partition("[")
    if bracket:
        key = remainder.rstrip("]").strip("'\"")
        return bool(re.search(rf"""^\s*["']{re.escape(key)}["']\s*:""", text, re.MULTILINE))
    definition = rf"""^\s*(?:async\s+def\s+|def\s+|class\s+){re.escape(name)}\b|^\s*{re.escape(name)}\s*[:=]"""
    return bool(re.search(definition, text, re.MULTILINE))


def test_inventory_is_reproducible_by_rerunning_the_derivation() -> None:
    """SC-009: re-deriving must reproduce the committed artefact byte-for-byte.

    A hand-edited row, or a new pin added to the tree without regenerating,
    reds here. This is the assertion that makes "derived" mean something.
    """
    fresh = _load_deriver().serialize(_load_deriver().build_document())
    committed = _ARTEFACT.read_text(encoding="utf-8")
    assert fresh == committed, (
        f"{_ARTEFACT.relative_to(_REPO_ROOT)} is stale or hand-edited — re-run "
        f"`python3 {_SCRIPT.relative_to(_REPO_ROOT)}`. A rule added to the tree since the last "
        "derivation must be dispositioned, not regenerated away."
    )


def test_every_entry_carries_a_disposition_from_the_vocabulary_and_a_reason() -> None:
    """C-005/SC-009: no rule is left undispositioned or unexplained.

    ``disposition: null`` is what the derivation emits for a *newly discovered*
    dependency with no recorded decision, so this is the fail-closed edge: a
    pin cannot enter the tree without someone adjudicating it.
    """
    vocabulary = _load_deriver().DISPOSITIONS_VOCABULARY
    offenders: list[str] = []
    for row in _entries("derived") + _entries("executed"):
        rule = str(row.get("rule"))
        disposition = row.get("disposition")
        reason = str(row.get("reason") or "")
        if disposition not in vocabulary:
            offenders.append(f"{rule}: disposition {disposition!r} not in {sorted(vocabulary)}")
        elif len(reason.strip()) < _MIN_REASON_CHARS:
            offenders.append(f"{rule}: reason is missing or too short to be one ({len(reason.strip())} chars)")
    assert not offenders, "inventory rows without a usable disposition + reason:\n  " + "\n  ".join(offenders)


def test_retired_rules_are_really_gone_from_the_tree() -> None:
    """A ``retire-as-moot`` record that is not true of the tree is worse than none.

    It reads as due diligence while the rule it claims to have retired is still
    sitting there — possibly still asserting something false.
    """
    lingering = [str(row["rule"]) for row in _entries("executed") if row.get("disposition") == "retire-as-moot" and _rule_exists(str(row["rule"]))]
    assert not lingering, (
        f"recorded as `retire-as-moot` but still present in the tree: {lingering} — either the retirement was not performed, or the record is wrong"
    )


def test_relocated_and_rewritten_rules_name_a_successor_that_exists() -> None:
    """The property has to have gone *somewhere*.

    ``relocate`` and ``rewrite`` both assert the guarantee survives; a successor
    that does not resolve means it did not.
    """
    broken: list[str] = []
    for row in _entries("executed"):
        disposition = row.get("disposition")
        if disposition not in {"relocate", "rewrite"}:
            continue
        successor = row.get("successor")
        rule = str(row["rule"])
        if not successor:
            broken.append(f"{rule}: {disposition} with no successor recorded")
        elif not _rule_exists(str(successor)):
            broken.append(f"{rule}: successor {successor!r} does not resolve in the tree")
        elif str(successor) == rule:
            broken.append(f"{rule}: successor is the rule itself, so {disposition!r} claims nothing")
    assert not broken, "dispositions whose successor does not hold up:\n  " + "\n  ".join(broken)


def test_the_load_bearing_dispositions_are_present_and_of_the_right_kind() -> None:
    """The two the contract calls out by name, pinned so a later edit cannot
    quietly turn either into a deletion.

    * The **pull-request-only** assertion pinned an exact string that is
      unsatisfiable under the new trigger, so a verbatim port would pass over a
      job that never runs -- it must be a ``rewrite``, never a relocation.
    * The **cross-surface action-pin parity** guard resolves an operand from the
      retiring host and is the anti-drift guarantee -- it must be a
      ``relocate``, never a retirement.
    """
    by_rule = {str(row["rule"]): row for row in _entries("executed")}

    pr_only = "tests/release/test_sonar_workflow.py::test_ci_quality_sonarcloud_job_is_pull_request_only"
    assert pr_only in by_rule, f"the pull-request-only assertion is missing from the executed ledger: {pr_only}"
    assert by_rule[pr_only]["disposition"] == "rewrite", (
        "the pull-request-only assertion must be REWRITTEN in the new trigger's vocabulary "
        f"(got {by_rule[pr_only]['disposition']!r}): its literal is unsatisfiable under workflow_run, "
        "so a verbatim relocation would assert a condition that is never true"
    )

    parity = "tests/release/test_sonar_workflow.py::test_all_three_sonar_surfaces_pin_the_same_sonar_action_shas"
    assert parity in by_rule, f"the cross-surface pin-parity guard is missing from the executed ledger: {parity}"
    assert by_rule[parity]["disposition"] == "relocate", (
        "the cross-surface action-pin parity guard must be RELOCATED, never dropped "
        f"(got {by_rule[parity]['disposition']!r}) — it is the only thing preventing the Sonar "
        "surfaces' action pins from drifting apart"
    )
