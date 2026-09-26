"""FR-005 boundary-contract ratchet — no write-side re-derivation (WP08 / T037).

The Mission A boundary contract (IC-01), ENFORCED here: after the write-side
adoption (WP02–WP06), **no** write surface in the adopted scope re-derives
``mission_id`` / ``mid8`` / ``primary_root`` independently. Identity/root/target
flow from the factory-projected fragments via the existing public resolvers
(``resolve_canonical_root`` / ``resolve_status_surface`` /
``resolve_placement_only`` / ``resolve_lanes_dir``), not hand-rolled walks.

This is the one allowed form-coupled test (NFR-003): a guard that FLAGS write-side
re-derivation in the adopted modules. It must:

* be **line-scoped**, not file-scoped — a file-level allow-list is a blanket
  escape and is rejected (paula SF-2). The allow-list is seeded with ONLY
  genuinely-deferred lines (the former S2 #1716 ladder line was drained by
  WP04/T017 of coord-write-placement-closure-01KYCF83 and removed).
* **bite** — a companion self-test plants a re-derivation in a fixture string and
  asserts the detector FLAGS it, proving the guard is not inert.
* **pass on the post-adoption tree** — a flag on an adopted module would mean that
  module still re-derives (a real FR-005 finding).

Detection is **token-based** (``tokenize``): only real code tokens are scanned, so
docstrings and comments that merely *describe* the prior walk (e.g. the
``_resolve_write_target`` docstring quoting the old selector) are NOT flagged. A
naive line/regex scan would false-flag those narrative lines.

coord-primary-partition-lock WP07 (T033 / FR-011) extends this ratchet with a
SECOND, AST-based grammar (below the original three token grammars): it flags
``CommitTarget(...)`` / ``safe_commit(...)`` calls whose ``ref`` /
``destination_ref`` argument is constructed from a current-checkout expression
rather than a ``placement_seam(...).write_target(kind)`` call (contracts/
ratchet-contract.md). This is genuinely AST-based (not token-based): the
forbidden pattern is a *call construction*, so parsing the tree means a
docstring merely quoting ``CommitTarget(ref=coordination_branch)`` never
becomes a ``Call`` node and is never flagged, without needing tokenize's
comment/string-skipping machinery.

coord-write-placement-closure-01KYCF83 WP06 (T025-T030 / FR-001, NFR-001)
RETIRES the 17-module ``_CHECKOUT_GRAMMAR_MODULES`` allowlist the second
grammar used and replaces it with a **whole-tree ``src/`` scan** (shared
walker: ``tests.architectural._placement_whole_tree_scan``): every module is
in scope unless it is an individually-justified sanctioned primitive
(``BOUNDARY_SANCTIONED_MODULES``) or falls under the RETAINED
``BOUNDARY_SANCTIONED_PREFIXES``. A module allowlist is exactly the blanket
escape a new, un-routed write surface could hide behind; the whole-tree scan
closes that gap. See ``test_adopted_and_residual_modules_have_no_checkout_derived_commit_target``.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.architectural._placement_whole_tree_scan import (
    BOUNDARY_SANCTIONED_MODULES,
    BOUNDARY_SANCTIONED_PREFIXES,
)
from tests.architectural._placement_whole_tree_scan import rel_path as _placement_rel_path
from tests.architectural._placement_whole_tree_scan import scan_scope as _whole_tree_scan_scope
from tests.architectural._ratchet_keys import (
    CompositeKey,
    ContentDescriptor,
    code_tokens_by_line,
    composite_key,
    descriptor_still_live,
    resolve_descriptor,
)

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src" / "specify_cli"

#: The write-side modules the adoption touched (US-1..US-4, FR-001/FR-002/
#: FR-003/FR-004/FR-008). These are the surfaces the boundary contract binds.
#:
#: coord-primary-partition-lock WP07 (T034, FR-011): expanded with the five
#: mission-artifact-placement write surfaces WP02-WP05 routed through
#: ``placement_seam(...).write_target(kind)`` -- each module is added to this
#: set in the SAME WP that routes it (contract sequencing rule), and by the
#: time WP07 lands all five are already routed.
_ADOPTED_MODULES: tuple[Path, ...] = (
    _SRC / "status" / "emit.py",
    _SRC / "status" / "work_package_lifecycle.py",
    _SRC / "status" / "lifecycle_events.py",
    _SRC / "status" / "store.py",
    _SRC / "coordination" / "status_transition.py",
    _SRC / "core" / "worktree.py",
    _SRC / "core" / "mission_creation.py",
    _SRC / "cli" / "commands" / "implement.py",
    _SRC / "cli" / "commands" / "agent" / "workflow.py",
    # coord-authority-trio-degod (#2464/#2465/#2508): workflow.py's god-function
    # write-side logic was split out into these two modules (workflow.py keeps
    # bare re-export shims for the moved names) -- the boundary contract must
    # keep following the CODE, not the original filename, so both successor
    # modules join the adopted scope alongside the still-real-content workflow.py.
    _SRC / "cli" / "commands" / "agent" / "workflow_cores.py",
    _SRC / "cli" / "commands" / "agent" / "workflow_executor.py",
    # coord-authority-trio-degod (#2464/#2465/#2508): implement.py's WP03
    # decomposition split pure helpers into implement_cores.py; same
    # code-follows-the-move rationale as workflow_cores.py/workflow_executor.py
    # above.
    _SRC / "cli" / "commands" / "implement_cores.py",
    _SRC / "cli" / "commands" / "agent" / "tasks_move_task.py",
    _SRC / "cli" / "commands" / "agent" / "mission_record_analysis.py",
)


@dataclass(frozen=True)
class _Finding:
    """A flagged write-side re-derivation: (path, line, kind, code, source)."""

    path: Path
    lineno: int
    kind: str
    code: str
    source: str

    def as_allow_key(self) -> CompositeKey:
        """The drift-proof ``(rel_path, qualname, token_line)`` composite allow-list key.

        Content-addressed (path + enclosing function + tokenized code line),
        matching the WP02 resolver's :class:`CompositeKey` shape (IC-DESCRIPTOR),
        not line-number addressed, so a benign blank/comment-line insertion above
        the guarded site leaves the key unchanged (FR-008 / WP06 / #2469 WP02).
        """
        qualname, token_line = composite_key(self.source, self.lineno)
        rel_path = self.path.relative_to(_REPO_ROOT).as_posix()
        return (rel_path, qualname, token_line)


#: Content-descriptor allow-list (IC-DESCRIPTOR, #2469 WP02/WP03): each entry
#: pins a deferred finding by ``(rel_path, qualname, token_substring)`` — the
#: WP02 shared resolver (:func:`resolve_descriptor`) resolves it LIVE to the
#: **exactly one** matching finding's ``(rel_path, qualname, token_line)``
#: composite key. Unlike a line-number seed, this survives ANY line drift
#: (blank/comment insertion, unrelated edits above the site, cross-lane
#: rebases) as long as the finding's enclosing function and tokenized code
#: line are unchanged — no re-anchoring "343 -> 347 -> ..." bookkeeping is
#: needed (#2072).
#:
#: WS#1 — RETIRED (coord-write-placement-closure-01KYCF83 / WP04 / T017 /
#: FR-003): the ``coordination/status_transition.py`` / ``_resolve_write_target``
#: FALLBACK arm ``return coord_branch or _current_branch(repo_root)`` this entry
#: deferred (#1716) has been DRAINED — the arm no longer reads the ambient
#: checkout HEAD (see ``test_wp05_write_target_drain.py``'s updated DRAINED
#: verdict). Shrink-only: the entry is deleted rather than left vacuous, per
#: this file's own ``test_checkout_head_selector_entry_is_still_a_live_finding``
#: convention for a routed/removed site.
#:
#: WS#2 — ``cli/commands/agent/workflow.py`` / ``_review_feedback_root``: the
#: sole, deduplicated ``feature_dir.parent.parent`` READ-side
#: review-feedback-root navigation (coord-primary-partition-lock WP07 /
#: T034) — categorically distinct from the WS#1 write-target selector (it
#: never touches ``mission_id``/``mid8``/``primary_root`` or a write
#: ``CommitTarget``).
#:
#: WS#3 — ``cli/commands/implement.py`` / ``_status_commit_destination_branch``:
#: tracked #2453 — the ``get_current_branch(repo_root) or fallback_branch``
#: git-HEAD selector. It ONLY predicts the pre-lane status-commit branch for
#: the protected-branch guard (``_protected_branch_status_commit_error``) —
#: it never feeds a write ``CommitTarget``/``destination_ref``. Routing the
#: prediction through the placement seam would change which branch the guard
#: evaluates (a behavior change), so it is deferred to the #2453 read-site
#: sweep bucket (D-1/C-003) rather than routed here.
#:
#: Adding a NEW entry here is a deliberate scope decision, not a routine
#: escape: it must point at a specific deferred-by-spec finding, with a
#: one-line rationale (per-descriptor, in ``rationale``).
_ALLOW_LIST_SEED: tuple[ContentDescriptor, ...] = (
    ContentDescriptor(
        rel_path="src/specify_cli/cli/commands/agent/workflow_cores.py",
        qualname="review_feedback_root",
        token_substring="return feature_dir . parent . parent",
        occurrence=None,
        rationale=(
            "coord-primary-partition-lock WP07 (T034): the sole, deduplicated "
            "feature_dir.parent.parent READ-side review-feedback-root "
            "navigation -- categorically distinct from the WS#1 write-target "
            "selector (never touches mission_id/mid8/primary_root or a write "
            "CommitTarget). coord-authority-trio-degod (#2464/#2465/#2508): the "
            "function moved from workflow.py to workflow_cores.py (bare "
            "re-export shim left behind in workflow.py as "
            "`review_feedback_root as _review_feedback_root`); descriptor "
            "re-pointed to the new location, same underlying code."
        ),
    ),
    ContentDescriptor(
        rel_path="src/specify_cli/cli/commands/implement.py",
        qualname="_status_commit_destination_branch",
        token_substring="get_current_branch ( repo_root ) or fallback_branch",
        occurrence=None,
        rationale=(
            "tracked: #2453 - predicts the pre-lane status-commit branch for "
            "the protected-branch guard only; never feeds a write "
            "CommitTarget/destination_ref. Deferred to the #2453 read-site "
            "sweep bucket (D-1/C-003)."
        ),
    ),
)

#: Composite key resolved LIVE for each ``_ALLOW_LIST_SEED`` entry (parallel,
#: order-preserving with the seed tuple — the staleness twin-guards below index
#: into both by descriptor identity, never a bare position).
_ALLOW_LIST_KEYS: tuple[CompositeKey, ...] = tuple(
    resolve_descriptor((_REPO_ROOT / descriptor.rel_path).read_text(encoding="utf-8"), descriptor)
    for descriptor in _ALLOW_LIST_SEED
)

#: Composite-keyed allow-list: ``frozenset[(rel_path, qualname, token_line)]``.
_ALLOW_LIST: frozenset[CompositeKey] = frozenset(_ALLOW_LIST_KEYS)


def _seed_and_key_for(rel_path: str) -> tuple[ContentDescriptor, CompositeKey]:
    """The ``(descriptor, seeded_key)`` pair whose descriptor targets ``rel_path``.

    Looks the entry up by its own ``rel_path`` rather than a positional index,
    so the twin-guards below stay correct if ``_ALLOW_LIST_SEED``'s entry order
    ever changes.
    """
    for descriptor, seeded_key in zip(_ALLOW_LIST_SEED, _ALLOW_LIST_KEYS, strict=True):
        if descriptor.rel_path == rel_path:
            return descriptor, seeded_key
    raise AssertionError(f"no _ALLOW_LIST_SEED entry targets {rel_path!r}")


def _scan_source(source: str, path: Path) -> list[_Finding]:
    """Flag write-side re-derivation in CODE lines of ``source``.

    Four re-derivation grammars (randy's write-path census / FR-005):

    * ``feature_dir.parent.parent`` (and deeper) root walks — tokenizes to
      ``. parent . parent`` / ``parent . parent``.
    * inline ``mission_id[:8]`` / ``mid8`` recompute — tokenizes to
      ``mission_id [ : 8 ]``.
    * ``coord_branch or _current_branch`` / ``coord_branch or current_branch``
      git-HEAD write-target selectors.
    * ``get_current_branch(...) or <fallback>`` git-HEAD branch selectors — the
      generic checkout-derived ``current-branch-or-fallback`` shape (e.g.
      ``implement.py``'s ``_status_commit_destination_branch``, which predicts
      the pre-lane status-commit branch for the protected-branch guard). Making
      this shape a first-class finding pulls the last checkout-derived selector
      an adopted module carries into the ratchet's field of view so it cannot
      silently drift; the one live site is tracked-VISIBLE in ``_ALLOW_LIST_SEED``
      (tracked: #2453 deferred read-site sweep, D-1/C-003).
    """
    findings: list[_Finding] = []
    for lineno, code in code_tokens_by_line(source).items():
        if "parent . parent" in code:
            findings.append(_Finding(path, lineno, "root_walk", code, source))
        if "mission_id [ : 8 ]" in code:
            findings.append(_Finding(path, lineno, "mid8_recompute", code, source))
        if "coord_branch or _current_branch" in code or "coord_branch or current_branch" in code:
            findings.append(_Finding(path, lineno, "write_target_head_selector", code, source))
        if "get_current_branch (" in code and ") or" in code:
            findings.append(_Finding(path, lineno, "checkout_head_selector", code, source))
    return findings


def _scan_module(path: Path) -> list[_Finding]:
    return _scan_source(path.read_text(encoding="utf-8"), path)


# ---------------------------------------------------------------------------
# The ratchet: adopted modules carry no un-allow-listed re-derivation.
# ---------------------------------------------------------------------------


def test_adopted_modules_have_no_write_side_rederivation() -> None:
    """FR-005 / C-BOUNDARY: every adopted module is free of re-derivation.

    A flag on an adopted module that is NOT on the line-scoped allow-list means
    that module still re-derives identity/root/target by hand — a real boundary
    violation. The permitted residuals are the WS#2/WS#3 entries seeded below
    (the deferred #1716 S2 line, WS#1, was drained by WP04/T017 and removed).
    """
    offenders: list[str] = []
    for module in _ADOPTED_MODULES:
        assert module.exists(), f"adopted module missing: {module}"
        for finding in _scan_module(module):
            if finding.as_allow_key() in _ALLOW_LIST:
                continue
            offenders.append(
                f"{finding.path.relative_to(_REPO_ROOT)}:{finding.lineno} "
                f"[{finding.kind}] {finding.code}"
            )

    assert not offenders, (
        "Write-side re-derivation found in adopted modules (FR-005 / C-BOUNDARY). "
        "Route each offender through a public resolver -- resolve_canonical_root / "
        "resolve_status_surface / resolve_placement_only / resolve_lanes_dir -- "
        "instead of a hand-rolled walk; if the finding is a genuinely deferred "
        "residual, add a rationale-carrying entry to _ALLOW_LIST_SEED keyed on its "
        "(rel_path, qualname, token_substring) instead of leaving it bare. "
        "Offenders:\n" + "\n".join(offenders)
    )


# ---------------------------------------------------------------------------
# "Ratchet bites" — the guard is not inert.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("planted", "expected_kind"),
    [
        ("    root = feature_dir.parent.parent\n", "root_walk"),
        ("    mid8 = mission_id[:8]\n", "mid8_recompute"),
        ("    ref = coord_branch or _current_branch(repo_root)\n", "write_target_head_selector"),
        ("    branch = get_current_branch(repo_root) or fallback_branch\n", "checkout_head_selector"),
    ],
)
def test_ratchet_bites_on_planted_rederivation(planted: str, expected_kind: str) -> None:
    """The detector FLAGS a planted re-derivation — proving the guard bites.

    Without this, a vacuous detector (one that never matches) would pass the
    ratchet above regardless. We feed the detector a fixture source string
    carrying each forbidden grammar and assert it is flagged with the right kind.
    """
    fixture_source = (
        "def _adopted_write_site(feature_dir, mission_id, coord_branch, repo_root):\n"
        '    """A docstring that merely mentions feature_dir.parent.parent must NOT flag."""\n'
        "    # a comment quoting coord_branch or _current_branch must NOT flag\n"
        f"{planted}"
        "    return root\n"
    )
    findings = _scan_source(fixture_source, _SRC / "coordination" / "status_transition.py")
    kinds = {f.kind for f in findings}
    assert expected_kind in kinds, (
        f"ratchet failed to flag planted {expected_kind!r}; got {kinds}"
    )


def test_ratchet_ignores_prose_quoting_a_prior_walk() -> None:
    """Docstrings/comments that DESCRIBE the prior walk are NOT flagged.

    The adopted ``_resolve_write_target`` docstring quotes the old
    ``coord_branch or _current_branch`` selector to document the fix; a
    line/regex scan would false-flag it. The token-based detector must see only
    code — this pins that the prose-only source yields ZERO findings.
    """
    prose_only = (
        "def _adopted_resolver(repo_root, mission_slug, coord_branch):\n"
        '    """The prior inline selector was coord_branch or _current_branch(repo_root).\n'
        "\n"
        "    It walked feature_dir.parent.parent and sliced mission_id[:8] by hand.\n"
        '    """\n'
        "    # historical: coord_branch or _current_branch(repo_root) and mission_id[:8]\n"
        "    return resolve_placement_only(repo_root, mission_slug).ref\n"
    )
    assert _scan_source(prose_only, _SRC / "coordination" / "status_transition.py") == []


def test_allow_list_is_line_scoped_not_a_blanket_file_escape() -> None:
    """The allow-list keys are ``(rel_path, qualname, token_line)`` composites — never bare paths.

    A file-scoped allow-list would silently excuse any future re-derivation added
    anywhere in that file (a blanket escape, rejected by paula SF-2). The
    content-descriptor re-key (FR-008 / WP06, #2469 WP02/WP03) keeps the entry
    line-SCOPED — it pins a specific path, a specific enclosing function, AND a
    specific tokenized code line, NOT a whole file. This re-expresses the
    original anti-blanket-escape intent for the descriptor key shape: each entry
    must be a 3-tuple of non-empty ``str``s whose third component (the
    token_line) is a real code line, never a whole-file wildcard.
    """
    assert _ALLOW_LIST, "the allow-list must seed the remaining tracked deferred lines (WS#2/WS#3)"
    for entry in _ALLOW_LIST:
        assert isinstance(entry, tuple) and len(entry) == 3, (
            f"allow-list entry must be a (rel_path, qualname, token_line) "
            f"composite, got {entry!r}"
        )
        rel_path, qualname, token_line = entry
        assert isinstance(rel_path, str) and rel_path, (
            f"rel_path component must be a non-empty str, got {rel_path!r}"
        )
        assert isinstance(qualname, str) and qualname, (
            f"qualname component must be a non-empty str, got {qualname!r}"
        )
        assert isinstance(token_line, str) and token_line, (
            "token_line component must be a non-empty code line (a real line, "
            f"not a whole-file wildcard), got {token_line!r}"
        )


def test_ws1_descriptor_no_longer_seeded_after_the_1716_drain() -> None:
    """WS#1 was DELETED (shrink-only) once #1716 was closed (WP04/T017).

    The ``coord_branch or _current_branch`` selector no longer exists in
    ``status_transition.py`` (see ``test_wp05_write_target_drain.py``'s
    DRAINED verdict), so there is nothing left for a WS#1 allow-list entry to
    pin. This asserts the entry stays gone -- a re-added WS#1 seed pointing at
    ``status_transition.py`` would mean either the drain regressed (the
    selector came back) or a NEW re-derivation was allow-listed instead of
    fixed; either way this test should be revisited deliberately, not
    silently.
    """
    assert all(
        descriptor.rel_path != "src/specify_cli/coordination/status_transition.py"
        for descriptor in _ALLOW_LIST_SEED
    ), (
        "a status_transition.py entry re-appeared in _ALLOW_LIST_SEED after the "
        "#1716 drain (WP04/T017) removed WS#1 -- confirm this is a genuinely "
        "NEW deferred finding, not the retired coord_branch-or-_current_branch "
        "selector coming back."
    )
    # Token-based (not raw-text) re-check: the updated docstring legitimately
    # QUOTES the retired selector as history (mirrors
    # test_ratchet_ignores_prose_quoting_a_prior_walk below), so only a real
    # CODE-token finding of kind write_target_head_selector would mean the
    # drain regressed.
    status_transition_path = _SRC / "coordination" / "status_transition.py"
    findings = [
        finding
        for finding in _scan_module(status_transition_path)
        if finding.kind == "write_target_head_selector"
    ]
    assert not findings, (
        "the retired #1716 selector reappeared as CODE in status_transition.py; "
        f"the WS#1 allow-list entry was deleted on the assumption it is gone for good: {findings!r}"
    )


def test_checkout_head_selector_entry_is_still_a_live_finding() -> None:
    """Staleness twin-guard for the tracked #2453 checkout-HEAD selector descriptor.

    The ``implement.py`` descriptor pins ``_status_commit_destination_branch``'s
    ``get_current_branch(repo_root) or fallback_branch`` prediction selector. If
    that site is finally routed through the placement seam (or removed),
    :func:`descriptor_still_live` returns ``False`` (0 matches, or a
    key-inequality) and this test fails loudly — the fix is to DELETE the
    now-stale allow-list entry (shrink-only), never to leave a vacuous
    allow-list rule masking nothing.
    """
    descriptor, seeded_key = _seed_and_key_for(
        "src/specify_cli/cli/commands/implement.py"
    )
    source = (_REPO_ROOT / descriptor.rel_path).read_text(encoding="utf-8")
    assert descriptor_still_live(source, descriptor, seeded_key), (
        f"{descriptor.rel_path} ({descriptor.qualname}) checkout_head_selector "
        "descriptor no longer resolves to its seeded live finding — the site "
        "was routed through the seam (or removed); DELETE the now-stale "
        "allow-list entry (shrink-only)."
    )
    # The pinned finding really IS the get_current_branch HEAD selector.
    _rel_path, _qualname, token_line = seeded_key
    assert "get_current_branch (" in token_line, (
        f"allow-listed {descriptor.rel_path} ({descriptor.qualname}) no longer "
        f"holds the get_current_branch HEAD selector (got token_line {token_line!r})."
    )


# ===========================================================================
# T033 (WP07 / FR-011) — the CommitTarget(ref=<checkout>) construction grammar.
# ===========================================================================
#
# contracts/ratchet-contract.md's "New grammar" section: the three token
# grammars above do not catch the ACTUAL bypass shape —
# ``CommitTarget(ref=<current-checkout expression>)`` — because the checkout
# read and the CommitTarget construction are usually two different lines. This
# section adds a fourth, AST-based grammar scoped to the write-site file set
# (the T034-expanded ``_ADOPTED_MODULES`` plus the residual/sanctioned files
# the squad's H-1/H-4/L-2 audit named): every ``CommitTarget(ref=...)`` /
# ``safe_commit(..., destination_ref=...)`` construction in that scope must be
# provably seam-derived (or allow-listed with a tracked rationale).

#: Callees whose result -- or a local variable assigned from a call to them --
#: is provably seam-derived, not a checkout read (mirrors the canonicalizer
#: discriminator's ``CANONICAL_FOLD_SEAM`` shape, SC-004 precedent). Each is a
#: documented thin wrapper over ``placement_seam(...).write_target(kind)``:
#: ``write_target`` itself (the seam method, e.g.
#: ``placement_seam(...).write_target(kind)``), ``_resolve_workflow_placement``
#: (workflow.py T017), ``_resolve_claim_commit_target`` (implement.py, wraps the
#: context's seam-resolved ``artifact_placement.placement_ref``), and
#: ``_require_record_analysis_placement`` (mission_record_analysis.py, same
#: pattern).
_SEAM_FOLD_CALLEES: frozenset[str] = frozenset(
    {
        "write_target",
        "_resolve_workflow_placement",
        "_resolve_claim_commit_target",
        "_require_record_analysis_placement",
    }
)

#: RETIRED (WP06/T026): the 17-module allowlist (14 ``_ADOPTED_MODULES`` + 3
#: extras) the whole-tree scan REPLACES. Kept ONLY as a historical record for
#: the T030 non-regression proof below -- a module in this set was
#: "formerly in scope" under the old allowlist, so planting a bypass THERE
#: proves nothing about the widening (it would have reded before WP06 too);
#: planting a bypass in a module OUTSIDE this set is what proves the
#: whole-tree scan now sees what the allowlist could not. No longer used to
#: constrain the scan itself -- see ``_whole_tree_scan_scope`` (imported from
#: the shared ``_placement_whole_tree_scan`` helper) for the actual scope.
_RETIRED_EXTRA_CHECKOUT_GRAMMAR_MODULES: tuple[Path, ...] = (
    _SRC / "orchestrator_api" / "commands.py",
    _SRC / "coordination" / "transaction.py",
    _SRC / "retrospective" / "writer.py",
)
_RETIRED_CHECKOUT_GRAMMAR_ALLOWLIST: frozenset[str] = frozenset(
    _placement_rel_path(p)
    for p in (_ADOPTED_MODULES + _RETIRED_EXTRA_CHECKOUT_GRAMMAR_MODULES)
)

#: Pinned copy of the pre-widening ``BOUNDARY_SANCTIONED_PREFIXES`` (WP06 /
#: T029 "prefix guard -- RETAIN, do not create"): the meta-test below asserts
#: the shared helper's tuple is STILL exactly this -- a newly-ADDED dir-prefix
#: entry reds immediately, forcing the adder to use a per-file
#: ``BOUNDARY_SANCTIONED_MODULES`` entry (with a rationale) instead.
#:
#: placement-port-residuals-closure-01KYDEF0 WP03 (2026-07-26 / FR-003/004,
#: SC-002, C-002): ``"src/specify_cli/migration/"`` DROPPED from this tuple --
#: the subtree carries ZERO ``CommitTarget``/``safe_commit`` construction
#: (empirically confirmed; see T014), so the prefix was pure unused blanket
#: scope, not an active sanction. Removing it restores "any module" scan
#: precision (SC-002/NFR-001) without allow-listing anything new. The
#: remaining two entries (``mission_runtime/``, ``upgrade/migrations/``) are
#: untouched (C-002). The SEPARATE, intentional ``migration/`` blanket in
#: ``test_mission_resolver_walker_gate.py::_MIGRATION_WALKER_DIR_PREFIXES``
#: (C-004) is a different scan and is NOT affected by this change.
_PINNED_BOUNDARY_SANCTIONED_PREFIXES: tuple[str, ...] = (
    "src/mission_runtime/",
    "src/specify_cli/upgrade/migrations/",
)


@dataclass(frozen=True)
class _CheckoutGrammarFinding:
    """One flagged ``CommitTarget(ref=...)`` / ``safe_commit(destination_ref=...)`` call."""

    path: Path
    lineno: int
    callee: str
    source: str

    def as_allow_key(self) -> CompositeKey:
        """The drift-proof ``(rel_path, qualname, token_line)`` composite allow-list key."""
        qualname, token_line = composite_key(self.source, self.lineno)
        rel_path = self.path.relative_to(_REPO_ROOT).as_posix()
        return (rel_path, qualname, token_line)


def _checkout_grammar_callee_name(call: ast.Call) -> str | None:
    """Return the callee identifier for bare-name OR attribute call forms."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _checkout_grammar_parent_map(tree: ast.Module) -> dict[int, ast.AST]:
    """Map ``id(child) -> parent`` for every node in *tree* (single pass)."""
    parents: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node
    return parents


def _checkout_grammar_enclosing_function(
    parents: dict[int, ast.AST], target: ast.AST
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """Return the DIRECT enclosing ``ast.FunctionDef`` of *target*, or ``None``."""
    cur: ast.AST | None = target
    while cur is not None:
        cur = parents.get(id(cur))
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return cur
    return None


def _names_assigned_from_seam(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Local names assigned from a call to a ``_SEAM_FOLD_CALLEES`` member.

    Intra-function only (FR-004 def-use discipline): a name assigned from the
    seam in a CALLER's scope never seam-derives a callee's bare parameter.
    """
    out: set[str] = set()
    for node in ast.walk(fn):
        value: ast.expr | None = None
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            value, targets = node.value, list(node.targets)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            value, targets = node.value, [node.target]
        if isinstance(value, ast.Call) and _checkout_grammar_callee_name(value) in _SEAM_FOLD_CALLEES:
            for tgt in targets:
                if isinstance(tgt, ast.Name):
                    out.add(tgt.id)
    return out


def _is_seam_derived(
    arg: ast.expr | None,
    enclosing_fn: ast.FunctionDef | ast.AsyncFunctionDef | None,
) -> bool:
    """True when *arg* is provably sourced from the seam, not a checkout read.

    SAFE iff *arg* is (a) a plain string literal (a hardcoded ref, never
    checkout state -- e.g. a ``CommitTarget(ref="")`` default-factory
    placeholder), (b) a direct call to a ``_SEAM_FOLD_CALLEES`` member, or
    (c) a local name assigned from one of those callees earlier in the SAME
    function. Everything else -- a bare parameter, an attribute read
    (``self.x`` / ``st.x``), a subprocess call, an ``or``-fallback expression
    -- is presumptively checkout-derived and must be routed or allow-listed.
    """
    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
        return True
    if isinstance(arg, ast.Call) and _checkout_grammar_callee_name(arg) in _SEAM_FOLD_CALLEES:
        return True
    if isinstance(arg, ast.Name) and enclosing_fn is not None:
        return arg.id in _names_assigned_from_seam(enclosing_fn)
    return False


#: T027 (WP06) def-vs-call discrimination: functions whose OWN body is the
#: seam-facade's DEFINITION, not a caller. ``git.commit_helpers.safe_commit``
#: builds its own ``CommitTarget`` from the legacy two-arg ``destination_ref=``
#: compat-shim parameter as part of IMPLEMENTING the facade -- that is the
#: exact conversion the shim exists to perform, not a caller bypass.
#: ``mission_metadata.write_meta`` is named for symmetry (contracts/
#: ratchet-contract.md lists it as a definition-site risk) even though it
#: currently constructs no ``CommitTarget`` at all. Widening the whole-tree
#: scan to 100% of ``src/`` (T026) newly brings ``commit_helpers.py`` into
#: view, so without this discrimination the facade's own internals would
#: false-red.
_CHECKOUT_GRAMMAR_DEFINITION_SITE_FUNCTIONS: frozenset[str] = frozenset(
    {"safe_commit", "write_meta"}
)


def _is_checkout_grammar_definition_site(
    enclosing_fn: ast.FunctionDef | ast.AsyncFunctionDef | None,
) -> bool:
    """True when *enclosing_fn* IS one of the seam-facade functions being
    DEFINED (T027) -- its own internal ``CommitTarget``/``safe_commit``
    construction is scanner out-of-scope, not a caller bypass.

    Scoped to the DIRECT enclosing function only (never file-wide): a
    different, non-facade function in the SAME file is still scanned (see
    ``test_definition_site_discrimination_does_not_mask_a_same_named_bypass_elsewhere``).
    """
    return enclosing_fn is not None and enclosing_fn.name in _CHECKOUT_GRAMMAR_DEFINITION_SITE_FUNCTIONS


def _commit_target_ref_arg(call: ast.Call) -> ast.expr | None:
    """The ``ref`` argument of a ``CommitTarget(...)`` call (positional or kw)."""
    if call.args:
        return call.args[0]
    for kw in call.keywords:
        if kw.arg == "ref":
            return kw.value
    return None


def _safe_commit_destination_ref_arg(call: ast.Call) -> ast.expr | None:
    """The ``destination_ref`` kwarg of a ``safe_commit(...)`` call, if used directly.

    ``safe_commit`` also accepts a ``target=CommitTarget(...)`` form; that
    construction is caught independently as its own ``CommitTarget(...)`` node
    during the same tree walk, so this helper returns ``None`` (skip) when no
    ``destination_ref=`` kwarg is present.
    """
    for kw in call.keywords:
        if kw.arg == "destination_ref":
            return kw.value
    return None


def _scan_checkout_grammar(source: str, path: Path) -> list[_CheckoutGrammarFinding]:
    """Flag non-seam-derived ``CommitTarget``/``safe_commit`` ref constructions.

    AST-based (unlike ``_scan_source`` above, which is token-based): the
    forbidden grammar is a call CONSTRUCTION, not a textual pattern, so parsing
    means a docstring merely quoting the pattern is inert prose (a ``Constant``
    string, never a ``Call`` node) and is never flagged.

    **Proxy honesty (WP06)**: this is a SYNTACTIC proxy, not a value-flow
    proof. "Seam-derived" means the ``ref``/``destination_ref`` argument is
    (a) a string literal, (b) a direct call to a known seam-fold callee, or
    (c) a local name assigned from such a call earlier in the SAME function
    (``_is_seam_derived``). A bare parameter that the CALLER already resolved
    through the seam one function up is indistinguishable, syntactically,
    from a genuinely checkout-derived parameter -- such sites are
    allow-listed with a rationale (``_CHECKOUT_GRAMMAR_ALLOW_LIST_SEED``), not
    silently passed. def-vs-call discrimination (T027,
    ``_is_checkout_grammar_definition_site``) additionally excludes the
    facade's OWN definition body (``safe_commit``/``write_meta``) from
    scanning -- a definition is not a call site.
    """
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError:
        return []
    parents = _checkout_grammar_parent_map(tree)
    findings: list[_CheckoutGrammarFinding] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        callee = _checkout_grammar_callee_name(node)
        if callee == "CommitTarget":
            arg = _commit_target_ref_arg(node)
        elif callee == "safe_commit":
            arg = _safe_commit_destination_ref_arg(node)
            if arg is None:
                continue
        else:
            continue
        fn = _checkout_grammar_enclosing_function(parents, node)
        if _is_checkout_grammar_definition_site(fn):
            continue
        if _is_seam_derived(arg, fn):
            continue
        findings.append(_CheckoutGrammarFinding(path, node.lineno, callee, source))
    return findings


def _scan_checkout_grammar_module(path: Path) -> list[_CheckoutGrammarFinding]:
    return _scan_checkout_grammar(path.read_text(encoding="utf-8"), path)


#: Tracked-VISIBLE content-descriptor allow-list (squad H-1/H-4/L-2,
#: contracts/ratchet-contract.md; re-keyed onto content descriptors by
#: #2469 WP02/WP03): every entry names a REAL, still-checkout-derived
#: construction, each with an explicit rationale -- flagged VISIBLE, never
#: silently ignored. ``tracked: #2453`` entries share the deferred read-site
#: sweep bucket (D-1/C-003); the ``PERMANENT`` entry documents a construction
#: that will never route through the MissionArtifactKind placement seam
#: because it is not a placement decision at all.
#:
#: NOTE: the former ``orchestrator_api/commands.py``
#: ``_resolve_history_commit_args`` unresolvable-mission-fallback entry was
#: DELETED (shrink-only ratchet) after read-surface-ssot-closeout FR-004: the
#: ``ActionContextError`` catch now raises ``PlacementResolutionRequired``
#: (fail-closed) instead of constructing a ``CommitTarget(ref=current_branch)``
#: via ``git branch --show-current`` -- there is no longer a checkout-grammar
#: construction at that site.
_CHECKOUT_GRAMMAR_ALLOW_LIST_SEED: tuple[ContentDescriptor, ...] = (
    ContentDescriptor(
        rel_path="src/specify_cli/coordination/transaction.py",
        qualname="BookkeepingTransaction.commit",
        token_substring="CommitTarget ( ref = self . destination_ref )",
        occurrence=None,
        rationale=(
            "FIXED (#2453) and NARROWED: BookkeepingTransaction.commit()'s "
            "single CommitTarget(ref=self.destination_ref) construction serves "
            "BOTH the genuinely-legacy and modern-coordination-less arms of "
            "_acquire_locked's legacy branch, so this AST finding cannot be "
            "split further by the scanner -- but as of the #2453 fix, "
            "_resolve_legacy_lane_destination's Path.cwd() HEAD read only "
            "reaches self.destination_ref for a GENUINELY-legacy mission (no "
            "stored topology, per _warrants_legacy_warning's classification). "
            "A modern coordination-less mission (stored single_branch/lanes "
            "topology, or flattened) now populates self.destination_ref from "
            "the caller-supplied, CWD-invariant destination_ref instead (routed "
            "to repo_root, never Path.cwd()) -- the #2647 write-side taint this "
            "entry originally tracked is closed for that shape. The remaining "
            "genuinely-legacy re-derivation is intentional, permanent debt (a "
            "pre-SSOT mission has no other reliable write target) -- there is "
            "no #2453 sweep left to defer."
        ),
    ),
    ContentDescriptor(
        rel_path="src/specify_cli/cli/commands/agent/tasks_map_requirements.py",
        qualname="_mr_resolve_context",
        token_substring="CommitTarget ( ref = st . target_branch )",
        occurrence=None,
        rationale=(
            "tracked: #2453 - st.target_branch is the "
            "_ensure_target_branch_checked_out current-checkout branch, not "
            "the seam-resolved placement; deferred to the #2453 sweep (this "
            "call predates the STATUS_STATE routing WP05 added elsewhere in "
            "this module)."
        ),
    ),
    ContentDescriptor(
        rel_path="src/specify_cli/cli/commands/agent/workflow.py",
        qualname="_commit_via_legacy_safe_commit",
        token_substring="CommitTarget ( ref = target_branch )",
        occurrence=None,
        rationale=(
            "tracked: #2453 - _commit_via_legacy_safe_commit's target_branch "
            "parameter is a pre-coordination-topology legacy mission's "
            "checked-out branch; same deferred bucket as the other #2453 "
            "residuals."
        ),
    ),
    ContentDescriptor(
        rel_path="src/specify_cli/cli/commands/agent/tasks_move_task.py",
        qualname="_mt_commit_lane_deliverables",
        token_substring="CommitTarget ( ref = workspace . branch_name )",
        occurrence=None,
        rationale=(
            "PERMANENT: _mt_commit_lane_deliverables commits arbitrary "
            "implementer deliverables onto the LANE's own branch "
            "(workspace.branch_name) -- not a MissionArtifactKind placement "
            "decision; the lane branch is fixed by lane allocation, never "
            "resolved via the placement seam. Out of IC-04 scope."
        ),
    ),
    # -- WP06 (T029) additions: newly in scope once the 17-module allowlist
    # was replaced by the whole-tree scan. -----------------------------------
    ContentDescriptor(
        rel_path="src/runtime/next/runtime_bridge_io.py",
        qualname="resolve_commit_target",
        token_substring="CommitTarget ( ref = coordination_branch )",
        occurrence=None,
        rationale=(
            "SYNTACTIC-PROXY residual: resolve_commit_target is documented as "
            "'the pure decision lifted out of _wrap_with_decision_git_log' -- "
            "it wraps the CALLER-supplied, already-resolved "
            "coordination_branch parameter into a CommitTarget VO. The actual "
            "placement resolution happens in the caller before this pure "
            "function is invoked; value-flow across that call boundary is not "
            "provable by a syntactic AST scanner (contracts/ratchet-contract.md "
            "'proxy honesty')."
        ),
    ),
    ContentDescriptor(
        rel_path="src/specify_cli/git/bookkeeping_commit.py",
        qualname="_commit_bookkeeping",
        token_substring="CommitTarget ( ref = destination_ref_override )",
        occurrence=None,
        rationale=(
            "landing/#5001: destination_ref_override is NOT checkout-derived -- "
            "it is the AUTHORITATIVE caller-resolved target (the FR-007 "
            "single-persisted-merge-target authority) passed by "
            "commit_merge_bookkeeping, superseding placement resolution for a "
            "PRIMARY_METADATA merge-housekeeping commit. Not a checkout read."
        ),
    ),
    # NOTE (placement-port-residuals-closure-01KYDEF0 WP04, FR-005): the four
    # ``decision_log.DecisionGitLog._resolve_default_target`` /
    # ``bookkeeping_commit._resolve_bookkeeping_commit_target``
    # ``CommitTarget(ref=...)`` descriptors formerly seeded here were DELETED
    # (shrink-only governance, matching the ``test_checkout_grammar_allow_list_
    # entries_are_still_live`` staleness contract above): WP04 extracted the
    # shared ``CommitTarget(ref=degrade_ref)`` degrade construction these two
    # call sites duplicated into ONE helper,
    # ``mission_runtime.write_target_degrade.resolve_write_target_or_degrade``.
    # Both call sites now only ever call that helper — the ``CommitTarget(...)``
    # construction itself no longer exists at either site, so the descriptors
    # resolve to zero candidates. The helper's own construction needs no new
    # allow-list entry: ``src/mission_runtime/`` is already a
    # ``BOUNDARY_SANCTIONED_PREFIXES`` entry (out of this scan's scope), same
    # as every other seam-internal primitive under that package.
)

#: Composite key resolved LIVE for each ``_CHECKOUT_GRAMMAR_ALLOW_LIST_SEED``
#: entry (parallel, order-preserving with the seed tuple).
_CHECKOUT_GRAMMAR_ALLOW_LIST_KEYS: tuple[CompositeKey, ...] = tuple(
    resolve_descriptor((_REPO_ROOT / descriptor.rel_path).read_text(encoding="utf-8"), descriptor)
    for descriptor in _CHECKOUT_GRAMMAR_ALLOW_LIST_SEED
)

_CHECKOUT_GRAMMAR_ALLOW_LIST: frozenset[CompositeKey] = frozenset(
    _CHECKOUT_GRAMMAR_ALLOW_LIST_KEYS
)


def test_checkout_grammar_boundary_excludes_sanctioned_modules() -> None:
    """Guard the detection boundary (contract): sanctioned primitives are never scanned.

    WP06 (T026/T029) widened the scan scope from the retired 17-module
    allowlist to every ``src/`` module (FR-001 / NFR-001) -- so this is now
    the meta-test for the two REMAINING sanctioning mechanisms, both owned by
    the shared ``_placement_whole_tree_scan`` helper:

    1. none of ``BOUNDARY_SANCTIONED_MODULES`` (the per-file, rationale-
       carrying exclusion set) ever sneaks into ``_whole_tree_scan_scope()``;
    2. ``BOUNDARY_SANCTIONED_PREFIXES`` is byte-for-byte the pre-widening
       tuple -- a newly-ADDED dir-prefix entry reds here immediately (T029
       "prefix guard -- RETAIN, do not create"): a new prefix is how the
       retired module allowlist would creep back in inverted form. Use a
       per-file ``BOUNDARY_SANCTIONED_MODULES`` entry with a rationale
       instead.
    """
    scanned_rel = {_placement_rel_path(p) for p in _whole_tree_scan_scope()}
    for sanctioned in BOUNDARY_SANCTIONED_MODULES:
        assert sanctioned not in scanned_rel, (
            f"{sanctioned} is a sanctioned coord primitive and must never enter "
            "the whole-tree placement-enforcement scan scope"
        )
    for rel in scanned_rel:
        assert not rel.startswith(BOUNDARY_SANCTIONED_PREFIXES), (
            f"{rel} falls under a sanctioned-primitive prefix "
            f"({BOUNDARY_SANCTIONED_PREFIXES}) and must never enter the "
            "whole-tree placement-enforcement scan scope"
        )
    assert BOUNDARY_SANCTIONED_PREFIXES == _PINNED_BOUNDARY_SANCTIONED_PREFIXES, (
        "BOUNDARY_SANCTIONED_PREFIXES drifted from the pinned pre-widening "
        f"tuple {_PINNED_BOUNDARY_SANCTIONED_PREFIXES!r} (got "
        f"{BOUNDARY_SANCTIONED_PREFIXES!r}). Adding a NEW dir-prefix entry is "
        "forbidden (T029) -- add a per-file BOUNDARY_SANCTIONED_MODULES entry "
        "with a rationale instead."
    )


def test_sanctioned_modules_carry_a_rationale() -> None:
    """T029 meta-test: every ``BOUNDARY_SANCTIONED_MODULES`` entry has a
    non-empty inline rationale.

    A sanctioned exclusion with no rationale is unauditable -- it cannot be
    told apart from a lazy escape hatch. Every entry must justify itself.
    """
    for rel, rationale in BOUNDARY_SANCTIONED_MODULES.items():
        assert isinstance(rationale, str) and rationale.strip(), (
            f"BOUNDARY_SANCTIONED_MODULES entry {rel!r} has no non-empty "
            "inline rationale (T029) -- every sanctioned-primitive exclusion "
            "must carry a justification."
        )


def _checkout_grammar_offenders(
    module_sources: Iterable[tuple[Path, str]],
) -> list[str]:
    """The ``_CHECKOUT_GRAMMAR_ALLOW_LIST``-filtered offender messages for
    ``module_sources`` -- the SAME logic the real whole-tree gate below runs,
    shared with the T030 synthetic-bypass proof so both exercise one code
    path (never a second, divergent implementation for the self-test).
    """
    offenders: list[str] = []
    for module, source in module_sources:
        for finding in _scan_checkout_grammar(source, module):
            if finding.as_allow_key() in _CHECKOUT_GRAMMAR_ALLOW_LIST:
                continue
            offenders.append(
                f"{finding.path.relative_to(_REPO_ROOT)}:{finding.lineno} "
                f"{finding.callee}(...) constructs a ref from a non-seam-derived "
                "expression — route it through placement_seam(...).write_target(kind) "
                "or allow-list it with a tracked rationale"
            )
    return offenders


def test_adopted_and_residual_modules_have_no_checkout_derived_commit_target() -> None:
    """T033 / FR-011 (WP06 / T026: whole-tree, not a 17-module allowlist).

    A flag on a scanned module that is NOT on ``_CHECKOUT_GRAMMAR_ALLOW_LIST``
    means a real ``CommitTarget(ref=<checkout>)`` (or ``safe_commit(...,
    destination_ref=<checkout>)``) bypass — the exact split-brain root the
    placement seam exists to close (research.md D5 / plan D11). The scan
    scope is now EVERY ``src/`` module minus the small, individually-
    justified sanctioned-primitive set (FR-001 / NFR-001) — no module
    allowlist for a bypass to hide behind.
    """
    modules = _whole_tree_scan_scope()
    assert len(modules) > len(_RETIRED_CHECKOUT_GRAMMAR_ALLOWLIST), (
        "sanity: the whole-tree scan scope must be strictly larger than the "
        "retired 17-module allowlist it replaced (T026) — got "
        f"{len(modules)} modules vs. {len(_RETIRED_CHECKOUT_GRAMMAR_ALLOWLIST)} retired."
    )
    for module in modules:
        assert module.exists(), f"checkout-grammar module missing: {module}"

    offenders = _checkout_grammar_offenders(
        (module, module.read_text(encoding="utf-8")) for module in modules
    )

    assert not offenders, (
        "Checkout-derived CommitTarget/safe_commit construction found (T033 / "
        "FR-011). Route the ref/destination_ref argument through "
        "placement_seam(...).write_target(kind) instead of a checkout read, or add "
        "a tracked, rationale-carrying entry to _CHECKOUT_GRAMMAR_ALLOW_LIST_SEED. "
        "Offenders:\n" + "\n".join(offenders)
    )


def test_checkout_grammar_allow_list_entries_are_still_live() -> None:
    """Staleness twin-guard: every seeded descriptor still resolves to its live finding.

    If a residual site is finally routed through the seam,
    :func:`descriptor_still_live` returns ``False`` (the descriptor resolves to
    zero matches, or to a different key) and this test fails loudly — the fix
    is to DELETE the now-stale seed entry (shrink-only governance), never to
    leave a vacuous allow-list rule masking nothing. Exactly-one + key-equal:
    NEVER "≥1 finding matches" (D-1 bite hole).
    """
    for descriptor, seeded_key in zip(
        _CHECKOUT_GRAMMAR_ALLOW_LIST_SEED, _CHECKOUT_GRAMMAR_ALLOW_LIST_KEYS, strict=True
    ):
        source = (_REPO_ROOT / descriptor.rel_path).read_text(encoding="utf-8")
        assert descriptor_still_live(source, descriptor, seeded_key), (
            f"{descriptor.rel_path} ({descriptor.qualname}) no longer resolves "
            "to its seeded live checkout-grammar finding — the site was routed "
            "through the seam (or removed); DELETE this now-stale allow-list "
            "entry (shrink-only, never leave a vacuous rule)."
        )


def test_retrospective_writer_is_checkout_grammar_clean() -> None:
    """``retrospective/writer.py`` (the sanctioned #2119 RETROSPECTIVE authority)
    produces ZERO checkout-grammar findings, needing NO allow-list entry.

    It never constructs a ``CommitTarget`` at all (it resolves the RETROSPECTIVE
    HOME directory via ``resolve_retrospective_home``; the actual commit
    happens downstream in ``git/bookkeeping_commit.py``, which the WP06
    whole-tree widening now scans directly -- see its own two allow-listed
    bootstrap-window-degrade entries above). Pins this so a future change
    adding a construction here is caught by the main ratchet above rather
    than silently needing this file re-audited.
    """
    assert _scan_checkout_grammar_module(_SRC / "retrospective" / "writer.py") == []


# ---------------------------------------------------------------------------
# T027 (WP06) — def-vs-call discrimination: the seam facade's OWN definition
# is not a caller bypass.
# ---------------------------------------------------------------------------


def test_definition_site_of_the_seam_facade_is_not_flagged() -> None:
    """T027: ``git.commit_helpers.safe_commit``'s OWN compat-shim construction
    (``target = CommitTarget(ref=destination_ref)``) is a DEFINITION site, not
    a caller bypass -- it must produce ZERO checkout-grammar findings.

    Widening the scan to 100% of ``src/`` (T026) newly brings
    ``commit_helpers.py`` into view; without the def-vs-call discrimination
    this would false-red on the facade's own internals.
    """
    findings = _scan_checkout_grammar_module(_SRC / "git" / "commit_helpers.py")
    assert findings == [], (
        "safe_commit's own compat-shim CommitTarget(ref=destination_ref) "
        "construction was flagged -- the def-vs-call discrimination (T027) "
        f"regressed. Findings: {findings!r}"
    )


def test_definition_site_discrimination_does_not_mask_a_same_named_bypass_elsewhere() -> None:
    """Anti-false-negative: the def-site exemption is scoped to the DIRECT
    enclosing function only, not file-wide.

    A DIFFERENT function (not literally named ``safe_commit``/``write_meta``)
    in the same fixture source must still be flagged if it constructs a
    checkout-derived ``CommitTarget`` -- proving the discrimination does not
    silently excuse an unrelated bypass sharing a file with the real shim.
    """
    fixture_source = (
        "def _not_the_shim(current_branch):\n"
        "    return CommitTarget(ref=current_branch)\n"
        "def safe_commit(destination_ref):\n"
        "    return CommitTarget(ref=destination_ref)\n"
    )
    findings = _scan_checkout_grammar(fixture_source, _SRC / "git" / "commit_helpers.py")
    assert len(findings) == 1, (
        "the def-site exemption for safe_commit masked a DIFFERENT, "
        f"non-shim function's bypass in the same fixture: {findings!r}"
    )
    assert findings[0].lineno == 2, (
        "expected the sole finding to be _not_the_shim's bypass (line 2), "
        f"got lineno {findings[0].lineno}"
    )


# ---------------------------------------------------------------------------
# T030 (WP06) — whole-tree proof: a bypass in a formerly-out-of-scope module
# reds, and regression parity is preserved for a formerly-in-scope module.
# ---------------------------------------------------------------------------

#: Synthetic bypass fixture reused by both T030 tests below.
_T030_INJECTED_BYPASS_SOURCE = (
    "def _injected_bypass(current_branch):\n"
    "    return CommitTarget(ref=current_branch)\n"
)


@pytest.mark.parametrize(
    "rel_path",
    [
        "src/specify_cli/doc_analysis/doc_state.py",
        "src/specify_cli/acceptance/__init__.py",
    ],
)
def test_whole_tree_scan_catches_bypass_in_formerly_out_of_scope_module(rel_path: str) -> None:
    """T030: a synthetic bypass planted in a module the RETIRED 17-module
    allowlist could NOT see now REDS and names the offending site.

    Injecting into a module that was already in the old allowlist would
    prove nothing about the widening (it would have reded before WP06 too) --
    each parametrized ``rel_path`` here is asserted to be OUTSIDE the retired
    scope first, so this test can only pass by exercising the widening.
    """
    assert rel_path not in _RETIRED_CHECKOUT_GRAMMAR_ALLOWLIST, (
        f"{rel_path} must be a module the retired 17-module allowlist could "
        "NOT see -- injecting a bypass into a formerly-in-scope module would "
        "not exercise the widening (T030)."
    )
    module = _REPO_ROOT / rel_path
    assert module.exists(), f"T030 fixture module missing: {module}"

    offenders = _checkout_grammar_offenders([(module, _T030_INJECTED_BYPASS_SOURCE)])

    assert offenders, (
        "whole-tree gate failed to flag a planted bypass in the formerly "
        f"out-of-scope module {rel_path} -- the widening is not effective."
    )
    assert any(rel_path in offender for offender in offenders), (
        f"the offending site {rel_path} was not named in the offender "
        f"message(s): {offenders!r}"
    )


def test_whole_tree_scan_control_still_flags_formerly_in_scope_module() -> None:
    """T030 regression-parity control (NFR-004): a synthetic bypass planted in
    a module that WAS already in the retired 17-module allowlist still reds
    too -- the widening did not accidentally narrow detection for the
    previously-covered set.
    """
    rel_path = "src/specify_cli/core/mission_creation.py"
    assert rel_path in _RETIRED_CHECKOUT_GRAMMAR_ALLOWLIST, (
        f"{rel_path} must be a module the retired 17-module allowlist COULD "
        "see, to serve as the regression-parity control."
    )
    module = _REPO_ROOT / rel_path

    offenders = _checkout_grammar_offenders([(module, _T030_INJECTED_BYPASS_SOURCE)])

    assert offenders, (
        "regression: a planted bypass in a formerly-in-scope module no "
        "longer reds under the whole-tree scan."
    )


# ---------------------------------------------------------------------------
# "The grammar bites" — self-tests (T036): a planted bypass goes RED.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("planted", "expected_callee"),
    [
        ("    return CommitTarget(ref=current_branch)\n", "CommitTarget"),
        (
            "    return safe_commit(repo_root=r, worktree_root=w, "
            "destination_ref=current_branch, message=m, paths=p)\n",
            "safe_commit",
        ),
    ],
)
def test_checkout_grammar_bites_on_planted_bypass(planted: str, expected_callee: str) -> None:
    """T036: re-introducing a ``CommitTarget(ref=<checkout>)`` bypass goes RED.

    Proves the new grammar is not inert by planting the EXACT forbidden
    construction contracts/ratchet-contract.md names
    (``CommitTarget(ref=current_branch)``) — plus the ``safe_commit(...,
    destination_ref=...)`` sibling form — into a fixture source and asserting
    the detector flags it.
    """
    fixture_source = (
        "def _adopted_write_site(current_branch, r, w, m, p):\n"
        f"{planted}"
    )
    findings = _scan_checkout_grammar(fixture_source, _SRC / "core" / "mission_creation.py")
    kinds = {f.callee for f in findings}
    assert expected_callee in kinds, (
        f"checkout-grammar failed to flag a planted {expected_callee}(...) bypass; "
        f"got {kinds}"
    )


def test_checkout_grammar_does_not_flag_seam_derived_construction() -> None:
    """Anti-false-positive: a ``write_target(...)``-derived ref is NOT flagged."""
    fixture_source = (
        "def _adopted_write_site(repo_root, mission_slug):\n"
        "    seam_target = placement_seam(repo_root, mission_slug).write_target(KIND)\n"
        "    return safe_commit(target=seam_target)\n"
    )
    assert (
        _scan_checkout_grammar(fixture_source, _SRC / "core" / "mission_creation.py") == []
    )


def test_checkout_grammar_does_not_flag_string_literal_placeholder() -> None:
    """Anti-false-positive: a hardcoded string literal ref is NEVER checkout state.

    Pins ``tasks_map_requirements.py``'s ``CommitTarget(ref="")``
    default-factory placeholder pattern.
    """
    fixture_source = (
        "def _factory():\n"
        '    return CommitTarget(ref="")\n'
    )
    assert (
        _scan_checkout_grammar(fixture_source, _SRC / "core" / "mission_creation.py") == []
    )


def test_checkout_grammar_ignores_prose_quoting_the_pattern() -> None:
    """A docstring that merely QUOTES the forbidden pattern is NOT flagged.

    Unlike the token-based scanner above, this is inherent to AST parsing (the
    string never becomes a ``Call`` node) — this test pins that guarantee for
    the new grammar specifically.
    """
    fixture_source = (
        "def _adopted_resolver(repo_root, mission_slug):\n"
        '    """The bypass looked like CommitTarget(ref=current_branch).\n'
        '    Never do that -- route through write_target(kind) instead.\n'
        '    """\n'
        "    return placement_seam(repo_root, mission_slug).write_target(KIND)\n"
    )
    assert (
        _scan_checkout_grammar(fixture_source, _SRC / "core" / "mission_creation.py") == []
    )


# ===========================================================================
# T015 (WP03 / FR-013, NFR-001/002) — plant-and-catch + motion battery.
# ===========================================================================
#
# Proves the content-descriptor migration (WP02/WP03) actually delivers what
# it promises: (1) benign line-drift above a migrated site never false-reds
# (the motion battery); (2) a genuinely new, un-allowlisted offender is never
# silently absorbed (the bite); (3) the D-1 same-qualname-sibling trap -- a
# NEW un-sanctioned offender landing in the SAME qualname with the SAME
# token line as a sanctioned site -- is caught by the exactly-one semantics,
# never masked by a naive "≥1 finding matches" staleness check.


def test_motion_battery_blank_and_comment_insertion_stays_green() -> None:
    """FR-013 / NFR-001/002 motion battery: benign insertion above a migrated
    site leaves ``descriptor_still_live`` GREEN.

    A blank line, a comment line, and a multi-line docstring inserted ABOVE a
    migrated site all shift its line number, but the descriptor's
    ``(qualname, token_substring)`` resolution is unaffected -- content
    descriptors are qualname + tokenized-code-line addressed, never
    line-number addressed (the whole point of the WP02/WP03 migration; #2072).
    """
    descriptor = ContentDescriptor(
        rel_path="fixture.py",
        qualname="_adopted_write_site",
        token_substring="coord_branch or _current_branch",
        occurrence=None,
        rationale="motion-battery fixture",
    )
    base_source = (
        "def _adopted_write_site(coord_branch, repo_root):\n"
        "    return coord_branch or _current_branch(repo_root)\n"
    )
    seeded_key = resolve_descriptor(base_source, descriptor)

    motions = (
        "\n",  # a blank line
        "    # a comment line inserted above the site\n",
        '    """A multi-line docstring inserted above the site.\n\n'
        '    More prose describing unrelated behavior.\n    """\n',
    )
    for motion in motions:
        drifted_source = (
            "def _adopted_write_site(coord_branch, repo_root):\n"
            f"{motion}"
            "    return coord_branch or _current_branch(repo_root)\n"
        )
        assert descriptor_still_live(drifted_source, descriptor, seeded_key), (
            f"motion battery false-red: benign insertion {motion!r} above the "
            "migrated site flipped the gate -- content descriptors must be "
            "immune to line drift caused by benign insertions."
        )


def test_bite_unallowlisted_rederivation_is_not_absorbed_by_the_allow_list() -> None:
    """T015 bite: a planted, un-allowlisted re-derivation is NOT excused.

    Distinct from ``test_ratchet_bites_on_planted_rederivation`` (which only
    proves the scanner FLAGS the pattern): this proves the flagged finding's
    composite allow-key is NOT a member of ``_ALLOW_LIST`` -- planting a new
    offender in a qualname that carries no seeded descriptor produces a
    finding the ratchet would reject, never one silently absorbed by an
    existing allow-list entry.
    """
    fixture_source = (
        "def _new_unsanctioned_write_site(coord_branch, repo_root):\n"
        "    return coord_branch or _current_branch(repo_root)\n"
    )
    findings = _scan_source(
        fixture_source, _SRC / "coordination" / "status_transition.py"
    )
    offending = [f for f in findings if f.kind == "write_target_head_selector"]
    assert offending, "the bite fixture must actually plant a flagged finding"
    for finding in offending:
        assert finding.as_allow_key() not in _ALLOW_LIST, (
            f"planted un-allowlisted finding {finding.as_allow_key()!r} was "
            "absorbed by the allow-list -- a fresh qualname must never "
            "collide with a real seeded descriptor."
        )


def test_same_qualname_sibling_offender_reds_the_twin_guard() -> None:
    """T015 D-1 same-qualname-sibling bite: a new sibling offender REDS, never silently absorbed.

    research.md's D-1 bite hole: a naive "≥1 finding matches" staleness check
    would stay GREEN even after a NEW un-sanctioned offender lands in the SAME
    qualname with the SAME token line as the sanctioned site -- silently
    absorbing (masking) the new offender under cover of the pre-existing
    allow-list entry. The exactly-one ``resolve_descriptor`` semantics instead
    RED the moment a second candidate appears in that qualname (a
    ``DescriptorResolutionError`` that :func:`descriptor_still_live` turns
    into ``False``), proving the sibling is NOT absorbed.
    """
    descriptor = ContentDescriptor(
        rel_path="fixture.py",
        qualname="_resolve_write_target",
        token_substring="coord_branch or _current_branch",
        occurrence=None,
        rationale="D-1 same-qualname-sibling fixture",
    )
    sanctioned_source = (
        "def _resolve_write_target(coord_branch, repo_root):\n"
        "    return coord_branch or _current_branch(repo_root)\n"
    )
    seeded_key = resolve_descriptor(sanctioned_source, descriptor)

    # A second, un-sanctioned offender lands in the SAME qualname with the
    # SAME token line (e.g. a copy-pasted duplicate branch) -- exactly the D-1
    # shape: the sanctioned site is still there, but it is no longer alone.
    sibling_source = (
        "def _resolve_write_target(coord_branch, repo_root):\n"
        "    if repo_root is None:\n"
        "        return coord_branch or _current_branch(repo_root)\n"
        "    return coord_branch or _current_branch(repo_root)\n"
    )
    assert not descriptor_still_live(sibling_source, descriptor, seeded_key), (
        "D-1 bite hole: a same-qualname sibling offender with an identical "
        "token line was silently absorbed instead of reding the twin-guard -- "
        "the resolver must require exactly-one, never '≥1 finding matches'."
    )
