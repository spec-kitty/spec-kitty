"""Verify the pinned tooling: the manifest, the workflow ``uses:`` lines and the install form (FR-018, NFR-003).

Reads ``contracts/tools/pins.json`` (``tools``: ``name``, ``kind``, ``version``, ``url``, ``sha256``,
``published``, ``advisory_feed_checked``) and the ``contracts*.yml`` workflow files, and never writes
the manifest. Failures, one stable code per cause:

* ``CHECKSUM_MISMATCH``: an artefact's bytes do not match its pinned sha256. The bytes come from a local
  copy found by file name in ``--artifacts DIR`` or, with ``--fetch``, from the https download; with
  neither, no bytes are compared and ``downloads`` stays 0.
* ``CHECKSUM_MISSING``: a tool carries no sha256, or one that is not 64 hexadecimal digits.
* ``UNPINNED_USES``: a workflow ``uses:`` is not ``owner/repo@<40-hex commit>`` (a local ``./`` action
  is exempt; a container needs an ``@sha256:`` digest).
* ``NOT_HTTPS``: a tool url is not an ``https`` URL (never fetched).
* ``UNPINNED_INSTALL``: any Python install form but the shared prelude, which is the SHA-pinned
  ``astral-sh/setup-uv`` with ``python-version: '3.12'`` followed by ``uv sync --frozen
  --no-install-project``. A bare ``pip install``, an unfrozen or differently flagged ``uv sync`` and a
  ``uv run`` without ``--frozen`` all fail, as does a job that syncs without that setup step.
* ``PUBLICATION_DATE_MISSING``: a tool has no ``published`` date in ``YYYY-MM-DD`` form.

Cannot do its job (exit 2): ``CHECKSUMS_UNVERIFIED`` (a tool with a valid pinned sha256 and an https url
was never hashed: no ``--artifacts`` copy, no ``--fetch``, and no explicit ``--pins-only``; one finding per
tool), ``MANIFEST_EMPTY`` (unreadable, or lists no tool), ``ZERO_TOOLS_VERIFIED``
(no entry was a mapping), ``ZERO_USES_LINES`` (no ``uses:`` line in any workflow) and
``DOWNLOAD_FAILED``. Output ``CONTRACT-CHECK verify_pins: <CODE>: <file>: <detail>`` per violation and a
last ``counts: tools=N uses_lines=N downloads=N`` line; exit 0 pass, 1 violation, 2 cannot do its job.

Run as a bare script (``python contracts/tools/verify_pins.py [--root DIR] [--pins FILE]
[--workflow FILE ...] [--artifacts DIR] [--fetch] [--pins-only]``); ``--root`` is the repository root. Standard library
plus PyYAML; imports nothing from ``tests/`` or ``scripts/``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

CHECK_NAME = "verify_pins"
DEFAULT_PINS = Path("contracts") / "tools" / "pins.json"
DEFAULT_WORKFLOW_GLOB = "contracts*.yml"
WORKFLOW_DIRECTORY = Path(".github") / "workflows"
PRELUDE_PYTHON = "3.12"
PRELUDE_SYNC_FLAGS = frozenset({"--frozen", "--no-install-project"})
DOWNLOAD_TIMEOUT_SECONDS = 300
_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PINNED_ACTION = re.compile(r"^[\w.-]+/[\w.-]+(?:/[\w./-]+)?@[0-9a-f]{40}$")
_PINNED_CONTAINER = re.compile(r"^docker://\S+@sha256:[0-9a-f]{64}$")
_PIP_INSTALL = re.compile(r"(?:^|[\s;&|(])pip3?\s+install\b")
_UV_PIP = re.compile(r"(?:^|[\s;&|(])uv\s+(?:pip|add|tool)\b")
_UV_SYNC = re.compile(r"(?:^|[\s;&|(])uv\s+sync\b([^;&|\n]*)")
_UV_RUN = re.compile(r"(?:^|[\s;&|(])uv\s+run\b([^;&|\n]*)")
Fetch = Callable[[str], bytes]


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
    counts: dict[str, int] = field(default_factory=lambda: {"tools": 0, "uses_lines": 0, "downloads": 0})

    @property
    def exit_code(self) -> int:
        if self.blocked:
            return 2
        return 1 if self.findings else 0

    def counts_line(self) -> str:
        return "counts: " + " ".join(f"{key}={value}" for key, value in self.counts.items())


def default_fetch(url: str) -> bytes:
    """Download ``url`` (already checked to be https) and return its bytes."""
    if urlparse(url).scheme != "https":
        raise ValueError(f"refusing a non-https url: {url}")
    with urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:  # noqa: S310 -- scheme checked to be https on the line above
        data: bytes = response.read()
    return data


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()  # noqa: TID251 -- file-integrity checksum of a pinned download, not the charter hash


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _check_manifest(report: Report, root: Path, pins: Path, artifacts: Path | None, fetch: Fetch | None, pins_only: bool) -> None:
    subject = _rel(pins, root)
    try:
        manifest: Any = json.loads(pins.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        report.blocked.append(Finding("MANIFEST_EMPTY", subject, f"manifest unreadable: {type(error).__name__}"))
        return
    tools = manifest.get("tools") if isinstance(manifest, dict) else None
    if not isinstance(tools, list) or not tools:
        report.blocked.append(Finding("MANIFEST_EMPTY", subject, "the manifest lists no tool"))
        return
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        report.counts["tools"] += 1
        _check_tool(report, subject, tool, artifacts, fetch, pins_only)
    if report.counts["tools"] == 0:
        report.blocked.append(Finding("ZERO_TOOLS_VERIFIED", subject, "no manifest entry was a mapping"))


def _check_tool(report: Report, subject: str, tool: dict[str, Any], artifacts: Path | None, fetch: Fetch | None, pins_only: bool) -> None:
    name = str(tool.get("name", "<unnamed>"))
    pinned = tool.get("sha256")
    digest_ok = isinstance(pinned, str) and bool(_SHA256.match(pinned))
    if not digest_ok:
        report.findings.append(Finding("CHECKSUM_MISSING", subject, f"{name} has no valid sha256"))
    published = tool.get("published")
    if not isinstance(published, str) or not _DATE.match(published):
        report.findings.append(Finding("PUBLICATION_DATE_MISSING", subject, f"{name} has no publication date (YYYY-MM-DD)"))
    url = tool.get("url")
    https = isinstance(url, str) and urlparse(url).scheme == "https"
    if isinstance(url, str) and not https:
        report.findings.append(Finding("NOT_HTTPS", subject, f"{name}: {url} is not an https url"))
    if not digest_ok or not isinstance(url, str) or not https:
        return
    data: bytes | None = None
    local = artifacts / Path(urlparse(url).path).name if artifacts is not None else None
    if local is not None and local.is_file():
        data = local.read_bytes()
    elif fetch is not None:
        try:
            data = fetch(url)
        except (OSError, ValueError) as error:
            report.blocked.append(Finding("DOWNLOAD_FAILED", subject, f"{name}: {type(error).__name__}: {error}"))
            return
    if data is None:
        if not pins_only:
            detail = f"{name} carries a pinned sha256 but its bytes were never hashed (pass --artifacts or --fetch, or --pins-only to check pins alone)"
            report.blocked.append(Finding("CHECKSUMS_UNVERIFIED", subject, detail))
        return
    report.counts["downloads"] += 1
    actual = sha256_hex(data)
    if actual != str(pinned).lower():
        report.findings.append(Finding("CHECKSUM_MISMATCH", subject, f"{name}: pinned {pinned} but the bytes are {actual}"))


def _is_pinned_uses(value: str) -> bool:
    return value.startswith("./") or bool(_PINNED_ACTION.match(value)) or bool(_PINNED_CONTAINER.match(value))


def _flags(tail: str) -> list[str]:
    flags: list[str] = []
    for token in tail.split():
        if not token.startswith("--"):
            break
        flags.append(token)
    return flags


def _install_problems(run: str) -> list[str]:
    problems: list[str] = []
    logical = run.replace("\\\n", " ")
    if _PIP_INSTALL.search(logical) or _UV_PIP.search(logical):
        problems.append("a pip or uv pip install is not the shared prelude")
    for match in _UV_SYNC.finditer(logical):
        flags = [token for token in match.group(1).split() if token.startswith("-")]
        if set(flags) != PRELUDE_SYNC_FLAGS or len(flags) != len(PRELUDE_SYNC_FLAGS):
            problems.append("uv sync must be exactly 'uv sync --frozen --no-install-project'")
    for match in _UV_RUN.finditer(logical):
        if "--frozen" not in _flags(match.group(1)):
            problems.append("uv run without --frozen may resolve and install")
    return problems


def _check_workflow(report: Report, root: Path, workflow: Path) -> None:
    subject = _rel(workflow, root)
    try:
        document: Any = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError, UnicodeDecodeError) as error:
        report.findings.append(Finding("UNPINNED_USES", subject, f"workflow unreadable: {type(error).__name__}"))
        return
    jobs = document.get("jobs") if isinstance(document, dict) else None
    for job_name, job in (jobs or {}).items():
        if not isinstance(job, dict):
            continue
        where = f"{subject}:{job_name}"
        steps = [step for step in job.get("steps") or [] if isinstance(step, dict)]
        entries = [job] + steps
        prelude_python = False
        uses_uv = False
        for entry in entries:
            uses = entry.get("uses")
            if isinstance(uses, str):
                report.counts["uses_lines"] += 1
                if not _is_pinned_uses(uses):
                    report.findings.append(Finding("UNPINNED_USES", where, f"{uses} is not pinned to a full commit"))
                if uses.startswith("astral-sh/setup-uv@"):
                    options = entry.get("with")
                    version = options.get("python-version") if isinstance(options, dict) else None
                    prelude_python = prelude_python or str(version) == PRELUDE_PYTHON
        for step in steps:
            run = step.get("run")
            if not isinstance(run, str):
                continue
            uses_uv = uses_uv or bool(_UV_SYNC.search(run) or _UV_RUN.search(run))
            for problem in _install_problems(run):
                report.findings.append(Finding("UNPINNED_INSTALL", where, problem))
        if uses_uv and not prelude_python:
            detail = f"uv is used without a pinned astral-sh/setup-uv step with python-version '{PRELUDE_PYTHON}'"
            report.findings.append(Finding("UNPINNED_INSTALL", where, detail))


def check(
    root: str | Path,
    pins: str | Path | None = None,
    workflows: list[Path] | None = None,
    artifacts: str | Path | None = None,
    fetch: Fetch | None = None,
    pins_only: bool = False,
) -> Report:
    root = Path(root)
    report = Report()
    _check_manifest(report, root, Path(pins) if pins else root / DEFAULT_PINS, Path(artifacts) if artifacts else None, fetch, pins_only)
    files = workflows if workflows is not None else sorted((root / WORKFLOW_DIRECTORY).glob(DEFAULT_WORKFLOW_GLOB))
    for workflow in files:
        _check_workflow(report, root, workflow)
    if report.counts["uses_lines"] == 0:
        report.blocked.append(Finding("ZERO_USES_LINES", str(WORKFLOW_DIRECTORY), "no uses: line found in any workflow"))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify pinned tool checksums, workflow action pins and the install form.")
    parser.add_argument("--root", default=".", help="repository root (default: .)")
    parser.add_argument("--pins", default=None, help="manifest file (default: <root>/contracts/tools/pins.json)")
    parser.add_argument("--workflow", action="append", default=None, help="workflow file (repeatable; default: <root>/.github/workflows/contracts*.yml)")
    parser.add_argument("--artifacts", default=None, help="directory of local artefact copies, matched by file name")
    parser.add_argument("--fetch", action="store_true", help="download each https artefact and compare its checksum")
    parser.add_argument("--pins-only", action="store_true", help="check the manifest fields and the workflow pins without hashing any artefact (never the default)")
    arguments = parser.parse_args(argv)
    workflows = [Path(w) for w in arguments.workflow] if arguments.workflow else None
    report = check(arguments.root, arguments.pins, workflows, arguments.artifacts, default_fetch if arguments.fetch else None, arguments.pins_only)
    for finding in (*report.blocked, *report.findings):
        print(finding.render())
    print(report.counts_line())
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
