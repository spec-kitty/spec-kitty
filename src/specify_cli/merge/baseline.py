"""Post-merge review baseline (``baseline_merge_commit``) record/verify cluster.

This module owns the mission-state-surface concern of the ``baseline_merge_commit``
``meta.json`` field: it is written here at merge time and read by
``spec-kitty review --mode post-merge``. Extracted verbatim from
``cli/commands/merge.py`` as part of the merge.py god-module decomposition
(epic #2026); behavior is byte-identical to the original definitions.

``merge/`` deliberately does NOT import ``cli.commands.merge``, so relocating
this cluster here introduces no import cycle.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from kernel.clock import now_utc_iso
from kernel._safe_re import re
from kernel.meta_decode import MetaDecodeError, decode_meta
from specify_cli.core.git_ops import resolve_primary_branch, run_command
from specify_cli.core.paths import (
    MissionMetaReadError,
    assert_safe_path_segment,
    load_meta_fail_closed,
    read_target_branch_from_meta,
)
from specify_cli.mission_metadata import write_meta

logger = logging.getLogger(__name__)

META_JSON = "meta.json"

#: Shape a supplied ``--merge-commit`` value must have before it is allowed
#: into a git argument list: 4–64 hex characters (git's minimum abbreviation
#: through a full SHA-256). Anything else — a branch name, ``HEAD``, or an
#: option-looking string — is refused before any subprocess runs.
_HEX_SHA_RE = re.compile(r"[0-9a-fA-F]{4,64}")

#: Provenance field stamped alongside ``baseline_merge_commit`` when the merge
#: was recorded from a GitHub PR acceptance (``spec-kitty accept --mode pr
#: --merge-commit`` / ``spec-kitty migrate backfill-merge-commit``). Holds the
#: exact commit that landed the mission on its target branch, so a later reader
#: can distinguish a PR-recorded baseline from a ``spec-kitty merge``-recorded
#: one without re-deriving it from git history.
_PR_MERGE_COMMIT_FIELD = "pr_merge_commit"

#: Second provenance field written with :data:`_PR_MERGE_COMMIT_FIELD`: what
#: kind of evidence the recorded ``baseline_merge_commit`` anchor rests on, so
#: ``spec-kitty review --mode post-merge`` can tell an anchor recorded under
#: the operator's explicit attestation from one whose evidence it does not
#: recognize — and refuse to report a green dead-code scan for any value it
#: does not recognize as complete (#4231 fix rounds: the impl-before-corpus
#: rebase landing, then the internal-merge landing).
_PR_MERGE_EVIDENCE_FIELD = "pr_merge_evidence"

#: Anchor-evidence class: the landing commit has two parents, so its first
#: parent is the pre-landing target tip — but only by the operator's recorded
#: ``--attest-first-landing-commit`` attestation that the merge was performed
#: ON the target branch. A merge performed on a mission or sibling branch and
#: then fast-forwarded onto the target is graph-identical to a merge performed
#: on the target (the internal-merge landing, #4231 fix round 4), so git alone
#: cannot prove which side the target stood on.
ANCHOR_EVIDENCE_MERGE_COMMIT_PARENT_ATTESTED = "merge-commit-parent-attested"

#: Anchor-evidence class: the landing commit has a single parent, so git
#: cannot prove that parent is the pre-landing target tip (a squash or
#: corpus-first stack parent IS the tip; an earlier same-PR implementation
#: commit is NOT — the two are graph-identical). Recordable only with the
#: operator's explicit ``--attest-first-landing-commit`` attestation, which is
#: what this persisted value names.
ANCHOR_EVIDENCE_CORPUS_PARENT_ATTESTED = "corpus-parent-attested"


def _resolve_merge_commit(feature_dir: Path) -> str:
    """Best-effort HEAD SHA of the checkout carrying *feature_dir*.

    Provenance only for the ``merged_commit`` marker: at the record call site
    the target branch has already advanced to the merge result, so ``HEAD`` is
    that commit. Non-raising — a non-repo path or a failed ``git`` degrades to
    an empty string and the caller falls back to the captured baseline SHA.
    """
    ret, out, _err = run_command(
        ["git", "rev-parse", "HEAD"],
        capture=True,
        check_return=False,
        cwd=feature_dir,
    )
    return out.strip() if ret == 0 else ""


class BaselineMergeCommitError(RuntimeError):
    """Raised when the post-merge review baseline cannot be recorded or verified.

    Modern lane missions (those whose ``meta.json`` carries a canonical
    ``mission_id``) MUST land ``baseline_merge_commit`` on the target branch.
    When the baseline is missing, the working meta is absent/corrupt, or the
    committed target meta lacks the expected value, downstream
    ``spec-kitty review`` raises ``MISSION_REVIEW_MODE_MISMATCH``. We surface
    that failure loudly at merge time instead of letting an apparently
    successful merge ship a mission that cannot be reviewed post-merge.
    """


def record_baseline_merge_commit(
    feature_dir: Path,
    baseline_commit: str | None,
    *,
    mission_id: str | None = None,
    merged_commit: str | None = None,
) -> Path | None:
    """Persist the post-merge review baseline AND merge completion marker in meta.json.

    Two sibling records land here on the same merge-finalize path
    (``executor.py`` ``_phase_capture_and_baseline``), folded into the one
    bookkeeping commit + durability path:

    * ``baseline_merge_commit`` — anchors post-merge review diffs. It should
      point at the target-branch baseline before the mission lands, not at the
      final housekeeping commit produced by merge.
    * ``merged_at`` (+ ``merged_commit``) — the post-merge completion marker
      (#4090). Its production writer was deleted in #2258 and never re-added,
      leaving the surface resolver's primary-wins guard
      (``surface_resolver.py`` ``_primary_mission_is_completed`` ->
      ``is_mission_merged`` -> ``meta.get("merged_at")``) and the runtime
      terminal short-circuit dormant. ``merged_at`` is a UTC ISO datetime;
      ``merged_commit`` is the merge-result SHA (provenance). Unlike
      ``baseline_merge_commit`` (modern-mission-only), the marker is written for
      EVERY merge, legacy included.

    For **modern lane missions** (``mission_id`` is set — the canonical ULID
    introduced by mission 083), an empty baseline, a missing ``meta.json``, or
    corrupt JSON is a HARD failure: we raise :class:`BaselineMergeCommitError`
    so the merge stops loudly instead of shipping a mission that
    ``spec-kitty review --mode post-merge`` cannot anchor
    (``MISSION_REVIEW_MODE_MISMATCH``).

    For **legacy missions** (no ``mission_id``) the historical soft behavior is
    preserved for the baseline: the function logs a warning and returns ``None``
    when meta cannot be read so the merge proceeds without a baseline.

    Both records are idempotent — a ``spec-kitty merge --resume`` never
    double-stamps an already-present field — and ``spec-kitty mission reopen``
    clears ``merged_*`` so a re-merge re-stamps a fresh ``merged_at``.

    *merged_commit* lets a caller that already holds the verified landing SHA
    (the PR-acceptance path's :data:`PrMergeEvidence.pr_merge_commit`) thread
    it through as the recorded ``merged_commit`` instead of falling back to
    :func:`_resolve_merge_commit`'s local checkout ``HEAD`` — which is wrong
    for PR acceptance when the local checkout has advanced past the PR
    landing. When omitted or blank, the existing ``_resolve_merge_commit(feature_dir)
    or baseline`` fallback is used unchanged.
    """
    is_modern = bool(mission_id and str(mission_id).strip())
    baseline = (baseline_commit or "").strip()

    if not baseline and is_modern:
        raise BaselineMergeCommitError(f"Cannot record baseline_merge_commit for modern mission {feature_dir.name}: no target baseline SHA was captured.")

    meta_path = feature_dir / META_JSON
    if not meta_path.exists():
        if is_modern:
            raise BaselineMergeCommitError(f"Cannot record baseline_merge_commit for modern mission {feature_dir.name}: meta.json is missing.")
        logger.warning(
            "Cannot record baseline_merge_commit for %s: meta.json is missing",
            feature_dir.name,
        )
        return None

    try:
        meta = load_meta_fail_closed(feature_dir)
    except MissionMetaReadError as exc:
        if is_modern:
            raise BaselineMergeCommitError(f"Cannot record baseline_merge_commit for modern mission {feature_dir.name}: meta.json is invalid ({exc}).") from exc
        logger.warning(
            "Cannot record baseline_merge_commit for %s: %s",
            feature_dir.name,
            exc,
        )
        return None

    if meta is None:
        if is_modern:
            raise BaselineMergeCommitError(f"Cannot record baseline_merge_commit for modern mission {feature_dir.name}: meta.json could not be loaded.")
        return None

    changed = False

    # baseline_merge_commit — only for missions with a captured baseline SHA,
    # idempotent on --resume.
    existing_baseline = meta.get("baseline_merge_commit")
    if baseline and not (existing_baseline and str(existing_baseline).strip()):
        meta["baseline_merge_commit"] = baseline
        changed = True

    # merged_at (+ merged_commit) — the #4090 completion marker, written for
    # every merge, idempotent on --resume.
    if not str(meta.get("merged_at") or "").strip():
        meta["merged_at"] = now_utc_iso()
        supplied_merged_commit = (merged_commit or "").strip()
        meta["merged_commit"] = supplied_merged_commit or (_resolve_merge_commit(feature_dir) or baseline)
        changed = True

    if changed:
        write_meta(feature_dir, meta, validate=False)
        return meta_path
    return None


def _recorded_baseline_from_working_meta(feature_dir: Path | None) -> str:
    if feature_dir is None:
        return ""
    try:
        working_meta = load_meta_fail_closed(feature_dir)
    except MissionMetaReadError:
        return ""
    if not isinstance(working_meta, dict):
        return ""
    return str(working_meta.get("baseline_merge_commit") or "").strip()


def _read_committed_meta_json(
    main_repo: Path,
    target_branch: str,
    meta_rel: str,
    mission_slug: str,
) -> dict[str, object]:
    ret, out, err = run_command(
        ["git", "show", f"{target_branch}:{meta_rel}"],
        capture=True,
        check_return=False,
        cwd=main_repo,
    )
    if ret != 0:
        raise BaselineMergeCommitError(
            f"Post-merge baseline validation failed for {mission_slug}: "
            f"could not read {meta_rel} from {target_branch} "
            f"({(err or '').strip() or 'git show failed'})."
        )

    try:
        committed_meta = decode_meta(out, on_malformed="raise")
    except MetaDecodeError as exc:
        message = str(exc)
        if message.startswith("Expected JSON object, got "):
            raise BaselineMergeCommitError(
                f"Post-merge baseline validation failed for {mission_slug}: committed {meta_rel} on {target_branch} is not a JSON object."
            ) from exc
        raise BaselineMergeCommitError(
            f"Post-merge baseline validation failed for {mission_slug}: committed {meta_rel} on {target_branch} is not valid JSON ({exc})."
        ) from exc
    return committed_meta if committed_meta is not None else {}


def assert_baseline_merge_commit_on_target(
    main_repo: Path,
    mission_slug: str,
    target_branch: str,
    expected_baseline: str | None,
    *,
    feature_dir: Path | None = None,
    mission_id: str | None = None,
) -> None:
    """Fail the merge if ``baseline_merge_commit`` did not land on *target_branch*.

    Mirrors :func:`_assert_merged_wps_reached_done`: it reads the target
    branch's COMMITTED ``kitty-specs/<slug>/meta.json`` via
    ``git show <target>:<path>`` and asserts ``baseline_merge_commit`` is both
    present and equal to the baseline that was actually RECORDED for this
    mission. This is the post-commit invariant that closes the gap behind
    ``MISSION_REVIEW_MODE_MISMATCH``: it proves the baseline is durable in git
    history (not just in the working tree) before any worktree removal or
    branch cleanup runs.

    The expected baseline is read from the recorded mission ``meta.json`` in
    *feature_dir* (the idempotent value written by
    :func:`record_baseline_merge_commit`) and only falls back to
    *expected_baseline* when that is unavailable. This is deliberate:
    ``target_baseline_sha`` is re-derived from the live target HEAD on every
    invocation, so on ``spec-kitty merge --resume`` — after a prior run already
    landed the mission/bookkeeping commits — the live HEAD has advanced past the
    original baseline. Comparing the committed value against a re-derived HEAD
    would spuriously fail an otherwise-correct resume; comparing it against the
    recorded value does not.

    Only enforced for **modern missions** (``mission_id`` set). Legacy missions
    never carry a baseline and are skipped.
    """
    if not (mission_id and str(mission_id).strip()):
        return

    recorded = _recorded_baseline_from_working_meta(feature_dir)
    expected = recorded or (expected_baseline or "").strip()
    if not expected:
        raise BaselineMergeCommitError(f"Cannot verify baseline_merge_commit for modern mission {mission_slug}: no recorded baseline SHA was found.")

    meta_rel = f"kitty-specs/{mission_slug}/{META_JSON}"
    committed_meta = _read_committed_meta_json(main_repo, target_branch, meta_rel, mission_slug)
    committed_baseline = str(committed_meta.get("baseline_merge_commit") or "").strip()
    if not committed_baseline:
        raise BaselineMergeCommitError(
            f"Post-merge baseline validation failed for {mission_slug}: "
            f"baseline_merge_commit is missing from committed {meta_rel} on "
            f"{target_branch}. Downstream `spec-kitty review --mode post-merge` "
            f"would fail with MISSION_REVIEW_MODE_MISMATCH."
        )

    if committed_baseline != expected:
        raise BaselineMergeCommitError(
            f"Post-merge baseline validation failed for {mission_slug}: "
            f"committed baseline_merge_commit ({committed_baseline}) on "
            f"{target_branch} does not match the captured baseline ({expected})."
        )


# ---------------------------------------------------------------------------
# PR-acceptance merge-evidence recording (#4231)
# ---------------------------------------------------------------------------


class PrMergeEvidenceError(RuntimeError):
    """Raised when a PR merge commit cannot be verified as genuine merge evidence.

    A mission accepted via ``--mode pr`` never passes through
    ``spec-kitty merge``, so the post-merge review baseline must be recorded
    from the PR's real merge commit instead. This error means the supplied
    commit does NOT prove what the caller asserted — it is not a commit in
    this repository, it does not carry the mission's corpus, the mission
    corpus already existed at its first parent (so it is not the commit that
    landed the mission), or it never landed on the target branch (an unmerged
    mission-branch commit satisfies every first-introduction check, so only
    the target-branch membership check separates it from a real landing).
    Recording it anyway would anchor the dead-code scan at the wrong tip and
    silently skip part of the gate, so the recording refuses loudly instead.
    """


@dataclass(frozen=True)
class PrMergeEvidence:
    """Verified git evidence that a commit landed one mission via PR.

    ``pr_merge_commit`` is the exact commit that landed the mission on its
    target branch; ``baseline_merge_commit`` is that commit's first parent —
    the post-merge review anchor, the same field ``spec-kitty merge``
    records. ``anchor_evidence`` names what kind of evidence that anchor
    rests on: :data:`ANCHOR_EVIDENCE_MERGE_COMMIT_PARENT_ATTESTED` (a
    two-parent landing whose first parent is the pre-landing target tip by
    the operator's recorded attestation that the merge was performed on the
    target branch) or :data:`ANCHOR_EVIDENCE_CORPUS_PARENT_ATTESTED` (a
    single-parent landing whose anchor is the pre-landing tip by the
    operator's recorded attestation). Neither is a git proof: post-landing
    git history cannot show which side of a landing the target branch stood
    on. See the "What the evidence proves" note in
    :func:`verify_pr_merge_evidence`.
    """

    pr_merge_commit: str
    baseline_merge_commit: str
    anchor_evidence: str = ""


def _rev_verify(repo_root: Path, revision: str) -> str:
    """Resolve *revision* to a full commit SHA or raise :class:`PrMergeEvidenceError`."""
    ret, out, err = run_command(
        ["git", "rev-parse", "--verify", revision],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    if ret != 0:
        raise PrMergeEvidenceError(
            f"cannot resolve {revision!r} to a commit in this repository "
            f"({(err or '').strip() or 'git rev-parse failed'}); fetch the "
            "target branch first, then retry"
        )
    return str(out).strip()


def _commit_has_mission_meta(repo_root: Path, commit: str, mission_slug: str) -> bool:
    """True iff ``kitty-specs/<slug>/meta.json`` exists at *commit*."""
    meta_rel = f"kitty-specs/{mission_slug}/{META_JSON}"
    ret, _out, _err = run_command(
        ["git", "cat-file", "-e", f"{commit}:{meta_rel}"],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    return int(ret) == 0


def _commit_has_mission_dir(repo_root: Path, commit: str, mission_slug: str) -> bool:
    """True iff the ``kitty-specs/<slug>/`` tree exists at *commit* at all.

    Wider than :func:`_commit_has_mission_meta`: a commit can carry part of
    the mission corpus (``spec.md``, tasks, contracts) without ``meta.json``
    yet — the staged-corpus shape. Anchoring a baseline at the parent of such
    a landing would diff past the already-landed part of the mission, so the
    verifier refuses it, not just the meta.json-only re-landing.
    """
    mission_dir = f"kitty-specs/{mission_slug}"
    ret, _out, _err = run_command(
        ["git", "cat-file", "-e", f"{commit}:{mission_dir}"],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    return int(ret) == 0


def _commit_is_on_target(repo_root: Path, commit: str, target_ref: str) -> bool:
    """True iff *commit* is an ancestor of *target_ref* — it landed there."""
    ret, _out, _err = run_command(
        ["git", "merge-base", "--is-ancestor", commit, target_ref],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    return int(ret) == 0


def _commit_is_merge(repo_root: Path, commit: str) -> bool:
    """True iff *commit* has a second parent (it is a merge commit).

    Distinguishes the two landing SHAPES for the persisted evidence class —
    a two-parent landing's anchor is its first parent, a single-parent
    landing's anchor is its only parent. It proves NOTHING about completeness
    either way: a merge performed on the target branch is graph-identical to
    a merge performed on a mission or sibling branch that was then
    fast-forwarded onto the target, so two parents alone do not show which
    side the target stood on (see :func:`verify_pr_merge_evidence`).
    """
    ret, _out, _err = run_command(
        ["git", "rev-parse", "--verify", "--quiet", f"{commit}^2"],
        capture=True,
        check_return=False,
        cwd=repo_root,
    )
    return int(ret) == 0


def _resolve_pr_target_ref(
    repo_root: Path,
    mission_slug: str,
    target_ref: str | None,
    *,
    effective_root: Path | None = None,
) -> str:
    """Resolve the branch the PR merged INTO, for the landing check.

    An explicitly supplied *target_ref* wins (shape-guarded: a value
    beginning with ``-`` would be parsed as a git option). Otherwise the
    mission's own declared ``target_branch`` from its primary ``meta.json``
    (the PR base is the mission's landing target), and finally the
    repository's primary branch with the feature-branch bias OFF — a checkout
    standing on a mission branch must never be mistaken for the landing
    target.

    *effective_root* is threaded straight through to
    :func:`resolve_primary_meta_dir` so this declared-target READ resolves the
    SAME ``meta.json`` the caller's WRITE leg targets. Without it, an
    owned-mission checkout that is itself a git worktree resolves via
    ``get_main_repo_root(repo_root)`` back to the PRIMARY repo root instead of
    the owned checkout — a genuinely different ``meta.json`` than the one
    :func:`record_pr_merge_baseline_for_mission` writes when it is called with
    an explicit ``effective_root``.
    """
    if target_ref is not None:
        supplied = target_ref.strip()
        if not supplied:
            raise PrMergeEvidenceError("the supplied target branch is empty")
        if supplied.startswith("-"):
            raise PrMergeEvidenceError(f"{supplied!r} is not a branch name (it looks like a git option)")
        return supplied
    try:
        declared = read_target_branch_from_meta(resolve_primary_meta_dir(repo_root, mission_slug, effective_root=effective_root))
    except MissionMetaReadError as exc:
        raise PrMergeEvidenceError(f"cannot read mission {mission_slug}'s declared target branch to verify the PR landing ({exc}).") from exc
    if declared:
        if declared.startswith("-"):
            raise PrMergeEvidenceError(f"mission {mission_slug}'s declared target_branch {declared!r} is not a branch name")
        # str() pins the adapter's documented ``str | None`` contract for the
        # narrow mypy check (cross-module ``specify_cli.*`` imports resolve as
        # Any there), the same idiom ``_rev_verify`` uses on ``run_command``
        # output.
        return str(declared)
    return str(resolve_primary_branch(repo_root, bias=False))


def verify_pr_merge_evidence(
    repo_root: Path,
    mission_slug: str,
    merge_commit: str,
    *,
    target_ref: str | None = None,
    attest_first_landing: bool = False,
    effective_root: Path | None = None,
) -> PrMergeEvidence:
    """Verify a supplied commit is the genuine PR landing commit for one mission.

    The verification is deliberately strict, because the recorded value anchors
    ``spec-kitty review --mode post-merge``'s dead-code scan: a wrong anchor
    silently skips part of the scan, which is worse than refusing. The value
    must first be a hexadecimal SHA (never a ref or an option-looking string),
    then five read-only git facts, never heuristics:

    1. ``merge_commit`` resolves to a real commit in this repository.
    2. The mission's ``kitty-specs/<slug>/meta.json`` exists AT the commit —
       the commit genuinely carries this mission.
    3. The commit has a first parent (it is not a root commit).
    4. The mission's ``meta.json`` does NOT exist at the first parent — the
       commit is the one that introduced the mission corpus. This also rejects
       the common operator mistake of supplying the mission branch head: its
       parent already contains the mission.
    5. The mission's ``kitty-specs/<slug>/`` directory does not exist at the
       first parent AT ALL — no part of the corpus (``spec.md``, tasks,
       contracts) landed earlier. A staged corpus whose ``meta.json`` arrives
       after its siblings would otherwise anchor the diff past the
       already-landed part and silently skip the gate for it.
    6. The commit IS on the target branch (``git merge-base --is-ancestor``)
       — it landed there. Checks 2–5 alone prove first introduction, not
       landing: an unmerged mission-branch commit that introduces the corpus
       satisfies every one of them, so this membership check is what actually
       distinguishes a landed PR merge from an unmerged branch commit.

    Check 4 refuses a partial re-landing (the mission dir already existed at
    the parent) on purpose: in that case a diff anchored at the parent would
    not cover the earlier-landed part of the mission, so recording it would
    skip the gate rather than run it.

    *target_ref* names the branch the PR merged INTO for check 6: an explicit
    value wins (``main``, ``origin/main``, ``refs/heads/main`` — anything
    rev-parse resolves), else the mission's declared ``target_branch``, else
    the repository's primary branch. *effective_root* is passed straight
    through to that declared-``target_branch`` read (see
    :func:`_resolve_pr_target_ref`) so it resolves the SAME ``meta.json`` an
    owned-mission caller's write leg targets, not the primary repo's copy.

    **What the evidence proves, and what it does not.** Checks 1–6 prove the
    commit landed on the target branch and introduced the mission corpus.
    They do NOT prove the anchor (the first parent) is the PRE-LANDING TARGET
    TIP — the fact that would make it cover the whole mission — for ANY
    operator-supplied landing shape:

    - **Two-parent merge commit** (the landing shape ``git merge --no-ff``
      and GitHub's "Create a merge commit" produce): the first parent is the
      pre-landing target tip only if the merge was performed ON the target
      branch. A merge performed on a mission or sibling branch — the
      internal-merge landing, where the corpus branch is merged into the
      implementation branch and the target is then fast-forwarded to the
      result — is graph-identical to it, and its first parent is an
      implementation commit, so a scan anchored there silently omits the
      implementation work. Post-landing git history cannot distinguish the
      two, so this shape is refused unless the caller supplies
      ``attest_first_landing=True`` (the operator's explicit attestation that
      the merge was performed on the target branch, so the first parent is
      the pre-landing target tip); with that attestation the returned
      ``anchor_evidence`` is
      :data:`ANCHOR_EVIDENCE_MERGE_COMMIT_PARENT_ATTESTED`.
    - **Single-parent landing commit** (squash, or a rebase-replayed corpus
      commit): the first parent is the pre-landing tip ONLY IF the supplied
      commit was the first commit of the landing (a squash contains the whole
      PR; a corpus-first stack begins with the corpus). For a landing whose
      implementation commits PRECEDED the corpus, the first parent is an
      earlier same-PR commit — graph-identical to unrelated work that landed
      on the target before the PR, so NO git check can separate the two.
      This shape is likewise refused unless the caller supplies
      ``attest_first_landing=True``; with that attestation the returned
      ``anchor_evidence`` is :data:`ANCHOR_EVIDENCE_CORPUS_PARENT_ATTESTED`.

    In both cases the recording persists the attested class, so the anchor's
    completeness rests on a recorded operator attestation, never on a claim
    git did not make. The honest alternative that would PROVE completeness —
    the PR's own commit list, which only forge discovery can supply — is
    tracked in #4277, not silently skipped. (The ``spec-kitty merge`` local
    lane needs no attestation: it captures the real target tip at merge time,
    before any landing exists.)
    """
    assert_safe_path_segment(mission_slug)

    supplied = (merge_commit or "").strip()
    if not supplied:
        raise PrMergeEvidenceError("no merge commit was supplied")
    if not _HEX_SHA_RE.fullmatch(supplied):
        # Shape guard BEFORE the value reaches a git argument list: a value
        # beginning with ``-`` would be parsed as a git option, and anything
        # non-hex is not a commit SHA an operator copied off a merged PR.
        raise PrMergeEvidenceError(f"{supplied!r} is not a commit SHA (expected a hexadecimal SHA, full or abbreviated, as shown on the merged PR)")

    pr_merge_commit = _rev_verify(repo_root, f"{supplied}^{{commit}}")

    if not _commit_has_mission_meta(repo_root, pr_merge_commit, mission_slug):
        raise PrMergeEvidenceError(
            f"commit {pr_merge_commit} does not carry kitty-specs/{mission_slug}/{META_JSON}; it is not the commit that landed mission {mission_slug}"
        )

    baseline_merge_commit = _rev_verify(repo_root, f"{pr_merge_commit}^1")

    if _commit_has_mission_meta(repo_root, baseline_merge_commit, mission_slug):
        raise PrMergeEvidenceError(
            f"commit {pr_merge_commit} is not the landing commit for mission "
            f"{mission_slug}: kitty-specs/{mission_slug}/{META_JSON} already "
            f"exists at its first parent {baseline_merge_commit}. Supply the "
            "commit that introduced the mission corpus on the target branch"
        )

    if _commit_has_mission_dir(repo_root, baseline_merge_commit, mission_slug):
        raise PrMergeEvidenceError(
            f"commit {pr_merge_commit} is not the landing commit for mission "
            f"{mission_slug}: kitty-specs/{mission_slug}/ already exists at "
            f"its first parent {baseline_merge_commit} (staged corpus — part "
            "of the mission landed before its meta.json). Anchoring there "
            "would skip the gate for the already-landed part; supply the "
            "commit that introduced the mission corpus"
        )

    resolved_target = _resolve_pr_target_ref(repo_root, mission_slug, target_ref, effective_root=effective_root)
    _rev_verify(repo_root, f"{resolved_target}^{{commit}}")  # a missing/unfetched target branch is its own clean refusal
    if not _commit_is_on_target(repo_root, pr_merge_commit, resolved_target):
        raise PrMergeEvidenceError(
            f"commit {pr_merge_commit} is not on target branch "
            f"{resolved_target!r}: it never landed there. Supply the commit "
            f"that landed mission {mission_slug} on {resolved_target} — the "
            "merge or squash commit shown on the merged PR. If the landing "
            f"is newer than this checkout, fetch {resolved_target} first; "
            "if the PR targeted a different branch, pass it explicitly "
            "(--target-branch)"
        )

    # Anchor-evidence classification (#4231 fix rounds 3–4). Post-landing git
    # history cannot prove the anchor (the first parent) is the pre-landing
    # target tip for ANY operator-supplied landing shape: a two-parent merge
    # performed on the target branch is graph-identical to an internal merge
    # (corpus merged into the implementation branch, target fast-forwarded to
    # the result), whose first parent is an implementation commit; and a
    # single-parent landing's parent is the tip only if the supplied commit
    # was the FIRST commit of the landing, which an earlier same-PR
    # implementation commit is graph-identical to. Recording either unattested
    # would anchor the dead-code scan at the wrong tip and silently skip part
    # of the gate, so BOTH shapes are refused unless the operator attests
    # explicitly — the attestation is then named in the persisted evidence
    # class, never presented as a git proof.
    is_merge = _commit_is_merge(repo_root, pr_merge_commit)
    if not attest_first_landing:
        if is_merge:
            raise PrMergeEvidenceError(
                f"commit {pr_merge_commit} is a merge commit, but two parents "
                "alone do not prove its first parent "
                f"{baseline_merge_commit} is the pre-landing target tip: a "
                "merge performed on the target branch is graph-identical to "
                "an internal merge (the corpus branch merged into the "
                "implementation branch, the target then fast-forwarded to "
                "the result), whose first parent is an implementation commit "
                "— anchoring there would silently skip the dead-code gate for "
                "that work. If this merge was performed ON the target branch, "
                "pass --attest-first-landing-commit to record that operator "
                "attestation. Full forge commit-list evidence is tracked in "
                "#4277."
            )
        raise PrMergeEvidenceError(
            f"commit {pr_merge_commit} has a single parent, so git cannot "
            f"prove its first parent {baseline_merge_commit} is the "
            "pre-landing target tip: for a squash or corpus-first stack "
            "landing the parent IS the tip, but for a landing whose "
            "implementation commits preceded the corpus the parent is an "
            "earlier same-PR commit, and the two are graph-identical — no "
            "git check separates them. Recording it anyway would anchor the "
            "dead-code scan at the wrong tip and silently skip part of the "
            "gate. If the supplied commit was the first commit of the "
            "landing, pass --attest-first-landing-commit to record that "
            "operator attestation. Full forge commit-list evidence is "
            "tracked in #4277."
        )
    anchor_evidence = ANCHOR_EVIDENCE_MERGE_COMMIT_PARENT_ATTESTED if is_merge else ANCHOR_EVIDENCE_CORPUS_PARENT_ATTESTED

    return PrMergeEvidence(
        pr_merge_commit=pr_merge_commit,
        baseline_merge_commit=baseline_merge_commit,
        anchor_evidence=anchor_evidence,
    )


def _stamp_pr_merge_provenance(
    feature_dir: Path,
    pr_merge_commit: str,
    pr_merge_evidence: str,
) -> None:
    """Stamp the ``pr_merge_commit`` / ``pr_merge_evidence`` provenance fields.

    Each field is set-once, never overwritten. ``pr_merge_evidence`` records
    what the recorded anchor's completeness rests on — the operator's
    recorded ``--attest-first-landing-commit`` attestation, either shape
    (:data:`ANCHOR_EVIDENCE_MERGE_COMMIT_PARENT_ATTESTED` for a two-parent
    landing, :data:`ANCHOR_EVIDENCE_CORPUS_PARENT_ATTESTED` for a
    single-parent one) — so ``spec-kitty review --mode post-merge`` can
    honour it instead of consuming every recorded anchor as though it were
    proven.
    """
    try:
        meta = load_meta_fail_closed(feature_dir)
    except MissionMetaReadError as exc:
        raise PrMergeEvidenceError(f"cannot stamp {_PR_MERGE_COMMIT_FIELD} for {feature_dir.name}: meta.json is invalid ({exc}).") from exc
    if meta is None:
        raise PrMergeEvidenceError(f"cannot stamp {_PR_MERGE_COMMIT_FIELD} for {feature_dir.name}: meta.json is missing.")
    commit_stamped = bool((meta.get(_PR_MERGE_COMMIT_FIELD) or "").strip())
    evidence_stamped = bool((meta.get(_PR_MERGE_EVIDENCE_FIELD) or "").strip())
    if not commit_stamped:
        meta[_PR_MERGE_COMMIT_FIELD] = pr_merge_commit
    if not evidence_stamped:
        meta[_PR_MERGE_EVIDENCE_FIELD] = pr_merge_evidence
    if commit_stamped and evidence_stamped:
        return
    write_meta(feature_dir, meta, validate=False)


def _record_pr_merge_baseline(
    feature_dir: Path,
    repo_root: Path,
    mission_slug: str,
    merge_commit: str,
    *,
    target_ref: str | None = None,
    attest_first_landing: bool = False,
    effective_root: Path | None = None,
) -> PrMergeEvidence:
    """Record a verified PR merge as the mission's post-merge review baseline.

    The feature-dir-level writer the public mission-level seam
    (:func:`record_pr_merge_baseline_for_mission`, used by both
    ``spec-kitty accept --mode pr --merge-commit`` and ``spec-kitty migrate
    backfill-merge-commit``) delegates to, so the field is written through the
    same canonical writer (:func:`record_baseline_merge_commit`) the
    local-merge path uses, never a forked one. Verifies the evidence first
    (fail loud, no fabrication — including that the commit actually landed on
    the target branch, and that the operator's explicit first-landing
    attestation is present for EITHER landing shape), then writes
    ``baseline_merge_commit`` = the merge commit's first parent and stamps
    :data:`_PR_MERGE_COMMIT_FIELD` = the merge commit itself plus
    :data:`_PR_MERGE_EVIDENCE_FIELD` = what the anchor's completeness rests
    on, as provenance.

    Idempotent with respect to an existing baseline:
    :func:`record_baseline_merge_commit` never overwrites a recorded value,
    so a re-run against an already-recorded mission leaves it byte-stable.

    Reusing the canonical writer also stamps the ``merged_at`` completion
    marker; ``merged_commit`` is threaded through as ``evidence.pr_merge_commit``
    — the verified PR landing commit, not the local checkout's ``HEAD`` (which
    may have advanced past the PR) — while ``merged_at`` remains the recording
    time, since git alone cannot recover the true merge timestamp (tracked in
    #4277).

    *effective_root* is threaded straight through to the verification's
    declared-``target_branch`` read (:func:`verify_pr_merge_evidence`) so that
    read resolves the SAME ``meta.json`` as *feature_dir* — the write target —
    instead of, for an owned-mission worktree checkout, silently falling back
    to the primary repo's copy of the mission.
    """
    evidence = verify_pr_merge_evidence(
        repo_root,
        mission_slug,
        merge_commit,
        target_ref=target_ref,
        attest_first_landing=attest_first_landing,
        effective_root=effective_root,
    )

    try:
        meta = load_meta_fail_closed(feature_dir)
    except MissionMetaReadError as exc:
        raise PrMergeEvidenceError(f"cannot record a PR merge baseline for {feature_dir.name}: meta.json is invalid ({exc}).") from exc
    raw_mission_id = meta.get("mission_id") if meta else None
    mission_id = str(raw_mission_id).strip() if raw_mission_id else None

    # Canonical write first (the load-bearing field), provenance stamp second —
    # each write is atomic, and a baseline without provenance is still a
    # reviewable mission, while provenance without a baseline would not be.
    record_baseline_merge_commit(
        feature_dir,
        evidence.baseline_merge_commit,
        mission_id=mission_id,
        merged_commit=evidence.pr_merge_commit,
    )
    _stamp_pr_merge_provenance(feature_dir, evidence.pr_merge_commit, evidence.anchor_evidence)
    return evidence


def resolve_primary_meta_dir(
    repo_root: Path,
    mission_slug: str,
    *,
    effective_root: Path | None = None,
) -> Path:
    """Resolve the mission's PRIMARY-partition ``meta.json`` directory.

    The one placement primitive both PR-recording callers share: routes
    through the kind-aware placement seam (``PRIMARY_METADATA``) so a
    ``baseline_merge_commit`` read or write lands on the primary partition's
    ``meta.json`` — the same leg the birth-cutover stamp and the acceptance
    recording write — rather than whatever directory a kind-blind handle
    resolution happened to hand the caller.
    """
    from mission_runtime import MissionArtifactKind, placement_seam
    from specify_cli.core.owned_mission import effective_root_kwargs

    return placement_seam(repo_root, mission_slug, **effective_root_kwargs(effective_root)).read_dir(MissionArtifactKind.PRIMARY_METADATA)


def record_pr_merge_baseline_for_mission(
    repo_root: Path,
    mission_slug: str,
    merge_commit: str,
    *,
    effective_root: Path | None = None,
    target_ref: str | None = None,
    attest_first_landing: bool = False,
) -> PrMergeEvidence:
    """Record a verified PR merge as a mission's baseline, on the PRIMARY leg.

    The mission-level entry point both callers (``accept --merge-commit`` and
    ``migrate backfill-merge-commit``) share: resolves the primary
    ``meta.json`` via :func:`resolve_primary_meta_dir`, then records through
    the module-private :func:`_record_pr_merge_baseline`. *attest_first_landing*
    is the operator's explicit attestation that the supplied commit's first
    parent is the pre-landing target tip (for a two-parent landing: the merge
    was performed on the target branch; for a single-parent one: it was the
    first commit of the landing) — see :func:`verify_pr_merge_evidence`.
    *effective_root* resolves both the write leg's ``feature_dir`` AND (via
    :func:`_record_pr_merge_baseline`) the declared-``target_branch`` read the
    verification falls back to when *target_ref* is omitted, so the two never
    resolve different ``meta.json`` files for an owned-mission checkout.
    """
    feature_dir = resolve_primary_meta_dir(repo_root, mission_slug, effective_root=effective_root)
    return _record_pr_merge_baseline(
        feature_dir,
        repo_root,
        mission_slug,
        merge_commit,
        target_ref=target_ref,
        attest_first_landing=attest_first_landing,
        effective_root=effective_root,
    )


__all__ = [
    "BaselineMergeCommitError",
    "PrMergeEvidence",
    "PrMergeEvidenceError",
    "assert_baseline_merge_commit_on_target",
    "record_baseline_merge_commit",
    "record_pr_merge_baseline_for_mission",
    "resolve_primary_meta_dir",
    "verify_pr_merge_evidence",
]
