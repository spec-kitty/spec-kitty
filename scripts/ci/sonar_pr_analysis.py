"""Trusted-input resolution for the per-change SonarCloud report.

Mission ``sonar-per-pr-coverage-reuse-01M2FR32`` WP05. Contract:
``kitty-specs/sonar-per-pr-coverage-reuse-01M2FR32/contracts/reporting-job-contract.md``
§C2 (input provenance) and §C3 (analysis-configuration trust).

The reporting job in ``.github/workflows/ci-aggregate.yml`` runs in base-repo
context with full credential access, so nothing it publishes may be derived from
content the change under review controls. This module is where that is decided:

* **change identity** comes from ``out/aggregate/source/source.json`` --
  ``aggregate_source.py``'s validated record, whose ``pr_number`` is derived from
  the immutable ``refs/pull/N/merge`` reference -- never from
  ``workflow_run.pull_requests[]``, the mutable projection that script documents
  and refuses;
* **head/base branch names and the origin repository** come from ONE
  authenticated read keyed on that already-validated number, and a payload whose
  head repository is not this repository is REFUSED: the same-origin guarantee
  (FR-011/NFR-004) is enforced here as well as in the workflow condition, so its
  removal is never a one-line edit;
* **the analysed revision** is bound to ``tested_sha`` and a mismatch raises
  (NFR-008) -- a misprojected report is plausible and silently wrong, which is
  worse than no report;
* **every emitted argument** is required to be whitespace-free, which closes the
  argument-injection class by construction instead of by enumerating the fields a
  contributor might reach.

``scripts/ci`` is not an importable package; this module is loaded by file path
in ``tests/ci/test_sonar_pr_analysis.py`` and invoked as a script by the job.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: A full commit SHA. ``aggregate_source.py`` writes nothing else.
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
#: ``owner/name``, the GitHub full-name form.
_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")
#: A git branch name conservative enough to survive being passed as one
#: whitespace-delimited scanner argument. Narrower than git's own ref grammar on
#: purpose: this is an allowlist, and a branch it rejects yields a loud refusal
#: rather than a mangled argument list.
_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,254}$")
#: Emitted by ``sonar_project_version.py`` from the trusted ``pyproject.toml``.
_VERSION_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")

#: Settings the trusted ``sonar-project.properties`` MUST carry: without them
#: the report has no publication identity and would either fail late or land on
#: the wrong project.
_REQUIRED_SETTINGS = ("sonar.projectKey", "sonar.organization")

#: The ``$GITHUB_OUTPUT`` delimiter. The runner assigns outputs line by line, so
#: the delimiter form is used even for values validated to be single-line.
_OUTPUT_DELIMITER = "SONAR_PR_ANALYSIS_EOF"

_SOURCE_ARGUMENT = "--source"
_SOURCE_HELP = "Path to the validated source record (out/aggregate/source/source.json)."


class SonarPrAnalysisError(RuntimeError):
    """A trusted input could not be resolved. Always fatal: never degrade."""


class TestedRevisionMismatch(SonarPrAnalysisError):
    """The fetched revision is not the revision the measurement was taken against."""


@dataclass(frozen=True)
class SourceRecord:
    """The validated fields of ``source.json`` this report depends on."""

    repository: str
    head_sha: str
    base_sha: str
    tested_sha: str
    pr_number: int


@dataclass(frozen=True)
class PullRequestIdentity:
    """The trusted branch/origin metadata, from one authenticated lookup."""

    number: int
    head_ref: str
    base_ref: str
    head_repository: str


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SonarPrAnalysisError(message)


def _read_json(path: Path, *, what: str) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise SonarPrAnalysisError(f"{what} is unreadable at {path}: {error}") from error
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise SonarPrAnalysisError(f"{what} at {path} is not valid JSON: {error}") from error


def _positive_int(value: Any, *, what: str) -> int:
    # `isinstance(True, int)` is True, and `pr_number: true` must not resolve to 1.
    _require(isinstance(value, int) and not isinstance(value, bool), f"{what} is not an integer: {value!r}")
    assert isinstance(value, int)
    _require(value >= 1, f"{what} is not positive: {value!r}")
    return value


def _matching(value: Any, pattern: re.Pattern[str], *, what: str) -> str:
    _require(isinstance(value, str) and bool(pattern.fullmatch(value)), f"{what} is malformed: {value!r}")
    assert isinstance(value, str)
    return value


def load_source_record(path: Path) -> SourceRecord:
    """Read and validate ``source.json`` (§C2 identity + analysed revision).

    A record without a ``pr_number`` is a push/dispatch source: this report is
    per-change only (FR-014/C-001), and falling back to a branch analysis would
    overwrite the standing analysis the nightly owns.
    """
    document = _read_json(path, what="the source record")
    _require(isinstance(document, dict), f"the source record at {path} is not a JSON object")
    assert isinstance(document, dict)
    return SourceRecord(
        repository=_matching(document.get("repository"), _REPOSITORY_RE, what="source.json repository"),
        head_sha=_matching(document.get("head_sha"), _SHA_RE, what="source.json head_sha"),
        base_sha=_matching(document.get("base_sha"), _SHA_RE, what="source.json base_sha"),
        tested_sha=_matching(document.get("tested_sha"), _SHA_RE, what="source.json tested_sha"),
        pr_number=_positive_int(document.get("pr_number"), what="source.json pr_number (this report is per-change only)"),
    )


def _side(payload: dict[str, Any], side: str) -> tuple[str, str]:
    """One side's ``(ref, repository full name)``, both validated."""
    node = payload.get(side)
    _require(isinstance(node, dict), f"the pull-request payload has no {side!r} object")
    assert isinstance(node, dict)
    repo = node.get("repo")
    _require(isinstance(repo, dict), f"the pull-request payload has no {side}.repo object")
    assert isinstance(repo, dict)
    return (
        _matching(node.get("ref"), _REF_RE, what=f"pull-request {side}.ref"),
        _matching(repo.get("full_name"), _REPOSITORY_RE, what=f"pull-request {side}.repo.full_name"),
    )


