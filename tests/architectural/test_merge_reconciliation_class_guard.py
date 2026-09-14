"""WP05 — class-closing guards for #2709 (FR-008 / SC-005).

Two NON-VACUOUS architectural lints that close the "merge silently overwrites
target-newer canonical state" defect class *by construction*, covering BOTH loss
mechanisms — NOT a re-run of the WP01 outcome repro. Precedent for the AST /
per-registry lint home: ``tests/architectural/test_merge_pipeline_ratchets.py``.

* **T012 — no-blind-copy AST lint** over the ``merge/`` projection path. The
  FR-005 regression is ``merge/bookkeeping_projection.py`` blind-``write_bytes``-ing
  a *foreign* status/meta/trace source straight onto the *authoritative*
  target-surface artifact (event log / ``meta.json`` / ``traces/*.md``) instead of
  reconciling it (``_union_event_logs`` / rematerialize). The lint fires on that
  exact shape and stays silent on the fixed tree — including the deliberately
  *derived* ``status.json`` copy (line ``write_bytes(source_status_bytes)``), which
  is a rematerialized/degenerate view, not an authoritative both-sides-divergent
  artifact.

* **T013 — driver-registry-completeness lint** (the primary #2709 ``-X theirs``
  vector, blind to the projection lint). Two independent assertions:
    - **sync**: every driver DECLARED in the in-code registry
      (``specify_cli.lanes.merge._MERGE_DRIVERS``) is REGISTERED in root
      ``.gitattributes`` and vice-versa — catches *dropping* an existing
      ``.gitattributes`` driver line;
    - **completeness (non-tautology)**: every both-sides-divergent canonical
      ``kitty-specs/**`` artifact enumerated from the INDEPENDENT
      mission-artifact-kind registry (``mission_runtime.artifacts`` —
      ``MissionArtifactKind`` + ``_MISSION_FILE_KIND_BY_BASENAME`` /
      ``_COORD_RESIDUE_DIRS`` / ``kind_for_mission_file``), NOT enumerated from
      ``.gitattributes`` itself, carries a registered merge driver. Fail-closed: a
      *future* net-new canonical artifact re-inherits #2709 via ``-X theirs``
      unless it is a driver or is explicitly classified as non-divergent below.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

import specify_cli
from mission_runtime.artifacts import (
    _COORD_RESIDUE_DIRS,
    _MISSION_FILE_KIND_BY_BASENAME,
    _PLACEMENT_ARTIFACT_KINDS,
    MissionArtifactKind,
    kind_for_mission_file,
)
from specify_cli.cli.commands import init as _init_command
from specify_cli.lanes.merge import _MERGE_DRIVERS
from specify_cli.upgrade.migrations import (
    m_3_1_1_event_log_merge_driver as _event_log_migration,
)
from specify_cli.upgrade.migrations import (
    auto_discover_migrations as _auto_discover_migrations,
)
from specify_cli.upgrade.migrations._merge_driver_seeding import (
    MergeDriverSeedingMigration as _MergeDriverSeedingMigration,
)
from specify_cli.upgrade.registry import MigrationRegistry as _MigrationRegistry

pytestmark = [pytest.mark.architectural]

SRC_ROOT = Path(specify_cli.__file__).resolve().parent
REPO_ROOT = SRC_ROOT.parents[1]
MERGE_DIR = SRC_ROOT / "merge"
GITATTRIBUTES = REPO_ROOT / ".gitattributes"

# Authoritative, both-sides-divergent artifact surfaces whose target copy must
# NEVER be blind-overwritten (append-only event log / field-merge ``meta.json`` /
# union ``traces``). A write-receiver variable naming any of these tokens is an
# authoritative-target write. The *derived* ``status.json`` snapshot deliberately
# carries none of these tokens, so its rematerialized/degenerate copy is exempt.
_AUTHORITATIVE_ARTIFACT_TOKENS: tuple[str, ...] = ("events", "meta", "trace")

# A write argument that is one of these is a raw *foreign* read passed straight
# through to the target (a blind copy), rather than a reconciled value.
_RAW_READ_CALLEES: frozenset[str] = frozenset(
    {"_read_optional_bytes", "read_bytes", "read_text"}
)


# ---------------------------------------------------------------------------
# T012 — no-blind-copy of a foreign source onto an authoritative target
# ---------------------------------------------------------------------------


def _merge_sources() -> list[Path]:
    return sorted(MERGE_DIR.rglob("*.py"))


def _receiver_name(node: ast.expr) -> str:
    """Best-effort name of a ``<receiver>.write_bytes(...)`` receiver expression."""
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Name):
        return node.id
    return ""


def _is_authoritative_target_write(call: ast.Call) -> bool:
    """True for ``<...events|meta|trace...>.write_bytes/​write_text(...)`` calls."""
    func = call.func
    if not (isinstance(func, ast.Attribute) and func.attr in {"write_bytes", "write_text"}):
        return False
    receiver = _receiver_name(func.value).lower()
    return any(token in receiver for token in _AUTHORITATIVE_ARTIFACT_TOKENS)


def _arg_is_raw_foreign_read(call: ast.Call) -> bool:
    """True when the write's first positional arg is a raw foreign-source read.

    A ``source_*`` bare name, an inline ``_read_optional_bytes(...)`` call, or an
    inline ``<path>.read_bytes()/​.read_text()`` call passed straight to the write
    is a blind copy. A reconciler call (``_union_event_logs(...)``,
    ``_rematerialize_status_snapshot(...)``, …) is NOT one of these, so reconciled
    writes are permitted.
    """
    if not call.args:
        return False
    arg = call.args[0]
    if isinstance(arg, ast.Name) and "source" in arg.id.lower():
        return True
    if isinstance(arg, ast.Call):
        callee = arg.func
        if isinstance(callee, ast.Name) and callee.id in _RAW_READ_CALLEES:
            return True
        if isinstance(callee, ast.Attribute) and callee.attr in _RAW_READ_CALLEES:
            return True
    return False


def test_no_blind_copy_of_foreign_source_onto_authoritative_target() -> None:
    """SC-005 (FR-005): the ``merge/`` projection path must never blind-copy a
    foreign status/meta/trace source onto the authoritative target artifact —
    it must reconcile (union / field-merge / rematerialize). RED on a synthetic
    ``trusted_target_events_path.write_bytes(source_events_bytes)`` reintroduction."""
    offenders: list[str] = []
    for source in _merge_sources():
        tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
        offenders.extend(
            f"{source.relative_to(SRC_ROOT)}:{node.lineno}"
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and _is_authoritative_target_write(node)
            and _arg_is_raw_foreign_read(node)
        )
    assert not offenders, (
        "Blind copy of a foreign source onto an authoritative both-sides-divergent "
        "target artifact in merge/ (FR-005/#2709 regression) — reconcile via the "
        f"union/field-merge/rematerialize seam instead of write_bytes: {offenders}"
    )


# ---------------------------------------------------------------------------
# T013 — driver-registry completeness (the -X theirs / no-driver vector)
# ---------------------------------------------------------------------------


def _gitattributes_merge_drivers() -> dict[str, str]:
    """Map ``pattern -> driver-key`` for every ``merge=`` line in ``.gitattributes``."""
    drivers: dict[str, str] = {}
    for raw in GITATTRIBUTES.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        if len(fields) < 2:
            continue
        pattern = fields[0]
        for attribute in fields[1:]:
            if attribute.startswith("merge="):
                drivers[pattern] = attribute.split("=", 1)[1]
    return drivers


def test_declared_merge_drivers_are_registered_in_gitattributes() -> None:
    """T013 sync (catches self-mutation (a) — dropping a ``.gitattributes`` line):
    the in-code ``_MERGE_DRIVERS`` registry and root ``.gitattributes`` must agree
    on every custom Spec Kitty merge driver, in both directions (C-006)."""
    registered = _gitattributes_merge_drivers()
    declared = {driver.pattern: driver.config_key for driver in _MERGE_DRIVERS}

    unregistered = [
        f"{pattern} merge={key}"
        for pattern, key in declared.items()
        if registered.get(pattern) != key
    ]
    assert not unregistered, (
        "Merge driver declared in specify_cli.lanes.merge._MERGE_DRIVERS but not "
        f"registered in root .gitattributes (#2709 re-inheritance risk): {unregistered}"
    )

    orphaned = [
        f"{pattern} merge={key}"
        for pattern, key in registered.items()
        if key.startswith("spec-kitty-") and declared.get(pattern) != key
    ]
    assert not orphaned, (
        "Spec Kitty merge driver registered in .gitattributes with no matching "
        f"_MERGE_DRIVERS declaration (drift): {orphaned}"
    )


# Canonical artifacts the mission classifies as NOT both-sides-divergent, so a
# custom reconcile driver is intentionally absent (fail-closed default is: any
# canonical artifact NOT listed here MUST carry a driver). Sourced by writer
# topology / FR-008 loss analysis, NOT from .gitattributes:
#   * human-authored planning SOURCE (registry ``_PRIMARY_ARTIFACT_KINDS``) — the
#     target never independently edits these; ``-X theirs`` keeping the mission
#     copy is the intended #1732 behavior, so no reconcile is needed;
#   * derived / materialized views — regenerated from the event log, so a lost
#     copy is recoverable by re-reduction;
#   * single-writer coordination / terminal artifacts — no both-sides divergence.
_NON_DIVERGENT_CANONICAL_ARTIFACTS: frozenset[str] = frozenset(
    {
        # planning SOURCE
        "spec.md",
        "data-model.md",
        "research.md",
        "plan.md",
        "tasks.md",
        # planning SOURCE (single-writer). #2937 WP06 classified ``wps.yaml`` to
        # the PRIMARY-partition ``TASKS_INDEX`` kind and versions it at
        # finalize-tasks: it is the work-package manifest SOURCE that
        # finalize-tasks authors on the PRIMARY partition and from which
        # ``tasks.md`` is regenerated. The target never independently edits it, so
        # ``-X theirs`` keeping the mission copy is the intended #1732 behavior —
        # no reconcile driver needed (same class as ``tasks.md`` above).
        "wps.yaml",
        # derived / materialized views
        "status.json",
        "lanes.json",
        "acceptance-matrix.json",
        "snapshot-latest.json",
        # single-writer derived baseline (post-merge stale-assertion snapshot,
        # review/baseline.py) — classified WORK_PACKAGE_TASK (PRIMARY partition),
        # written by exactly one path, never both-sides-divergent bookkeeping.
        "baseline-tests.json",
        # single-writer coordination / terminal
        "issue-matrix.md",
        "analysis-report.md",
        "retrospective.yaml",
    }
)


def _canonical_artifact_file_globs() -> dict[str, MissionArtifactKind]:
    """``kitty-specs/**`` file-glob -> kind for every canonical FILE artifact.

    Sourced from the INDEPENDENT mission-artifact-kind registry path maps (NOT from
    ``.gitattributes``), so registering a NEW canonical artifact there trips the
    completeness lint below (non-tautology). Directory kinds (``tasks/``,
    ``checklists/`` — human-authored planning collections) are handled separately.
    """
    return {
        f"kitty-specs/**/{filename}": kind
        for filename, kind in _MISSION_FILE_KIND_BY_BASENAME.items()
    }


