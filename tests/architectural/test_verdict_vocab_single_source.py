"""FR-005 -- the vocabulary-bridge single-source architectural guard.

``status/verdict_vocab.py`` is the one canonical surface for the artifact
<-> event verdict equivalence (``rejected`` <-> ``changes_requested``,
D-PLAN-14's emission scope, the full four-value artifact domain). Before this
WP the equivalence was re-inlined independently in seven modules (paula
finding). This file is the check that keeps it that way:

- **Negative check** (:func:`test_no_module_other_than_bridge_spells_the_inline_equivalence`):
  no module other than the bridge itself spells the co-occurring
  ``"rejected"``/``"changes_requested"`` string-literal equivalence -- an
  AST-derived, module-level scan (:func:`_co_occurring_equivalence_modules`),
  not a same-line grep, so splitting the two literals across lines/functions
  cannot dodge it (squad #5's evasion concern).
- **Positive check** (:func:`test_swept_module_imports_and_calls_verdict_vocab`):
  each of the 5 WP04-owned sweep sites must genuinely route through the
  bridge somewhere in its own AST. This defeats the complementary evasion --
  a module that simply stops spelling the literals (e.g. by hardcoding an
  equivalent behaviour some other way) without ever routing through the
  canonical surface would pass the negative check alone but fails this one.

  Two import shapes count as "routing through the bridge", and
  ``verdict-seam-boundary-hardening-01KZG179`` (FR-002/FR-005) retired the
  first in favour of the second repo-wide:

  1. **Module-object shape** (pre-FR-005): ``from specify_cli.status import
     verdict_vocab`` + an attribute-call (``verdict_vocab.<fn>(...)``).
  2. **Façade-symbol shape** (post-FR-005, the ONLY shape live in the tree
     today): ``from specify_cli.status import <fn>`` (the bridge's public
     functions, promoted onto ``status.__all__``) + a bare-name call
     (``<fn>(...)``). ``test_status_module_boundary.py``'s
     ``test_ast_scan_catches_submodule_object_import`` now actively
     *forbids* shape 1 tree-wide, so shape 2 is the only one any real sweep
     site can legally use -- but both are accepted here since this file's
     concern is genuine routing through the bridge, not the import shape
     (that is ``test_status_module_boundary.py``'s job).

  Review cycle 1 (reviewer-renata) rejected an earlier version of this file
  that ALSO listed ``status/models.py`` and ``status/reducer.py`` here: at
  base, neither module co-occurs the equivalence pair in CODE (only in
  comments/a docstring), so they were never genuine sweep sites -- forcing
  them onto the positive-check list produced two dead public symbols
  (a decorative ``EVENT_VERDICTS`` re-export and an uncalled
  ``ReviewResultLookup.is_recognized_verdict`` property) whose only purpose
  was passing this check. The negative check already covers both modules for
  free (neither co-occurs the literal pair, so both trivially pass it); this
  file no longer lists them as positive-check sites. See
  ``reviewer-feedback-wp04-c1.md`` for the full finding.

A **named allowlist** (:data:`_UNSWEPT_ALLOWLIST`) originally exempted two
WP05-owned sites (``review/cycle.py:794``,
``post_merge/review_artifact_consistency.py``) from both checks -- WP04
shipped it GREEN with exactly those two entries (D-PLAN IC-02b:
guard-lands-last; WP04 does not touch either module). WP05
(verdict-seam-write-unification-01KZ9Q35, squad #15 BLOCKING acceptance
check) swept both sites onto the bridge and EMPTIED this allowlist --
:func:`test_allowlist_is_empty_after_wp05` asserts this programmatically.

This file ALSO carries the bridge's own unit tests (T016: totality over all
four inbound values + the render-only inverse) and the D-PLAN-14 negative
test (T019: an arbiter override must never synthesize an approved
``review_result`` event).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from specify_cli.status import verdict_vocab
from specify_cli.status.models import ReviewOverride, WPInnerStateDelta
from spec_kitty_events.diary import _apply_annotation_delta

# 2026-08-07 (landing fix, verdict-seam-write-unification #3245): this module
# shipped with no module-level pytestmark, making it invisible to every
# marker-based CI job (test_pytest_marker_convention.py) and to the
# arch-adversarial pole's `-m '<shard> and ... and architectural'` selection
# (test_ci_collection_completeness.py #2957) -- an architectural guard under
# tests/architectural/ carries the `architectural` marker, matching every
# sibling file in this directory.
pytestmark = [pytest.mark.architectural]

#: The bridge itself -- excluded from both the negative and positive scans
#: (it is the canonical surface, not a sweep site).
_BRIDGE_RELPATH = "src/specify_cli/status/verdict_vocab.py"

#: WP05 (verdict-seam-write-unification-01KZ9Q35, squad #15 BLOCKING
#: acceptance check) EMPTIED this allowlist: both former entries
#: (``review/cycle.py:794`` and ``review_artifact_consistency.py``) now
#: import and call ``status.verdict_vocab`` instead of re-inlining the
#: ``rejected``/``changes_requested`` equivalence. This is a named,
#: SHRUNK-TO-EMPTY allowlist (D-PLAN IC-02b: guard-lands-last) -- WP05's own
#: Definition of Done asserts this programmatically
#: (:func:`test_allowlist_is_empty_after_wp05`): a non-empty allowlist here
#: fails WP05; it is not advisory.
_UNSWEPT_ALLOWLIST: frozenset[str] = frozenset()

#: The exact literal pair whose CO-OCCURRENCE (not either alone) is the
#: forbidden inline equivalence (contract's "grep-guard on co-occurring
#: literals", upgraded here to an AST scan for non-line-adjacency).
_EQUIVALENCE_LITERALS: frozenset[str] = frozenset({"rejected", "changes_requested"})

#: The bridge's public, CALLABLE functions (excludes the ``EventVerdict`` /
#: ``ArtifactVerdict`` / ``EmissionArtifactVerdict`` type aliases and the
#: ``APPROVED`` / ``REJECTED`` / ``ARBITER_OVERRIDE`` /
#: ``APPROVED_AFTER_ORCHESTRATOR_FIX`` / ``CHANGES_REQUESTED`` string
#: constants, none of which are ever *called*). A module that imports one of
#: these directly from the ``specify_cli.status`` façade (FR-001/FR-006
#: promoted them onto ``status.__all__``) and invokes it by its bare name is
#: routing through the canonical bridge just as genuinely as the retired
#: ``verdict_vocab.<fn>(...)`` module-object shape -- see
#: :func:`_bound_facade_symbol_names`.
_VERDICT_VOCAB_CALLABLE_SYMBOLS: frozenset[str] = frozenset(
    {
        "artifact_verdicts",
        "event_verdicts",
        "emission_artifact_verdicts",
        "to_event_verdict",
        "to_artifact_verdict",
        "emission_event_verdict",
        "is_changes_requested",
        "is_approved",
    }
)


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "src" / "specify_cli").is_dir():
            return parent
    raise AssertionError("could not locate repo root from test file")


def _string_constants(tree: ast.AST) -> set[str]:
    """Every string constant literal anywhere in *tree* -- comments and
    f-string non-constant parts are never AST ``Constant`` string nodes, so
    this naturally ignores prose/comments and only sees genuine code-level
    literals."""
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


def _write_module(root: Path, relpath: str, source: str) -> Path:
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def _co_occurring_equivalence_modules(root: Path) -> dict[str, set[str]]:
    """AST-derived, MODULE-level (not same-line) scan: every ``*.py`` under
    ``src/specify_cli`` (excluding the bridge itself) whose string constants
    include BOTH ``"rejected"`` and ``"changes_requested"`` anywhere in the
    module. Module-level (rather than same-expression) scope is deliberate:
    it is immune to splitting the two literals across different lines,
    functions, or classes within the same file (squad #5's evasion)."""
    offenders: dict[str, set[str]] = {}
    scan_root = root / "src" / "specify_cli"
    if not scan_root.is_dir():
        return offenders
    for path in sorted(scan_root.rglob("*.py")):
        relpath = path.relative_to(root).as_posix()
        if relpath == _BRIDGE_RELPATH:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        present = _string_constants(tree) & _EQUIVALENCE_LITERALS
        if present == _EQUIVALENCE_LITERALS:
            offenders[relpath] = present
    return offenders


def _bound_verdict_vocab_names(tree: ast.Module) -> set[str]:
    """Local names this module's OWN import statements bind to the
    ``specify_cli.status.verdict_vocab`` module object (handles ``import ...
    as`` aliasing). This is the PRE-FR-005 shape: ``test_status_module_
    boundary.py``'s ``test_ast_scan_catches_submodule_object_import`` now
    forbids it tree-wide (verdict-seam-boundary-hardening-01KZG179), so no
    real sweep site uses it any more -- kept here so a module that DID still
    use it would be recognized as genuinely routing through the bridge
    rather than silently falling through to "no evidence found". Deliberately
    excludes ``from specify_cli.status.verdict_vocab import X`` -- that binds
    a FUNCTION/attribute, not the module object, so a later bare call to
    ``X(...)`` would not show up as a ``verdict_vocab.<attr>(...)``
    attribute-call shape."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "specify_cli.status":
            for alias in node.names:
                if alias.name == "verdict_vocab":
                    names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "specify_cli.status.verdict_vocab":
                    names.add((alias.asname or alias.name).split(".")[-1])
    return names


def _bound_facade_symbol_names(tree: ast.Module) -> set[str]:
    """Local names this module's OWN import statements bind to one of the
    bridge's public CALLABLE functions imported DIRECTLY from the
    ``specify_cli.status`` façade (handles ``as`` aliasing). This is the
    POST-FR-005 shape (verdict-seam-boundary-hardening-01KZG179,
    FR-001/FR-002/FR-006): every real sweep site imports ``<fn>`` rather
    than the ``verdict_vocab`` module object, because the module-object
    shape is the exact bypass ``test_status_module_boundary.py`` now
    forbids tree-wide."""
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "specify_cli.status":
            for alias in node.names:
                if alias.name in _VERDICT_VOCAB_CALLABLE_SYMBOLS:
                    names.add(alias.asname or alias.name)
    return names


def _imports_and_calls_verdict_vocab(path: Path) -> bool:
    """True iff *path* genuinely routes through the bridge somewhere in its
    own AST, via EITHER of the two import shapes below.

    This is the anti-evasion half of the guard: the negative check alone can
    be satisfied by a module that just stops spelling the two literals
    together (e.g. by re-deriving the same behaviour some other way without
    ever consulting the canonical bridge). Requiring an actual import + a
    CALL through a bound name means a module that maps verdicts must ROUTE
    through the canonical surface, not merely avoid a particular spelling.

    - **Module-object shape** (pre-FR-005): imports the ``verdict_vocab``
      module object and attribute-calls it (``verdict_vocab.<fn>(...)``).
    - **Façade-symbol shape** (post-FR-005, the live shape): imports one of
      the bridge's public functions directly from ``specify_cli.status`` and
      bare-name-calls it (``<fn>(...)``).
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    module_bound_names = _bound_verdict_vocab_names(tree)
    facade_bound_names = _bound_facade_symbol_names(tree)
    if not module_bound_names and not facade_bound_names:
        return False
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in module_bound_names
        ):
            return True
        if isinstance(node.func, ast.Name) and node.func.id in facade_bound_names:
            return True
    return False


