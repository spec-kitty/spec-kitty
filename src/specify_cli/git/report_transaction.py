"""Opt-in report transaction over the canonical PRIMARY commit router.

Checks detect cooperative-writer races; they are not an OS-wide editor lock.
An initially pending local receipt keeps a retained failed report ineligible
for freshness, including when only HEAD or the unrelated index raced.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from uuid import uuid4

from mission_runtime import MissionArtifactKind, placement_seam

from specify_cli.analysis_inputs import collect_material_inputs
from specify_cli.analysis_report import (
    ANALYSIS_REPORT_FILENAME,
    _sha256_file,
    _split_carrier,
    parse_structured_findings,
    render_analysis_report,
    report_semantics,
    write_analysis_report,
)
from specify_cli.coordination.commit_router import commit_for_mission
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
    entries = iter(_git(root, "status", "--porcelain=v1", "-z", "--untracked-files=all").split(b"\0"))
    paths: set[str] = set()
    for entry in entries:
        if not entry:
            continue
        status = entry[:2]
        paths.add(entry[3:].decode("utf-8", "surrogateescape"))
        if b"R" in status or b"C" in status:
            paths.add(next(entries).decode("utf-8", "surrogateescape"))
    return paths


def _index(root: Path, report: str) -> tuple[bytes, ...]:
    entries = _git(root, "ls-files", "--stage", "-v", "-z").split(b"\0")
    result = []
    for entry in entries:
        if not entry:
            continue
        header, path = entry.split(b"\t", 1)
        if header[:1] != b"H" or header.split()[-1] != b"0":
            raise ValueError("Unsupported index flags, sparse entry or unresolved conflict")
        if path.decode("utf-8", "surrogateescape") != report:
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


def record_report_transaction(*, repo_root: Path, feature_dir: Path, body: str, analyzer_agent: str | None, target_branch: str) -> dict[str, object]:
    """Record only the report; never reset or restore concurrent operator state."""
    report = feature_dir / ANALYSIS_REPORT_FILENAME
    relative = report.relative_to(repo_root).as_posix()
    message = f"docs(record-analysis): record analysis report for mission {feature_dir.name}"
    wrote = False
    committed: str | None = None
    head: bytes | None = None
    token = uuid4().hex
    try:
        parse_structured_findings(body)
        cursor = repo_root
        for part in report.relative_to(repo_root).parts:
            cursor /= part
            if cursor.is_symlink():
                raise ValueError("Report destination contains a symlink")
        _require_idle(repo_root)
        target = placement_seam(repo_root, feature_dir.name).write_target(MissionArtifactKind.ANALYSIS_REPORT)
        if target.ref != target_branch:
            raise ValueError("Analysis report placement changed before preflight")
        preflight_commit(repo_root=repo_root, worktree_root=repo_root, target=target, message=message, paths=(report,))
        inputs = collect_material_inputs(feature_dir, repo_root)
        material_paths = {entry["path"] for entry in inputs.values()}
        dirty = _dirty_paths(repo_root)
        relevant = dirty & (material_paths | {relative})
        tracked = set(_git(repo_root, "ls-files", "-z").decode("utf-8", "surrogateescape").split("\0"))
        relevant.update(path for path in material_paths if path is not None and (repo_root / path).is_file() and path not in tracked)
        if relevant:
            return {"success": False, "commit_status": "failed_before_write", "error_code": "DIRTY_ANALYSIS_INPUT", "dirty_paths": sorted(relevant)}
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
                or report.read_text(encoding="utf-8") != existing
            ):
                raise ValueError("Repository changed during unchanged-report verification")
            return {**preview.to_dict(), "success": True, "commit_status": "unchanged", "commit_hash": None}
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
        if (
            _git(repo_root, "rev-parse", "HEAD").strip() != head
            or _index(repo_root, relative) != index
            or _working(repo_root, relative) != working
            or collect_material_inputs(feature_dir, repo_root) != inputs
        ):
            raise ValueError("Repository changed before report commit; retained report is unqualified")
        outcome = commit_for_mission(
            repo_root=repo_root,
            mission_slug=feature_dir.name,
            files=(report,),
            message=message,
            policy=ProtectionPolicy.resolve(repo_root),
            kind=MissionArtifactKind.ANALYSIS_REPORT,
            target_branch=target_branch,
        )
        if outcome.status != "committed" or outcome.commit_hash is None:
            raise ValueError(outcome.diagnostic or f"Report commit did not complete: {outcome.status}")
        committed = outcome.commit_hash
        parents = _git(repo_root, "rev-list", "--parents", "-n", "1", committed).split()
        changed = _git(repo_root, "diff-tree", "--no-commit-id", "--name-only", "-z", "-r", committed).split(b"\0")
        if (
            parents != [committed.encode(), head]
            or changed != [relative.encode(), b""]
            or _git(repo_root, "rev-parse", "HEAD").strip() != committed.encode()
            or _index(repo_root, relative) != index
            or _working(repo_root, relative) != working
            or collect_material_inputs(feature_dir, repo_root) != inputs
            or _sha256_file(report) != report_hash
            or _git(repo_root, "show", f"{committed}:{relative}") != report.read_bytes()
        ):
            raise ValueError("Post-commit verification failed; retained commit requires recovery")
        atomic_write(receipt_path, json.dumps({"state": "qualified", "report": relative, "sha256": report_hash, "commit": committed}))
        return {**result.to_dict(), "success": True, "commit_status": "committed", "commit_hash": committed}
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        if wrote and committed is None and head is not None:
            # A failing post-commit hook/router can throw after Git advanced.
            # Report the observed ref honestly; never reset it.
            try:
                observed = _git(repo_root, "rev-parse", "HEAD").strip()
                if observed != head:
                    committed = observed.decode()
            except (OSError, subprocess.CalledProcessError):
                pass
        return {
            "success": False,
            "commit_status": "committed_unqualified" if committed else "written_uncommitted" if wrote else "failed_before_write",
            "commit_hash": committed,
            "error": str(exc),
            "remediation": (
                "Preserve concurrent work, inspect the retained report and commit, reconcile material inputs, then rerun analysis and report-only recording."
            ),
        }