# Directory-kind coordination residues that are human-authored planning
# collections (WP03 task files / checklists): each WP's ``tasks/WPNN-*.md`` /
# ``checklists/*.md`` is authored once and never independently edited on the
# target side, so a stale mission-side copy is not both-sides-divergent
# bookkeeping -- ``-X theirs`` keeping the mission copy is correct and no
# reconcile driver is needed. Coord-write-placement-closure-01KYCF83 WP02
# (FR-006) added a THIRD directory-kind residue, ``traces`` (mission tracer
# files, ``MissionArtifactKind.TRACER_FILE``): tracer files are seeded at
# PLANNING and then APPENDED to during EVERY lane's implement loop (mission
# tracer files, #2095) -- when multiple lanes append to the SAME tracer file,
# the mission and target sides both accumulate independent, non-overlapping
# appends, which IS both-sides-divergent bookkeeping (the exact #2709 shape
# a blind ``-X theirs`` would clobber). This is why the pre-existing
# ``spec-kitty-traces`` order-preserving union merge driver
# (``merge_driver.py::merge_driver_traces``) already covers
# ``kitty-specs/**/traces/*.md`` across all four seeding surfaces (registry /
# .gitattributes / init seed / upgrade migration, T013b below) -- traces is
# divergent, not human-source, and its driver already exists; this dir set
# only needed WP02's classification decision documented, not new plumbing.
#
# review-cycle-verdict-seam-rebuild-01KZ2W7W WP04 (T017, ADR 2026-08-03-1):
# ``tasks`` ITSELF stays in this non-divergent set, and stays correct, for a
# subtle reason worth stating explicitly rather than leaving implicit. T014
# classifies ``tasks/<wp>/review-cycle-*.md`` via a FILENAME-anchored pattern
# leg in ``_artifact_kind_for_path`` that runs BEFORE the unconditional
# ``_COORD_RESIDUE_DIRS.get("tasks")`` fallback this set's membership governs
# -- so a review-cycle file NEVER reaches the ``tasks`` directory-kind
# fallback at all once T014 lands; only genuinely single-writer WP task files
# (``tasks/WP*.md``, ``tasks/<wp>/baseline-tests.json``) still do, and THEIR
# non-divergent classification is unaffected. This is precisely why (per the
# WP's own risk note) this guard's own ``divergent_dirs == {"traces"}``
# assertion below does NOT go red on a skipped T017 -- REVIEW_CYCLE is
# invisible to BOTH of this file's enumeration mechanisms
# (``_COORD_RESIDUE_DIRS`` directory-kinds and ``_MISSION_FILE_KIND_BY_
# BASENAME`` exact-basename kinds), because it uses a THIRD, pattern-based
# mechanism neither enumerates.
#
# The real hazard is NOT in this dict's classification (which stays
# accurate) -- it is that ``review-cycle-*.md`` is a genuinely both-sides-
# divergent COORD artifact (PARTITION_RATIONALE, T013) living inside the SAME
# physical ``tasks/`` directory ``git merge --squash -X theirs`` reconciles
# as ONE opaque unit at the git level, which has NO visibility into this
# module's kind-level distinctions. See
# ``test_review_cycle_tasks_hazard_is_ruled_and_tracked`` below for the T017
# ruling (option (a): a reconcile driver, scoped narrowly to
# ``kitty-specs/**/tasks/*/review-cycle-*.md`` -- never the whole
# ``tasks/*.md`` glob, which would wrongly union-merge single-writer WP task
# files too) and why WP04 recorded it as a cross-WP dependency rather than landed
# in this WP: registering it touches ``.gitattributes`` /
# ``specify_cli.lanes.merge._MERGE_DRIVERS`` / the ``init`` seed / an upgrade
# migration, all OUTSIDE this WP's ``owned_files``.
_NON_DIVERGENT_COORD_RESIDUE_DIRS: frozenset[str] = frozenset(
    {
        "tasks",
        "checklists",
        # #3928: the Decision Moment ledger directory (``decisions/index.json``
        # + ``decisions/DM-<ulid>.md``, ``decisions/store.py``) -- SINGLE-WRITER
        # coordination bookkeeping, not both-sides-divergent: Decision Moments
        # are opened/resolved only by the decisions service during the
        # charter/specify/plan interview flows (``OriginFlow`` has no implement
        # lane), the manual ``spec-kitty decision`` command, and Slack-extraction
        # resolve in ``widen/review.py`` -- one writer path, never independent
        # target-side appends like ``traces/``. Each ``DM-<ulid>.md`` is a
        # one-shot write under a ULID-unique name (no filename collision to
        # union), and ``index.json`` is an atomic single-writer rewrite -- the
        # ``issue-matrix.md`` single-writer coordination class, not the #2709
        # ``traces`` append class.
        "decisions",
    }
)