def resolve_pull_request(payload: dict[str, Any], record: SourceRecord) -> PullRequestIdentity:
    """Resolve branch names and origin from one authenticated lookup (§C2).

    The payload must answer for the *validated* number: a mismatch means the
    lookup was keyed on something other than ``source.json``. A head repository
    other than this one is refused outright -- ``workflow_run`` grants
    credentials regardless of origin, so this is the second, independent
    enforcement of FR-011/NFR-004.
    """
    _require(isinstance(payload, dict), "the pull-request payload is not a JSON object")
    number = _positive_int(payload.get("number"), what="pull-request number")
    _require(
        number == record.pr_number,
        f"the pull-request lookup answered for #{number} but the validated identity is #{record.pr_number} -- the lookup was not keyed on source.json",
    )
    head_ref, head_repository = _side(payload, "head")
    base_ref, base_repository = _side(payload, "base")
    _require(
        head_repository == record.repository,
        f"refusing to report on a change originating from {head_repository!r}, not {record.repository!r} (FR-011/NFR-004)",
    )
    _require(base_repository == record.repository, f"the pull-request base repository is {base_repository!r}, not {record.repository!r}")
    return PullRequestIdentity(number=number, head_ref=head_ref, base_ref=base_ref, head_repository=head_repository)


def verify_tested_revision(fetched_sha: str, record: SourceRecord) -> None:
    """Bind the fetched merge ref to the measured revision (NFR-008)."""
    fetched = _matching(fetched_sha, _SHA_RE, what="the fetched revision")
    if fetched != record.tested_sha:
        raise TestedRevisionMismatch(
            f"the fetched merge revision {fetched} is not the measured revision {record.tested_sha} -- "
            "the change was pushed to after its test pass, so analysing it would project line numbers onto a different tree"
        )