# ---------------------------------------------------------------------------
# G2 -- negative check (no inline equivalence outside the bridge/allowlist)
# ---------------------------------------------------------------------------


def test_no_module_other_than_bridge_spells_the_inline_equivalence() -> None:
    """G2: outside the 2-entry WP05 allowlist, no module spells the
    co-occurring ``rejected``/``changes_requested`` equivalence inline."""
    root = _repo_root()
    offenders = _co_occurring_equivalence_modules(root)
    unexpected = set(offenders) - _UNSWEPT_ALLOWLIST
    assert not unexpected, (
        "inline rejected<->changes_requested equivalence found outside "
        f"status/verdict_vocab.py and the WP05 allowlist: {sorted(unexpected)}"
    )






def test_synthetic_module_splitting_the_literals_across_lines_still_reds(
    tmp_path: Path,
) -> None:
    """Anti-gaming (squad #5): splitting ``'rejected'`` and
    ``'changes_requested'`` across different lines/functions cannot dodge the
    negative check -- it is module-level AST constant presence, not
    same-line/same-expression adjacency."""
    relpath = "src/specify_cli/synthetic_split_equivalence.py"
    _write_module(
        tmp_path,
        relpath,
        "def a() -> str:\n"
        "    return 'rejected'\n"
        "\n\n"
        "def b() -> str:\n"
        "    return 'changes_requested'\n",
    )
    offenders = _co_occurring_equivalence_modules(tmp_path)
    assert relpath in offenders