def test_both_sides_divergent_canonical_artifacts_carry_merge_driver() -> None:
    """T013 completeness (catches self-mutation (b) — a NEW canonical artifact with
    no driver): every both-sides-divergent canonical ``kitty-specs/**`` artifact in
    the mission-artifact-kind registry MUST carry a registered merge driver, else a
    future ``git merge --squash -X theirs`` silently re-inherits #2709. Fail-closed:
    a registry artifact not in ``_NON_DIVERGENT_CANONICAL_ARTIFACTS`` is required to
    have a driver.

    Directory-kind residues (``_COORD_RESIDUE_DIRS``) split into the SAME two
    buckets as file artifacts: human-authored/non-divergent
    (``_NON_DIVERGENT_COORD_RESIDUE_DIRS`` -- ``tasks``/``checklists``) vs.
    both-sides-divergent (``traces`` -- WP02/FR-006's ``TRACER_FILE``
    classification), fail-closed: a THIRD, unclassified residue directory
    reds here rather than silently passing.
    """
    registered_patterns = set(_gitattributes_merge_drivers())
    divergent_dirs = set(_COORD_RESIDUE_DIRS) - _NON_DIVERGENT_COORD_RESIDUE_DIRS
    assert _NON_DIVERGENT_COORD_RESIDUE_DIRS | divergent_dirs == set(_COORD_RESIDUE_DIRS)
    assert divergent_dirs == {"traces"}, (
        "a new coordination-residue directory kind appeared in "
        "_COORD_RESIDUE_DIRS that this guard does not yet classify -- add it "
        "to _NON_DIVERGENT_COORD_RESIDUE_DIRS (human-authored, single-writer) "
        "or confirm it registers a union merge driver below (both-sides-"
        f"divergent), never silently: {sorted(divergent_dirs)}"
    )
    for residue_dir in divergent_dirs:
        pattern = f"kitty-specs/**/{residue_dir}/*.md"
        assert pattern in registered_patterns, (
            f"coordination-residue directory {residue_dir!r} is classified "
            "both-sides-divergent bookkeeping but carries no registered merge "
            f"driver for {pattern!r} in root .gitattributes -- it re-inherits "
            "#2709 under `git merge --squash -X theirs`."
        )

    uncovered: list[str] = []
    for glob, kind in _canonical_artifact_file_globs().items():
        basename = glob.rsplit("/", 1)[-1]
        if basename in _NON_DIVERGENT_CANONICAL_ARTIFACTS:
            continue
        # Cross-check the INDEPENDENT public classifier recognizes this artifact.
        assert kind_for_mission_file(f"kitty-specs/some-mission/{basename}") is kind
        if glob not in registered_patterns:
            uncovered.append(f"{glob} ({kind.value})")
    assert not uncovered, (
        "Both-sides-divergent canonical artifact(s) with no registered merge driver "
        "in root .gitattributes — they re-inherit #2709 under `git merge --squash "
        "-X theirs`. Register a reconcile driver (C-006) or, if genuinely "
        "single-writer/derived/human-source, classify in "
        f"_NON_DIVERGENT_CANONICAL_ARTIFACTS: {uncovered}"
    )


