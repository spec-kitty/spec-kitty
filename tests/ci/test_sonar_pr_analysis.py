"""Unit tests for ``scripts/ci/sonar_pr_analysis.py`` (WP05, T024).

Mission ``sonar-per-pr-coverage-reuse-01M2FR32``. Contract:
``kitty-specs/sonar-per-pr-coverage-reuse-01M2FR32/contracts/reporting-job-contract.md``
§C2 (input provenance), §C3 (analysis-configuration trust).

The per-change reporting job in ``.github/workflows/ci-aggregate.yml`` must
never derive a publication-governing value from content the change under review
controls. This module owns the three refusals that make that true:

* **identity** comes from the validated source record (``source.json``'s
  ``pr_number``, itself derived from the immutable ``refs/pull/N/merge``
  reference by ``aggregate_source.py``), never from
  ``workflow_run.pull_requests[]`` — the mutable projection the producing
  script explicitly refuses;
* **head/base branch names and the origin repository** come from ONE
  authenticated read keyed on that already-validated ``pr_number``, and a
  payload whose head repository is not this repository is REFUSED (FR-011 /
  NFR-004 restated at the trusted-lookup layer, so the same-origin guarantee
  does not rest on the workflow ``if:`` alone);
* **the analysed revision** is bound to ``source.json``'s ``tested_sha``, and a
  fetched revision that does not equal it raises (NFR-008) — a loud failure,
  never a silently mis-projected report.

Every emitted ``-D`` argument is additionally required to be whitespace-free,
which closes the argument-injection class by construction rather than by
enumerating the values a contributor might reach.

The module is loaded by file path (``scripts/ci`` is not an importable
package), mirroring ``tests/ci/test_sonar_project_version.py``.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

pytestmark = pytest.mark.fast

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT_PATH = _REPO_ROOT / "scripts" / "ci" / "sonar_pr_analysis.py"

_TESTED_SHA = "a" * 40
_HEAD_SHA = "b" * 40
_BASE_SHA = "c" * 40
_REPOSITORY = "spec-kitty/spec-kitty"

_PROPERTIES = """\
# comment
sonar.projectKey=spec-kitty_spec-kitty
sonar.organization=spec-kitty