def test_synthetic_module_with_only_one_literal_does_not_red(tmp_path: Path) -> None:
    """Single-value sites (only one of the two literals) are NOT a G2
    violation -- only the co-occurring PAIR is forbidden."""
    relpath = "src/specify_cli/synthetic_single_value.py"
    _write_module(
        tmp_path,
        relpath,
        "def only_checks_one() -> bool:\n"
        "    return 'changes_requested' == 'changes_requested'\n",
    )
    offenders = _co_occurring_equivalence_modules(tmp_path)
    assert relpath not in offenders


# ---------------------------------------------------------------------------
# T017 -- positive check (import + call), and its own anti-evasion proofs
# ---------------------------------------------------------------------------




def test_synthetic_module_with_fake_verdict_vocab_object_reds_positive_check(
    tmp_path: Path,
) -> None:
    """A module that calls something LOCALLY NAMED ``verdict_vocab`` without
    ever importing the real bridge does NOT satisfy the positive check --
    the bound-name resolution requires an actual import statement, so a
    module cannot fake compliance with a same-named local object."""
    relpath = "src/specify_cli/synthetic_fake_call.py"
    _write_module(
        tmp_path,
        relpath,
        "class _Fake:\n"
        "    def to_event_verdict(self, v: str) -> str:\n"
        "        return v\n\n\n"
        "verdict_vocab = _Fake()\n"
        "verdict_vocab.to_event_verdict('rejected')\n",
    )
    assert not _imports_and_calls_verdict_vocab(tmp_path / relpath)


