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
import os
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.architectural._ast_scan import parse_source, read_source
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
_PRE_WRITE_DIR_ADOPTED_MODULES: tuple[Path, ...] = (
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

#: coord-artifact-single-home-01M3V4BE WP20 (T106 binding correction, scout X3):
#: every module that now consumes ``placement_seam(...).write_dir(kind)`` /
#: ``WriteLocation`` (the single COORD write-location accessor). The first
#: grammar's ``root_walk`` kind (``<expr>.parent.parent``) is the ONE rule that
#: catches "guess the checkout root by walking up from a ``WriteLocation``
#: path" -- ``test_no_worktree_name_guess.py`` explicitly excludes that class
#: (``.path.parent.parent``, deferred to #2007), so the scan scope is widened
#: HERE, to the ``write_dir`` consumers, rather than there. Use
#: ``WriteLocation.surface_root`` instead of a ``.parent.parent`` walk.
#:
#: ``src/runtime/next/runtime_bridge_decision_log.py`` lives outside ``_SRC`` (it
#: is under ``src/runtime``), so its path is spelled from ``_REPO_ROOT``. It
#: replaced ``runtime_bridge.py`` here when ``_wrap_with_decision_git_log`` (the
#: bridge's only ``write_dir`` call) moved to it (#2560).
_WRITE_DIR_CONSUMER_MODULES: tuple[Path, ...] = (
    _SRC / "decisions" / "emit.py",
    _SRC / "decisions" / "service.py",
    _SRC / "decisions" / "fork.py",
    _SRC / "events" / "decision_log.py",
    _REPO_ROOT / "src" / "runtime" / "next" / "runtime_bridge_decision_log.py",
    _SRC / "review" / "cycle.py",
    _SRC / "cli" / "commands" / "accept.py",
    _SRC / "cli" / "commands" / "_decisions_doctor.py",
    _SRC / "consolidation" / "executor.py",
    # #2026: executor.py was split along its phases; the whole family stays in
    # scan scope (the run status-dir write accessor lives in entry_preflight).
    _SRC / "consolidation" / "entry_preflight.py",
    _SRC / "consolidation" / "run_state.py",
    _SRC / "consolidation" / "coord_strand.py",
    _SRC / "consolidation" / "phase_claim.py",
    _SRC / "consolidation" / "phase_advance.py",
    _SRC / "consolidation" / "phase_bookkeeping.py",
    _SRC / "consolidation" / "phase_gate.py",
    _SRC / "consolidation" / "phase_teardown.py",
    _SRC / "consolidation" / "phase_finalize.py",
    _SRC / "consolidation" / "resume_recovery.py",
    _SRC / "cli" / "commands" / "materialize.py",
    _SRC / "coordination" / "commit_router.py",
    _SRC / "coordination" / "coord_seed.py",
    _SRC / "coordination" / "transaction.py",
    # implement-degod WP04: the planning-commit decisions moved here; the scan follows the code.
    _SRC / "coordination" / "planning_commit.py",
    # implement-degod WP05: the planning-commit adapter moved here; the scan follows the code.
    _SRC / "cli" / "commands" / "implement_planning_commit.py",
    # implement-degod WP08: the claim preflight and claim commit moved here; the scan follows the code.
    _SRC / "cli" / "commands" / "implement_claim.py",
    # implement-degod WP09: the phase blocks and the --recover family moved here; the scan follows the code.
    _SRC / "cli" / "commands" / "implement_phases.py",
    _SRC / "cli" / "commands" / "implement_recover.py",
    _SRC / "lanes" / "recovery.py",
    _SRC / "retrospective" / "tracer_writer.py",
    _SRC / "tasks" / "issue_matrix.py",
    _SRC / "acceptance" / "matrix.py",
    _SRC / "acceptance" / "gates_core.py",
    _SRC / "cli" / "commands" / "agent" / "issue_verdict.py",
    _SRC / "cli" / "commands" / "agent" / "tasks_mark_status.py",
    # #5629: the move-task gate family moved out of tasks_move_task.py into this
    # seam; the scan keeps following the code, so the successor module joins.
    _SRC / "cli" / "commands" / "agent" / "tasks_move_task_gates.py",
    # #5695: so do the hop builders and the executor (about 950 lines).
    _SRC / "cli" / "commands" / "agent" / "tasks_move_task_hops.py",
    _SRC / "cli" / "commands" / "agent" / "tasks_move_task_executor.py",
    _SRC / "agent_tasks_ports.py",
    # #5634: mission_creation.py (an original adopted module) was split into
    # leaf modules with the bodies moved verbatim; the scan keeps following the
    # code, so every leaf joins (the façade stays in the adopted scope above).
    _SRC / "core" / "mission_creation_errors.py",
    _SRC / "core" / "mission_creation_identity.py",
    _SRC / "core" / "mission_creation_roots.py",
    _SRC / "core" / "mission_creation_duplicates.py",
    _SRC / "core" / "mission_creation_protected_mint.py",
    _SRC / "core" / "mission_creation_scaffold.py",
    _SRC / "core" / "mission_creation_meta.py",
    _SRC / "core" / "mission_creation_events.py",
    _SRC / "core" / "mission_creation_commit.py",
    _SRC / "core" / "mission_creation_rollback.py",
    _SRC / "core" / "mission_creation_decisions.py",
    _SRC / "cli" / "commands" / "retrospect.py",
    _SRC / "cli" / "commands" / "agent_retrospect.py",
)

#: ``_PRE_WRITE_DIR_ADOPTED_MODULES`` above is the ORIGINAL adopted scope,
#: frozen under that name: ``_RETIRED_CHECKOUT_GRAMMAR_ALLOWLIST`` below is a
#: historical record of the pre-WP06 17-module allowlist, so it keeps deriving
#: from it (not from the widened scan scope) or the T030 "formerly out of
#: scope" non-regression proof would silently change meaning.
#: The first grammar's scan scope: the original adopted modules plus every
#: ``write_dir`` consumer (WP20, FR-014).
_ADOPTED_MODULES = _PRE_WRITE_DIR_ADOPTED_MODULES + tuple(module for module in _WRITE_DIR_CONSUMER_MODULES if module not in _PRE_WRITE_DIR_ADOPTED_MODULES)


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
#: WS#3 — ``cli/commands/implement_claim.py`` / ``_status_commit_destination_branch``
#: (moved from ``implement.py`` by implement-degod WP08):
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
        rel_path="src/specify_cli/cli/commands/implement_claim.py",
        qualname="_status_commit_destination_branch",
        token_substring="get_current_branch ( repo_root ) or fallback_branch",
        occurrence=None,
        rationale=(
            "tracked: #2453 - predicts the pre-lane status-commit branch for "
            "the protected-branch guard only; never feeds a write "
            "CommitTarget/destination_ref. Deferred to the #2453 read-site "
            "sweep bucket (D-1/C-003). implement-degod WP08: the function "
            "moved implement.py -> implement_claim.py; descriptor re-pointed, "
            "same underlying code."
        ),
    ),
)