# ---------------------------------------------------------------------------
# T017 — the tasks/ two-sided REVIEW_CYCLE hazard (review-cycle-verdict-seam-
# rebuild-01KZ2W7W WP04, ADR 2026-08-03-1).
#
# RULING: option (a) -- a reconcile driver -- not option (b). Option (b)
# requires "a passing test that demonstrates the clobber scenario cannot
# occur"; no such test can be honest today. Per the ADR's own measurement, a
# coord mission's first review cycle for a WP lands PRIMARY (create-window
# split, T018) and every later cycle lands COORD -- BOTH are live for the SAME
# wp_id simultaneously during the migration window, before WP05a's atomicity
# and WP06b's consumer unification land, so nothing in the tree today
# structurally prevents the #2804 clobber shape for `tasks/<wp>/review-cycle-
# <N>.md`. Per the WP's own instruction ("if you cannot produce such a test,
# option (a) is required, not preferred"), (a) is the ruling.
#
# NOT landed as a driver diff in this WP: implementing (a) requires (1) a NEW
# merge-driver command (union-merging two independently-numbered review-cycle
# documents is not a safe line-union like `merge_driver_traces` -- two
# DIFFERENT verdicts under the SAME filename must not be interleaved into one
# nonsensical document; the correct reconciliation needs to coordinate with
# WP09's numbering rework, not just union bytes) PLUS (2) registration across
# FOUR surfaces (`.gitattributes`, `specify_cli.lanes.merge._MERGE_DRIVERS`,
# the `init` command seed, an upgrade migration) that are ALL outside this
# WP's `owned_files`. Recorded as an explicit, cited, time-critical cross-WP
# dependency in WP04's review findings instead of
# silently expanding this WP's file ownership (mirrors T015's caller-side
# finding).
#
# This test PINS the current, honest state (no driver yet) as a fail-closed
# tripwire: it goes RED the instant the review-cycle pattern coincides with an
# already-registered driver (drift-catcher) and is the single place a future
# WP flips the assertion to a positive "driver IS registered" check once the
# cross-WP dependency above is closed.
#
# verdict-seam-write-unification-01KZ9Q35 WP09 (FR-014/D-PLAN-6): the driver
# WP18 registered here was originally REFUSE-fail-closed (exit 1, abort the
# squash). WP05 of this later mission demoted the ``.md`` render to
# non-authoritative, unread best-effort prose (``status.events.jsonl``'s
# ``review_result`` slot is the sole verdict authority now), so the
# fabrication risk that justified refusing no longer applies -- WP09
# DOWNGRADED the driver to non-aborting: it still embeds both divergent
# renders verbatim behind conflict markers (never blending/fabricating a
# merged verdict), but no longer raises, so the squash proceeds. This test's
# own assertions below are unaffected (they only check the driver stays
# REGISTERED in .gitattributes, not its exit-code class) --
# ``test_review_cycle_driver_downgraded_to_non_aborting`` immediately below
# is the guard that pins the new reconciliation class.
# ---------------------------------------------------------------------------

