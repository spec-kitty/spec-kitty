"""Planted-violation tests for ``contracts/tools/breaking_check.py`` (FR-016, D-P6).

The committed fixture pairs live under ``contracts/tools/fixtures/breaking_check/``: one ``baseline`` module and
one candidate module per case. The comparison itself is oasdiff's. Where the real binary is on ``PATH`` (the CI
job installs it; a developer may too) the fixture pairs run through it; otherwise the same cases run with the
process boundary faked by canned oasdiff answers, so the decision logic is always exercised. Tag and shallow-clone
states use throw-away git repositories.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

from tests.contract._loader import load_tool

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

TOOLS_DIR = Path(__file__).resolve().parents[2] / "contracts" / "tools"
FIXTURES = TOOLS_DIR / "fixtures" / "breaking_check"
BASELINE = FIXTURES / "baseline"
CANDIDATES = FIXTURES / "candidates"
SCRIPT = TOOLS_DIR / "breaking_check.py"
REAL_OASDIFF = shutil.which("oasdiff")

# case -> (code expected without a major move, oasdiff change id the real binary reports)
BREAKING_CASES = {
    "removed_property": "response-required-property-removed",
    "removed_path": "api-path-removed-without-deprecation",
    "required_parameter": "new-required-request-parameter",
    "narrowed_enum": "request-parameter-enum-value-removed",
    "changed_type": "response-property-type-changed",
    # Response schemas are closed: oasdiff reports an added response property at level INFO, our own rule makes it breaking.
    "added_response_property": "response-optional-property-added",
}
# Every other way a response grows. oasdiff reports each at level INFO; the closed-response rule raises each to ERR.
RESPONSE_ADDITION_CASES = {
    "added_response_allof_branch": "response-body-all-of-added",
    "added_response_property_allof": "response-property-all-of-added",
    "added_response_success_status": "response-success-status-added",
    "added_response_error_status": "response-non-success-status-added",
    "added_response_media_type": "response-media-type-added",
    "added_response_header": "response-header-added",
}
BREAKING_CASES.update(RESPONSE_ADDITION_CASES)


@pytest.fixture(scope="module")
def checker() -> ModuleType:
    with pytest.MonkeyPatch.context() as mp:
        yield load_tool(mp, SCRIPT, "breaking_check_under_test", syspath=TOOLS_DIR)


def _fake_oasdiff(entries_for: Callable[[Path, Path], list[dict[str, object]]]) -> Callable[[Sequence[str], Path | None], tuple[int, str, str]]:
    """A runner that answers ``oasdiff`` through ``entries_for`` and runs every other command for real."""

    def run(command: Sequence[str], cwd: Path | None = None) -> tuple[int, str, str]:
        if Path(command[0]).name == "oasdiff":
            return 0, json.dumps(entries_for(Path(command[2]), Path(command[3]))), ""
        completed = subprocess.run(list(command), capture_output=True, text=True, check=False, cwd=cwd)  # noqa: S603 -- test helper, argument list
        return completed.returncode, completed.stdout, completed.stderr

    return run


def _response_additions(
    thing_old: dict[str, Any], thing_new: dict[str, Any], schema_old: dict[str, Any], schema_new: dict[str, Any], change: Callable[[str, str], None]
) -> None:
    """The ways a response grows (a property, an allOf branch, a status, a header, a media type), named as oasdiff names them."""
    for name in schema_new["properties"]:
        if name not in schema_old["properties"]:
            change("response-optional-property-added", f"added the optional property `{name}` to the response with the `200` status")
        elif len(schema_new["properties"][name].get("allOf", [])) > len(schema_old["properties"][name].get("allOf", [])):
            change("response-property-all-of-added", f"added `subschema #1` to the `{name}` response property `allOf` list for the response status `200`")
    if len(schema_new.get("allOf", [])) > len(schema_old.get("allOf", [])):
        change("response-body-all-of-added", "added `subschema #1` to the response body `allOf` list for the response status `200`")
    responses_old, responses_new = thing_old["responses"], thing_new["responses"]
    for status in responses_new:
        if status not in responses_old:
            kind = "success" if status.startswith("2") else "non-success"
            change(f"response-{kind}-status-added", f"added the {kind} response with the status `{status}`")
    for status in responses_old:
        for header in responses_new.get(status, {}).get("headers", {}):
            if header not in responses_old[status].get("headers", {}):
                change("response-header-added", f"added the new `{header}` response header for the response status `{status}`")
        for media in responses_new.get(status, {}).get("content", {}):
            if media not in responses_old[status].get("content", {}):
                change("response-media-type-added", f"added the new `{media}` response media type for the response status `{status}`")


def _structural_entries(base: Path, revision: Path) -> list[dict[str, object]]:
    """A stand-in for oasdiff over the fixture bundles: it names the structural differences the cases plant."""
    old, new = yaml.safe_load(base.read_text(encoding="utf-8")), yaml.safe_load(revision.read_text(encoding="utf-8"))
    entries: list[dict[str, object]] = []

    def change(identifier: str, text: str, path: str = "/things") -> None:
        entries.append({"id": identifier, "text": text, "level": 3, "operation": "GET", "path": path})

    for path in old["paths"]:
        if path not in new["paths"]:
            change("api-path-removed-without-deprecation", "api path removed without deprecation", path)
    thing_old = old["paths"]["/things"]["get"]
    thing_new = new["paths"]["/things"]["get"]
    schema_old = thing_old["responses"]["200"]["content"]["application/json"]["schema"]
    schema_new = thing_new["responses"]["200"]["content"]["application/json"]["schema"]
    for name in schema_old["properties"]:
        if name not in schema_new["properties"]:
            change("response-required-property-removed", f"removed the required property `{name}` from the response with the `200` status")
        elif schema_old["properties"][name].get("type") != schema_new["properties"][name].get("type"):
            change("response-property-type-changed", f"the `{name}` response's property `type` changed")
    _response_additions(thing_old, thing_new, schema_old, schema_new, change)
    if any(p.get("required") for p in thing_new.get("parameters", [])):
        change("new-required-request-parameter", "added the new required `query` request parameter `owner`")
    old_enum = set(thing_old["parameters"][0]["schema"]["enum"])
    new_enum = set(thing_new["parameters"][0]["schema"]["enum"])
    for value in sorted(old_enum - new_enum):
        change("request-parameter-enum-value-removed", f"removed the enum value `{value}` from the `query` request parameter `color`")
    return entries


def _runner() -> Callable[[Sequence[str], Path | None], tuple[int, str, str]]:
    if REAL_OASDIFF is not None:
        return _real_runner
    return _fake_oasdiff(_structural_entries)


def _real_runner(command: Sequence[str], cwd: Path | None = None) -> tuple[int, str, str]:
    completed = subprocess.run(list(command), capture_output=True, text=True, check=False, cwd=cwd)  # noqa: S603 -- test helper, argument list
    return completed.returncode, completed.stdout, completed.stderr


def _which(name: str) -> str | None:
    if name == "oasdiff":
        return REAL_OASDIFF or "/fixture/bin/oasdiff"
    return shutil.which(name)


def _run(checker: ModuleType, root: Path, *extra: str, runner: object = None, which: Callable[[str], str | None] = _which) -> tuple[int, str]:
    lines: list[str] = []
    code = checker.run(["--root", str(root), *extra], runner=runner or _runner(), which=which, out=lines.append)
    return code, "\n".join(lines)


def _pair(checker: ModuleType, case: str, *extra: str, root: Path | None = None) -> tuple[int, str]:
    return _run(checker, root or CANDIDATES / case, "--baseline-root", str(BASELINE), *extra)


def _with_version(tmp_path: Path, case: str, version: str) -> Path:
    """A copy of a committed candidate with ``info.version`` moved (the fixture itself is never edited)."""
    root = tmp_path / f"{case}-{version}"
    shutil.copytree(CANDIDATES / case, root)
    document = root / "things" / "openapi.yaml"
    text = document.read_text(encoding="utf-8").replace("version: 1.0.0", f"version: {version}")
    document.write_text(text, encoding="utf-8")
    return root


def test_fixture_tree_is_not_a_module_and_is_committed() -> None:
    tracked = subprocess.run(["git", "ls-files", str(FIXTURES)], capture_output=True, text=True, check=True, cwd=FIXTURES).stdout.split()  # noqa: S603, S607 -- git, argument list
    on_disk = [p for p in FIXTURES.rglob("*") if p.is_file()]
    assert on_disk and len(tracked) == len(on_disk)


# -- the five breaking classes: fail without a major move, pass with one --------------------------


@pytest.mark.parametrize("case", sorted(BREAKING_CASES))
def test_breaking_change_fails_without_a_major_move(checker: ModuleType, case: str) -> None:
    code, output = _pair(checker, case)
    assert code == 1, output
    assert "BREAKING_WITHOUT_MAJOR: things:" in output
    assert "counts: modules=1 baselines=1 breaking=" in output
    assert "breaking=0" not in output


@pytest.mark.parametrize("case", sorted(BREAKING_CASES))
def test_breaking_change_passes_with_a_major_move(checker: ModuleType, tmp_path: Path, case: str) -> None:
    code, output = _pair(checker, case, root=_with_version(tmp_path, case, "2.0.0"))
    assert code == 0, output
    assert "BREAKING_WITHOUT_MAJOR" not in output
    assert "baselines=1" in output
    assert "breaking=0" not in output, "the breaking change is still counted when the major moved"


@pytest.mark.parametrize("case", sorted(BREAKING_CASES))
def test_a_minor_move_does_not_excuse_a_breaking_change(checker: ModuleType, tmp_path: Path, case: str) -> None:
    code, output = _pair(checker, case, root=_with_version(tmp_path, case, "1.9.0"))
    assert code == 1 and "BREAKING_WITHOUT_MAJOR" in output, output


# -- clean controls and the version rule -----------------------------------------------------------


def test_unchanged_candidate_is_clean(checker: ModuleType) -> None:
    code, output = _pair(checker, "clean_same")
    assert code == 0, output
    assert "counts: modules=1 baselines=1 breaking=0 provisional_changes=0 no_baseline_initial=0" in output


def test_compatible_change_with_a_minor_move_is_clean(checker: ModuleType) -> None:
    code, output = _pair(checker, "clean_minor")
    assert code == 0, output
    assert "breaking=0" in output


def test_changed_bundle_with_the_same_version_fails(checker: ModuleType) -> None:
    code, output = _pair(checker, "changed_same_version")
    assert code == 1
    assert "BUNDLE_CHANGED_VERSION_SAME: things:" in output


def test_lowered_version_fails_with_its_own_code(checker: ModuleType, tmp_path: Path) -> None:
    code, output = _pair(checker, "clean_minor", root=_with_version(tmp_path, "changed_same_version", "0.9.0"))
    assert code == 1 and "VERSION_DECREASED: things:" in output


def test_a_request_side_optional_addition_stays_non_breaking(checker: ModuleType) -> None:
    """clean_minor adds an optional query parameter (and drops a provisional response property): compatible, minor move."""
    parameters = yaml.safe_load((CANDIDATES / "clean_minor" / "things" / "paths" / "things.yaml").read_text(encoding="utf-8"))["get"]["parameters"]
    assert [p["name"] for p in parameters] == ["color", "limit"] and not parameters[1]["required"]
    code, output = _pair(checker, "clean_minor")
    assert code == 0 and "breaking=0" in output, output


def test_an_added_response_property_is_breaking_and_names_the_closed_schema_rule(checker: ModuleType) -> None:
    code, output = _pair(checker, "added_response_property")
    assert code == 1, output
    assert "BREAKING_WITHOUT_MAJOR: things:" in output and "added the optional property `size`" in output
    assert "closed response schemas" in output


def test_the_response_addition_rule_lists_every_oasdiff_id_that_reports_one(checker: ModuleType) -> None:
    assert set(checker.RESPONSE_ADDITION_IDS) == {
        # a property added to a response schema
        "response-optional-property-added",
        "response-required-property-added",
        "response-optional-write-only-property-added",
        "response-required-write-only-property-added",
        # a property added through a new allOf branch (oneOf and anyOf branches are already errors in oasdiff)
        "response-body-all-of-added",
        "response-property-all-of-added",
        # a response that did not exist before, or a new shape of an existing one
        "response-success-status-added",
        "response-non-success-status-added",
        "response-media-type-added",
        "response-header-added",
    }
    assert set(RESPONSE_ADDITION_CASES.values()) <= set(checker.RESPONSE_ADDITION_IDS)


@pytest.mark.parametrize("case", sorted(RESPONSE_ADDITION_CASES))
def test_each_response_addition_names_its_own_change(checker: ModuleType, case: str) -> None:
    """The failure text carries the change oasdiff described, so a reader sees which part of the response grew."""
    code, output = _pair(checker, case)
    assert code == 1, output
    assert "BREAKING_WITHOUT_MAJOR: things:" in output and "closed response schemas" in output


@pytest.mark.skipif(REAL_OASDIFF is None, reason="needs the real oasdiff to prove which change id it reports")
@pytest.mark.parametrize("case", sorted(RESPONSE_ADDITION_CASES))
def test_the_real_oasdiff_reports_each_response_addition_under_the_listed_id(checker: ModuleType, tmp_path: Path, case: str) -> None:
    base = checker.write_document(checker.build_bundle(BASELINE / "things", tmp_path / "b"), tmp_path / "base.yaml")
    head = checker.write_document(checker.build_bundle(CANDIDATES / case / "things", tmp_path / "h"), tmp_path / "head.yaml")
    reported = {entry["id"]: entry["level"] for entry in checker.oasdiff_changelog(_real_runner, REAL_OASDIFF or "", base, head)}
    assert reported == {RESPONSE_ADDITION_CASES[case]: 1}, "the case plants exactly one change, which oasdiff alone calls INFO"


@pytest.mark.skipif(REAL_OASDIFF is None, reason="needs the real oasdiff to prove its default level for an added response property")
@pytest.mark.parametrize("case", ["added_response_property", *sorted(RESPONSE_ADDITION_CASES)])
def test_oasdiff_alone_does_not_call_an_added_response_property_breaking(checker: ModuleType, tmp_path: Path, case: str) -> None:
    """The reason the rule exists: the real binary reports each addition at INFO, which a plain ``breaking`` run would let through."""
    base = checker.write_document(checker.build_bundle(BASELINE / "things", tmp_path / "b"), tmp_path / "base.yaml")
    head = checker.write_document(checker.build_bundle(CANDIDATES / case / "things", tmp_path / "h"), tmp_path / "head.yaml")
    assert checker.oasdiff_breaking(_real_runner, REAL_OASDIFF or "", base, head) == []


# -- provisional elements are reported separately and never fail -----------------------------------


def test_provisional_only_change_does_not_fail_and_is_reported(checker: ModuleType) -> None:
    code, output = _pair(checker, "provisional_only")
    assert code == 0, output
    assert "PROVISIONAL_CHANGE: things:" in output
    assert "provisional_changes=1" in output and "breaking=0" in output
    assert "BUNDLE_CHANGED_VERSION_SAME" not in output


def test_strip_provisional_removes_the_property_and_its_required_entry(checker: ModuleType) -> None:
    document = {
        "required": ["id", "guess"],
        "properties": {"id": {"type": "string"}, "guess": {"x-provisional": {"open_decision": "x"}}},
        "get": {"x-provisional": {"open_decision": "x"}},
        "parameters": [{"name": "a"}, {"name": "b", "x-provisional": {"open_decision": "x"}}],
    }
    stripped = checker.strip_provisional(document)
    assert stripped == {"required": ["id"], "properties": {"id": {"type": "string"}}, "parameters": [{"name": "a"}]}
    assert document["required"] == ["id", "guess"], "the input is not modified"


# -- no baseline: the first release is an explicit, counted state ----------------------------------


def _git(repo: Path, *arguments: str) -> None:
    subprocess.run(["git", "-C", str(repo), *arguments], check=True, capture_output=True, text=True)  # noqa: S603, S607 -- test helper, argument list


def _repo(tmp_path: Path, case: str = "clean_same", version: str = "1.0.0", heading: str | None = None) -> Path:
    repo = tmp_path / "repo"
    (repo / "contracts").mkdir(parents=True)
    shutil.copytree(CANDIDATES / case / "things", repo / "contracts" / "things")
    if version != "1.0.0":
        document = repo / "contracts" / "things" / "openapi.yaml"
        document.write_text(document.read_text(encoding="utf-8").replace("version: 1.0.0", f"version: {version}"), encoding="utf-8")
    if heading is not None:
        changelog = repo / "contracts" / "things" / "CHANGELOG.md"
        changelog.write_text(changelog.read_text(encoding="utf-8").replace("## 1.0.0", f"## {heading}"), encoding="utf-8")
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "fixture@example.invalid")
    _git(repo, "config", "user.name", "fixture")
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "baseline")
    return repo


def test_no_baseline_with_the_initial_version_is_loud_counted_and_summarised(checker: ModuleType, tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    summary = tmp_path / "summary.md"
    code, output = _run(checker, repo / "contracts", "--summary", str(summary))
    assert code == 0, output
    assert "NO_BASELINE_INITIAL_VERSION: things:" in output
    assert "no_baseline_initial=1" in output and "baselines=0" in output
    assert "PREVIEW_REF_NONE" in output and "preview_ref=none" in output
    assert "NO_BASELINE_INITIAL_VERSION" in summary.read_text(encoding="utf-8")


def test_no_baseline_with_another_version_fails(checker: ModuleType, tmp_path: Path) -> None:
    repo = _repo(tmp_path, version="1.4.0")
    code, output = _run(checker, repo / "contracts")
    assert code == 1 and "NO_BASELINE_NOT_INITIAL: things:" in output
    assert "no_baseline_initial=0" in output


def test_no_baseline_without_a_changelog_entry_fails(checker: ModuleType, tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / "contracts" / "things" / "CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    code, output = _run(checker, repo / "contracts")
    assert code == 1 and "NO_BASELINE_NOT_INITIAL" in output


# -- -SNAPSHOT: the work in progress of a version -----------------------------------------------------


def test_no_baseline_with_the_initial_snapshot_version_is_the_first_release_in_progress(checker: ModuleType, tmp_path: Path) -> None:
    repo = _repo(tmp_path, version="1.0.0-SNAPSHOT", heading="1.0.0-SNAPSHOT")
    code, output = _run(checker, repo / "contracts")
    assert code == 0, output
    assert "NO_BASELINE_INITIAL_VERSION: things:" in output and "1.0.0-SNAPSHOT" in output
    assert "no_baseline_initial=1" in output


def test_no_baseline_with_a_snapshot_of_another_version_fails(checker: ModuleType, tmp_path: Path) -> None:
    repo = _repo(tmp_path, version="1.1.0-SNAPSHOT", heading="1.1.0-SNAPSHOT")
    code, output = _run(checker, repo / "contracts")
    assert code == 1 and "NO_BASELINE_NOT_INITIAL: things:" in output


def test_no_baseline_with_the_initial_snapshot_needs_its_own_changelog_heading(checker: ModuleType, tmp_path: Path) -> None:
    repo = _repo(tmp_path, version="1.0.0-SNAPSHOT")  # the heading stays ## 1.0.0
    code, output = _run(checker, repo / "contracts")
    assert code == 1 and "NO_BASELINE_NOT_INITIAL: things:" in output


def test_a_snapshot_of_a_later_major_excuses_a_breaking_change_against_the_release(checker: ModuleType, tmp_path: Path) -> None:
    code, output = _pair(checker, "removed_property", root=_with_version(tmp_path, "removed_property", "2.0.0-SNAPSHOT"))
    assert code == 0, output
    assert "BREAKING_WITHOUT_MAJOR" not in output and "breaking=0" not in output


def test_a_snapshot_of_a_minor_does_not_excuse_a_breaking_change(checker: ModuleType, tmp_path: Path) -> None:
    code, output = _pair(checker, "removed_property", root=_with_version(tmp_path, "removed_property", "1.1.0-SNAPSHOT"))
    assert code == 1 and "BREAKING_WITHOUT_MAJOR" in output


def test_a_compatible_change_under_the_next_minor_snapshot_passes(checker: ModuleType, tmp_path: Path) -> None:
    code, output = _pair(checker, "changed_same_version", root=_with_version(tmp_path, "changed_same_version", "1.1.0-SNAPSHOT"))
    assert code == 0, output


def test_the_snapshot_of_the_released_version_is_below_the_release(checker: ModuleType, tmp_path: Path) -> None:
    """1.0.0-SNAPSHOT is the work in progress OF 1.0.0, so a changed bundle against the 1.0.0 release has gone backwards."""
    code, output = _pair(checker, "changed_same_version", root=_with_version(tmp_path, "changed_same_version", "1.0.0-SNAPSHOT"))
    assert code == 1 and "VERSION_DECREASED: things:" in output


def test_a_snapshot_release_tag_is_never_the_baseline(checker: ModuleType) -> None:
    assert checker.latest_release_tag(["contract-things-v1.0.0-SNAPSHOT"], "things") is None
    assert checker.latest_release_tag(["contract-things-v1.0.0", "contract-things-v2.0.0-SNAPSHOT"], "things") == "contract-things-v1.0.0"
    assert checker.latest_release_tag(["contract-things-v1.0.0-rc.1"], "things") == "contract-things-v1.0.0-rc.1"


@pytest.mark.parametrize(
    ("version", "snapshot"),
    [
        ("1.0.0-SNAPSHOT", True),
        ("1.0.0-SNAPSHOT+b1", True),  # build metadata does not change what the version is
        ("1.0.0-rc.1-SNAPSHOT+build.7", True),
        ("1.0.0", False),
        ("1.0.0+SNAPSHOT", False),  # SNAPSHOT as build metadata is not a prerelease
        ("1.0.0-rc.1+b1", False),
        ("1.0.0-snapshot", False),  # a legal prerelease, released with --prerelease
        ("1.0.0-SNAPSHOT.1", False),
    ],
)
def test_breaking_check_and_release_check_agree_on_what_a_snapshot_is(checker: ModuleType, version: str, snapshot: bool) -> None:
    with pytest.MonkeyPatch.context() as mp:
        releaser = load_tool(mp, TOOLS_DIR / "release_check.py", "release_check_for_snapshot_parity", syspath=TOOLS_DIR)
        refused_as_release = releaser.is_snapshot(version)
    baseline = checker.latest_release_tag([f"contract-things-v{version}"], "things")
    assert refused_as_release is snapshot
    assert (baseline is None) is snapshot, "a tag release_check refuses as a snapshot must never be the release baseline"


def test_release_tag_baseline_is_rebuilt_from_git_and_compared(checker: ModuleType, tmp_path: Path) -> None:
    repo = _repo(tmp_path, "clean_same")
    _git(repo, "tag", "contract-things-v1.0.0")
    for name in ("contract-things-v0.9.0", "contract-other-v7.0.0", "contract-things-vnext"):
        _git(repo, "tag", name)
    shutil.rmtree(repo / "contracts" / "things")
    shutil.copytree(CANDIDATES / "required_parameter" / "things", repo / "contracts" / "things")
    code, output = _run(checker, repo / "contracts")
    assert code == 1, output
    assert "BREAKING_WITHOUT_MAJOR: things:" in output and "baselines=1" in output
    assert "NO_BASELINE" not in output and "PREVIEW" not in output, "a release baseline replaces the preview report"


def test_the_tag_being_released_is_never_its_own_baseline(checker: ModuleType, tmp_path: Path) -> None:
    """The release workflow runs on the pushed tag; without ``--release-tag`` the check would compare the commit with itself."""
    repo = _repo(tmp_path, "clean_same")
    _git(repo, "tag", "contract-things-v1.0.0")
    shutil.rmtree(repo / "contracts" / "things")
    shutil.copytree(CANDIDATES / "required_parameter" / "things", repo / "contracts" / "things")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "a breaking change that keeps the major")
    _git(repo, "tag", "contract-things-v1.1.0")
    code, output = _run(checker, repo / "contracts")
    assert code == 0 and "breaking=0" in output, "the pushed tag is the newest release, so the plain run compares the commit with itself"
    code, output = _run(checker, repo / "contracts", "--release-tag", "contract-things-v1.1.0")
    assert code == 1 and "BREAKING_WITHOUT_MAJOR: things:" in output and "baselines=1" in output, output


def test_latest_release_tag_can_leave_out_the_tag_being_released(checker: ModuleType) -> None:
    tags = ["contract-things-v1.0.0", "contract-things-v1.1.0"]
    assert checker.latest_release_tag(tags, "things", exclude="contract-things-v1.1.0") == "contract-things-v1.0.0"
    assert checker.latest_release_tag(tags, "things") == "contract-things-v1.1.0"


def test_latest_release_tag_picks_the_highest_semver_and_ignores_other_tags(checker: ModuleType) -> None:
    tags = ["contract-things-v1.2.0", "contract-things-v1.10.0", "contract-things-v1.10.0-rc.1", "contract-other-v9.0.0", "contract-things-v2"]
    assert checker.latest_release_tag(tags, "things") == "contract-things-v1.10.0"
    assert checker.latest_release_tag(["contract-things-v1.0.0-rc.1", "contract-things-v1.0.0"], "things") == "contract-things-v1.0.0"
    assert checker.latest_release_tag([], "things") is None


# -- the preview report is informational ------------------------------------------------------------


def test_preview_report_names_the_latest_preview_tag(checker: ModuleType, tmp_path: Path) -> None:
    repo = _repo(tmp_path, "clean_same")
    for name in ("preview/things/p2", "preview/things/p10", "preview/things/p9"):
        _git(repo, "tag", name)
    code, output = _run(checker, repo / "contracts")
    assert code == 0, output
    assert "preview_ref=preview/things/p10" in output
    assert "PREVIEW_DELTA things: preview_ref=preview/things/p10" in output


def test_preview_delta_alone_never_fails(checker: ModuleType, tmp_path: Path) -> None:
    repo = _repo(tmp_path, "clean_same")
    _git(repo, "tag", "preview/things/p1")
    shutil.rmtree(repo / "contracts" / "things")
    shutil.copytree(CANDIDATES / "removed_path" / "things", repo / "contracts" / "things")
    code, output = _run(checker, repo / "contracts")
    assert code == 0, output
    assert "NO_BASELINE_INITIAL_VERSION" in output and "preview_ref=preview/things/p1" in output
    assert "PREVIEW_DELTA things: level=" in output, "the removed path is reported against the preview tag"


def test_a_preview_tag_listing_that_fails_never_changes_the_exit_status(checker: ModuleType, tmp_path: Path) -> None:
    """The preview report is informational: when only ITS tag listing fails the run still passes and says so."""
    repo = _repo(tmp_path, "clean_same")
    inner = _runner()

    def runner(command: Sequence[str], cwd: Path | None = None) -> tuple[int, str, str]:
        if "tag" in command and "preview/things/*" in command:
            return 1, "", "fatal: the tag listing failed"
        return inner(command, cwd)

    code, output = _run(checker, repo / "contracts", runner=runner)

    assert code == 0, output
    assert "PREVIEW_DELTA things: preview_ref=unavailable (TAG_LIST_ERROR" in output and "informational, never fails" in output
    assert "preview_ref=unavailable" in output.splitlines()[-1]
    assert "NO_BASELINE_INITIAL_VERSION" in output


def test_a_release_tag_listing_that_fails_still_cannot_do_its_job(checker: ModuleType, tmp_path: Path) -> None:
    """Contrast: the RELEASE tag listing decides the baseline, so its failure is exit 2, not informational."""
    repo = _repo(tmp_path, "clean_same")
    inner = _runner()

    def runner(command: Sequence[str], cwd: Path | None = None) -> tuple[int, str, str]:
        if "tag" in command and "--list" in command and not any(str(part).startswith("preview/") for part in command):
            return 1, "", "fatal: the tag listing failed"
        return inner(command, cwd)

    code, output = _run(checker, repo / "contracts", runner=runner)

    assert code == 2 and "TAG_LIST_ERROR" in output


# -- cannot do its job: exit 2 ----------------------------------------------------------------------


def test_shallow_clone_exits_2(checker: ModuleType, tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    shallow = tmp_path / "shallow"
    subprocess.run(["git", "clone", "-q", "--depth", "1", f"file://{repo}", str(shallow)], check=True, capture_output=True, text=True)  # noqa: S603, S607 -- test helper
    code, output = _run(checker, shallow / "contracts")
    assert code == 2 and "SHALLOW_CHECKOUT" in output
    assert output.splitlines()[-1].startswith("counts: ")


def test_tag_listing_error_exits_2(checker: ModuleType, tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    def failing_tag(command: Sequence[str], cwd: Path | None = None) -> tuple[int, str, str]:
        if "tag" in command:
            return 128, "", "fatal: cannot list tags"
        return _real_runner(command, cwd)

    code, output = _run(checker, repo / "contracts", runner=failing_tag)
    assert code == 2 and "TAG_LIST_ERROR" in output


def test_unbuildable_baseline_exits_2(checker: ModuleType, tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    document = repo / "contracts" / "things" / "openapi.yaml"
    clean = document.read_text(encoding="utf-8")
    document.write_text(clean.replace("paths/things.yaml", "paths/absent.yaml"), encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "dangling path file")
    _git(repo, "tag", "contract-things-v1.0.0")
    document.write_text(clean, encoding="utf-8")
    code, output = _run(checker, repo / "contracts")
    assert code == 2 and "BASELINE_UNBUILDABLE" in output


def test_missing_oasdiff_exits_2(checker: ModuleType) -> None:
    code, output = _run(checker, CANDIDATES / "clean_same", "--baseline-root", str(BASELINE), which=lambda _name: None)
    assert code == 2 and "OASDIFF_MISSING" in output
    assert output.splitlines()[-1].startswith("counts: ")


def test_oasdiff_failure_exits_2(checker: ModuleType) -> None:
    def broken(command: Sequence[str], cwd: Path | None = None) -> tuple[int, str, str]:
        return 3, "", "boom"

    code, output = _run(checker, CANDIDATES / "removed_path", "--baseline-root", str(BASELINE), runner=broken, which=lambda _n: "/fixture/bin/oasdiff")
    assert code == 2 and "OASDIFF_FAILED" in output


def test_no_module_exits_2(checker: ModuleType, tmp_path: Path) -> None:
    code, output = _run(checker, tmp_path, "--baseline-root", str(BASELINE))
    assert code == 2 and "NO_MODULE" in output
