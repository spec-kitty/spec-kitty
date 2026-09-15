"""PR-merge evidence verification and recording (issue #4231).

A mission accepted through ``acceptance_mode: pr`` never passes through
``spec-kitty merge``, so its ``meta.json`` never carried
``baseline_merge_commit``. These tests pin the seam that repairs that state
from REAL git evidence only:

* :func:`verify_pr_merge_evidence` resolves the supplied commit, requires the
  mission corpus AT it and absent at its first parent (proving it is the
  landing commit — and rejecting the mission-branch-head confusion), derives
  the pre-landing target tip from that parent, and requires the commit to
  have LANDED on the target branch — presence at the commit with absence at
  the parent is first-introduction evidence, which an unmerged mission-branch
  commit satisfies just as well as a real landing, so the
  ``merge-base --is-ancestor`` membership check is what tells them apart.
* :func:`_record_pr_merge_baseline` writes ``baseline_merge_commit`` through
  the canonical writer plus the ``pr_merge_commit`` provenance field, and is
  idempotent over an already-recorded baseline.
* The landing shapes GitHub actually produces are all covered — a two-parent
  merge commit, a single-parent squash landing, a rebase-style replay, a
  staged corpus-then-implementation stack, and the internal-merge landing —
  and NONE of them yields a git-proven anchor: an internal merge merged on a
  mission branch and fast-forwarded onto the target is graph-identical to a
  merge performed on the target, so every shape is refused without the
  operator's explicit ``--attest-first-landing-commit`` attestation.

Every test here drives the real ``git`` binary, so the module carries
``git_repo`` / ``integration`` / ``non_sandbox`` and must NOT carry ``fast``
(see ``tests/architectural/test_pytest_marker_correctness.py``).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.merge.baseline import (
    ANCHOR_EVIDENCE_CORPUS_PARENT_ATTESTED,
    ANCHOR_EVIDENCE_MERGE_COMMIT_PARENT_ATTESTED,
    _PR_MERGE_COMMIT_FIELD,
    _PR_MERGE_EVIDENCE_FIELD,
    _record_pr_merge_baseline,
    _stamp_pr_merge_provenance,
    PrMergeEvidenceError,
    verify_pr_merge_evidence,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.git_repo,
    pytest.mark.non_sandbox,
]

_SLUG = "321-pr-merged-mission-01TESTTES"
_MISSION_ID = "01TESTPRMERGEEVIDENCE000000"


def _git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _write_meta(feature_dir: Path) -> None:
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_id": _MISSION_ID, "mission_slug": _SLUG}) + "\n",
        encoding="utf-8",
    )


def _pr_merged_repo(
    tmp_path: Path,
    *,
    squash: bool = False,
) -> tuple[Path, Path, str, str]:
    """Build a repo whose mission landed on main through a PR-shaped merge.

    Returns ``(repo_root, feature_dir, merge_commit, pre_merge_parent)``. The
    base commit on main predates the mission corpus; the mission branch adds
    ``kitty-specs/<slug>/``; the landing commit merges it back — a two-parent
    merge commit by default, or a single-parent squash-style commit.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.name", "PR Baseline Test")
    _git(repo_root, "config", "user.email", "pr-baseline-test@example.invalid")
    _git(repo_root, "branch", "-M", "main")
    (repo_root / "README.md").write_text("# base\n", encoding="utf-8")
    _git(repo_root, "add", "README.md")
    _git(repo_root, "commit", "-qm", "base")

    _git(repo_root, "checkout", "-qb", "kitty/mission-head")
    feature_dir = repo_root / "kitty-specs" / _SLUG
    _write_meta(feature_dir)
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-qm", "mission corpus")
    # A second commit on the mission branch, so the branch HEAD is a
    # follow-up whose parent already carries the corpus (the shape a real
    # mission branch has by the time its PR merges).
    (feature_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-qm", "mission follow-up")

    _git(repo_root, "checkout", "-q", "main")
    if squash:
        # A squash-style landing: a single-parent commit on main that
        # introduces the mission corpus whose parent lacks it.
        _git(repo_root, "merge", "--squash", "-q", "kitty/mission-head")
        _git(repo_root, "commit", "-qm", "squash-land mission")
    else:
        _git(repo_root, "merge", "--no-ff", "-qm", "Merge PR: land mission", "kitty/mission-head")
    merge_commit = _git(repo_root, "rev-parse", "HEAD").stdout.strip()
    pre_merge_parent = _git(repo_root, "rev-parse", "HEAD^1").stdout.strip()
    return repo_root, feature_dir, merge_commit, pre_merge_parent


def test_verify_two_parent_merge_commit_needs_attestation(
    tmp_path: Path,
) -> None:
    """A two-parent merge landing's anchor is the first parent — ATTESTED.

    Two parents alone do not prove the first parent is the pre-landing
    target tip: a merge performed on the target branch is graph-identical to
    an internal merge fast-forwarded onto the target (see
    ``test_internal_merge_fast_forwarded_to_target_is_the_attestation_gap``),
    so the bare call is refused and the attested call records the anchor as
    resting on that attestation, never on git proof.
    """
    repo_root, _feature_dir, merge_commit, pre_merge_parent = _pr_merged_repo(tmp_path)

    with pytest.raises(PrMergeEvidenceError, match="two parents alone do not prove"):
        verify_pr_merge_evidence(repo_root, _SLUG, merge_commit)

    evidence = verify_pr_merge_evidence(repo_root, _SLUG, merge_commit, attest_first_landing=True)

    assert evidence.pr_merge_commit == merge_commit
    assert evidence.baseline_merge_commit == pre_merge_parent
    assert evidence.anchor_evidence == ANCHOR_EVIDENCE_MERGE_COMMIT_PARENT_ATTESTED


def test_verify_accepts_short_sha_and_normalizes_to_full(
    tmp_path: Path,
) -> None:
    """A shortened SHA resolves to the full commit — the operator copies it off the PR page."""
    repo_root, _feature_dir, merge_commit, _parent = _pr_merged_repo(tmp_path)

    evidence = verify_pr_merge_evidence(repo_root, _SLUG, merge_commit[:10], attest_first_landing=True)

    assert evidence.pr_merge_commit == merge_commit


def test_verify_squash_style_landing_commit(
    tmp_path: Path,
) -> None:
    """A single-parent squash landing needs the operator's explicit attestation.

    Git cannot prove a single-parent landing's parent is the pre-landing tip
    (a squash parent IS the tip; an earlier same-PR implementation commit is
    NOT — graph-identical), so the bare call is refused and the attested call
    records the anchor as resting on that attestation, never on git proof.
    """
    repo_root, _feature_dir, merge_commit, pre_merge_parent = _pr_merged_repo(tmp_path, squash=True)

    with pytest.raises(PrMergeEvidenceError, match="cannot prove"):
        verify_pr_merge_evidence(repo_root, _SLUG, merge_commit)

    evidence = verify_pr_merge_evidence(repo_root, _SLUG, merge_commit, attest_first_landing=True)

    assert evidence.baseline_merge_commit == pre_merge_parent
    assert evidence.anchor_evidence == ANCHOR_EVIDENCE_CORPUS_PARENT_ATTESTED


def test_verify_rejects_unknown_commit(tmp_path: Path) -> None:
    repo_root, _feature_dir, _merge_commit, _parent = _pr_merged_repo(tmp_path)

    with pytest.raises(PrMergeEvidenceError, match="cannot resolve"):
        verify_pr_merge_evidence(repo_root, _SLUG, "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef")


def test_verify_rejects_empty_commit(tmp_path: Path) -> None:
    repo_root, _feature_dir, _merge_commit, _parent = _pr_merged_repo(tmp_path)

    with pytest.raises(PrMergeEvidenceError, match="no merge commit"):
        verify_pr_merge_evidence(repo_root, _SLUG, "   ")


def test_verify_rejects_commit_without_the_mission_corpus(tmp_path: Path) -> None:
    """A real commit that never carried this mission is not merge evidence for it."""
    repo_root, _feature_dir, _merge_commit, pre_merge_parent = _pr_merged_repo(tmp_path)
    # The pre-merge parent is a real commit — but it predates the mission.
    with pytest.raises(PrMergeEvidenceError, match="does not carry"):
        verify_pr_merge_evidence(repo_root, _SLUG, pre_merge_parent)


def test_verify_rejects_the_mission_branch_head(tmp_path: Path) -> None:
    """The mission branch HEAD carries the corpus — and so does ITS parent.

    Supplying the mission head instead of the PR merge commit would anchor the
    dead-code diff at the wrong tip (only the follow-up commit's delta) and
    silently skip the mission's own earlier additions, so the
    parent-carries-corpus check refuses it. (A single-commit mission branch's
    first commit is graph-identical to a squash landing — a new commit whose
    parent lacks the corpus — but it has NOT landed on the target branch, so
    the landing check refuses it; see
    :func:`test_verify_rejects_unmerged_specify_only_branch_commit`.)
    """
    repo_root, _feature_dir, _merge_commit, _parent = _pr_merged_repo(tmp_path)
    mission_head = _git(repo_root, "rev-parse", "kitty/mission-head").stdout.strip()

    with pytest.raises(PrMergeEvidenceError, match="not the landing commit"):
        verify_pr_merge_evidence(repo_root, _SLUG, mission_head)


def _unmerged_specify_repo(tmp_path: Path) -> tuple[Path, Path, str]:
    """The #4231 monitor repro: a Specify-only commit on an UNMERGED branch.

    ``main`` carries a base commit; the mission branch adds exactly one commit
    introducing only ``kitty-specs/<slug>/meta.json``; the branch is never
    merged. Presence of the corpus at that commit and absence at its parent
    prove first introduction — but not landing, which is exactly the
    distinction the verifier must make.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.name", "PR Baseline Test")
    _git(repo_root, "config", "user.email", "pr-baseline-test@example.invalid")
    _git(repo_root, "branch", "-M", "main")
    (repo_root / "README.md").write_text("# base\n", encoding="utf-8")
    _git(repo_root, "add", "README.md")
    _git(repo_root, "commit", "-qm", "base")

    _git(repo_root, "checkout", "-qb", "kitty/mission-unmerged")
    feature_dir = repo_root / "kitty-specs" / _SLUG
    _write_meta(feature_dir)
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-qm", "Specify: mission corpus only")
    specify_commit = _git(repo_root, "rev-parse", "HEAD").stdout.strip()

    _git(repo_root, "checkout", "-q", "main")
    return repo_root, feature_dir, specify_commit


def test_verify_rejects_unmerged_specify_only_branch_commit(tmp_path: Path) -> None:
    """First introduction is not landing: an unmerged Specify commit is refused.

    The commit carries the corpus, its parent lacks it — every
    first-introduction check passes — but it is not an ancestor of the target
    branch, so it is not merge evidence. Recording it would anchor the
    dead-code scan at a tip the mission never reached.
    """
    repo_root, _feature_dir, specify_commit = _unmerged_specify_repo(tmp_path)

    with pytest.raises(PrMergeEvidenceError, match="not on target branch"):
        verify_pr_merge_evidence(repo_root, _SLUG, specify_commit)


def test_record_refuses_unmerged_specify_commit_without_writing(tmp_path: Path) -> None:
    """The recording seam refuses the unmerged Specify commit and writes nothing.

    The meta.json lives on the unmerged branch (absent from the ``main``
    checkout), so a refusal must leave the branch's copy untouched — verified
    by reading it through git, not the (absent) working-tree path.
    """
    repo_root, feature_dir, specify_commit = _unmerged_specify_repo(tmp_path)
    before = _git(repo_root, "show", f"kitty/mission-unmerged:kitty-specs/{_SLUG}/meta.json").stdout

    with pytest.raises(PrMergeEvidenceError, match="not on target branch"):
        _record_pr_merge_baseline(feature_dir, repo_root, _SLUG, specify_commit)

    after = _git(repo_root, "show", f"kitty/mission-unmerged:kitty-specs/{_SLUG}/meta.json").stdout
    assert after == before


def _rebase_landed_repo(tmp_path: Path) -> tuple[Path, Path, str, str, str]:
    """A rebase-style PR landing: branch commits replayed onto the target tip.

    Returns ``(repo_root, feature_dir, replayed_corpus_commit,
    pre_landing_tip, original_corpus_commit)``. The branch carries
    [corpus][follow-up]; it lands by replaying onto ``main`` (the rebase-merge
    shape), so the replayed corpus commit's first parent IS the pre-landing
    ``main`` tip — while the ORIGINAL branch commit, graph-identical in
    content, never landed.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.name", "PR Baseline Test")
    _git(repo_root, "config", "user.email", "pr-baseline-test@example.invalid")
    _git(repo_root, "branch", "-M", "main")
    (repo_root / "README.md").write_text("# base\n", encoding="utf-8")
    _git(repo_root, "add", "README.md")
    _git(repo_root, "commit", "-qm", "base")

    _git(repo_root, "checkout", "-qb", "kitty/mission-head")
    feature_dir = repo_root / "kitty-specs" / _SLUG
    _write_meta(feature_dir)
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-qm", "mission corpus")
    original_corpus = _git(repo_root, "rev-parse", "HEAD").stdout.strip()
    (feature_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-qm", "mission follow-up")

    # Advance main past the fork point so the replay is a real rebase (the
    # branch commits are re-created on the new tip), not a fast-forward.
    _git(repo_root, "checkout", "-q", "main")
    (repo_root / "unrelated.txt").write_text("other PR\n", encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-qm", "unrelated work lands first")
    pre_landing_tip = _git(repo_root, "rev-parse", "main").stdout.strip()

    # Rebase-merge landing: replay the branch onto the new main tip, then
    # fast-forward main to the replayed commits.
    _git(repo_root, "checkout", "-q", "-b", "replay", "kitty/mission-head")
    _git(repo_root, "rebase", "main")
    _git(repo_root, "checkout", "-q", "main")
    _git(repo_root, "merge", "--ff-only", "-q", "replay")
    replayed_corpus = _git(repo_root, "rev-parse", "main~1").stdout.strip()
    _git(repo_root, "branch", "-qD", "replay")
    return repo_root, feature_dir, replayed_corpus, pre_landing_tip, original_corpus


def test_verify_accepts_rebase_style_landing(tmp_path: Path) -> None:
    """A rebase-merge landing verifies at the replayed corpus commit — attested.

    The replay put the corpus commit directly onto the old ``main`` tip, so
    its first parent IS the pre-landing target tip — but the commit is
    single-parent, so git cannot prove that (an impl-before-corpus replay is
    graph-identical), and the operator's attestation is required. The
    follow-up commit on top of it is refused either way (its parent carries
    the corpus).
    """
    repo_root, _feature_dir, replayed_corpus, pre_landing_tip, _orig = _rebase_landed_repo(tmp_path)

    with pytest.raises(PrMergeEvidenceError, match="cannot prove"):
        verify_pr_merge_evidence(repo_root, _SLUG, replayed_corpus)

    evidence = verify_pr_merge_evidence(repo_root, _SLUG, replayed_corpus, attest_first_landing=True)

    assert evidence.pr_merge_commit == replayed_corpus
    assert evidence.baseline_merge_commit == pre_landing_tip
    assert evidence.anchor_evidence == ANCHOR_EVIDENCE_CORPUS_PARENT_ATTESTED

    follow_up = _git(repo_root, "rev-parse", "main").stdout.strip()
    with pytest.raises(PrMergeEvidenceError, match="not the landing commit"):
        verify_pr_merge_evidence(repo_root, _SLUG, follow_up, attest_first_landing=True)


def test_verify_rejects_original_branch_commit_after_rebase_landing(tmp_path: Path) -> None:
    """The pre-replay branch commit is content-identical to the landing — and refused.

    Every first-introduction check passes for it (corpus at it, absent at its
    parent), but it never landed on the target branch: only the replayed
    copies did. This is the unmerged-commit distinction in its sharpest form.
    """
    repo_root, _feature_dir, _replayed, _tip, original_corpus = _rebase_landed_repo(tmp_path)

    with pytest.raises(PrMergeEvidenceError, match="not on target branch"):
        verify_pr_merge_evidence(repo_root, _SLUG, original_corpus)


def test_verify_accepts_staged_corpus_then_implementation(tmp_path: Path) -> None:
    """Corpus first, implementation after: the corpus commit is the landing.

    A staged workflow whose FIRST landed commit carries the whole mission
    corpus (``meta.json`` + spec) anchors at the pre-landing tip and covers
    the implementation commit on top of it.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.name", "PR Baseline Test")
    _git(repo_root, "config", "user.email", "pr-baseline-test@example.invalid")
    _git(repo_root, "branch", "-M", "main")
    (repo_root / "README.md").write_text("# base\n", encoding="utf-8")
    _git(repo_root, "add", "README.md")
    _git(repo_root, "commit", "-qm", "base")

    feature_dir = repo_root / "kitty-specs" / _SLUG
    _write_meta(feature_dir)
    (feature_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-qm", "Specify: full corpus")
    corpus_commit = _git(repo_root, "rev-parse", "HEAD").stdout.strip()
    pre_landing_tip = _git(repo_root, "rev-parse", "HEAD^1").stdout.strip()

    # The implementation commit lands on top of the corpus.
    (repo_root / "src_impl.py").write_text("IMPL = 1\n", encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-qm", "implement")

    # Single-parent landing: the corpus commit was the first commit of the
    # stack, so the attestation is what makes the anchor recordable.
    with pytest.raises(PrMergeEvidenceError, match="cannot prove"):
        verify_pr_merge_evidence(repo_root, _SLUG, corpus_commit)

    evidence = verify_pr_merge_evidence(repo_root, _SLUG, corpus_commit, attest_first_landing=True)

    assert evidence.baseline_merge_commit == pre_landing_tip
    assert evidence.anchor_evidence == ANCHOR_EVIDENCE_CORPUS_PARENT_ATTESTED


def test_impl_before_corpus_rebase_landing_is_the_attestation_gap(tmp_path: Path) -> None:
    """Implementation BEFORE the corpus: the one shape git alone cannot prove.

    A rebase landing whose first commits carried the mission's implementation
    outside ``kitty-specs/`` and whose corpus arrives mid-stack: the corpus
    commit's parent is an earlier same-PR commit, graph-identical to unrelated
    work that landed on the target before the PR — no git check can separate
    them. The seam therefore REFUSES the bare call (a recorded anchor there
    would silently under-scan the dead-code gate) and, under the operator's
    explicit ``--attest-first-landing-commit`` attestation, records the
    pre-corpus commit as the anchor while NAMING that it rests on an
    attestation, never on git proof — ``corpus-parent-attested`` is persisted
    so ``review --mode post-merge`` can tell it from a proven anchor. A
    regression here (silently accepting it unattested, or presenting it as
    proven) changes the published contract; the forge commit-list evidence
    that would close the gap properly is tracked in #4277.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.name", "PR Baseline Test")
    _git(repo_root, "config", "user.email", "pr-baseline-test@example.invalid")
    _git(repo_root, "branch", "-M", "main")
    (repo_root / "README.md").write_text("# base\n", encoding="utf-8")
    _git(repo_root, "add", "README.md")
    _git(repo_root, "commit", "-qm", "base")

    _git(repo_root, "checkout", "-qb", "kitty/mission-impl-first")
    # Implementation lands FIRST, outside kitty-specs/ — invisible to every
    # corpus check.
    (repo_root / "src_impl.py").write_text("IMPL = 1\n", encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-qm", "implement first")
    # The corpus arrives second — its parent carries no kitty-specs content.
    feature_dir = repo_root / "kitty-specs" / _SLUG
    _write_meta(feature_dir)
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-qm", "Specify: corpus second")

    # Rebase-merge landing: replay onto main and fast-forward.
    _git(repo_root, "checkout", "-q", "main")
    _git(repo_root, "checkout", "-q", "-b", "replay", "kitty/mission-impl-first")
    _git(repo_root, "rebase", "main")
    _git(repo_root, "checkout", "-q", "main")
    _git(repo_root, "merge", "--ff-only", "-q", "replay")
    _git(repo_root, "branch", "-qD", "replay")
    replayed_corpus = _git(repo_root, "rev-parse", "main").stdout.strip()
    replayed_impl = _git(repo_root, "rev-parse", "main~1").stdout.strip()
    true_pre_landing_tip = _git(repo_root, "rev-parse", "main~2").stdout.strip()
    assert replayed_impl != true_pre_landing_tip  # the gap: impl precedes the corpus

    # The bare call is refused: git cannot prove the corpus commit's parent is
    # the pre-landing tip, and recording it unattested would anchor the
    # dead-code scan at the wrong tip (an under-scan presented as "verified").
    with pytest.raises(PrMergeEvidenceError, match="cannot prove"):
        verify_pr_merge_evidence(repo_root, _SLUG, replayed_corpus)

    # Under the operator's explicit attestation the anchor IS recorded — as
    # the pre-CORPUS commit (an earlier same-PR commit), which is precisely
    # the documented gap — and the persisted evidence class names the
    # attestation, never a git proof. Complete evidence would need the PR's
    # commit list (#4277).
    evidence = verify_pr_merge_evidence(repo_root, _SLUG, replayed_corpus, attest_first_landing=True)
    assert evidence.pr_merge_commit == replayed_corpus
    assert evidence.baseline_merge_commit == replayed_impl
    assert evidence.baseline_merge_commit != true_pre_landing_tip
    assert evidence.anchor_evidence == ANCHOR_EVIDENCE_CORPUS_PARENT_ATTESTED

    # The recording persists the evidence class alongside the anchor, so the
    # review consumer can tell an attested anchor from a proven one.
    recorded = _record_pr_merge_baseline(feature_dir, repo_root, _SLUG, replayed_corpus, attest_first_landing=True)
    assert recorded.anchor_evidence == ANCHOR_EVIDENCE_CORPUS_PARENT_ATTESTED
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["baseline_merge_commit"] == replayed_impl
    assert meta[_PR_MERGE_COMMIT_FIELD] == replayed_corpus
    assert meta[_PR_MERGE_EVIDENCE_FIELD] == ANCHOR_EVIDENCE_CORPUS_PARENT_ATTESTED


def test_internal_merge_fast_forwarded_to_target_is_the_attestation_gap(
    tmp_path: Path,
) -> None:
    """The internal-merge landing: two parents that prove nothing.

    The counterexample from the #4231 fix-round review: main base B; the
    implementation branch adds ``impl.py`` at I; a sibling corpus branch adds
    ``kitty-specs/<slug>/meta.json`` at C; C is merged INTO the
    implementation branch producing the two-parent merge M (first parent I);
    main is then fast-forwarded to M. Post-landing git history is
    graph-identical to a merge performed on the target branch, yet M's first
    parent is the implementation commit I — anchoring there omits ``impl.py``
    from the scan range. The bare call must therefore be refused (never
    stamped as a git-proven ``merge-commit-parent`` anchor), and only the
    operator's explicit attestation records it, naming the attestation.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.name", "PR Baseline Test")
    _git(repo_root, "config", "user.email", "pr-baseline-test@example.invalid")
    _git(repo_root, "branch", "-M", "main")
    (repo_root / "README.md").write_text("# base\n", encoding="utf-8")
    _git(repo_root, "add", "README.md")
    _git(repo_root, "commit", "-qm", "base")

    # Implementation branch: mission work OUTSIDE kitty-specs/, invisible to
    # every corpus check.
    _git(repo_root, "checkout", "-qb", "kitty/mission-impl")
    (repo_root / "impl.py").write_text("IMPL = 1\n", encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-qm", "implement")
    impl_commit = _git(repo_root, "rev-parse", "HEAD").stdout.strip()

    # Sibling corpus branch: only the mission corpus.
    _git(repo_root, "checkout", "-qb", "kitty/mission-corpus", "main")
    feature_dir = repo_root / "kitty-specs" / _SLUG
    _write_meta(feature_dir)
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-qm", "Specify: corpus")

    # Internal merge: the corpus branch is merged INTO the implementation
    # branch (first parent = the implementation commit), then main is
    # fast-forwarded to the merge — graph-identical to a PR merge performed
    # on the target branch.
    _git(repo_root, "checkout", "-q", "kitty/mission-impl")
    _git(repo_root, "merge", "--no-ff", "-qm", "Merge corpus into implementation", "kitty/mission-corpus")
    internal_merge = _git(repo_root, "rev-parse", "HEAD").stdout.strip()
    _git(repo_root, "checkout", "-q", "main")
    _git(repo_root, "merge", "--ff-only", "-q", "kitty/mission-impl")
    assert _git(repo_root, "rev-parse", "main").stdout.strip() == internal_merge
    # The gap: a scan anchored at the merge's first parent omits impl.py.
    diff_names = _git(repo_root, "diff", "--name-only", f"{internal_merge}^1..main").stdout.split()
    assert "impl.py" not in diff_names

    # The bare call is refused — never recorded as a git-proven anchor.
    with pytest.raises(PrMergeEvidenceError, match="two parents alone do not prove"):
        verify_pr_merge_evidence(repo_root, _SLUG, internal_merge, target_ref="main")

    # Under the operator's explicit attestation the anchor IS recorded — as
    # the implementation commit, which is precisely the documented gap — and
    # the persisted evidence class names the attestation, never a git proof.
    evidence = verify_pr_merge_evidence(repo_root, _SLUG, internal_merge, target_ref="main", attest_first_landing=True)
    assert evidence.pr_merge_commit == internal_merge
    assert evidence.baseline_merge_commit == impl_commit
    assert evidence.anchor_evidence == ANCHOR_EVIDENCE_MERGE_COMMIT_PARENT_ATTESTED

    recorded = _record_pr_merge_baseline(feature_dir, repo_root, _SLUG, internal_merge, target_ref="main", attest_first_landing=True)
    assert recorded.anchor_evidence == ANCHOR_EVIDENCE_MERGE_COMMIT_PARENT_ATTESTED
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["baseline_merge_commit"] == impl_commit
    assert meta[_PR_MERGE_COMMIT_FIELD] == internal_merge
    assert meta[_PR_MERGE_EVIDENCE_FIELD] == ANCHOR_EVIDENCE_MERGE_COMMIT_PARENT_ATTESTED


def test_verify_rejects_meta_landing_after_staged_siblings(tmp_path: Path) -> None:
    """A corpus staged spec-first, meta-last: the meta commit is refused.

    ``spec.md`` landed in an earlier commit, so the ``meta.json``-introducing
    commit's first parent already carries part of the mission corpus. A diff
    anchored there would skip the spec — so this is a refusal, never a
    guessed earlier anchor (the operator supplies the commit that introduced
    the corpus, or the mission re-lands whole).
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.name", "PR Baseline Test")
    _git(repo_root, "config", "user.email", "pr-baseline-test@example.invalid")
    _git(repo_root, "branch", "-M", "main")
    (repo_root / "README.md").write_text("# base\n", encoding="utf-8")
    _git(repo_root, "add", "README.md")
    _git(repo_root, "commit", "-qm", "base")

    feature_dir = repo_root / "kitty-specs" / _SLUG
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-qm", "Specify: spec only")
    spec_commit = _git(repo_root, "rev-parse", "HEAD").stdout.strip()

    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_id": _MISSION_ID, "mission_slug": _SLUG}) + "\n",
        encoding="utf-8",
    )
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-qm", "meta lands later")
    meta_commit = _git(repo_root, "rev-parse", "HEAD").stdout.strip()

    # The spec-only commit does not carry meta.json at all.
    with pytest.raises(PrMergeEvidenceError, match="does not carry"):
        verify_pr_merge_evidence(repo_root, _SLUG, spec_commit)
    # The meta.json commit's parent already carries the mission directory.
    with pytest.raises(PrMergeEvidenceError, match="staged corpus"):
        verify_pr_merge_evidence(repo_root, _SLUG, meta_commit)


def test_verify_explicit_target_ref(tmp_path: Path) -> None:
    """An explicit target branch (any rev-parse form) is honored verbatim."""
    repo_root, _feature_dir, merge_commit, pre_merge_parent = _pr_merged_repo(tmp_path)

    for ref in ("main", "refs/heads/main"):
        evidence = verify_pr_merge_evidence(repo_root, _SLUG, merge_commit, target_ref=ref, attest_first_landing=True)
        assert evidence.baseline_merge_commit == pre_merge_parent


def test_verify_honors_mission_declared_target_branch(tmp_path: Path) -> None:
    """The mission's declared ``target_branch`` is the default landing target.

    A landing on a non-primary branch ``release`` verifies without any
    explicit ``--target-branch`` because the mission meta declares it — and
    the SAME commit is refused when the meta instead declares ``main`` (the
    declared target wins over the repository's primary branch).
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.name", "PR Baseline Test")
    _git(repo_root, "config", "user.email", "pr-baseline-test@example.invalid")
    _git(repo_root, "branch", "-M", "main")
    (repo_root / "README.md").write_text("# base\n", encoding="utf-8")
    _git(repo_root, "add", "README.md")
    _git(repo_root, "commit", "-qm", "base")
    _git(repo_root, "checkout", "-qb", "release")

    feature_dir = repo_root / "kitty-specs" / _SLUG
    _write_meta(feature_dir)
    _meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    _meta["target_branch"] = "release"
    (feature_dir / "meta.json").write_text(json.dumps(_meta) + "\n", encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-qm", "land on release")
    landing = _git(repo_root, "rev-parse", "release").stdout.strip()
    pre_release_tip = _git(repo_root, "rev-parse", "release^1").stdout.strip()

    # Single-parent landing on the declared branch: recordable under the
    # operator's first-landing attestation (git cannot prove the parent is
    # the pre-landing tip for this shape).
    evidence = verify_pr_merge_evidence(repo_root, _SLUG, landing, attest_first_landing=True)
    assert evidence.baseline_merge_commit == pre_release_tip
    assert evidence.anchor_evidence == ANCHOR_EVIDENCE_CORPUS_PARENT_ATTESTED

    # Same commit, mission now declaring main: refused — the declared target
    # is the landing target, not whatever branch happens to hold the commit.
    # (Fires at the target-branch check, before any attestation is consulted.)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_id": _MISSION_ID, "mission_slug": _SLUG, "target_branch": "main"}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(PrMergeEvidenceError, match="not on target branch 'main'"):
        verify_pr_merge_evidence(repo_root, _SLUG, landing, attest_first_landing=True)


def test_verify_rejects_unknown_target_branch(tmp_path: Path) -> None:
    """A target branch that does not exist locally is its own clean refusal."""
    repo_root, _feature_dir, merge_commit, _parent = _pr_merged_repo(tmp_path)

    with pytest.raises(PrMergeEvidenceError, match="cannot resolve"):
        verify_pr_merge_evidence(repo_root, _SLUG, merge_commit, target_ref="no-such-branch")


@pytest.mark.parametrize("bogus_target", ["", "   ", "--evil", "-b"])
def test_verify_rejects_malformed_target_ref(tmp_path: Path, bogus_target: str) -> None:
    """Shape guard: an empty or option-shaped target branch never reaches git."""
    repo_root, _feature_dir, merge_commit, _parent = _pr_merged_repo(tmp_path)

    with pytest.raises(PrMergeEvidenceError, match="not a branch name|is empty"):
        verify_pr_merge_evidence(repo_root, _SLUG, merge_commit, target_ref=bogus_target)


def test_record_writes_baseline_and_provenance(tmp_path: Path) -> None:
    repo_root, feature_dir, merge_commit, pre_merge_parent = _pr_merged_repo(tmp_path)

    evidence = _record_pr_merge_baseline(feature_dir, repo_root, _SLUG, merge_commit, attest_first_landing=True)

    assert evidence.baseline_merge_commit == pre_merge_parent
    assert evidence.anchor_evidence == ANCHOR_EVIDENCE_MERGE_COMMIT_PARENT_ATTESTED
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["baseline_merge_commit"] == pre_merge_parent
    assert meta[_PR_MERGE_COMMIT_FIELD] == merge_commit
    assert meta[_PR_MERGE_EVIDENCE_FIELD] == ANCHOR_EVIDENCE_MERGE_COMMIT_PARENT_ATTESTED


def test_record_is_idempotent_and_set_once(tmp_path: Path) -> None:
    """A re-run never overwrites a recorded baseline or provenance stamp."""
    repo_root, feature_dir, merge_commit, pre_merge_parent = _pr_merged_repo(tmp_path)
    _record_pr_merge_baseline(feature_dir, repo_root, _SLUG, merge_commit, attest_first_landing=True)

    # Re-running with the same verified commit changes nothing.
    _record_pr_merge_baseline(feature_dir, repo_root, _SLUG, merge_commit, attest_first_landing=True)
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["baseline_merge_commit"] == pre_merge_parent
    assert meta[_PR_MERGE_COMMIT_FIELD] == merge_commit
    assert meta[_PR_MERGE_EVIDENCE_FIELD] == ANCHOR_EVIDENCE_MERGE_COMMIT_PARENT_ATTESTED

    # An already-recorded baseline is never replaced, even by a fresh call
    # whose verification would derive a different value (set-once semantics of
    # the canonical writer, which this seam must not bypass).
    meta["baseline_merge_commit"] = "cafe000000000000000000000000000000000000"
    meta[_PR_MERGE_COMMIT_FIELD] = "f00d0000000000000000000000000000000000000"
    meta[_PR_MERGE_EVIDENCE_FIELD] = "faca000000000000000000000000000000000000"
    (feature_dir / "meta.json").write_text(json.dumps(meta) + "\n", encoding="utf-8")
    _record_pr_merge_baseline(feature_dir, repo_root, _SLUG, merge_commit, attest_first_landing=True)
    meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["baseline_merge_commit"] == "cafe000000000000000000000000000000000000"
    assert meta[_PR_MERGE_COMMIT_FIELD] == "f00d0000000000000000000000000000000000000"
    assert meta[_PR_MERGE_EVIDENCE_FIELD] == "faca000000000000000000000000000000000000"


def test_record_refuses_unverifiable_commit_without_writing(tmp_path: Path) -> None:
    """No fabrication: an unverifiable SHA leaves meta.json untouched."""
    repo_root, feature_dir, _merge_commit, _parent = _pr_merged_repo(tmp_path)
    before = (feature_dir / "meta.json").read_text(encoding="utf-8")

    with pytest.raises(PrMergeEvidenceError):
        _record_pr_merge_baseline(feature_dir, repo_root, _SLUG, "0123456789abcdef" * 5)

    assert (feature_dir / "meta.json").read_text(encoding="utf-8") == before


@pytest.mark.parametrize("bogus", ["--help", "HEAD", "main", "kitty/mission-head", "z9"])
def test_verify_rejects_non_sha_input_before_any_git_run(tmp_path: Path, bogus: str) -> None:
    """Shape guard: a non-hex value never reaches a git argument list.

    A value beginning with ``-`` would be parsed as a git option; a ref name
    is not the commit SHA an operator copied off a merged PR. Both are
    refused before any subprocess runs (the repo root need not even exist).
    """
    repo_root = tmp_path / "not-even-a-repo"
    repo_root.mkdir()

    with pytest.raises(PrMergeEvidenceError, match="is not a commit SHA"):
        verify_pr_merge_evidence(repo_root, _SLUG, bogus)


def test_verify_refuses_unreadable_declared_target_branch(tmp_path: Path) -> None:
    """A corrupt working ``meta.json`` is a clean refusal at target resolution.

    The git checks read the COMMITTED corpus, so they all pass; the declared
    ``target_branch`` read is the first working-tree read, and a corrupt
    ``meta.json`` there must refuse loudly (never guess a target) — the
    mission-declared target is what the landing check runs against.
    """
    repo_root, feature_dir, merge_commit, _parent = _pr_merged_repo(tmp_path)
    (feature_dir / "meta.json").write_text("{ not valid json", encoding="utf-8")

    with pytest.raises(PrMergeEvidenceError, match="cannot read mission .* declared target branch"):
        verify_pr_merge_evidence(repo_root, _SLUG, merge_commit)


def test_verify_rejects_option_shaped_declared_target_branch(tmp_path: Path) -> None:
    """A declared ``target_branch`` that looks like a git option never reaches git."""
    repo_root, feature_dir, merge_commit, _parent = _pr_merged_repo(tmp_path)
    _meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    _meta["target_branch"] = "--evil"
    (feature_dir / "meta.json").write_text(json.dumps(_meta) + "\n", encoding="utf-8")

    with pytest.raises(PrMergeEvidenceError, match="declared target_branch '--evil' is not a branch name"):
        verify_pr_merge_evidence(repo_root, _SLUG, merge_commit)


def test_record_refuses_corrupt_working_meta_without_writing(tmp_path: Path) -> None:
    """A corrupt working ``meta.json`` fails the recording after verification.

    The git evidence verifies (an explicit target skips the declared-target
    read), but the recording's own working-meta read is fail-closed: nothing
    is written, and the operator sees the corrupt-file reason.
    """
    repo_root, feature_dir, merge_commit, _parent = _pr_merged_repo(tmp_path)
    (feature_dir / "meta.json").write_text("{ not valid json", encoding="utf-8")

    with pytest.raises(PrMergeEvidenceError, match="cannot record a PR merge baseline"):
        _record_pr_merge_baseline(feature_dir, repo_root, _SLUG, merge_commit, target_ref="main", attest_first_landing=True)
    assert (feature_dir / "meta.json").read_text(encoding="utf-8") == "{ not valid json"


def test_record_refuses_missing_working_meta_at_the_stamp(tmp_path: Path) -> None:
    """A legacy mission whose working ``meta.json`` vanished refuses at the stamp.

    With no ``mission_id`` the canonical writer soft-warns (legacy lane), so
    the refusal the operator sees is the provenance stamp's own fail-closed
    missing-file error — the recording never silently proceeds without the
    provenance pair.
    """
    repo_root, feature_dir, merge_commit, _parent = _pr_merged_repo(tmp_path)
    # Legacy: the committed corpus carries no mission_id, and the working
    # copy is deleted outright after the commit.
    _meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    _meta.pop("mission_id", None)
    (feature_dir / "meta.json").write_text(json.dumps(_meta) + "\n", encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-qm", "legacy meta")
    _git(repo_root, "rev-parse", "HEAD")  # corpus still committed for the git checks
    (feature_dir / "meta.json").unlink()

    with pytest.raises(PrMergeEvidenceError, match="meta.json is missing"):
        _record_pr_merge_baseline(feature_dir, repo_root, _SLUG, merge_commit, target_ref="main", attest_first_landing=True)


def test_stamp_refuses_invalid_working_meta(tmp_path: Path) -> None:
    """The provenance stamp alone is fail-closed on a corrupt ``meta.json``."""
    repo_root, feature_dir, _merge_commit, _parent = _pr_merged_repo(tmp_path)
    (feature_dir / "meta.json").write_text("[ not a json object", encoding="utf-8")

    with pytest.raises(PrMergeEvidenceError, match=f"cannot stamp {_PR_MERGE_COMMIT_FIELD}"):
        _stamp_pr_merge_provenance(feature_dir, _merge_commit, "corpus-parent-attested")