_REVIEW_CYCLE_MERGE_DRIVER_PATTERN = "kitty-specs/**/tasks/*/review-cycle-*.md"


def test_review_cycle_tasks_hazard_is_ruled_and_tracked() -> None:
    """T017: REVIEW_CYCLE's tasks/ two-sided divergence hazard is ruled
    (option (a): a reconcile driver, scoped narrowly) AND LANDED (WP18,
    review-cycle-verdict-seam-rebuild-01KZ2W7W): a driver is registered in
    root .gitattributes, closing WP04's ``WP04-XWP-03`` cross-WP dependency rather
    than leaving a vague "downstream WPs should check this." The driver's
    exit-code class (originally refuse-fail-closed, downgraded to
    non-aborting by WP09/FR-014) is pinned separately below -- this test
    only guards registration, not behavior.
    """
    # REVIEW_CYCLE must actually be COORD-partition for the hazard to apply at
    # all -- if this ever flipped PRIMARY, the whole tasks/ two-sidedness
    # this test guards against would not exist.
    assert MissionArtifactKind.REVIEW_CYCLE in _PLACEMENT_ARTIFACT_KINDS

    # REVIEW_CYCLE is invisible to BOTH of this guard's existing enumeration
    # mechanisms (basename-exact and directory-kind) -- it uses a THIRD,
    # pattern-based classifier leg neither one enumerates. This is a factual
    # statement about the current classifier shape, not aspirational: if
    # REVIEW_CYCLE ever appeared in either map, this guard's OWN completeness
    # check above would already be enumerating it and this whole T017 test
    # would need to be revisited.
    assert MissionArtifactKind.REVIEW_CYCLE not in _MISSION_FILE_KIND_BY_BASENAME.values()
    assert MissionArtifactKind.REVIEW_CYCLE not in _COORD_RESIDUE_DIRS.values()

    # The ``tasks`` directory-kind residue itself must NOT be reclassified
    # divergent -- T014's filename-anchoring means genuinely single-writer WP
    # task files are the ONLY files still reaching the ``tasks`` directory-kind
    # fallback; review-cycle files are intercepted by the pattern leg first
    # (see ``_NON_DIVERGENT_COORD_RESIDUE_DIRS``'s own comment above). Restates
    # (does not silently duplicate) the invariant
    # ``test_both_sides_divergent_canonical_artifacts_carry_merge_driver``
    # already pins (``divergent_dirs == {"traces"}``), so a reader of THIS
    # test does not have to assume it holds.
    assert "tasks" in _NON_DIVERGENT_COORD_RESIDUE_DIRS

    # LANDED (WP18/T078). This was a tripwire asserting NO driver was
    # registered yet, whose failure message instructed exactly this flip once
    # the cross-WP dependency WP04-XWP-03 landed. WP18 registered the driver,
    # so the assertion is now the positive presence check the tripwire asked
    # for, mirroring the ``traces`` pattern check above.
    #
    # The driver is deliberately NOT a byte-union merge (unlike ``traces``):
    # two DIFFERENT verdicts colliding under the SAME filename are never
    # interleaved -- ``merge_driver_review_cycle`` embeds both documents
    # verbatim behind conflict markers instead. What CHANGED (WP09/FR-014,
    # see the module-comment block above) is only whether that embedding
    # aborts the squash: it no longer does.
    registered_patterns = set(_gitattributes_merge_drivers())
    assert _REVIEW_CYCLE_MERGE_DRIVER_PATTERN in registered_patterns, (
        "the review-cycle merge driver regressed out of root .gitattributes -- "
        f"{_REVIEW_CYCLE_MERGE_DRIVER_PATTERN!r} must stay registered or the "
        "tasks/ two-sided create-window clobber (T017/WP04-XWP-03) re-opens "
        "under `git merge --squash -X theirs`"
    )


