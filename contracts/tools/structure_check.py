"""Structure check for the contracts README and each module CHANGELOG (spec FR-001, FR-024).

The check reads headings only (a heading inside a code fence does not count) and fails when:

* ``README_HEADING_MISSING``: ``contracts/README.md`` lacks one of the headings in
  :data:`README_HEADINGS` (one per required topic; this constant is the single authority).
* ``CHANGELOG_HEADING_MISSING``: a module ``CHANGELOG.md`` lacks one of the section headings in
  :data:`CHANGELOG_SECTIONS`, or the module has no ``CHANGELOG.md`` at all.
* ``CHANGELOG_VERSION_HEADING_MISSING``: a module ``CHANGELOG.md`` has no heading for the module's
  current ``info.version`` (the heading text is the version, optionally followed by a space and a
  note such as a date; ``1.0.01`` does not satisfy ``1.0.0``).

It cannot do its job (exit 2) with ``ZERO_HEADINGS``: no module was found, the README holds no
heading (or is missing), or no module CHANGELOG holds any heading. Output:
``CONTRACT-CHECK structure_check: <CODE>: <subject>: <detail>`` per violation and a last
``counts:`` line; exit 0 pass, 1 violation, 2 cannot do its job. Node-free: markdown lint of these
files stays advisory (spec C-005).

Run as a bare script (``python contracts/tools/structure_check.py [--root DIR]``).
Standard library plus PyYAML; imports nothing from ``tests/`` or ``scripts/``.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

CHECK_NAME = "structure_check"
NON_MODULE_DIRECTORIES = frozenset({"_shared", "fixtures", "gradle", "tools", "build", "node_modules"})
ROOT_DOCUMENT = "openapi.yaml"
README = "README.md"
CHANGELOG = "CHANGELOG.md"

# The README topics, copied verbatim from the Work Package 01 hand-off list (the README skeleton).
README_HEADINGS: tuple[str, ...] = (
    "Layout",
    "Path file naming",
    "Relative $ref rules",
    "_shared admission",
    "Module version and the /api/v1 prefix",
    "x-source, x-derived and x-provisional",
    "Lane terminology",
    "Workflow phase and glossary phase",
    "Topology enum",
    "The bundle is a build product",
    "Validate and bundle locally",
    "Markdown lint is advisory",
    "Not the CLI contract registry",
    "Board columns are a consumer convention",
    "Versioning rule",
    "Residual risk: handle-shaped strings",
    "Reader-author warning",
    "Preview tags",
)
CHANGELOG_SECTIONS: tuple[str, ...] = ("Added", "Changed", "Removed", "Provisional")
_HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*#*\s*$")
_FENCE = re.compile(r"^\s*(```|~~~)")


@dataclass(frozen=True)
class Finding:
    code: str
    subject: str
    detail: str

    def render(self) -> str:
        return f"CONTRACT-CHECK {CHECK_NAME}: {self.code}: {self.subject}: {self.detail}"


@dataclass
class Report:
    findings: list[Finding] = field(default_factory=list)
    blocked: list[Finding] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=lambda: {"readme_headings": 0, "changelog_headings": 0})

    @property
    def exit_code(self) -> int:
        if self.blocked:
            return 2
        return 1 if self.findings else 0

    def counts_line(self) -> str:
        return "counts: " + " ".join(f"{key}={value}" for key, value in self.counts.items())


def read_headings(path: Path) -> list[str] | None:
    """The heading texts of a markdown file in order, ignoring code fences; ``None`` when unreadable."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    headings: list[str] = []
    fenced = False
    for line in text.splitlines():
        if _FENCE.match(line):
            fenced = not fenced
            continue
        match = None if fenced else _HEADING.match(line)
        if match:
            headings.append(match.group(1))
    return headings


def _version_of(module: Path) -> str | None:
    try:
        document: Any = yaml.safe_load((module / ROOT_DOCUMENT).read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError, UnicodeDecodeError):
        return None
    info = document.get("info") if isinstance(document, dict) else None
    version = info.get("version") if isinstance(info, dict) else None
    return str(version) if version is not None else None


def has_version_heading(headings: list[str], version: str) -> bool:
    pattern = re.compile(r"^\[?" + re.escape(version) + r"\]?(?:\s.*)?$")
    return any(pattern.match(heading) for heading in headings)


def modules_of(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(p for p in root.iterdir() if p.is_dir() and p.name not in NON_MODULE_DIRECTORIES and (p / ROOT_DOCUMENT).is_file())


def check(root: str | Path) -> Report:
    root = Path(root)
    report = Report()

    readme_headings = read_headings(root / README)
    report.counts["readme_headings"] = len(readme_headings or [])
    if not readme_headings:
        report.blocked.append(Finding("ZERO_HEADINGS", README, "no heading could be read from the README (missing, unreadable or without headings)"))
    else:
        present = set(readme_headings)
        for heading in README_HEADINGS:
            if heading not in present:
                report.findings.append(Finding("README_HEADING_MISSING", heading, f"{README} has no heading '{heading}'"))

    modules = modules_of(root)
    if not modules:
        report.blocked.append(Finding("ZERO_HEADINGS", str(root), "no module found, so no CHANGELOG heading could be read"))
    for module in modules:
        changelog = read_headings(module / CHANGELOG)
        report.counts["changelog_headings"] += len(changelog or [])
        present_sections = set(changelog or [])
        for section in CHANGELOG_SECTIONS:
            if section not in present_sections:
                report.findings.append(Finding("CHANGELOG_HEADING_MISSING", f"{module.name}/{CHANGELOG}", f"no heading '{section}'"))
        version = _version_of(module)
        if version is None or not has_version_heading(changelog or [], version):
            report.findings.append(
                Finding("CHANGELOG_VERSION_HEADING_MISSING", f"{module.name}/{CHANGELOG}", f"no heading for the current info.version '{version}'")
            )
    if modules and report.counts["changelog_headings"] == 0:
        report.blocked.append(Finding("ZERO_HEADINGS", str(root), "no module CHANGELOG holds any heading"))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check the contracts README and module CHANGELOG headings.")
    parser.add_argument("--root", default="contracts", help="contracts root (default: contracts)")
    arguments = parser.parse_args(argv)
    report = check(arguments.root)
    for finding in (*report.blocked, *report.findings):
        print(finding.render())
    print(report.counts_line())
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