sonar.sources=src
sonar.tests=tests
sonar.python.version=3.11
"""


def _load_module() -> ModuleType:
    if not _SCRIPT_PATH.exists():
        pytest.fail(f"sonar_pr_analysis.py missing: {_SCRIPT_PATH.relative_to(_REPO_ROOT)} (WP05 not yet delivered)")
    spec = importlib.util.spec_from_file_location("sonar_pr_analysis", _SCRIPT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot build an import spec for {_SCRIPT_PATH}")
    module = importlib.util.module_from_spec(spec)
    # Registered BEFORE execution: `@dataclass` resolves `cls.__module__`
    # through `sys.modules`, so a module executed while unregistered raises.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def module() -> ModuleType:
    return _load_module()


def _source_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "repository": _REPOSITORY,
        "run_id": 42,
        "run_attempt": 1,
        "head_sha": _HEAD_SHA,
        "base_sha": _BASE_SHA,
        "tested_sha": _TESTED_SHA,
        "pr_number": 4334,
    }
    payload.update(overrides)
    return payload


def _write_source(tmp_path: Path, **overrides: Any) -> Path:
    path = tmp_path / "source.json"
    path.write_text(json.dumps(_source_payload(**overrides)) + "\n", encoding="utf-8")
    return path


def _pull_request_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "number": 4334,
        "head": {"ref": "issue-4334-sonar-reuse-shard-coverage", "repo": {"full_name": _REPOSITORY}},
        "base": {"ref": "main", "repo": {"full_name": _REPOSITORY}},
    }
    payload.update(overrides)
    return payload


def _write_properties(tmp_path: Path, body: str = _PROPERTIES) -> Path:
    path = tmp_path / "sonar-project.properties"
    path.write_text(body, encoding="utf-8")
    return path


def _write_coverage(tmp_path: Path, names: tuple[str, ...] = ("coverage-fast-cli-shard1-of-1.xml",)) -> Path:
    directory = tmp_path / "coverage"
    directory.mkdir()
    for name in names:
        (directory / name).write_text("<coverage/>", encoding="utf-8")
    return directory


# ---------------------------------------------------------------------------
# The validated source record (§C2: identity, analysed revision)
# ---------------------------------------------------------------------------
def test_load_source_record_reads_the_validated_identity(module: ModuleType, tmp_path: Path) -> None:
    record = module.load_source_record(_write_source(tmp_path))
    assert record.repository == _REPOSITORY
    assert record.pr_number == 4334
    assert record.tested_sha == _TESTED_SHA
    assert record.head_sha == _HEAD_SHA


def test_load_source_record_refuses_a_record_without_a_change_number(module: ModuleType, tmp_path: Path) -> None:
    """A push/dispatch source record carries ``pr_number: null``.

    The reporting job is per-change only (FR-014/C-001); a record with no change
    identity must refuse rather than fall back to a branch analysis, which would
    overwrite the standing branch analysis the nightly owns.
    """
    with pytest.raises(module.SonarPrAnalysisError):
        module.load_source_record(_write_source(tmp_path, pr_number=None))


@pytest.mark.parametrize(
    "overrides",
    [
        {"tested_sha": "not-a-sha"},
        {"head_sha": ""},
        {"base_sha": "abc"},
        {"repository": "spec-kitty"},
        {"pr_number": 0},
        {"pr_number": "4334"},
        {"pr_number": True},
    ],
    ids=["tested-sha", "head-sha", "base-sha", "repository", "zero-number", "string-number", "bool-number"],
)
def test_load_source_record_refuses_a_malformed_field(module: ModuleType, tmp_path: Path, overrides: dict[str, Any]) -> None:
    with pytest.raises(module.SonarPrAnalysisError):
        module.load_source_record(_write_source(tmp_path, **overrides))


def test_load_source_record_refuses_a_non_object_document(module: ModuleType, tmp_path: Path) -> None:
    path = tmp_path / "source.json"
    path.write_text("[]\n", encoding="utf-8")
    with pytest.raises(module.SonarPrAnalysisError):
        module.load_source_record(path)


# ---------------------------------------------------------------------------
# The authenticated lookup (§C2: branch names, origin repository)
# ---------------------------------------------------------------------------
def test_resolve_pull_request_returns_the_trusted_branch_names(module: ModuleType, tmp_path: Path) -> None:
    record = module.load_source_record(_write_source(tmp_path))
    identity = module.resolve_pull_request(_pull_request_payload(), record)
    assert identity.number == 4334
    assert identity.head_ref == "issue-4334-sonar-reuse-shard-coverage"
    assert identity.base_ref == "main"
    assert identity.head_repository == _REPOSITORY


def test_resolve_pull_request_refuses_a_foreign_head_repository(module: ModuleType, tmp_path: Path) -> None:
    """FR-011 / NFR-004 restated at the trusted-lookup layer.

    ``workflow_run`` runs in base-repo context with full credential access
    regardless of the contribution's origin, so the same-origin guarantee is
    condition-enforced. Enforcing it in exactly one place would make its removal
    a single-line edit; this refusal is the second, independent enforcement.
    """
    record = module.load_source_record(_write_source(tmp_path))
    payload = _pull_request_payload(head={"ref": "attack", "repo": {"full_name": "someone-else/spec-kitty"}})
    with pytest.raises(module.SonarPrAnalysisError):
        module.resolve_pull_request(payload, record)


def test_resolve_pull_request_refuses_a_number_that_is_not_the_validated_one(module: ModuleType, tmp_path: Path) -> None:
    """The lookup must be keyed on the VALIDATED identity, and proven to be.

    A payload answering for a different change means the key was taken from
    somewhere other than ``source.json`` — exactly the mutable-projection defect
    ``aggregate_source.py`` refuses upstream.
    """
    record = module.load_source_record(_write_source(tmp_path))
    with pytest.raises(module.SonarPrAnalysisError):
        module.resolve_pull_request(_pull_request_payload(number=9999), record)


@pytest.mark.parametrize(
    "ref",
    ["branch with spaces", "branch\nname", "", "-Dsonar.projectKey=attacker_project"],
    ids=["space", "newline", "empty", "argument-injection"],
)
def test_resolve_pull_request_refuses_an_unsafe_branch_name(module: ModuleType, tmp_path: Path, ref: str) -> None:
    record = module.load_source_record(_write_source(tmp_path))
    payload = _pull_request_payload(head={"ref": ref, "repo": {"full_name": _REPOSITORY}})
    with pytest.raises(module.SonarPrAnalysisError):
        module.resolve_pull_request(payload, record)


def test_resolve_pull_request_refuses_a_missing_base_branch(module: ModuleType, tmp_path: Path) -> None:
    record = module.load_source_record(_write_source(tmp_path))
    with pytest.raises(module.SonarPrAnalysisError):
        module.resolve_pull_request(_pull_request_payload(base={"repo": {"full_name": _REPOSITORY}}), record)


# ---------------------------------------------------------------------------
# NFR-008 — the analysed revision is bound to the measured revision
# ---------------------------------------------------------------------------
def test_verify_tested_revision_accepts_the_recorded_revision(module: ModuleType, tmp_path: Path) -> None:
    record = module.load_source_record(_write_source(tmp_path))
    module.verify_tested_revision(_TESTED_SHA, record)


def test_verify_tested_revision_raises_on_mismatch(module: ModuleType, tmp_path: Path) -> None:
    """NFR-008: line numbers projected onto a different revision produce a
    plausible, silently wrong report. The mismatch must be LOUD."""
    record = module.load_source_record(_write_source(tmp_path))
    with pytest.raises(module.TestedRevisionMismatch) as excinfo:
        module.verify_tested_revision("d" * 40, record)
    assert _TESTED_SHA in str(excinfo.value)


def test_verify_tested_revision_raises_on_a_malformed_fetched_revision(module: ModuleType, tmp_path: Path) -> None:
    record = module.load_source_record(_write_source(tmp_path))
    with pytest.raises(module.SonarPrAnalysisError):
        module.verify_tested_revision("FETCH_HEAD", record)


# ---------------------------------------------------------------------------
# §C3 — every publication-governing setting resolved from trusted content
# ---------------------------------------------------------------------------
def test_load_trusted_settings_reads_the_properties_file(module: ModuleType, tmp_path: Path) -> None:
    settings = module.load_trusted_settings(_write_properties(tmp_path))
    assert settings["sonar.projectKey"] == "spec-kitty_spec-kitty"
    assert settings["sonar.organization"] == "spec-kitty"


def test_load_trusted_settings_refuses_a_file_without_the_publication_identity(module: ModuleType, tmp_path: Path) -> None:
    with pytest.raises(module.SonarPrAnalysisError):
        module.load_trusted_settings(_write_properties(tmp_path, "sonar.sources=src\n"))


def test_coverage_report_paths_are_sorted_and_relative(module: ModuleType, tmp_path: Path) -> None:
    directory = _write_coverage(tmp_path, ("coverage-b.xml", "coverage-a.xml"))
    paths = module.coverage_report_paths(directory)
    assert [Path(entry).name for entry in paths] == ["coverage-a.xml", "coverage-b.xml"]


def test_coverage_report_paths_refuse_an_empty_set(module: ModuleType, tmp_path: Path) -> None:
    """NFR-006: a report published from zero reconciled files would read as a
    total coverage collapse. Refuse rather than publish it."""
    directory = tmp_path / "coverage"
    directory.mkdir()
    with pytest.raises(module.SonarPrAnalysisError):
        module.coverage_report_paths(directory)


def test_build_scanner_args_passes_every_publication_setting_explicitly(module: ModuleType, tmp_path: Path) -> None:
    record = module.load_source_record(_write_source(tmp_path))
    identity = module.resolve_pull_request(_pull_request_payload(), record)
    settings = module.load_trusted_settings(_write_properties(tmp_path))
    args = module.build_scanner_args(
        record=record,
        pull_request=identity,
        settings=settings,
        project_version="3.2.7rc1",
        report_paths=["out/aggregate/coverage/coverage-fast-cli-shard1-of-1.xml"],
    )
    joined = " ".join(args)
    assert "-Dsonar.projectKey=spec-kitty_spec-kitty" in args
    assert "-Dsonar.organization=spec-kitty" in args
    assert "-Dsonar.projectVersion=3.2.7rc1" in args
    assert "-Dsonar.pullrequest.key=4334" in args
    assert "-Dsonar.pullrequest.branch=issue-4334-sonar-reuse-shard-coverage" in args
    assert "-Dsonar.pullrequest.base=main" in args
    assert f"-Dsonar.scm.revision={_TESTED_SHA}" in args
    assert "-Dsonar.python.coverage.reportPaths=out/aggregate/coverage/coverage-fast-cli-shard1-of-1.xml" in args
    # `sonar.branch.name` would make this a BRANCH analysis, overwriting the
    # standing analysis the nightly owns (C-001).
    assert "sonar.branch.name" not in joined


def test_build_scanner_args_comma_joins_the_reconciled_set(module: ModuleType, tmp_path: Path) -> None:
    record = module.load_source_record(_write_source(tmp_path))
    identity = module.resolve_pull_request(_pull_request_payload(), record)
    settings = module.load_trusted_settings(_write_properties(tmp_path))
    args = module.build_scanner_args(
        record=record,
        pull_request=identity,
        settings=settings,
        project_version="3.2.7rc1",
        report_paths=["a/coverage-1.xml", "a/coverage-2.xml"],
    )
    assert "-Dsonar.python.coverage.reportPaths=a/coverage-1.xml,a/coverage-2.xml" in args


def test_build_scanner_args_refuses_whitespace_in_any_emitted_argument(module: ModuleType, tmp_path: Path) -> None:
    """Closes the argument-injection class by construction.

    The emitted arguments are joined with spaces into one ``args:`` value, so a
    value carrying whitespace would split into additional scanner arguments.
    Rather than enumerate which fields a contributor could reach, refuse the
    property outright.
    """
    record = module.load_source_record(_write_source(tmp_path))
    identity = module.resolve_pull_request(_pull_request_payload(), record)
    settings = module.load_trusted_settings(_write_properties(tmp_path))
    with pytest.raises(module.SonarPrAnalysisError):
        module.build_scanner_args(
            record=record,
            pull_request=identity,
            settings=settings,
            project_version="3.2.7 rc1",
            report_paths=["a/coverage-1.xml"],
        )


def test_build_scanner_args_refuses_an_empty_project_version(module: ModuleType, tmp_path: Path) -> None:
    """An empty ``sonar.projectVersion`` silently freezes the new-code baseline
    (the #2421 defect ``sonar_project_version.py`` exists to prevent)."""
    record = module.load_source_record(_write_source(tmp_path))
    identity = module.resolve_pull_request(_pull_request_payload(), record)
    settings = module.load_trusted_settings(_write_properties(tmp_path))
    with pytest.raises(module.SonarPrAnalysisError):
        module.build_scanner_args(
            record=record,
            pull_request=identity,
            settings=settings,
            project_version="",
            report_paths=["a/coverage-1.xml"],
        )