def test_review_cycle_driver_downgraded_to_non_aborting(tmp_path: Path) -> None:
    """WP09 (FR-014/D-PLAN-6): the reconciliation-class guard for the
    review-cycle driver -- a genuine two-verdict collision must embed both
    renders verbatim behind conflict markers (never blend/fabricate) AND must
    NOT raise, now that the ``.md`` is non-authoritative, unread prose (WP05
    of this mission demoted it; the event-sourced ``review_result`` slot is
    the sole verdict authority). This is the guard
    ``test_review_cycle_tasks_hazard_is_ruled_and_tracked`` above explicitly
    defers to for the driver's exit-code CLASS."""
    from specify_cli.cli.commands.merge_driver import merge_driver_review_cycle

    base = tmp_path / "O"
    ours = tmp_path / "A"
    theirs = tmp_path / "B"
    base.write_text("", encoding="utf-8")
    ours.write_text("verdict: approved\n", encoding="utf-8")
    theirs.write_text("verdict: rejected\n", encoding="utf-8")

    merge_driver_review_cycle(str(base), str(ours), str(theirs))  # must NOT raise

    merged = ours.read_text(encoding="utf-8")
    assert "verdict: approved" in merged
    assert "verdict: rejected" in merged
    assert "<<<<<<<" in merged, "both renders must still be embedded, never blended"


