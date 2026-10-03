"""Check that the versions the JVM build uses equal the versions ``contracts/tools/pins.json`` pins (FR-018, NFR-003).

``verify_pins.py`` judges the manifest, the workflow ``uses:`` lines and the install form; it never reads the
build. This check closes that gap: the JVM toolchain is installed from ``pins.json``, but the build file declares
its own plugin version, and the two can drift apart without any other check noticing. It compares, for the two
JVM-side tools of the manifest:

* ``openapi-generator-gradle-plugin``: the ``id 'org.openapi.generator' version '...'`` line of
  ``contracts/build.gradle``, and every ``openapi-generator-gradle-plugin`` and
  ``org.openapi.generator.gradle.plugin`` component of ``contracts/gradle/verification-metadata.xml``.
* ``gradle``: the version in ``distributionUrl`` of ``contracts/gradle/wrapper/gradle-wrapper.properties`` (the
  repository commits no wrapper, so this is compared only if the file exists) and every ``gradle-version:`` input
  of a ``contracts*.yml`` workflow step.
* both: the manifest's own ``url`` must carry the entry's ``version`` (a bumped ``version`` with an old ``url``
  would install the old tool while every comparison above passed).

Failure, one stable code: ``GRADLE_PIN_MISMATCH`` (a value the build uses is not the pinned version).

Cannot do its job (exit 2, fail closed): ``GRADLE_PIN_UNREADABLE`` (a file that must be read is missing, is not
valid JSON, XML or YAML, or the manifest lacks a JVM-side entry), ``GRADLE_PIN_UNPARSEABLE`` (a file was read but
holds no value to compare: no plugin version in ``build.gradle``, no plugin component in the verification
metadata) and ``ZERO_COMPARISONS`` (nothing was compared at all). Output
``CONTRACT-CHECK gradle_pin_check: <CODE>: <file>: <detail>`` per violation and a last
``counts: pinned=N compared=N`` line (the pinned JVM-side tools found, the build values compared); exit 0 pass,
1 violation, 2 cannot do its job.

Run as a bare script (``python contracts/tools/gradle_pin_check.py [--root DIR] [--pins FILE] [--build FILE]
[--metadata FILE] [--wrapper FILE] [--workflow FILE ...]``); ``--root`` is the repository root. Standard library
plus PyYAML; imports nothing from ``tests/`` or ``scripts/``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import xml.etree.ElementTree as ElementTree  # noqa: S405 -- parses committed repository files only, never network input
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

CHECK_NAME = "gradle_pin_check"
GRADLE_TOOL = "gradle"
PLUGIN_TOOL = "openapi-generator-gradle-plugin"
DEFAULT_PINS = Path("contracts") / "tools" / "pins.json"
DEFAULT_BUILD = Path("contracts") / "build.gradle"
DEFAULT_METADATA = Path("contracts") / "gradle" / "verification-metadata.xml"
DEFAULT_WRAPPER = Path("contracts") / "gradle" / "wrapper" / "gradle-wrapper.properties"
WORKFLOW_DIRECTORY = Path(".github") / "workflows"
DEFAULT_WORKFLOW_GLOB = "contracts*.yml"
PLUGIN_ID_LINE = re.compile(r"""\bid\s*\(?\s*['"]org\.openapi\.generator['"]\s*\)?\s*version\s*\(?\s*['"]([^'"]+)['"]""")
WRAPPER_URL_LINE = re.compile(r"^\s*distributionUrl\s*=\s*(\S+)\s*$", re.MULTILINE)
WRAPPER_VERSION = re.compile(r"gradle-(\d[^/]*?)-(?:bin|all)\.zip")
PLUGIN_COMPONENTS = frozenset({"openapi-generator-gradle-plugin", "org.openapi.generator.gradle.plugin"})


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
    counts: dict[str, int] = field(default_factory=lambda: {"pinned": 0, "compared": 0})

    @property
    def exit_code(self) -> int:
        if self.blocked:
            return 2
        return 1 if self.findings else 0

    def counts_line(self) -> str:
        return "counts: " + " ".join(f"{key}={value}" for key, value in self.counts.items())

    def compare(self, subject: str, what: str, actual: str, pinned: str) -> None:
        self.counts["compared"] += 1
        if actual != pinned:
            self.findings.append(Finding("GRADLE_PIN_MISMATCH", subject, f"{what} is {actual} but pins.json pins {pinned}"))


def _rel(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _read(report: Report, root: Path, path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        report.blocked.append(Finding("GRADLE_PIN_UNREADABLE", _rel(path, root), f"unreadable: {type(error).__name__}"))
        return None


def _load_pins(report: Report, root: Path, pins: Path) -> dict[str, dict[str, Any]]:
    subject = _rel(pins, root)
    text = _read(report, root, pins)
    if text is None:
        return {}
    try:
        manifest: Any = json.loads(text)
    except ValueError as error:
        report.blocked.append(Finding("GRADLE_PIN_UNREADABLE", subject, f"manifest is not valid JSON: {type(error).__name__}"))
        return {}
    tools = manifest.get("tools") if isinstance(manifest, dict) else None
    entries = {str(t["name"]): t for t in tools or [] if isinstance(t, dict) and isinstance(t.get("name"), str)}
    found: dict[str, dict[str, Any]] = {}
    for name in (GRADLE_TOOL, PLUGIN_TOOL):
        entry = entries.get(name)
        if entry is None or not isinstance(entry.get("version"), str) or not entry["version"]:
            report.blocked.append(Finding("GRADLE_PIN_UNREADABLE", subject, f"the manifest has no {name} entry with a version"))
            continue
        found[name] = entry
        report.counts["pinned"] += 1
        url = entry.get("url")
        version = entry["version"]
        if isinstance(url, str):
            report.compare(subject, f"the {name} url carries a version that", _url_version(url, version), version)
    return found


def _url_version(url: str, version: str) -> str:
    """The pinned version if the url names it as a whole path or file-name token, else a marker that cannot equal it."""
    return version if re.search(rf"(?<![\w.]){re.escape(version)}(?![\w.]*\d)(?=[/.\-]|$)", url) else f"<absent from {url}>"


def _check_build(report: Report, root: Path, build: Path, pinned: str) -> None:
    text = _read(report, root, build)
    if text is None:
        return
    versions = PLUGIN_ID_LINE.findall(text)
    if not versions:
        report.blocked.append(Finding("GRADLE_PIN_UNPARSEABLE", _rel(build, root), "no version for the org.openapi.generator plugin id was found"))
        return
    for version in versions:
        report.compare(_rel(build, root), "the org.openapi.generator plugin version", version, pinned)


def _check_metadata(report: Report, root: Path, metadata: Path, pinned: str) -> None:
    subject = _rel(metadata, root)
    text = _read(report, root, metadata)
    if text is None:
        return
    try:
        tree = ElementTree.fromstring(text)  # noqa: S314 -- a committed repository file
    except ElementTree.ParseError as error:
        report.blocked.append(Finding("GRADLE_PIN_UNREADABLE", subject, f"not valid XML: {type(error).__name__}"))
        return
    seen = 0
    for element in tree.iter():
        if element.tag.rpartition("}")[2] != "component" or element.get("name") not in PLUGIN_COMPONENTS:
            continue
        seen += 1
        report.compare(subject, f"the {element.get('group')}:{element.get('name')} component", str(element.get("version")), pinned)
    if seen == 0:
        report.blocked.append(Finding("GRADLE_PIN_UNPARSEABLE", subject, "no openapi-generator plugin component was found"))


def _check_wrapper(report: Report, root: Path, wrapper: Path, pinned: str) -> None:
    if not wrapper.exists():
        return
    text = _read(report, root, wrapper)
    if text is None:
        return
    match = WRAPPER_URL_LINE.search(text)
    version = WRAPPER_VERSION.search(match.group(1)) if match else None
    if version is None:
        report.blocked.append(Finding("GRADLE_PIN_UNPARSEABLE", _rel(wrapper, root), "no gradle version in distributionUrl"))
        return
    report.compare(_rel(wrapper, root), "the wrapper distribution version", version.group(1), pinned)


def _check_workflow(report: Report, root: Path, workflow: Path, pinned: str) -> None:
    text = _read(report, root, workflow)
    if text is None:
        return
    try:
        document: Any = yaml.safe_load(text)
    except yaml.YAMLError as error:
        report.blocked.append(Finding("GRADLE_PIN_UNREADABLE", _rel(workflow, root), f"not valid YAML: {type(error).__name__}"))
        return
    jobs = document.get("jobs") if isinstance(document, dict) else None
    for job_name, job in (jobs or {}).items():
        for step in (job.get("steps") or []) if isinstance(job, dict) else []:
            options = step.get("with") if isinstance(step, dict) else None
            if isinstance(options, dict) and "gradle-version" in options:
                report.compare(f"{_rel(workflow, root)}:{job_name}", "the gradle-version input", str(options["gradle-version"]), pinned)


def check(
    root: str | Path,
    pins: str | Path | None = None,
    build: str | Path | None = None,
    metadata: str | Path | None = None,
    wrapper: str | Path | None = None,
    workflows: list[Path] | None = None,
) -> Report:
    root = Path(root)
    report = Report()
    found = _load_pins(report, root, Path(pins) if pins else root / DEFAULT_PINS)
    plugin = found.get(PLUGIN_TOOL)
    gradle = found.get(GRADLE_TOOL)
    if plugin is not None:
        _check_build(report, root, Path(build) if build else root / DEFAULT_BUILD, plugin["version"])
        _check_metadata(report, root, Path(metadata) if metadata else root / DEFAULT_METADATA, plugin["version"])
    if gradle is not None:
        _check_wrapper(report, root, Path(wrapper) if wrapper else root / DEFAULT_WRAPPER, gradle["version"])
        files = workflows if workflows is not None else sorted((root / WORKFLOW_DIRECTORY).glob(DEFAULT_WORKFLOW_GLOB))
        for workflow in files:
            _check_workflow(report, root, workflow, gradle["version"])
    if report.counts["compared"] == 0 and not report.blocked:
        report.blocked.append(Finding("ZERO_COMPARISONS", _rel(root, root), "no build value was compared with a pin"))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check that the JVM build's versions equal the versions pinned in pins.json.")
    parser.add_argument("--root", default=".", help="repository root (default: .)")
    parser.add_argument("--pins", default=None, help="manifest file (default: <root>/contracts/tools/pins.json)")
    parser.add_argument("--build", default=None, help="build file (default: <root>/contracts/build.gradle)")
    parser.add_argument("--metadata", default=None, help="Gradle verification metadata (default: <root>/contracts/gradle/verification-metadata.xml)")
    parser.add_argument("--wrapper", default=None, help="wrapper properties, compared only if the file exists")
    parser.add_argument("--workflow", action="append", default=None, help="workflow file (repeatable; default: <root>/.github/workflows/contracts*.yml)")
    arguments = parser.parse_args(argv)
    workflows = [Path(w) for w in arguments.workflow] if arguments.workflow else None
    report = check(arguments.root, arguments.pins, arguments.build, arguments.metadata, arguments.wrapper, workflows)
    for finding in (*report.blocked, *report.findings):
        print(finding.render())
    print(report.counts_line())
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
