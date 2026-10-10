"""Opt-in report transaction over the canonical PRIMARY commit router.

Checks detect cooperative-writer races; they are not an OS-wide editor lock.
An initially pending local receipt keeps a retained failed report ineligible
for freshness, including when only HEAD or the unrelated index raced.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4
from typing import cast

from charter.bundle import CHARTER_MD, CHARTER_YAML
from kernel.git import GitPath, IndexEntry, commit_paths, index_entries, status_entries, tracked_paths
from mission_runtime import ActionContextError, MissionArtifactKind, OwnedCheckout, placement_seam

from specify_cli.analysis_inputs import collect_material_inputs
from specify_cli.analysis_report import (
    ANALYSIS_REPORT_FILENAME,
    _sha256_file,
    _split_carrier,
    collect_input_artifact_hashes,
    parse_structured_findings,
    render_analysis_report,
    report_semantics,
    write_analysis_report,
)
from specify_cli.coordination.commit_outcome import commit_outcome_exit_code, commit_outcome_payload
from specify_cli.coordination.commit_router import CommitRouterResult, commit_for_mission
from specify_cli.core.atomic import atomic_write
from specify_cli.git.commit_helpers import preflight_commit
from specify_cli.git.protection_policy import ProtectionPolicy
from specify_cli.status import git_operation_in_progress


def _git(root: Path, *args: str) -> bytes:
    return subprocess.run(["git", "--literal-pathspecs", *args], cwd=root, check=True, capture_output=True).stdout


def _receipt_path(root: Path, token: str) -> Path:
    if not re.fullmatch(r"[0-9a-f]{32}", token):
        raise ValueError("Invalid report transaction identifier")
    git_dir = Path(_git(root, "rev-parse", "--absolute-git-dir").decode().strip())
    return git_dir / "spec-kitty-report-transactions" / f"{token}.json"


def report_is_qualified(root: Path, report: Path, token: object) -> bool:
    """Missing receipts fail closed, including reports copied to another clone."""
    if not isinstance(token, str):
        return False
    try:
        receipt = json.loads(_receipt_path(root, token).read_text())
        if not isinstance(receipt, dict):
            return False
        commit = receipt.get("commit")
        if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40,64}", commit):
            return False
        _git(root, "merge-base", "--is-ancestor", commit, "HEAD")
        return (
            receipt.get("state") == "qualified"
            and receipt.get("report") == report.relative_to(root).as_posix()
            and receipt.get("sha256") == _sha256_file(report)
            and _git(root, "show", f"{commit}:{report.relative_to(root).as_posix()}") == report.read_bytes()
        )
    except (OSError, ValueError, subprocess.CalledProcessError):
        return False


def _dirty_paths(root: Path) -> set[str]:
    paths: set[str] = set()
    for entry in status_entries(root, untracked="all"):
        paths.add(str(entry.path))
        if entry.orig_path is not None:
            paths.add(str(entry.orig_path))
    return paths


def _index(root: Path, report: str) -> tuple[IndexEntry, ...]:
    report_path = GitPath.parse(report)
    result = []
    for entry in index_entries(root, tags=True):
        if entry.tag != "H" or entry.stage != 0:
            raise ValueError("Unsupported index flags, sparse entry or unresolved conflict")
        if entry.path != report_path:
            result.append(entry)
    return tuple(result)


def _working(root: Path, report: str) -> dict[str, tuple[str, int]]:
    result = {}
    for relative in _dirty_paths(root) - {report}:
        path = root / relative
        if path.is_symlink():
            result[relative] = (str(path.readlink()), path.lstat().st_mode)
        elif path.is_file():
            result[relative] = (_sha256_file(path), path.stat().st_mode)
        elif not path.exists():
            result[relative] = ("absent", 0)
        else:
            raise ValueError("Unsupported dirty directory or submodule")
    return result


def _require_idle(root: Path) -> None:
    # Consume the canonical git-op detector (status.views) rather than
    # re-enumerating markers here, so one vocabulary governs both the
    # status-materialization guard and this transaction guard. ``sequencer``
    # (multi-commit cherry-pick/revert/rebase) was folded into that canonical
    # set so no coverage is lost by the consolidation.
    if git_operation_in_progress(root):
        raise ValueError("Active Git operation in progress")


def _matching_qualified_report(root: Path, report: Path, rendered: str) -> str | None:
    if not report.is_file():
        return None
    existing = report.read_text(encoding="utf-8")
    metadata, _ = _split_carrier(existing)
    if metadata is None or not report_is_qualified(root, report, metadata.get("report_transaction")):
        return None
    return existing if report_semantics(existing) == report_semantics(rendered) else None


def _guard_unchanged_inputs(
    *,
    repo_root: Path,
    feature_dir: Path,
    relative: str,
    head: bytes,
    index: tuple[IndexEntry, ...],
    working: dict[str, tuple[str, int]],
    inputs: dict[str, dict[str, str | None]],
    canonical_inputs: dict[str, dict[str, str | None]] | None = None,
) -> None:
    """Re-check the concurrency guard right before the commit.

    Raises ``ValueError`` the instant anything a prior snapshot captured has
    moved under us, so the retained (already-written) report is flagged
    unqualified rather than silently committed over a concurrent change.
    """
    if (
        _git(repo_root, "rev-parse", "HEAD").strip() != head
        or _index(repo_root, relative) != index
        or _working(repo_root, relative) != working
        or collect_material_inputs(feature_dir, repo_root) != inputs
        or _canonical_inputs_changed(feature_dir, repo_root, canonical_inputs)
    ):
        raise ValueError("Repository changed before report commit; retained report is unqualified")


class ReportCommitRefused(ValueError):
    """``_commit_report``'s own refusal, carrying the router's outcome (WP14 B4).

    A plain :class:`ValueError` subclass so every existing ``except
    ValueError`` catch keeps catching it unchanged -- including
    :func:`record_report_transaction`'s own broad except tuple -- while the
    attached ``outcome`` lets that caller additively surface
    ``commit_outcome_payload(outcome)`` on the failure arm too
    (contracts/commit-outcome.md rule 6), instead of discarding the typed
    result with the raise.
    """

    def __init__(self, message: str, outcome: CommitRouterResult) -> None:
        super().__init__(message)
        self.outcome = outcome


def _commit_report(
    *,
    repo_root: Path,
    feature_dir: Path,
    report: Path,
    message: str,
    target_branch: str,
    owned: OwnedCheckout | None = None,
) -> CommitRouterResult:
    """Commit *report* through the canonical router; raise on anything but a clean commit.

    Returns the router's :class:`CommitRouterResult` so the caller can both
    read ``commit_hash`` and render the per-surface outcome (WP14,
    ``contracts/commit-outcome.md``).
    """
    outcome = commit_for_mission(
        repo_root=repo_root,
        mission_slug=feature_dir.name,
        files=(report,),
        message=message,
        policy=ProtectionPolicy.resolve(repo_root),
        kind=MissionArtifactKind.ANALYSIS_REPORT,
        target_branch=target_branch,
        **({"owned": owned} if owned else {}),
    )
    # WP14 review correction (round 2, binding -- the WP13 precedent this
    # mission's spec_commit_cmd.py consumer was rejected over): the legacy
    # top-level ``status`` is only the CALLER-partition projection
    # (contract rule 4) -- a ``"committed"`` top-level status can still hide
    # a refused/errored OTHER surface in a split batch. Never derive
    # success/failure from ``status`` alone; always cross-check
    # ``commit_outcome_exit_code`` (contract rule 5) against every surface.
    if outcome.status != "committed" or outcome.commit_hash is None or commit_outcome_exit_code(outcome) != 0:
        # B4 (cycle 2 review): the OLD message -- "Report commit did not
        # complete: committed" -- was contradictory for BOTH arms below:
        # ``status`` genuinely IS "committed" in each. Name the real problem
        # instead of echoing the (correct) status back as if it were wrong.
        if outcome.status == "committed" and outcome.commit_hash is None:
            fallback = "Report commit did not complete: committed status without a resolved commit hash"
        elif outcome.status == "committed":
            fallback = "Report committed on its own surface, but a sibling surface was refused or errored"
        else:
            fallback = f"Report commit did not complete: {outcome.status}"
        raise ReportCommitRefused(outcome.diagnostic or fallback, outcome)
    return outcome


@dataclass(frozen=True)
class ReportTransactionOutcome:
    """The typed return of :func:`record_report_transaction` (WP14 B4, contracts/commit-outcome.md rule 6).

    ``payload`` is the existing JSON-serializable dict (unchanged keys/shape
    for every caller that only ever consumed the dict). ``router_result`` is
    the typed :class:`CommitRouterResult` behind the additive ``surfaces``
    payload key -- carried alongside so a text-mode caller renders through
    :func:`~specify_cli.coordination.commit_outcome.render_commit_outcome`
    directly instead of re-parsing the dict back into ``SurfaceOutcome`` /
    ``PathFate`` objects (the hand-rolled second outcome shape this ruling
    deletes from ``mission_record_analysis.py``). ``None`` when no router
    call happened (the dirty-input short-circuit) or it raised before
    producing a :class:`CommitRouterResult` (a plain non-refusal exception).
    """

    payload: dict[str, object]
    router_result: CommitRouterResult | None = None


def _owned_canonical_inputs(
    feature_dir: Path,
    repo_root: Path,
    owned: OwnedCheckout | None,
) -> dict[str, dict[str, str | None]] | None:
    """Snapshot the renderer's actual input hashes, including the canonical R charter."""
    if owned is None:
        return None
    if repo_root.resolve() != owned.owned_root:
        raise ValueError("Owned report transactions must operate in the validated checkout")
    owned.files([feature_dir / ANALYSIS_REPORT_FILENAME])
    return cast(dict[str, dict[str, str | None]], collect_input_artifact_hashes(feature_dir, repo_root))