# ---------------------------------------------------------------------------
# T013b — driver-registry parity across the fresh/upgraded-repo seed surfaces
#
# The driver spec is declared in FOUR places: the in-code ``_MERGE_DRIVERS``
# registry, root ``.gitattributes`` (bound bidirectionally above), the ``init``
# seed (fresh repos), and the upgrade migrations (existing repos). The
# ``.gitattributes`` binding alone does NOT protect a NEW driver added to the
# registry+``.gitattributes`` but forgotten in the init seed or a migration:
# fresh/upgraded repos then silently re-inherit #2709 for that artifact because
# their ``.gitattributes`` never gains the mapping. These two lints bind the
# remaining two surfaces to the registry (superset direction).
# ---------------------------------------------------------------------------

_MERGE_ATTRIBUTES_LINE = re.compile(r"^\S+ merge=\S+$")


def _registry_attribute_lines() -> set[str]:
    """``<pattern> merge=<key>`` line for every driver in the in-code registry."""
    return {driver.attributes_line for driver in _MERGE_DRIVERS}


def _init_seed_attribute_lines() -> set[str]:
    """Every gitattributes ``merge=`` line the ``init`` command seeds for new repos.

    Scanned from the init module namespace (any ``<pattern> merge=<key>`` string
    constant), NOT a hardcoded list — a NEW driver constant is picked up
    automatically, and a registry driver with NO init constant trips the lint.
    """
    return {
        value
        for value in vars(_init_command).values()
        if isinstance(value, str) and _MERGE_ATTRIBUTES_LINE.match(value)
    }


