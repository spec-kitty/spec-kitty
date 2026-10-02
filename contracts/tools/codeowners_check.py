"""CODEOWNERS check for the contracts tree (spec FR-023).

Reads ``.github/CODEOWNERS`` under ``--root`` (the repository root) and fails when:

* ``RULE_MISSING``: no rule is aimed at the contracts tree (no pattern starts with ``contracts``).
* ``PATTERN_DOES_NOT_COVER_MODULE``: a contracts rule exists but the last-matching-rule resolution
  finds no rule covering ``contracts/mission-status/`` (or another module found under the root).
* ``HANDLE_MISSING``: the rule that decides ownership of a module (the last matching rule, as
  GitHub resolves it) does not name every handle in :data:`REQUIRED_HANDLES`.

It cannot do its job (exit 2) when the file is absent (``FILE_MISSING``), holds no rule
(``ZERO_RULES``), or, in a git checkout whose top level is ``--root``, is not tracked
(``NOT_TRACKED``: ignored, or never added), because a CODEOWNERS file that git does not carry would
pass every content check and never reach a reviewer. Review through this file is advisory: nothing
on GitHub enforces it today. Output ``CONTRACT-CHECK codeowners_check: <CODE>: <file>: <detail>`` per
violation and a last ``counts: rules=N`` line; exit 0 pass, 1 violation, 2 cannot do its job.

Pattern matching follows CODEOWNERS rather than ``.gitignore``: ``/dir/`` and ``/dir/**`` own
everything below, ``/dir/*`` owns only the files directly in it, a pattern with no slash matches at
any depth.

Run as a bare script (``python contracts/tools/codeowners_check.py [--root DIR]``). Standard
library only; imports nothing from ``tests/`` or ``scripts/``.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

CHECK_NAME = "codeowners_check"
CODEOWNERS = Path(".github") / "CODEOWNERS"
REQUIRED_HANDLES: tuple[str, ...] = ("@stijn-dejongh", "@MOES-Media")
CONTRACTS_PREFIX = "contracts"
DEFAULT_MODULE = "mission-status"
ROOT_DOCUMENT = "openapi.yaml"
NON_MODULE_DIRECTORIES = frozenset({"_shared", "fixtures", "gradle", "tools", "build", "node_modules"})


@dataclass(frozen=True)
class Finding:
    code: str
    subject: str
    detail: str

    def render(self) -> str:
        return f"CONTRACT-CHECK {CHECK_NAME}: {self.code}: {self.subject}: {self.detail}"


@dataclass(frozen=True)
class Rule:
    pattern: str
    owners: tuple[str, ...]


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)
    blocked: list[Finding] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=lambda: {"rules": 0})

    @property
    def exit_code(self) -> int:
        if self.blocked:
            return 2
        return 1 if self.findings else 0

    def counts_line(self) -> str:
        return "counts: " + " ".join(f"{key}={value}" for key, value in self.counts.items())


def parse_rules(text: str) -> list[Rule]:
    rules: list[Rule] = []
    for raw in text.splitlines():
        line = raw.split(" #", 1)[0].strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        rules.append(Rule(parts[0], tuple(parts[1:])))
    return rules


def _glob(body: str) -> str:
    out: list[str] = []
    position = 0
    while position < len(body):
        char = body[position]
        if body.startswith("**/", position):
            out.append("(?:.*/)?")
            position += 3
            continue
        if body.startswith("**", position):
            out.append(".*")
            position += 2
            continue
        out.append("[^/]*" if char == "*" else "[^/]" if char == "?" else re.escape(char))
        position += 1
    return "".join(out)


def pattern_covers(pattern: str, path: str) -> bool:
    """True when a CODEOWNERS ``pattern`` owns the repository-relative file ``path``."""
    anchored = pattern.startswith("/") or "/" in pattern.rstrip("/")
    body = pattern.strip("/")
    if not body:
        return False
    last = body.rsplit("/", 1)[-1]
    descends = last == "**" or not any(token in last for token in "*?")
    tail = "(?:/.*)?" if descends else ""
    head = "" if anchored else "(?:.*/)?"
    if pattern.endswith("/"):
        tail = "/.+"
    return re.fullmatch(head + _glob(body) + tail, path) is not None


def _module_names(root: Path) -> list[str]:
    contracts = root / CONTRACTS_PREFIX
    found = (
        sorted(p.name for p in contracts.iterdir() if p.is_dir() and p.name not in NON_MODULE_DIRECTORIES and (p / ROOT_DOCUMENT).is_file())
        if contracts.is_dir()
        else []
    )
    return sorted({DEFAULT_MODULE, *found})


def _git(root: Path, *arguments: str) -> subprocess.CompletedProcess[str] | None:
    git = shutil.which("git")
    if git is None:
        return None
    return subprocess.run([git, "-C", str(root), *arguments], capture_output=True, text=True, check=False)  # noqa: S603 -- git resolved by shutil.which, fixed argument list


def _tracking_problem(root: Path) -> str | None:
    """Why git does not carry the file, when ``root`` is the top level of a git checkout; else ``None``."""
    top = _git(root, "rev-parse", "--show-toplevel")
    if top is None or top.returncode != 0 or Path(top.stdout.strip()).resolve() != root.resolve():
        return None
    listed = _git(root, "ls-files", "--", CODEOWNERS.as_posix())
    if listed is None or listed.stdout.strip():
        return None
    ignored = _git(root, "check-ignore", "-q", "--", CODEOWNERS.as_posix())
    return "ignored by a .gitignore rule" if ignored is not None and ignored.returncode == 0 else "untracked (never added to the index)"


def check(root: str | Path) -> Report:
    root = Path(root)
    report = Report()
    subject = CODEOWNERS.as_posix()
    path = root / CODEOWNERS
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        report.blocked.append(Finding("FILE_MISSING", subject, f"cannot read the file: {type(error).__name__}"))
        return report
    rules = parse_rules(text)
    report.counts["rules"] = len(rules)
    if not rules:
        report.blocked.append(Finding("ZERO_RULES", subject, "the file holds no rule"))
    problem = _tracking_problem(root)
    if problem is not None:
        report.blocked.append(Finding("NOT_TRACKED", subject, f"the file is {problem}, so git does not carry it"))
    if report.blocked:
        return report
    if not any(rule.pattern.lstrip("/").startswith(CONTRACTS_PREFIX) for rule in rules):
        report.findings.append(Finding("RULE_MISSING", subject, "no rule is aimed at the contracts tree"))
        return report
    for module in _module_names(root):
        target = f"{CONTRACTS_PREFIX}/{module}/{ROOT_DOCUMENT}"
        deciding = next((rule for rule in reversed(rules) if pattern_covers(rule.pattern, target)), None)
        if deciding is None:
            report.findings.append(Finding("PATTERN_DOES_NOT_COVER_MODULE", subject, f"no rule covers {CONTRACTS_PREFIX}/{module}/"))
            continue
        owned = {owner.lower() for owner in deciding.owners}
        for handle in REQUIRED_HANDLES:
            if handle.lower() not in owned:
                report.findings.append(
                    Finding("HANDLE_MISSING", subject, f"the rule '{deciding.pattern}' deciding {CONTRACTS_PREFIX}/{module}/ does not name {handle}")
                )
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check .github/CODEOWNERS covers the contracts tree with the required owners.")
    parser.add_argument("--root", default=".", help="repository root (default: .)")
    arguments = parser.parse_args(argv)
    report = check(arguments.root)
    for finding in (*report.blocked, *report.findings):
        print(finding.render())
    print(report.counts_line())
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