def _canonical_inputs_changed(
    feature_dir: Path,
    repo_root: Path,
    expected: dict[str, dict[str, str | None]] | None,
) -> bool:
    return expected is not None and collect_input_artifact_hashes(feature_dir, repo_root) != expected


def _canonical_charter_dirt(owned: OwnedCheckout | None, inputs: dict[str, dict[str, str | None]] | None) -> set[str]:
    """Gate only the canonical charter actually hashed by the owned renderer."""
    if owned is None or inputs is None:
        return set()
    path = inputs["charter"]["path"]
    candidates = {Path(path).as_posix()} if path is not None else set()
    # Missing higher-priority authority is still an input: a dirty deletion
    # must not become a clean fallback to Markdown or to no charter.
    if path != CHARTER_YAML.as_posix():
        candidates.add(CHARTER_YAML.as_posix())
    if path is None:
        candidates.add(CHARTER_MD.as_posix())
    return candidates & _dirty_paths(owned.repository_root)


def record_report_transaction(
    *,
    repo_root: Path,
    feature_dir: Path,
    body: str,
    analyzer_agent: str | None,
    target_branch: str,
    owned: OwnedCheckout | None = None,
) -> ReportTransactionOutcome:
    """Record only the report; never reset or restore concurrent operator state."""
    report = feature_dir / ANALYSIS_REPORT_FILENAME
    relative = "" if owned else report.relative_to(repo_root).as_posix()
    message = f"docs(record-analysis): record analysis report for mission {feature_dir.name}"
    wrote = False
    committed: str | None = None
    head: bytes | None = None
    token = uuid4().hex
    try:
        canonical_inputs = _owned_canonical_inputs(feature_dir, repo_root, owned)
        relative = report.relative_to(repo_root).as_posix()
        parse_structured_findings(body)
        cursor = repo_root
        for part in report.relative_to(repo_root).parts:
            cursor /= part
            if cursor.is_symlink():
                raise ValueError("Report destination contains a symlink")
        _require_idle(repo_root)
        target = placement_seam(repo_root, feature_dir.name, **({"owned": owned} if owned else {})).write_target(MissionArtifactKind.ANALYSIS_REPORT)
        if target.ref != target_branch:
            raise ValueError("Analysis report placement changed before preflight")
        preflight_commit(repo_root=repo_root, worktree_root=repo_root, target=target, message=message, paths=(report,), **({"owned": owned} if owned else {}))
        inputs = collect_material_inputs(feature_dir, repo_root)
        material_paths = {entry["path"] for entry in inputs.values()}
        dirty = _dirty_paths(repo_root)
        relevant = dirty & (material_paths | {relative})
        relevant.update(_canonical_charter_dirt(owned, canonical_inputs))
        tracked = {str(path) for path in tracked_paths(repo_root)}
        relevant.update(path for path in material_paths if path is not None and (repo_root / path).is_file() and path not in tracked)
        if relevant:
            return ReportTransactionOutcome(
                {"success": False, "commit_status": "failed_before_write", "error_code": "DIRTY_ANALYSIS_INPUT", "dirty_paths": sorted(relevant)}
            )
        head = _git(repo_root, "rev-parse", "HEAD").strip()
        index = _index(repo_root, relative)
        working = _working(repo_root, relative)
        preview, rendered = render_analysis_report(
            feature_dir=feature_dir,
            repo_root=repo_root,
            body=body,
            analyzer_agent=analyzer_agent,
            material_inputs=inputs,
            transaction_id=token,
        )
        existing = _matching_qualified_report(repo_root, report, rendered)
        if existing is not None:
            if (
                _git(repo_root, "rev-parse", "HEAD").strip() != head
                or _index(repo_root, relative) != index
                or _working(repo_root, relative) != working
                or collect_material_inputs(feature_dir, repo_root) != inputs
                or _canonical_inputs_changed(feature_dir, repo_root, canonical_inputs)
                or report.read_text(encoding="utf-8") != existing
            ):
                raise ValueError("Repository changed during unchanged-report verification")
            return ReportTransactionOutcome({**preview.to_dict(), "success": True, "commit_status": "unchanged", "commit_hash": None})
        receipt_path = _receipt_path(repo_root, token)
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write(receipt_path, json.dumps({"state": "pending", "report": relative}))
        result = write_analysis_report(
            feature_dir=feature_dir, repo_root=repo_root, body=body, analyzer_agent=analyzer_agent, material_inputs=inputs, transaction_id=token
        )
        wrote = True
        report_hash = result.content_sha256
        if report_hash is None or _sha256_file(report) != report_hash:
            raise ValueError("Report changed after rendering; retained report is unqualified")
        _require_idle(repo_root)
        _guard_unchanged_inputs(
            repo_root=repo_root,
            feature_dir=feature_dir,
            relative=relative,
            head=head,
            index=index,
            working=working,
            inputs=inputs,
            canonical_inputs=canonical_inputs,
        )
        outcome = _commit_report(
            repo_root=repo_root,
            feature_dir=feature_dir,
            report=report,
            message=message,
            target_branch=target_branch,
            **({"owned": owned} if owned else {}),
        )
        committed = outcome.commit_hash
        parents = _git(repo_root, "rev-list", "--parents", "-n", "1", committed).split()
        changed = commit_paths(repo_root, committed)
        if (
            parents != [committed.encode(), head]
            or changed != (GitPath.parse(relative),)
            or _git(repo_root, "rev-parse", "HEAD").strip() != committed.encode()
            or _index(repo_root, relative) != index
            or _working(repo_root, relative) != working
            or collect_material_inputs(feature_dir, repo_root) != inputs
            or _canonical_inputs_changed(feature_dir, repo_root, canonical_inputs)
            or _sha256_file(report) != report_hash
            or _git(repo_root, "show", f"{committed}:{relative}") != report.read_bytes()
        ):
            raise ValueError("Post-commit verification failed; retained commit requires recovery")
        atomic_write(receipt_path, json.dumps({"state": "qualified", "report": relative, "sha256": report_hash, "commit": committed}))
        return ReportTransactionOutcome(
            {**result.to_dict(), "success": True, "commit_status": "committed", "commit_hash": committed, **commit_outcome_payload(outcome)},
            router_result=outcome,
        )
    except (ActionContextError, OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        if wrote and committed is None and head is not None:
            # A failing post-commit hook/router can throw after Git advanced.
            # Report the observed ref honestly; never reset it.
            try:
                observed = _git(repo_root, "rev-parse", "HEAD").strip()
                if observed != head:
                    committed = observed.decode()
            except (OSError, subprocess.CalledProcessError):
                pass
        payload: dict[str, object] = {
            "success": False,
            "commit_status": "committed_unqualified" if committed else "written_uncommitted" if wrote else "failed_before_write",
            "commit_hash": committed,
            "error": str(exc),
            "remediation": (
                "Preserve concurrent work, inspect the retained report and commit, reconcile material inputs, then rerun analysis and report-only recording."
            ),
        }
        # B4 (cycle 2 review): a ``ReportCommitRefused`` carries the router's
        # own outcome -- additively include its ``surfaces`` on the FAILURE
        # arm too, not only the success arm, so a text-mode caller can render
        # the per-surface outcome here as well.
        if isinstance(exc, ActionContextError):
            payload["error_code"] = exc.code
        refused_outcome = exc.outcome if isinstance(exc, ReportCommitRefused) else None
        if refused_outcome is not None:
            payload.update(commit_outcome_payload(refused_outcome))
        return ReportTransactionOutcome(payload, router_result=refused_outcome)