def test_synthetic_module_importing_but_never_calling_reds_positive_check(
    tmp_path: Path,
) -> None:
    """A module that imports the bridge but never calls any of its
    functions (e.g. only mentions it in a docstring/comment) does not
    satisfy the positive check -- import alone is not adoption."""
    relpath = "src/specify_cli/synthetic_import_only.py"
    _write_module(
        tmp_path,
        relpath,
        "from specify_cli.status import verdict_vocab\n\n\n"
        "_NOTE = 'see verdict_vocab for details'\n",
    )
    assert not _imports_and_calls_verdict_vocab(tmp_path / relpath)


def test_synthetic_module_importing_and_calling_the_bridge_greens_positive_check(
    tmp_path: Path,
) -> None:
    """Sanity: the positive check DOES accept the module-object shape
    (import + a call through the bound name) -- proves the check is
    satisfiable via that shape, not just a permanent red. This shape is
    retired repo-wide (see ``test_status_module_boundary.py``'s
    ``test_ast_scan_catches_submodule_object_import``); it is exercised here
    only to prove this file's OWN detection logic still recognizes it."""
    relpath = "src/specify_cli/synthetic_real_sweep.py"
    _write_module(
        tmp_path,
        relpath,
        "from specify_cli.status import verdict_vocab\n\n\n"
        "def f(v: str) -> str:\n"
        "    return verdict_vocab.to_event_verdict(v)\n",
    )
    assert _imports_and_calls_verdict_vocab(tmp_path / relpath)


# ---------------------------------------------------------------------------
# T017b -- façade-symbol shape (post-FR-005, the shape every live sweep site
# actually uses) and its own anti-evasion proofs.
# ---------------------------------------------------------------------------


def test_synthetic_module_with_fake_facade_symbol_reds_positive_check(
    tmp_path: Path,
) -> None:
    """A module that defines and calls a LOCALLY-NAMED function that shares a
    name with one of the bridge's public functions, without ever importing
    it from ``specify_cli.status``, does NOT satisfy the positive check --
    the bound-name resolution requires an actual façade import, so a module
    cannot fake compliance with a same-named local callable."""
    relpath = "src/specify_cli/synthetic_fake_facade_call.py"
    _write_module(
        tmp_path,
        relpath,
        "def to_event_verdict(v: str) -> str:\n"
        "    return v\n\n\n"
        "to_event_verdict('rejected')\n",
    )
    assert not _imports_and_calls_verdict_vocab(tmp_path / relpath)


def test_synthetic_module_importing_facade_symbol_but_never_calling_reds_positive_check(
    tmp_path: Path,
) -> None:
    """A module that imports a bridge function from the façade but never
    calls it (e.g. only re-exports or mentions it in a docstring) does not
    satisfy the positive check -- import alone is not adoption, in the
    façade-symbol shape just as in the module-object shape."""
    relpath = "src/specify_cli/synthetic_facade_import_only.py"
    _write_module(
        tmp_path,
        relpath,
        "from specify_cli.status import to_event_verdict\n\n\n"
        "_NOTE = 'see to_event_verdict for details'\n",
    )
    assert not _imports_and_calls_verdict_vocab(tmp_path / relpath)


def test_synthetic_module_importing_and_calling_facade_symbol_greens_positive_check(
    tmp_path: Path,
) -> None:
    """Sanity: the positive check DOES accept the façade-symbol shape
    (direct import from ``specify_cli.status`` + a bare-name call) -- this is
    the shape all 5 real sweep sites use post-FR-005/FR-006, so this proves
    the check is satisfiable by the shape actually live in the tree, not
    only by the retired module-object shape."""
    relpath = "src/specify_cli/synthetic_facade_real_sweep.py"
    _write_module(
        tmp_path,
        relpath,
        "from specify_cli.status import to_event_verdict\n\n\n"
        "def f(v: str) -> str:\n"
        "    return to_event_verdict(v)\n",
    )
    assert _imports_and_calls_verdict_vocab(tmp_path / relpath)