def _migration_seed_attribute_lines() -> set[str]:
    """Every gitattributes ``merge=`` line the upgrade migrations seed.

    Discovered, not enumerated: every registered migration deriving from
    ``MergeDriverSeedingMigration`` contributes its ``drivers``, plus the legacy
    single-entry event-log migration (``m_3_1_1``, predates the shared base).
    Their UNION is the upgraded-repo seed surface.

    Discovery matters here: an enumeration listing specific modules goes stale
    the moment a new driver migration lands, and this guard then passes a driver
    that no migration actually seeds — the exact failure it exists to catch.
    """
    lines = {_event_log_migration._ATTRIBUTES_ENTRY}
    _auto_discover_migrations()  # registration fires on import; discovery is lazy
    for migration in _MigrationRegistry.get_all():
        if isinstance(migration, _MergeDriverSeedingMigration):
            lines.update(driver.attributes_entry for driver in migration.drivers)
    return lines


def test_init_seed_is_superset_of_registry_merge_drivers() -> None:
    """T013b (fresh repos): every driver in ``_MERGE_DRIVERS`` MUST also be seeded
    by ``init`` into ``.gitattributes`` — else a freshly ``init``-ed repo never
    activates the driver and re-inherits #2709 for that artifact. RED when a
    registry driver has no matching init constant."""
    missing = _registry_attribute_lines() - _init_seed_attribute_lines()
    assert not missing, (
        "Merge driver(s) declared in specify_cli.lanes.merge._MERGE_DRIVERS but NOT "
        "seeded by the init command (fresh repos re-inherit #2709 — no .gitattributes "
        f"mapping). Add the entry in specify_cli/cli/commands/init.py: {sorted(missing)}"
    )


def test_migration_seed_is_superset_of_registry_merge_drivers() -> None:
    """T013b (upgraded repos): every driver in ``_MERGE_DRIVERS`` MUST also be seeded
    by an upgrade migration (m_3_1_1 event-log ∪ m_3_2_6 meta/traces) — else an
    UPGRADED repo never activates the driver and re-inherits #2709 for that
    artifact. RED when a registry driver is in neither migration."""
    missing = _registry_attribute_lines() - _migration_seed_attribute_lines()
    assert not missing, (
        "Merge driver(s) declared in specify_cli.lanes.merge._MERGE_DRIVERS but NOT "
        "seeded by any upgrade migration (upgraded repos re-inherit #2709). Add the "
        f"driver to an m_*_meta_traces / event-log migration: {sorted(missing)}"
    )