def load_trusted_settings(path: Path) -> dict[str, str]:
    """Parse ``sonar-project.properties`` from the TRUSTED checkout (§C3).

    This file is deliberately NOT one of the two trees the change under review
    replaces, so its values are project-controlled. Reading them here and
    re-passing them explicitly makes that provenance auditable at the call site.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise SonarPrAnalysisError(f"the trusted analysis properties are unreadable at {path}: {error}") from error
    settings: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        if key.strip().startswith("sonar."):
            settings[key.strip()] = value.strip()
    for required in _REQUIRED_SETTINGS:
        _require(bool(settings.get(required)), f"{path} does not define {required} -- the report has no publication identity")
    return settings


def coverage_report_paths(directory: Path) -> list[str]:
    """The reconciled per-change coverage files, sorted (§C2, NFR-006).

    An empty set is refused: a report published from zero files reads as a total
    coverage collapse, which is a worse signal than no report at all.
    """
    paths = sorted(entry.as_posix() for entry in directory.glob("coverage-*.xml"))
    _require(bool(paths), f"no reconciled coverage reports under {directory} -- refusing to publish a report with no measurement")
    return paths


def build_scanner_args(
    *,
    record: SourceRecord,
    pull_request: PullRequestIdentity,
    settings: dict[str, str],
    project_version: str,
    report_paths: list[str],
) -> list[str]:
    """Every publication-governing setting, explicit and from trusted content.

    ``sonar.branch.name`` is deliberately absent: this is a *pull-request*
    analysis, and a branch analysis here would overwrite the standing analysis
    the nightly owns (C-001).
    """
    version = _matching(project_version, _VERSION_RE, what="sonar.projectVersion (derived from the trusted pyproject.toml)")
    _require(bool(report_paths), "refusing to publish a report with no coverage reports")
    args = [
        f"-Dsonar.projectKey={settings['sonar.projectKey']}",
        f"-Dsonar.organization={settings['sonar.organization']}",
        f"-Dsonar.projectVersion={version}",
        f"-Dsonar.scm.revision={record.tested_sha}",
        f"-Dsonar.pullrequest.key={pull_request.number}",
        f"-Dsonar.pullrequest.branch={pull_request.head_ref}",
        f"-Dsonar.pullrequest.base={pull_request.base_ref}",
        f"-Dsonar.python.coverage.reportPaths={','.join(report_paths)}",
    ]
    for arg in args:
        # The arguments are joined with spaces into one `args:` value, so
        # whitespace anywhere would split into additional scanner arguments.
        _require(arg.split() == [arg], f"refusing to emit a scanner argument containing whitespace: {arg!r}")
    return args


def _emit(lines: list[str]) -> None:
    """Write ``key=value`` lines to ``$GITHUB_OUTPUT``, else to stdout."""
    destination = os.environ.get("GITHUB_OUTPUT")
    if not destination:
        print("\n".join(lines))
        return
    with open(destination, "a", encoding="utf-8") as handle:
        for line in lines:
            key, _, value = line.partition("=")
            handle.write(f"{key}<<{_OUTPUT_DELIMITER}\n{value}\n{_OUTPUT_DELIMITER}\n")


def _command_pr_number(args: argparse.Namespace) -> None:
    print(load_source_record(args.source).pr_number)


def _command_verify_revision(args: argparse.Namespace) -> None:
    verify_tested_revision(args.fetched, load_source_record(args.source))
    print(f"sonar-pr: fetched revision matches the measured revision {args.fetched} (NFR-008)")


def _command_scanner_args(args: argparse.Namespace) -> None:
    record = load_source_record(args.source)
    pull_request = resolve_pull_request(_read_json(args.pull_request, what="the pull-request payload"), record)
    scanner_args = build_scanner_args(
        record=record,
        pull_request=pull_request,
        settings=load_trusted_settings(args.properties),
        project_version=args.project_version,
        report_paths=coverage_report_paths(args.coverage_dir),
    )
    _emit([f"args={' '.join(scanner_args)}", f"tested-sha={record.tested_sha}", f"pr-number={record.pr_number}"])


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)

    pr_number = subcommands.add_parser("pr-number", help="Print the validated change number.")
    pr_number.add_argument(_SOURCE_ARGUMENT, required=True, type=Path, help=_SOURCE_HELP)
    pr_number.set_defaults(handler=_command_pr_number)

    verify = subcommands.add_parser("verify-revision", help="Bind a fetched revision to the measured one (NFR-008).")
    verify.add_argument(_SOURCE_ARGUMENT, required=True, type=Path, help=_SOURCE_HELP)
    verify.add_argument("--fetched", required=True, help="The revision `git rev-parse FETCH_HEAD` resolved to.")
    verify.set_defaults(handler=_command_verify_revision)

    scanner = subcommands.add_parser("scanner-args", help="Emit the explicit, trusted scanner arguments.")
    scanner.add_argument(_SOURCE_ARGUMENT, required=True, type=Path, help=_SOURCE_HELP)
    scanner.add_argument("--pull-request", required=True, type=Path, help="The authenticated pull-request lookup payload.")
    scanner.add_argument("--properties", required=True, type=Path, help="The TRUSTED sonar-project.properties.")
    scanner.add_argument("--coverage-dir", required=True, type=Path, help="The reconciled per-change coverage directory.")
    scanner.add_argument("--project-version", required=True, help="sonar.projectVersion, derived from the trusted pyproject.toml.")
    scanner.set_defaults(handler=_command_scanner_args)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        args.handler(args)
    except SonarPrAnalysisError as error:
        # Loud and fatal: stdout stays EMPTY so a shell `$(...)` capture is
        # empty and the calling step fails rather than proceeding on a guess.
        print(f"::error::sonar-pr: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