# ---------------------------------------------------------------------------
# T016 -- the bridge's own unit tests (total mapping + render-only inverse)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("artifact_verdict", "expected_event_verdict"),
    [
        ("approved", "approved"),
        ("rejected", "changes_requested"),
        ("arbiter_override", "approved"),
        ("approved_after_orchestrator_fix", "approved"),
    ],
)
def test_to_event_verdict_is_total_over_all_four_inbound_values(
    artifact_verdict: str, expected_event_verdict: str
) -> None:
    """G1: the mapping is total over all four inbound artifact values."""
    assert verdict_vocab.to_event_verdict(artifact_verdict) == expected_event_verdict


def test_to_event_verdict_rejects_unknown_input() -> None:
    with pytest.raises(ValueError):
        verdict_vocab.to_event_verdict("damaged")


@pytest.mark.parametrize(
    ("event_verdict", "expected_artifact_verdict"),
    [
        ("approved", "approved"),
        ("changes_requested", "rejected"),
    ],
)
def test_to_artifact_verdict_inverse_for_prose_render(
    event_verdict: str, expected_artifact_verdict: str
) -> None:
    assert verdict_vocab.to_artifact_verdict(event_verdict) == expected_artifact_verdict


def test_to_artifact_verdict_rejects_unknown_input() -> None:
    with pytest.raises(ValueError):
        verdict_vocab.to_artifact_verdict("damaged")


def test_artifact_and_event_verdict_domains() -> None:
    assert verdict_vocab.artifact_verdicts() == {
        "approved",
        "rejected",
        "arbiter_override",
        "approved_after_orchestrator_fix",
    }
    assert verdict_vocab.event_verdicts() == {"approved", "changes_requested"}
    assert verdict_vocab.emission_artifact_verdicts() == {"approved", "rejected"}


def test_is_changes_requested_and_is_approved_predicates() -> None:
    assert verdict_vocab.is_changes_requested("changes_requested") is True
    assert verdict_vocab.is_changes_requested("approved") is False
    assert verdict_vocab.is_changes_requested(None) is False
    assert verdict_vocab.is_approved("approved") is True
    assert verdict_vocab.is_approved("changes_requested") is False


# ---------------------------------------------------------------------------
# D-PLAN-14 / T019 -- override never synthesizes a review_result verdict
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "override_verdict", ["arbiter_override", "approved_after_orchestrator_fix"]
)
def test_emission_event_verdict_refuses_override_values(override_verdict: str) -> None:
    """D-PLAN-14: an override/orchestrator-fix artifact verdict must NEVER be
    accepted by the emission-scoped helper -- it is not a valid input to an
    *emitted* ``review_result`` event. A caller attempting this gets a
    refusal, never a silently-synthesized ``"approved"``."""
    with pytest.raises(ValueError):
        verdict_vocab.emission_event_verdict(override_verdict)


@pytest.mark.parametrize(
    ("artifact_verdict", "expected_event_verdict"),
    [("approved", "approved"), ("rejected", "changes_requested")],
)
def test_emission_event_verdict_accepts_the_two_scoped_values(
    artifact_verdict: str, expected_event_verdict: str
) -> None:
    assert verdict_vocab.emission_event_verdict(artifact_verdict) == expected_event_verdict


def test_arbiter_override_does_not_synthesize_an_approved_review_result_event() -> None:
    """End-to-end negative test (T019): an arbiter override recorded via a
    :class:`ReviewOverride` annotation delta must never be reflected as a
    synthesized ``approved`` ``review_result`` event by the reducer --
    ``reducer.py``'s ``_apply_annotation_delta`` keeps the ``review``
    (override) slot and the ``review_result`` (reviewer verdict) slot
    strictly separate; only the former is written here, and the latter is
    never derived from it via this bridge or otherwise."""
    override = ReviewOverride(
        at="2026-01-01T00:00:00+00:00",
        actor="arbiter",
        wp_id="WP01",
        reason="stale rejection superseded",
    )
    state: dict[str, object] = {}
    delta = WPInnerStateDelta(review=override)

    _apply_annotation_delta(state, delta)

    assert state.get("review") == override.to_dict()
    assert "review_result" not in state, (
        "an arbiter override must be recorded via the 'review' slot only -- "
        "the reducer must never fabricate a 'review_result' verdict "
        "(approved or otherwise) from an override annotation"
    )