#: Composite key resolved LIVE for each ``_ALLOW_LIST_SEED`` entry (parallel,
#: order-preserving with the seed tuple — the staleness twin-guards below index
#: into both by descriptor identity, never a bare position).
_ALLOW_LIST_KEYS: tuple[CompositeKey, ...] = tuple(
    resolve_descriptor((_REPO_ROOT / descriptor.rel_path).read_text(encoding="utf-8"), descriptor) for descriptor in _ALLOW_LIST_SEED
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
      ``implement_claim.py``'s ``_status_commit_destination_branch``, which predicts
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
            offenders.append(f"{finding.path.relative_to(_REPO_ROOT)}:{finding.lineno} [{finding.kind}] {finding.code}")

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
    assert expected_kind in kinds, f"ratchet failed to flag planted {expected_kind!r}; got {kinds}"


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
        assert isinstance(entry, tuple) and len(entry) == 3, f"allow-list entry must be a (rel_path, qualname, token_line) composite, got {entry!r}"
        rel_path, qualname, token_line = entry
        assert isinstance(rel_path, str) and rel_path, f"rel_path component must be a non-empty str, got {rel_path!r}"
        assert isinstance(qualname, str) and qualname, f"qualname component must be a non-empty str, got {qualname!r}"
        assert isinstance(token_line, str) and token_line, (
            f"token_line component must be a non-empty code line (a real line, not a whole-file wildcard), got {token_line!r}"
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
    assert all(descriptor.rel_path != "src/specify_cli/coordination/status_transition.py" for descriptor in _ALLOW_LIST_SEED), (
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
    findings = [finding for finding in _scan_module(status_transition_path) if finding.kind == "write_target_head_selector"]
    assert not findings, (
        "the retired #1716 selector reappeared as CODE in status_transition.py; "
        f"the WS#1 allow-list entry was deleted on the assumption it is gone for good: {findings!r}"
    )


def test_checkout_head_selector_entry_is_still_a_live_finding() -> None:
    """Staleness twin-guard for the tracked #2453 checkout-HEAD selector descriptor.

    The ``implement_claim.py`` descriptor pins ``_status_commit_destination_branch``'s
    ``get_current_branch(repo_root) or fallback_branch`` prediction selector. If
    that site is finally routed through the placement seam (or removed),
    :func:`descriptor_still_live` returns ``False`` (0 matches, or a
    key-inequality) and this test fails loudly — the fix is to DELETE the
    now-stale allow-list entry (shrink-only), never to leave a vacuous
    allow-list rule masking nothing.
    """
    descriptor, seeded_key = _seed_and_key_for("src/specify_cli/cli/commands/implement_claim.py")
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
        f"allow-listed {descriptor.rel_path} ({descriptor.qualname}) no longer holds the get_current_branch HEAD selector (got token_line {token_line!r})."
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
#: (workflow.py T017), and ``_require_record_analysis_placement``
#: (mission_record_analysis.py, wraps the seam-resolved placement ref).
#: ``_resolve_claim_commit_target`` (implement_cores.py) was deleted with no
#: production caller left (#5232 / FR-018), so it is no longer a fold callee.
_SEAM_FOLD_CALLEES: frozenset[str] = frozenset(
    {
        "write_target",
        "_resolve_workflow_placement",
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
    _placement_rel_path(p) for p in (_PRE_WRITE_DIR_ADOPTED_MODULES + _RETIRED_EXTRA_CHECKOUT_GRAMMAR_MODULES)
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


def _checkout_grammar_enclosing_function(parents: dict[int, ast.AST], target: ast.AST) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
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
_CHECKOUT_GRAMMAR_DEFINITION_SITE_FUNCTIONS: frozenset[str] = frozenset({"safe_commit", "write_meta"})


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
    tree = parse_source(source, display=str(path))
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
    return _scan_checkout_grammar(read_source(path), path)


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
#: construction at that site. The helper itself was later deleted as dead code
#: (append-history stopped committing WP-file edits in #2684).
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
        rel_path="src/runtime/next/runtime_bridge_decision_log.py",
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
    resolve_descriptor((_REPO_ROOT / descriptor.rel_path).read_text(encoding="utf-8"), descriptor) for descriptor in _CHECKOUT_GRAMMAR_ALLOW_LIST_SEED
)

_CHECKOUT_GRAMMAR_ALLOW_LIST: frozenset[CompositeKey] = frozenset(_CHECKOUT_GRAMMAR_ALLOW_LIST_KEYS)


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
        assert sanctioned not in scanned_rel, f"{sanctioned} is a sanctioned coord primitive and must never enter the whole-tree placement-enforcement scan scope"
    for rel in scanned_rel:
        assert not rel.startswith(BOUNDARY_SANCTIONED_PREFIXES), (
            f"{rel} falls under a sanctioned-primitive prefix ({BOUNDARY_SANCTIONED_PREFIXES}) and must never enter the whole-tree placement-enforcement scan scope"
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

    offenders = _checkout_grammar_offenders((module, module.read_text(encoding="utf-8")) for module in modules)

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
    for descriptor, seeded_key in zip(_CHECKOUT_GRAMMAR_ALLOW_LIST_SEED, _CHECKOUT_GRAMMAR_ALLOW_LIST_KEYS, strict=True):
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
    assert len(findings) == 1, f"the def-site exemption for safe_commit masked a DIFFERENT, non-shim function's bypass in the same fixture: {findings!r}"
    assert findings[0].lineno == 2, f"expected the sole finding to be _not_the_shim's bypass (line 2), got lineno {findings[0].lineno}"


# ---------------------------------------------------------------------------
# T030 (WP06) — whole-tree proof: a bypass in a formerly-out-of-scope module
# reds, and regression parity is preserved for a formerly-in-scope module.
# ---------------------------------------------------------------------------

#: Synthetic bypass fixture reused by both T030 tests below.
_T030_INJECTED_BYPASS_SOURCE = "def _injected_bypass(current_branch):\n    return CommitTarget(ref=current_branch)\n"


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

    assert offenders, f"whole-tree gate failed to flag a planted bypass in the formerly out-of-scope module {rel_path} -- the widening is not effective."
    assert any(rel_path in offender for offender in offenders), f"the offending site {rel_path} was not named in the offender message(s): {offenders!r}"


def test_whole_tree_scan_control_still_flags_formerly_in_scope_module() -> None:
    """T030 regression-parity control (NFR-004): a synthetic bypass planted in
    a module that WAS already in the retired 17-module allowlist still reds
    too -- the widening did not accidentally narrow detection for the
    previously-covered set.
    """
    rel_path = "src/specify_cli/core/mission_creation.py"
    assert rel_path in _RETIRED_CHECKOUT_GRAMMAR_ALLOWLIST, (
        f"{rel_path} must be a module the retired 17-module allowlist COULD see, to serve as the regression-parity control."
    )
    module = _REPO_ROOT / rel_path

    offenders = _checkout_grammar_offenders([(module, _T030_INJECTED_BYPASS_SOURCE)])

    assert offenders, "regression: a planted bypass in a formerly-in-scope module no longer reds under the whole-tree scan."


# ---------------------------------------------------------------------------
# "The grammar bites" — self-tests (T036): a planted bypass goes RED.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("planted", "expected_callee"),
    [
        ("    return CommitTarget(ref=current_branch)\n", "CommitTarget"),
        (
            "    return safe_commit(repo_root=r, worktree_root=w, destination_ref=current_branch, message=m, paths=p)\n",
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
    fixture_source = f"def _adopted_write_site(current_branch, r, w, m, p):\n{planted}"
    findings = _scan_checkout_grammar(fixture_source, _SRC / "core" / "mission_creation.py")
    kinds = {f.callee for f in findings}
    assert expected_callee in kinds, f"checkout-grammar failed to flag a planted {expected_callee}(...) bypass; got {kinds}"


def test_checkout_grammar_does_not_flag_seam_derived_construction() -> None:
    """Anti-false-positive: a ``write_target(...)``-derived ref is NOT flagged."""
    fixture_source = (
        "def _adopted_write_site(repo_root, mission_slug):\n"
        "    seam_target = placement_seam(repo_root, mission_slug).write_target(KIND)\n"
        "    return safe_commit(target=seam_target)\n"
    )
    assert _scan_checkout_grammar(fixture_source, _SRC / "core" / "mission_creation.py") == []


def test_checkout_grammar_does_not_flag_string_literal_placeholder() -> None:
    """Anti-false-positive: a hardcoded string literal ref is NEVER checkout state.

    Pins ``tasks_map_requirements.py``'s ``CommitTarget(ref="")``
    default-factory placeholder pattern.
    """
    fixture_source = 'def _factory():\n    return CommitTarget(ref="")\n'
    assert _scan_checkout_grammar(fixture_source, _SRC / "core" / "mission_creation.py") == []


def test_checkout_grammar_ignores_prose_quoting_the_pattern() -> None:
    """A docstring that merely QUOTES the forbidden pattern is NOT flagged.

    Unlike the token-based scanner above, this is inherent to AST parsing (the
    string never becomes a ``Call`` node) — this test pins that guarantee for
    the new grammar specifically.
    """
    fixture_source = (
        "def _adopted_resolver(repo_root, mission_slug):\n"
        '    """The bypass looked like CommitTarget(ref=current_branch).\n'
        "    Never do that -- route through write_target(kind) instead.\n"
        '    """\n'
        "    return placement_seam(repo_root, mission_slug).write_target(KIND)\n"
    )
    assert _scan_checkout_grammar(fixture_source, _SRC / "core" / "mission_creation.py") == []


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
    base_source = "def _adopted_write_site(coord_branch, repo_root):\n    return coord_branch or _current_branch(repo_root)\n"
    seeded_key = resolve_descriptor(base_source, descriptor)

    motions = (
        "\n",  # a blank line
        "    # a comment line inserted above the site\n",
        '    """A multi-line docstring inserted above the site.\n\n    More prose describing unrelated behavior.\n    """\n',
    )
    for motion in motions:
        drifted_source = f"def _adopted_write_site(coord_branch, repo_root):\n{motion}    return coord_branch or _current_branch(repo_root)\n"
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
    fixture_source = "def _new_unsanctioned_write_site(coord_branch, repo_root):\n    return coord_branch or _current_branch(repo_root)\n"
    findings = _scan_source(fixture_source, _SRC / "coordination" / "status_transition.py")
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
    sanctioned_source = "def _resolve_write_target(coord_branch, repo_root):\n    return coord_branch or _current_branch(repo_root)\n"
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


# ===========================================================================
# WP20 (coord-artifact-single-home-01M3V4BE, FR-014 / SC-005) -- the THIRD
# grammar: a COORD-partition writer must not derive its write location from a
# READ resolver.
# ===========================================================================
#
# research D18 / R19. The defect class: a writer asks ``read_dir(<COORD kind>)``
# (or ``resolve_status_surface`` ...) "where does this live?" and writes there.
# A read resolver is allowed to FALL BACK (to the PRIMARY partition, to a
# stale path); a writer must not. The sanctioned accessor is
# ``placement_seam(...).write_dir(kind)`` (``contracts/write-location-accessor.md``:
# "``read_dir`` is never a write location for a COORD kind; the FR-014 gate
# enforces that").
#
# This extends the gate family above -- it is NOT a new gate file (FR-014,
# squad finding P10). Non-vacuity (charter Standing Order 5): a concrete census
# FLOOR whose every pair must resolve to a live definition, a planted-mutation
# bite test, and a shrink-only allow-list that starts EMPTY (operator ruling
# Q4) and whose cap of 0 lives in ``_baselines.yaml``.
#
# Legacy root-staging copy (post-tasks squad P-M2): the commit router's legacy
# ``shutil.copy2`` root-staging copy is a recorded in-mission closeout fold
# (tasks.md "Closeout items"), not an allow-list entry here. This comment marks
# where the class is guarded so the follow-up stays visible; do NOT allow-list it.

#: The census: one ``(rel_path_from_repo_root, dotted_qualname)`` pair per COORD
#: writer function (research D18, RE-DERIVED against the merged code: several
#: WPs renamed or extracted functions). Each names the function that NOW holds
#: the write -- never a read helper (reads legitimately keep the read resolver,
#: C-002). A stale qualname reds ``test_coord_writer_census_floor_is_live``;
#: the remedy is to re-point the pair at the function that holds the write now,
#: never to delete it to green.
#:
#: Re-pointed since D18 was written (``_PRE_SPLIT_QUALNAMES`` below records the
#: mapping back to the names D18 used, for the red-at-base proof):
#:
#: * ``decisions/service.py::_mission_dir`` -> ``_write_mission_dir`` (WP09 split
#:   the READ-side ``_mission_dir`` probe from the write path).
#: * ``review/cycle.py::_review_cycle_wp_dir`` -> ``_review_cycle_write_location``
#:   (WP08: ``_review_cycle_wp_dir`` is now the READ-mode resolver).
#: * ``tasks/issue_matrix.py::scaffold_issue_matrix`` -> ``write_issue_matrix``
#:   (WP10: the write moved into the ``write_dir`` thunk; the scaffold keeps
#:   only its idempotency existence probe).
#: * ``acceptance_verdict.py::_matrix_read_dir`` -> ``_matrix_write_dir``.
#: * ``retrospect.py::_canonical_events_path`` -> ``_canonical_events_write_path``
#:   and ``agent_retrospect.py::_canonical_events_dir`` ->
#:   ``_canonical_events_write_dir`` (WP14 split the read helpers from the
#:   append/commit write path).
#: * ``status_transition.py::_coord_feature_dir`` (retired by WP07) -> the two
#:   functions that now hold the COORD status write: ``_resolve_fallback_coord_worktree``
#:   and ``_emit_on_coord_then_commit``.
#: * ``mission_finalize.py::_emit_local_canonical_events`` ->
#:   ``mission_finalize_bootstrap.py`` (#5627 moved the function verbatim into
#:   the bootstrap phase module).
_COORD_WRITER_CENSUS: tuple[tuple[str, str], ...] = (
    ("src/specify_cli/decisions/emit.py", "_mission_dir"),
    ("src/specify_cli/decisions/service.py", "_write_mission_dir"),
    ("src/specify_cli/agent_tasks_ports.py", "RealCoordCommitRouter.feature_write_dir"),
    ("src/specify_cli/cli/commands/agent/tasks_mark_status.py", "_ms_resolve_read_dir"),
    ("src/specify_cli/cli/commands/agent/tasks_finalize.py", "_ft_apply_writes"),
    ("src/specify_cli/cli/commands/agent/mission_finalize_bootstrap.py", "_emit_local_canonical_events"),
    ("src/specify_cli/review/cycle.py", "_review_cycle_write_location"),
    ("src/specify_cli/retrospective/tracer_writer.py", "_local_staging_path"),
    ("src/specify_cli/tasks/issue_matrix.py", "write_issue_matrix"),
    ("src/specify_cli/cli/commands/agent/acceptance_verdict.py", "_matrix_write_dir"),
    ("src/specify_cli/coordination/status_transition.py", "_resolve_fallback_coord_worktree"),
    ("src/specify_cli/coordination/status_transition.py", "_emit_on_coord_then_commit"),
    ("src/specify_cli/coordination/transaction.py", "BookkeepingTransaction._acquire_locked"),
    ("src/specify_cli/coordination/transaction.py", "BookkeepingTransaction.preflight_refusal"),
    # #2560: re-pointed; ``_wrap_with_decision_git_log`` moved verbatim to the decision-log seam.
    ("src/runtime/next/runtime_bridge_decision_log.py", "_wrap_with_decision_git_log"),
    ("src/specify_cli/cli/commands/accept.py", "_coord_status_feature_dir"),
    ("src/specify_cli/cli/commands/retrospect.py", "_canonical_events_write_path"),
    ("src/specify_cli/cli/commands/agent_retrospect.py", "_canonical_events_write_dir"),
    # #5634: re-pointed; ``_emit_create_events`` moved verbatim to the events leaf.
    ("src/specify_cli/core/mission_creation_events.py", "_emit_create_events"),
    # Operator ruling Q4 / research D21: the consolidation and ``materialize``
    # sites were MIGRATED (WP18), not allow-listed.
    ("src/specify_cli/consolidation/phase_advance.py", "_phase_baseline_and_surface"),
    ("src/specify_cli/consolidation/executor.py", "_run_lane_based_consolidation"),
    ("src/specify_cli/cli/commands/materialize.py", "_resolve_selected_dir"),
    ("src/specify_cli/cli/commands/materialize.py", "materialize"),
    ("src/specify_cli/lanes/recovery.py", "reconcile_status"),
)

#: For the red-at-base proof ONLY (T107): the qualname(s) a census pair had at
#: ``ecb5dd914a`` (research D18's own names), before the Mission split each READ
#: helper from its write-side successor. When ``SPEC_KITTY_GATE_SCAN_ROOT``
#: points at the base tree, an absent census pair falls back to these so the
#: pre-fix offenders (e.g. ``decisions/service.py::_mission_dir``) are scanned
#: instead of being reported "absent at base". Never consulted against this
#: repository.
_PRE_SPLIT_QUALNAMES: dict[tuple[str, str], tuple[str, ...]] = {
    ("src/specify_cli/decisions/service.py", "_write_mission_dir"): ("_mission_dir",),
    ("src/specify_cli/review/cycle.py", "_review_cycle_write_location"): ("_review_cycle_wp_dir",),
    ("src/specify_cli/tasks/issue_matrix.py", "write_issue_matrix"): ("scaffold_issue_matrix",),
    ("src/specify_cli/cli/commands/agent/acceptance_verdict.py", "_matrix_write_dir"): ("_matrix_read_dir",),
    ("src/specify_cli/cli/commands/retrospect.py", "_canonical_events_write_path"): ("_canonical_events_path",),
    ("src/specify_cli/cli/commands/agent_retrospect.py", "_canonical_events_write_dir"): ("_canonical_events_dir",),
    ("src/specify_cli/coordination/status_transition.py", "_resolve_fallback_coord_worktree"): ("_coord_feature_dir",),
    ("src/specify_cli/coordination/status_transition.py", "_emit_on_coord_then_commit"): ("_coord_feature_dir",),
}

#: research D18 "Floor assertion": at least this many scanned writer functions.
_COORD_WRITER_FLOOR = 22

#: ``MissionArtifactKind`` members that live on the COORD partition. A
#: ``read_dir(PRIMARY_METADATA)`` in a writer is the ledger/planning PRIMARY
#: read and is NOT flagged.
_COORD_ARTIFACT_KIND_NAMES: frozenset[str] = frozenset(
    {
        "STATUS_STATE",
        "DECISION_LOG",
        "TRACER_FILE",
        "REVIEW_CYCLE",
        "ISSUE_MATRIX",
        "ACCEPTANCE_MATRIX",
    }
)

#: Read resolvers that must never appear in a COORD writer's body (research D18
#: "Forbidden tokens"). ``read_dir`` is handled separately because it is only
#: forbidden with a COORD-kind argument.
_FORBIDDEN_READ_RESOLVER_CALLEES: frozenset[str] = frozenset(
    {
        "read_dir_for",
        "candidate_feature_dir_for_mission",
        "resolve_feature_dir_for_mission",
        "resolve_status_surface",
        "resolve_status_surface_with_anchor",
        "coord_read_dir_for",
    }
)

_READ_DIR_CALLEE = "read_dir"
_KITTY_SPECS_DIR_NAME = "KITTY_SPECS_DIR"
_WORKTREE_OPERAND_MARKER = "worktree"
#: The ``callee`` reported for a ``<worktree> / KITTY_SPECS_DIR / ...`` composition.
_KITTY_SPECS_WORKTREE_COMPOSITION = "KITTY_SPECS_DIR / <worktree>"

#: Environment override pointing the census scan at another tree. Used ONLY by
#: hand for the red-at-base proof (T107): it is never a test default, and an
#: unset/blank value always means this repository.
_SCAN_ROOT_ENV = "SPEC_KITTY_GATE_SCAN_ROOT"

#: Shrink-only allow-list for the third grammar. It starts EMPTY (operator
#: ruling Q4: the consolidation executor and ``materialize`` writers migrated
#: instead). Adding an entry is a deliberate scope decision that needs a
#: per-descriptor ``rationale`` AND grows the ``test_no_write_side_rederivation:
#: coord_writer_allowlist`` cap in ``_baselines.yaml`` (currently 0) -- which
#: ``test_ratchet_baselines.py`` reds. A COORD writer that still derives its
#: location from a read resolver is a real finding for the owning WP's lane,
#: not an allow-list candidate.
_COORD_WRITER_ALLOW_LIST_SEED: tuple[ContentDescriptor, ...] = ()

#: Composite key resolved LIVE per seed entry (parallel, order-preserving).
_COORD_WRITER_ALLOW_LIST_KEYS: tuple[CompositeKey, ...] = tuple(
    resolve_descriptor((_REPO_ROOT / descriptor.rel_path).read_text(encoding="utf-8"), descriptor) for descriptor in _COORD_WRITER_ALLOW_LIST_SEED
)

_COORD_WRITER_ALLOW_LIST: frozenset[CompositeKey] = frozenset(_COORD_WRITER_ALLOW_LIST_KEYS)


@dataclass(frozen=True)
class _CoordWriterFinding:
    """One read-resolver use inside a census writer function."""

    rel_path: str
    qualname: str
    lineno: int
    callee: str
    source: str

    def as_allow_key(self) -> CompositeKey:
        """The drift-proof ``(rel_path, qualname, token_line)`` composite allow-list key."""
        enclosing, token_line = composite_key(self.source, self.lineno)
        return (self.rel_path, enclosing, token_line)

    def describe(self) -> str:
        return f"{self.rel_path}::{self.qualname}:{self.lineno} {self.callee}"


@dataclass(frozen=True)
class _CensusScan:
    """The result of scanning a census: findings plus the pairs that did not resolve."""

    findings: list[_CoordWriterFinding]
    absent: list[tuple[str, str]]


def _gate_scan_root(environ: Mapping[str, str] | None = None) -> Path:
    """The tree the census is scanned in: ``_REPO_ROOT`` unless the override is set.

    ``SPEC_KITTY_GATE_SCAN_ROOT`` exists for the manual red-at-base proof only.
    Blank or whitespace-only means "not set"; a value that is not a directory
    fails loudly rather than scanning nothing.
    """
    raw = (os.environ if environ is None else environ).get(_SCAN_ROOT_ENV, "").strip()
    if not raw:
        return _REPO_ROOT
    root = Path(raw).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"{_SCAN_ROOT_ENV}={raw!r} is not a directory")
    return root


FunctionNode = ast.FunctionDef | ast.AsyncFunctionDef


def _find_function(tree: ast.Module, qualname: str) -> FunctionNode | None:
    """The single function a dotted ``qualname`` names, or ``None``.

    Walks class bodies for each dotted owner (``Class.method``). Zero matches
    and more than one match (a redefinition) both return ``None``: the census
    requires each pair to resolve to exactly one live definition.
    """
    *owners, name = qualname.split(".")
    body: list[ast.stmt] = tree.body
    for owner in owners:
        classes = [node for node in body if isinstance(node, ast.ClassDef) and node.name == owner]
        if len(classes) != 1:
            return None
        body = classes[0].body
    functions = [node for node in body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name]
    return functions[0] if len(functions) == 1 else None


def _artifact_kind_member(call: ast.Call) -> str | None:
    """The ``MissionArtifactKind`` member a ``read_dir(...)`` call names, if syntactically visible.

    The kind is the first positional argument or the ``kind=`` keyword; both
    ``MissionArtifactKind.X`` (attribute) and a bare ``X`` name resolve. A kind
    held in a variable is invisible to this syntactic proxy and is not flagged.
    """
    argument: ast.expr | None = call.args[0] if call.args else None
    if argument is None:
        argument = next((kw.value for kw in call.keywords if kw.arg == "kind"), None)
    if isinstance(argument, ast.Attribute):
        return argument.attr
    if isinstance(argument, ast.Name):
        return argument.id
    return None


def _classify_call(call: ast.Call) -> str | None:
    """The reported callee when *call* is a forbidden read-resolver use, else ``None``."""
    callee = _checkout_grammar_callee_name(call)
    if callee in _FORBIDDEN_READ_RESOLVER_CALLEES:
        return callee
    if callee == _READ_DIR_CALLEE:
        member = _artifact_kind_member(call)
        if member in _COORD_ARTIFACT_KIND_NAMES:
            return f"{_READ_DIR_CALLEE}({member})"
    return None


def _div_operands(node: ast.expr) -> list[ast.expr]:
    """Flatten a left-leaning ``a / b / c`` path chain into its operands."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        return _div_operands(node.left) + _div_operands(node.right)
    return [node]


def _operand_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None


def _composes_kitty_specs_onto_worktree(node: ast.BinOp) -> bool:
    """True for a ``/`` chain holding ``KITTY_SPECS_DIR`` AND a worktree-named operand.

    The heuristic is deliberately NARROW (it is scoped to the census functions
    only): the chain must contain the ``KITTY_SPECS_DIR`` name and a ``Name`` or
    ``Attribute`` operand whose identifier contains ``worktree`` (e.g.
    ``coord_worktree``, ``self.worktree_path``). ``primary_root / KITTY_SPECS_DIR``
    is the legitimate PRIMARY composition and is not flagged.
    """
    if not isinstance(node.op, ast.Div):
        return False
    names = [name for name in map(_operand_name, _div_operands(node)) if name]
    return _KITTY_SPECS_DIR_NAME in names and any(_WORKTREE_OPERAND_MARKER in name.lower() for name in names)


def _classify_node(node: ast.AST) -> str | None:
    if isinstance(node, ast.Call):
        return _classify_call(node)
    if isinstance(node, ast.BinOp) and _composes_kitty_specs_onto_worktree(node):
        return _KITTY_SPECS_WORKTREE_COMPOSITION
    return None


def _scan_function(function: FunctionNode, source: str, rel_path: str, qualname: str) -> list[_CoordWriterFinding]:
    """Every forbidden read-resolver use in *function*'s body, nested defs included.

    ``a / KITTY_SPECS_DIR / c`` parses as nested ``BinOp`` nodes that share one
    start position, so findings are de-duplicated on ``(line, column, callee)``.
    """
    seen: set[tuple[int, int, str]] = set()
    findings: list[_CoordWriterFinding] = []
    for node in ast.walk(function):
        callee = _classify_node(node)
        lineno = getattr(node, "lineno", None)
        if callee is None or lineno is None:
            continue
        key = (lineno, getattr(node, "col_offset", 0), callee)
        if key in seen:
            continue
        seen.add(key)
        findings.append(_CoordWriterFinding(rel_path, qualname, lineno, callee, source))
    return sorted(findings, key=lambda finding: (finding.lineno, finding.callee))


def _scan_coord_writer(source: str, rel_path: str, qualname: str) -> list[_CoordWriterFinding]:
    """Parse *source* and scan the one function *qualname* names (``[]`` if it is absent)."""
    tree = parse_source(source, display=rel_path)
    function = _find_function(tree, qualname)
    if function is None:
        return []
    return _scan_function(function, source, rel_path, qualname)


def _load_census_module(repo_root: Path, rel_path: str) -> tuple[str, ast.Module] | None:
    """The ``(source, tree)`` of a census file under *repo_root*, or ``None`` when it is absent."""
    file_path = repo_root / rel_path
    if not file_path.is_file():
        return None
    text = read_source(file_path)
    return text, parse_source(text, display=rel_path)


def _resolve_census_function(tree: ast.Module, pair: tuple[str, str], fallbacks: Mapping[tuple[str, str], tuple[str, ...]]) -> tuple[str, FunctionNode] | None:
    """The ``(qualname, function)`` a census pair resolves to, trying its fallbacks in order."""
    for qualname in (pair[1], *fallbacks.get(pair, ())):
        function = _find_function(tree, qualname)
        if function is not None:
            return qualname, function
    return None


def _scan_census(
    repo_root: Path,
    census: tuple[tuple[str, str], ...] = _COORD_WRITER_CENSUS,
    *,
    fallbacks: Mapping[tuple[str, str], tuple[str, ...]] | None = None,
) -> _CensusScan:
    """Scan every census pair under *repo_root*.

    A pair whose file or qualname does not resolve is reported in ``absent``
    rather than raising, so the red-at-base proof can run against a revision
    that predates some census functions. *fallbacks* (the base proof passes
    ``_PRE_SPLIT_QUALNAMES``) names alternative qualnames to try for an absent
    pair; the default is none, so the live gate has no such escape.
    """
    findings: list[_CoordWriterFinding] = []
    absent: list[tuple[str, str]] = []
    modules: dict[str, tuple[str, ast.Module] | None] = {}
    for pair in census:
        rel_path = pair[0]
        if rel_path not in modules:
            modules[rel_path] = _load_census_module(repo_root, rel_path)
        loaded = modules[rel_path]
        resolved = _resolve_census_function(loaded[1], pair, fallbacks or {}) if loaded is not None else None
        if loaded is None or resolved is None:
            absent.append(pair)
            continue
        qualname, function = resolved
        findings.extend(_scan_function(function, loaded[0], rel_path, qualname))
    return _CensusScan(findings, absent)


def test_coord_writers_do_not_derive_write_location_from_read_resolver() -> None:
    """FR-014 / R19: no census COORD writer derives its write location from a read resolver.

    Run with ``SPEC_KITTY_GATE_SCAN_ROOT=<tree>`` to scan another revision (the
    T107 red-at-base proof); census pairs absent from that tree are reported,
    not fatal.
    """
    root = _gate_scan_root()
    overridden = root != _REPO_ROOT
    scan = _scan_census(root, fallbacks=_PRE_SPLIT_QUALNAMES if overridden else None)
    if overridden:
        print(f"scan root override {root}: scanned {len(_COORD_WRITER_CENSUS) - len(scan.absent)} writers; absent at base: {scan.absent!r}")
    offenders = [finding for finding in scan.findings if finding.as_allow_key() not in _COORD_WRITER_ALLOW_LIST]
    assert not offenders, (
        "A COORD-partition writer derives its write location from a READ resolver "
        "(FR-014 / contracts/write-location-accessor.md: read_dir is never a write "
        "location for a COORD kind). Route the write through "
        "placement_seam(...).write_dir(kind) and use WriteLocation.path / "
        ".surface_root. Offenders:\n" + "\n".join(finding.describe() for finding in offenders)
    )


def test_coord_writer_census_floor_is_live() -> None:
    """Non-vacuity: the census meets its floor and every pair resolves to a live definition."""
    if _gate_scan_root() != _REPO_ROOT:
        pytest.skip(f"{_SCAN_ROOT_ENV} override: the red-at-base proof does not assert the floor")
    assert len(set(_COORD_WRITER_CENSUS)) == len(_COORD_WRITER_CENSUS), "duplicate census pairs would inflate the floor"
    assert len(_COORD_WRITER_CENSUS) >= _COORD_WRITER_FLOOR, (
        f"the COORD writer census holds {len(_COORD_WRITER_CENSUS)} pairs; the floor is {_COORD_WRITER_FLOOR} (research D18)"
    )
    absent = _scan_census(_REPO_ROOT).absent
    assert not absent, (
        "Stale COORD writer census pair(s) (no live definition): "
        + ", ".join(f"{rel_path}::{qualname}" for rel_path, qualname in absent)
        + ". Re-point the census at the function that now holds the write; never delete it to green."
    )


def test_census_names_the_real_base_offenders() -> None:
    """The red-at-base proof depends on the two real offenders staying reachable (research D18).

    ``decisions/emit.py::_mission_dir`` is census-named as-is; the base-revision
    ``decisions/service.py::_mission_dir`` is reached through its write-side
    successor ``_write_mission_dir`` via ``_PRE_SPLIT_QUALNAMES``.
    """
    assert ("src/specify_cli/decisions/emit.py", "_mission_dir") in _COORD_WRITER_CENSUS
    service_pair = ("src/specify_cli/decisions/service.py", "_write_mission_dir")
    assert service_pair in _COORD_WRITER_CENSUS
    assert "_mission_dir" in _PRE_SPLIT_QUALNAMES[service_pair]


# ---------------------------------------------------------------------------
# Scan-root override, qualname lookup, census scanning (NFR-003: every helper
# and branch has a focused test).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("environ", [{}, {_SCAN_ROOT_ENV: ""}, {_SCAN_ROOT_ENV: "   "}])
def test_gate_scan_root_defaults_to_this_repository(environ: dict[str, str]) -> None:
    assert _gate_scan_root(environ) == _REPO_ROOT


def test_gate_scan_root_honours_a_directory_override(tmp_path: Path) -> None:
    assert _gate_scan_root({_SCAN_ROOT_ENV: f"  {tmp_path}  "}) == tmp_path.resolve()


def test_gate_scan_root_refuses_a_non_directory(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    with pytest.raises(ValueError, match="is not a directory"):
        _gate_scan_root({_SCAN_ROOT_ENV: str(missing)})


_LOOKUP_SOURCE = (
    "def top():\n"
    "    pass\n"
    "async def coroutine():\n"
    "    pass\n"
    "class Owner:\n"
    "    def method(self):\n"
    "        pass\n"
    "    class Inner:\n"
    "        def deep(self):\n"
    "            pass\n"
    "def twice():\n"
    "    pass\n"
    "def twice():\n"
    "    pass\n"
)


@pytest.mark.parametrize(
    ("qualname", "resolves"),
    [
        ("top", True),
        ("coroutine", True),
        ("Owner.method", True),
        ("Owner.Inner.deep", True),
        ("missing", False),
        ("Owner.missing", False),
        ("Missing.method", False),
        ("twice", False),  # a redefinition is not "exactly one live definition"
    ],
)
def test_find_function_resolves_only_a_single_live_definition(qualname: str, resolves: bool) -> None:
    tree = parse_source(_LOOKUP_SOURCE, display="<lookup>")
    assert (_find_function(tree, qualname) is not None) is resolves


def test_scan_census_reports_findings_and_absent_pairs_under_an_injected_root(tmp_path: Path) -> None:
    module = tmp_path / "pkg" / "writer.py"
    module.parent.mkdir()
    module.write_text(
        "def _writer(seam):\n"
        "    return seam.read_dir(MissionArtifactKind.STATUS_STATE)\n"
        "def _clean(seam):\n"
        "    return seam.write_dir(MissionArtifactKind.STATUS_STATE).path\n",
        encoding="utf-8",
    )
    census = (
        ("pkg/writer.py", "_writer"),
        ("pkg/writer.py", "_clean"),
        ("pkg/writer.py", "_gone"),
        ("pkg/absent.py", "_writer"),
    )
    scan = _scan_census(tmp_path, census)
    assert [(f.rel_path, f.qualname, f.callee) for f in scan.findings] == [("pkg/writer.py", "_writer", "read_dir(STATUS_STATE)")]
    assert scan.absent == [("pkg/writer.py", "_gone"), ("pkg/absent.py", "_writer")]


def test_scan_census_falls_back_to_the_pre_split_qualname_only_when_asked(tmp_path: Path) -> None:
    """The base-proof fallback finds the pre-split offender; the live gate (no fallbacks) reports it absent."""
    module = tmp_path / "pkg" / "svc.py"
    module.parent.mkdir()
    module.write_text(
        "def _mission_dir(seam):\n    return seam.read_dir(MissionArtifactKind.STATUS_STATE)\n",
        encoding="utf-8",
    )
    pair = ("pkg/svc.py", "_write_mission_dir")
    fallbacks = {pair: ("_gone_too", "_mission_dir")}

    without = _scan_census(tmp_path, (pair,))
    assert without.findings == []
    assert without.absent == [pair]

    with_fallback = _scan_census(tmp_path, (pair,), fallbacks=fallbacks)
    assert [(f.qualname, f.callee) for f in with_fallback.findings] == [("_mission_dir", "read_dir(STATUS_STATE)")]
    assert with_fallback.absent == []


def test_pre_split_qualnames_only_re_point_live_census_pairs() -> None:
    """Every fallback key is a live census pair, so the table cannot rot into dead entries."""
    for pair in _PRE_SPLIT_QUALNAMES:
        assert pair in _COORD_WRITER_CENSUS


# ---------------------------------------------------------------------------
# Empty shrink-only allow-list and its stale-entry twin (T108).
# ---------------------------------------------------------------------------


def test_coord_writer_allow_list_entries_are_still_live() -> None:
    """Staleness twin: every seeded descriptor still resolves to its live finding.

    The seed starts empty, so this iterates zero times today; the twin's own
    behaviour is proven non-vacuous by the two tests below.
    """
    for descriptor, seeded_key in zip(_COORD_WRITER_ALLOW_LIST_SEED, _COORD_WRITER_ALLOW_LIST_KEYS, strict=True):
        source = (_REPO_ROOT / descriptor.rel_path).read_text(encoding="utf-8")
        assert descriptor_still_live(source, descriptor, seeded_key), (
            f"{descriptor.rel_path} ({descriptor.qualname}) no longer resolves to its seeded live COORD-writer "
            "finding -- the site was migrated to write_dir (or removed); DELETE the now-stale entry (shrink-only)."
        )


_TWIN_FIXTURE_SOURCE = "def _synthetic_writer(seam):\n    return seam.read_dir(MissionArtifactKind.STATUS_STATE)\n"
_TWIN_FIXTURE_DESCRIPTOR = ContentDescriptor(
    rel_path="src/specify_cli/synthetic.py",
    qualname="_synthetic_writer",
    token_substring="read_dir ( MissionArtifactKind . STATUS_STATE )",
    occurrence=None,
    rationale="twin-guard self-test fixture; never a real allow-list entry",
)


def test_coord_writer_twin_guard_bites_when_the_allowed_site_is_migrated_away() -> None:
    """The twin is not vacuous: a descriptor whose site no longer exists is reported stale."""
    seeded_key = resolve_descriptor(_TWIN_FIXTURE_SOURCE, _TWIN_FIXTURE_DESCRIPTOR)
    assert descriptor_still_live(_TWIN_FIXTURE_SOURCE, _TWIN_FIXTURE_DESCRIPTOR, seeded_key)

    migrated = "def _synthetic_writer(seam):\n    return seam.write_dir(MissionArtifactKind.STATUS_STATE).path\n"
    assert not descriptor_still_live(migrated, _TWIN_FIXTURE_DESCRIPTOR, seeded_key)


def test_coord_writer_twin_guard_bites_on_a_token_that_does_not_exist() -> None:
    nonexistent = _TWIN_FIXTURE_DESCRIPTOR._replace(token_substring="a_token_that_exists_nowhere")
    seeded_key = ("src/specify_cli/synthetic.py", "_synthetic_writer", "a_token_that_exists_nowhere")
    assert not descriptor_still_live(_TWIN_FIXTURE_SOURCE, nonexistent, seeded_key)


# ---------------------------------------------------------------------------
# The planted-mutation bite test (T109, R19) and its negative controls.
# ---------------------------------------------------------------------------

_SYNTHETIC_REL_PATH = "src/specify_cli/synthetic.py"


def _synthetic_writer_source(expression: str) -> str:
    return f"def _synthetic_writer(seam, repo_root, slug, worktree):\n    return {expression}\n"


def _scan_synthetic(source: str) -> list[_CoordWriterFinding]:
    return _scan_coord_writer(source, _SYNTHETIC_REL_PATH, "_synthetic_writer")


@pytest.mark.parametrize(
    ("planted", "expected_callee"),
    [
        ("seam.read_dir(MissionArtifactKind.STATUS_STATE)", "read_dir(STATUS_STATE)"),
        ("seam.read_dir(kind=MissionArtifactKind.DECISION_LOG)", "read_dir(DECISION_LOG)"),
        ("seam.read_dir(REVIEW_CYCLE)", "read_dir(REVIEW_CYCLE)"),
        ("seam.read_dir(MissionArtifactKind.ISSUE_MATRIX)", "read_dir(ISSUE_MATRIX)"),
        ("seam.read_dir(MissionArtifactKind.ACCEPTANCE_MATRIX)", "read_dir(ACCEPTANCE_MATRIX)"),
        ("placement_seam(repo_root, slug).read_dir(MissionArtifactKind.TRACER_FILE)", "read_dir(TRACER_FILE)"),
        ("read_dir_for(repo_root, slug)", "read_dir_for"),
        ("resolve_feature_dir_for_mission(repo_root, slug)", "resolve_feature_dir_for_mission"),
        ("candidate_feature_dir_for_mission(repo_root, slug)", "candidate_feature_dir_for_mission"),
        ("resolve_status_surface(repo_root, slug)", "resolve_status_surface"),
        ("resolve_status_surface_with_anchor(repo_root, slug)", "resolve_status_surface_with_anchor"),
        ("coord_read_dir_for(repo_root, slug)", "coord_read_dir_for"),
        ("worktree / KITTY_SPECS_DIR / slug", _KITTY_SPECS_WORKTREE_COMPOSITION),
        ("self.coord_worktree / KITTY_SPECS_DIR / slug", _KITTY_SPECS_WORKTREE_COMPOSITION),
    ],
)
def test_coord_writer_grammar_bites_on_planted_read_resolver(planted: str, expected_callee: str) -> None:
    """A read resolver planted in a synthetic writer REDS the scan (R19 self-mutation)."""
    callees = [finding.callee for finding in _scan_synthetic(_synthetic_writer_source(planted))]
    assert expected_callee in callees, f"grammar failed to flag planted {planted!r}; got {callees}"


def test_coord_writer_grammar_flags_a_plant_inside_a_nested_function() -> None:
    source = "def _synthetic_writer(seam):\n    def _inner():\n        return seam.read_dir(MissionArtifactKind.STATUS_STATE)\n    return _inner()\n"
    assert [finding.callee for finding in _scan_synthetic(source)] == ["read_dir(STATUS_STATE)"]


def test_coord_writer_grammar_reports_a_composition_once() -> None:
    """``a / KITTY_SPECS_DIR / b`` is nested ``BinOp`` nodes but ONE finding."""
    findings = _scan_synthetic(_synthetic_writer_source("worktree / KITTY_SPECS_DIR / slug / 'tasks'"))
    assert [finding.callee for finding in findings] == [_KITTY_SPECS_WORKTREE_COMPOSITION]


def test_coord_writer_grammar_is_driven_by_the_forbidden_callee_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """Self-mutation: emptying the forbidden-callee set silences the plant, so the bite test does bite."""
    source = _synthetic_writer_source("resolve_status_surface(repo_root, slug)")
    assert _scan_synthetic(source)
    monkeypatch.setattr(
        "tests.architectural.test_no_write_side_rederivation._FORBIDDEN_READ_RESOLVER_CALLEES",
        frozenset(),
    )
    assert _scan_synthetic(source) == []


@pytest.mark.parametrize(
    "control",
    [
        # The sanctioned accessor: the gate must not ban the fix.
        "seam.write_dir(MissionArtifactKind.STATUS_STATE).path",
        "placement_seam(repo_root, slug).write_dir(kind=MissionArtifactKind.TRACER_FILE)",
        # The PRIMARY read is legitimate in a writer.
        "seam.read_dir(MissionArtifactKind.PRIMARY_METADATA)",
        "seam.read_dir(kind=MissionArtifactKind.PRIMARY_METADATA)",
        # A kind held in a variable is invisible to the syntactic proxy.
        "seam.read_dir(kind)",
        # PRIMARY composition: no worktree-named operand.
        "repo_root / KITTY_SPECS_DIR / slug",
        # A worktree operand without KITTY_SPECS_DIR.
        "worktree / 'status.events.jsonl'",
    ],
)
def test_coord_writer_grammar_does_not_flag_sanctioned_forms(control: str) -> None:
    assert _scan_synthetic(_synthetic_writer_source(control)) == []


def test_coord_writer_grammar_ignores_prose_quoting_a_read_resolver() -> None:
    """A docstring or comment is a ``Constant``, never a ``Call``: quoting the pattern is inert."""
    source = (
        "def _synthetic_writer(seam):\n"
        '    """Formerly seam.read_dir(MissionArtifactKind.STATUS_STATE) and resolve_status_surface(...)."""\n'
        "    # historical: worktree / KITTY_SPECS_DIR / slug and coord_read_dir_for(repo_root, slug)\n"
        "    return seam.write_dir(MissionArtifactKind.STATUS_STATE).path\n"
    )
    assert _scan_synthetic(source) == []


def test_coord_writer_grammar_is_scoped_to_the_census_function() -> None:
    """A sibling READ helper may keep the read resolver (C-002); only the named writer is scanned."""
    source = (
        "def _reader(seam):\n"
        "    return seam.read_dir(MissionArtifactKind.STATUS_STATE)\n"
        "def _synthetic_writer(seam):\n"
        "    return seam.write_dir(MissionArtifactKind.STATUS_STATE).path\n"
    )
    assert _scan_synthetic(source) == []


def test_coord_writer_allow_list_filters_only_a_matching_composite_key() -> None:
    """An allow-list entry absorbs exactly its own finding, never a sibling's."""
    source = (
        "def _synthetic_writer(seam):\n"
        "    first = seam.read_dir(MissionArtifactKind.STATUS_STATE)\n"
        "    second = seam.read_dir(MissionArtifactKind.TRACER_FILE)\n"
        "    return first, second\n"
    )
    findings = _scan_synthetic(source)
    assert len(findings) == 2
    keys = {finding.as_allow_key() for finding in findings}
    assert len(keys) == 2
    assert findings[0].as_allow_key()[0] == _SYNTHETIC_REL_PATH


# ---------------------------------------------------------------------------
# The widened ``root_walk`` scope: ``.parent.parent`` from a WriteLocation.
# ---------------------------------------------------------------------------


def test_write_dir_consumer_modules_are_all_in_the_root_walk_scope() -> None:
    """Every ``write_dir`` consumer module is scanned by the first grammar's ``root_walk`` kind."""
    assert len(_WRITE_DIR_CONSUMER_MODULES) >= 23
    for module in _WRITE_DIR_CONSUMER_MODULES:
        assert module.is_file(), f"write_dir consumer module missing: {module}"
        assert module in _ADOPTED_MODULES, f"{module} is not scanned for root_walk re-derivation"


def test_root_walk_scope_keeps_the_retired_checkout_allowlist_frozen() -> None:
    """Widening the first grammar's scope must not rewrite the historical 17-module record."""
    assert len(_RETIRED_CHECKOUT_GRAMMAR_ALLOWLIST) == 17
    assert _placement_rel_path(_SRC / "decisions" / "emit.py") not in _RETIRED_CHECKOUT_GRAMMAR_ALLOWLIST


@pytest.mark.parametrize(
    "planted",
    [
        "    root = seam.write_dir(MissionArtifactKind.STATUS_STATE).path.parent.parent\n",
        "    location = seam.write_dir(MissionArtifactKind.TRACER_FILE)\n    root = location.path.parent.parent\n",
    ],
)
def test_root_walk_bites_on_parent_parent_from_a_write_location(planted: str) -> None:
    """Guessing the checkout root from a ``WriteLocation`` path REDS; ``surface_root`` does not."""
    source = f"def _synthetic_writer(seam):\n{planted}    return root\n"
    assert "root_walk" in {finding.kind for finding in _scan_source(source, _SRC / "decisions" / "emit.py")}


def test_root_walk_does_not_flag_the_checkout_root_accessor() -> None:
    source = "def _synthetic_writer(seam):\n    return seam.write_dir(MissionArtifactKind.STATUS_STATE).surface_root\n"
    assert _scan_source(source, _SRC / "decisions" / "emit.py") == []
