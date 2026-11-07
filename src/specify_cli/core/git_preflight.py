"""Deterministic git preflight checks for agent and merge workflows."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import shlex
import subprocess


__all__ = [
    "GitPreflightIssue",
    "GitPreflightResult",
    "run_git_preflight",
    "build_git_preflight_failure_payload",
]


@dataclass
class GitPreflightIssue:
    """Single preflight issue with optional remediation command."""

    code: str
    check: str
    message: str
    remediation: str
    command: str | None = None

    def to_dict(self) -> dict[str, str]:
        payload = {
            "code": self.code,
            "check": self.check,
            "message": self.message,
            "remediation": self.remediation,
        }
        if self.command:
            payload["command"] = self.command
        return payload


@dataclass
class GitPreflightResult:
    """Result envelope for git preflight checks."""

    repo_root: Path
    errors: list[GitPreflightIssue] = field(default_factory=list)
    warnings: list[GitPreflightIssue] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.errors

    @property
    def first_error(self) -> GitPreflightIssue | None:
        return self.errors[0] if self.errors else None

    def remediation_commands(self) -> list[str]:
        commands: list[str] = []
        for issue in self.errors:
            if issue.command:
                commands.append(issue.command)
        return commands

    def to_dict(self) -> dict[str, object]:
        return {
            "repo_root": str(self.repo_root),
            "passed": self.passed,
            "errors": [issue.to_dict() for issue in self.errors],
            "warnings": [issue.to_dict() for issue in self.warnings],
        }


@dataclass
class _GitCommandResult:
    returncode: int
    stdout: str
    stderr: str


def _run_git(repo_root: Path, args: list[str], timeout: int = 15) -> _GitCommandResult:
    """Run git command and normalize failure shape for deterministic handling."""
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=timeout,
        )
        return _GitCommandResult(
            returncode=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
        )
    except FileNotFoundError:
        return _GitCommandResult(
            returncode=127,
            stdout="",
            stderr="git executable not found on PATH",
        )
    except subprocess.TimeoutExpired:
        return _GitCommandResult(
            returncode=124,
            stdout="",
            stderr=f"git command timed out: git {' '.join(args)}",
        )


def _is_dubious_ownership(stderr: str) -> bool:
    text = stderr.lower()
    return "dubious ownership" in text or "safe.directory" in text


def _safe_directory_command(repo_root: Path) -> str:
    return f"git config --global --add safe.directory {shlex.quote(str(repo_root))}"


def _first_line(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def run_git_preflight(
    repo_root: Path,
    *,
    check_worktree_list: bool = True,
) -> GitPreflightResult:
    """Run deterministic git preflight checks with actionable remediation."""
    root = repo_root.resolve()
    result = GitPreflightResult(repo_root=root)

    repo_check = _run_git(root, ["rev-parse", "--is-inside-work-tree"])
    if repo_check.returncode != 0 or repo_check.stdout.strip().lower() != "true":
        if _is_dubious_ownership(repo_check.stderr):
            result.errors.append(
                GitPreflightIssue(
                    code="UNTRUSTED_REPOSITORY",
                    check="repository_trust",
                    message="Git rejected repository ownership trust (safe.directory).",
                    remediation="Mark the repository as trusted for this machine.",
                    command=_safe_directory_command(root),
                )
            )
        else:
            detail = _first_line(repo_check.stderr) or "Repository is not recognized by git."
            result.errors.append(
                GitPreflightIssue(
                    code="NOT_A_GIT_REPOSITORY",
                    check="repository_presence",
                    message=f"Git repository check failed: {detail}",
                    remediation="Run command from the repository root or set SPECIFY_REPO_ROOT.",
                    command=f"cd {shlex.quote(str(root))} && git status",
                )
            )
        return result

    if check_worktree_list:
        worktree_check = _run_git(root, ["worktree", "list", "--porcelain"])
        if worktree_check.returncode != 0:
            if _is_dubious_ownership(worktree_check.stderr):
                result.errors.append(
                    GitPreflightIssue(
                        code="UNTRUSTED_REPOSITORY",
                        check="repository_trust",
                        message="Git rejected repository ownership trust while listing worktrees.",
                        remediation="Mark the repository as trusted for this machine.",
                        command=_safe_directory_command(root),
                    )
                )
            else:
                detail = _first_line(worktree_check.stderr) or "Unable to enumerate git worktrees."
                result.errors.append(
                    GitPreflightIssue(
                        code="WORKTREE_LIST_FAILED",
                        check="worktree_listing",
                        message=f"Git worktree discovery failed: {detail}",
                        remediation="Run the worktree listing command from the primary checkout root.",
                        command=f"git -C {shlex.quote(str(root))} worktree list --porcelain",
                    )
                )
            return result

    # Transport view is intentional here, not an oversight: only the exit
    # code is consulted (never the URL value) to warn that "fetch/push
    # steps may be skipped" — a push/fetch-facing question, not identity.
    # #111's raw-config criterion applies to identity/slug sites only;
    # triaged and left as-is in spec-kitty#113.
    origin_check = _run_git(root, ["remote", "get-url", "origin"])
    if origin_check.returncode != 0:
        result.warnings.append(
            GitPreflightIssue(
                code="MISSING_ORIGIN_REMOTE",
                check="remote_origin",
                message="Remote 'origin' is not configured; fetch/push steps may be skipped.",
                remediation="Configure origin if remote sync is required.",
                command=f"git -C {shlex.quote(str(root))} remote add origin <url>",
            )
        )

    return result


def build_git_preflight_failure_payload(
    preflight: GitPreflightResult,
    *,
    command_name: str,
) -> dict[str, object]:
    """Build deterministic JSON payload for preflight failures."""
    primary = preflight.first_error
    message = primary.message if primary else "Git preflight failed."
    return {
        "error_code": "GIT_PREFLIGHT_FAILED",
        "error": message,
        "command": command_name,
        "repo_root": str(preflight.repo_root),
        "preflight": preflight.to_dict(),
        "remediation": preflight.remediation_commands(),
    }
