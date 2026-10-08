"""Planted-violation tests for ``contracts/tools/leak_scan.py`` (FR-012, NFR-004, FR-021, FR-025).

Leak-class plants are never committed: ``fixture_builder`` assembles them from fragments into a temporary
root next to a clean control, and the scan must report exactly the planted code there and nothing on the
control. Only clean controls and the exit-2 shapes are committed, under ``contracts/tools/fixtures/leak_scan/``.
The scan has no exempt directory: it also runs over the real ``contracts/tools`` tree (the self-reference
control) and over the whole real ``contracts`` tree, each with a floor on what it scanned.
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

from tests.contract._loader import load_tool

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = REPO_ROOT / "contracts"
TOOLS_DIR = CONTRACTS / "tools"
FIXTURE_ROOT = TOOLS_DIR / "fixtures" / "leak_scan"
SCRIPT = TOOLS_DIR / "leak_scan.py"

OLD_KINDS = ["host-path-strict", "host-path-human", "email", "email-dotless", "github-token", "aws-key", "private-key", "forbidden-property"]
STRICT_NAMES = [
    "id",
    "laneId",
    "laneBranch",
    "planningBranch",
    "pattern",
    "feedbackReference",
    "reviewer",
    "kind",
    "mediaType",
    "changeState",
    "specKittyVersion",
    "currentBranch",
    "profileId",
    "action",
    "invocationId",
    "sourceCode",
]
ARTIFACT_PATH_REASONS = [
    "empty",
    "too_long",
    "absolute",
    "tilde",
    "drive_letter",
    "backslash",
    "nul",
    "line_break",
    "empty_segment",
    "trailing_slash",
    "dot_segment",
    "dotdot_segment",
]
ARTIFACT_PATH_KINDS = [f"artifact-path-{reason.replace('_', '-')}" for reason in ARTIFACT_PATH_REASONS] + ["artifact-path-reference"]
REGRESSION_CONTROL_KINDS = ["content-host-path-and-email", "credential-in-content", "credential-in-title"]
ALL_KINDS = OLD_KINDS + [f"strict-{name}" for name in STRICT_NAMES] + ARTIFACT_PATH_KINDS + REGRESSION_CONTROL_KINDS
MALFORMED = "ARTIFACT_PATH_MALFORMED"

SLASH = chr(47)
AT = chr(64)
NUL = chr(0)
BACKSLASH = chr(92)


@pytest.fixture(scope="module")
def scan() -> Iterator[Any]:
    with pytest.MonkeyPatch.context() as mp:
        yield load_tool(mp, SCRIPT, "leak_scan_under_test", syspath=TOOLS_DIR)


def test_no_tracked_contracts_file_lies_under_a_directory_name_the_scan_skips(scan: Any) -> None:
    """The docstring names the skipped directories and promises none of them holds a shipped file."""
    listed = subprocess.run(["git", "ls-files", "-z", "--", "contracts"], cwd=REPO_ROOT, capture_output=True, check=True).stdout
    tracked = [name for name in listed.decode("utf-8").split(chr(0)) if name]
    assert tracked, "git listed no contracts file"
    hidden = [name for name in tracked if scan.SKIPPED_DIRECTORIES & set(Path(name).parts)]
    assert hidden == [], f"tracked files the scan never reads: {hidden}"


@pytest.fixture(scope="module")
def builder(scan: Any) -> ModuleType:
    return sys.modules["fixture_builder"]


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *arguments], capture_output=True, text=True, check=False, cwd=REPO_ROOT)


def _home(tail: str = "project") -> str:
    return SLASH + "home" + SLASH + "someone" + SLASH + tail


def _email() -> str:
    return "someone" + AT + "example.invalid"


# -- every planted kind is found, the control on the same root is not ---------------------------


@pytest.mark.parametrize("kind", ALL_KINDS)
def test_each_leak_kind_is_found_and_the_control_on_the_same_root_is_not(scan: Any, builder: ModuleType, kind: str, tmp_path: Path) -> None:
    built = builder.build(kind, tmp_path)
    report = scan.check(tmp_path)
    planted = [f for f in report.findings if builder.PLANTED_FILE in f.subject]
    control = [f for f in report.findings if builder.CONTROL_FILE in f.subject]
    assert control == [], control
    assert set(built.expected_codes) <= {f.code for f in planted}, (kind, [f.render() for f in report.findings])
    assert {f.code for f in planted} <= set(built.expected_codes) | {"HOST_PATH", "EMAIL", "SECRET"}
    assert report.exit_code == 1


def test_a_finding_never_prints_the_leaked_value(scan: Any, builder: ModuleType, tmp_path: Path) -> None:
    builder.build("host-path-human", tmp_path)
    builder.build("email", tmp_path / "second")
    builder.build("email-dotless", tmp_path / "third")
    for finding in scan.check(tmp_path).findings:
        assert "someone" not in finding.render()


@pytest.mark.parametrize("kind", ["github-token", "aws-key", "private-key"])
def test_a_planted_secret_is_reported_as_secret_without_echoing_it(scan: Any, builder: ModuleType, tmp_path: Path, kind: str) -> None:
    built = builder.build(kind, tmp_path)
    planted = [f for f in scan.check(tmp_path).findings if builder.PLANTED_FILE in f.subject]
    assert {f.code for f in planted} == {"SECRET"}
    value = yaml.safe_load((tmp_path / "planted" / "examples" / builder.PLANTED_FILE).read_text(encoding="utf-8"))[built.field]
    assert all(value[:12] not in f.render() for f in planted)


def test_the_strict_class_catches_a_tilde_path_that_the_human_text_pass_alone_would_not(scan: Any, builder: ModuleType, tmp_path: Path) -> None:
    builder.build("host-path-strict", tmp_path)
    codes = [(f.code, f.subject) for f in scan.check(tmp_path).findings]
    assert len(codes) == 1 and codes[0][0] == "HOST_PATH" and codes[0][1].endswith("targetBranch")


def test_the_forbidden_name_is_found_in_a_json_key_but_not_in_a_value(scan: Any, tmp_path: Path) -> None:
    name = "record" + "Path"
    (tmp_path / "a.json").write_text(json.dumps({"slug": "x", "title": "y", name: "relative/value"}), encoding="utf-8")
    (tmp_path / "b.json").write_text(json.dumps({"slug": "x", "title": name}), encoding="utf-8")
    codes = {f.subject.split(":")[0]: f.code for f in scan.check(tmp_path).findings}
    assert codes == {"a.json": "FORBIDDEN_PROPERTY_NAME"}


def test_the_text_pass_reads_every_file_type(scan: Any, tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text(f"See {_home('notes')} for details.\n", encoding="utf-8")
    (tmp_path / "CHANGELOG.md").write_text(f"Thanks {_email()}.\n", encoding="utf-8")
    (tmp_path / "tool.py").write_text(f'NOTE = "{_home()}"\n', encoding="utf-8")
    (tmp_path / "ok.yaml").write_text("slug: example\ntitle: Example\n", encoding="utf-8")
    found = {(f.subject.split(":")[0], f.code) for f in scan.check(tmp_path).findings}
    assert found == {("README.md", "HOST_PATH"), ("CHANGELOG.md", "EMAIL"), ("tool.py", "HOST_PATH")}


@pytest.mark.parametrize("directory", ["fixtures", "tools", "examples", "planted", "_shared"])
def test_no_directory_is_exempt(scan: Any, builder: ModuleType, tmp_path: Path, directory: str) -> None:
    builder.build("host-path-human", tmp_path / directory / "nested")
    assert [f.code for f in scan.check(tmp_path).findings if directory in f.subject] == ["HOST_PATH", "HOST_PATH"]


def test_a_planted_line_is_reported_with_its_line_number(scan: Any, tmp_path: Path) -> None:
    (tmp_path / "doc.md").write_text(f"first line\nsecond line\nthird {_home()} line\n", encoding="utf-8")
    assert [f.subject for f in scan.check(tmp_path).findings] == ["doc.md:3"]


# -- the real pass controls, and the clean control root ---------------------------------------------


def test_the_clean_control_passes_with_every_class_populated(scan: Any) -> None:
    report = scan.check(FIXTURE_ROOT / "clean")
    assert report.findings == [] and report.blocked == []
    assert report.counts["files"] == 3
    assert report.counts["values_strict"] >= 5 and report.counts["values_human"] >= 4 and report.counts["values_all"] >= 10


def test_the_two_real_pass_controls_are_not_leaks(scan: Any, tmp_path: Path) -> None:
    (tmp_path / "a.yaml").write_text("slug: example\nfriendlyName: ~/.kittify Runtime Centralization\ntitle: '/tmp burn-down: sync'\n", encoding="utf-8")
    assert scan.check(tmp_path).findings == []


# -- a file the structured pass cannot parse ------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "content"),
    [
        pytest.param("broken.yaml", "slug: [unclosed\ntitle: x\n", id="yaml"),
        pytest.param("broken.yml", "a: b\n\tc: d\n", id="yml"),
        pytest.param("broken.json", '{"slug": "x",}', id="json"),
    ],
)
def test_a_yaml_or_json_file_that_fails_to_parse_is_a_parse_failed_finding(scan: Any, tmp_path: Path, name: str, content: str) -> None:
    (tmp_path / "ok.yaml").write_text("slug: example\ntitle: Example\n", encoding="utf-8")
    (tmp_path / name).write_text(content, encoding="utf-8")
    report = scan.check(tmp_path)
    parse_failed = [f for f in report.findings if f.code == "PARSE_FAILED"]
    assert [f.subject for f in parse_failed] == [name]
    assert report.exit_code == 1
    assert all(f.subject == name for f in report.findings)
    result = _run("--root", str(tmp_path))
    assert result.returncode == 1
    assert f"CONTRACT-CHECK leak_scan: PARSE_FAILED: {name}: " in result.stdout


def test_a_parse_failure_never_prints_the_file_content(scan: Any, tmp_path: Path) -> None:
    (tmp_path / "ok.yaml").write_text("slug: example\ntitle: Example\n", encoding="utf-8")
    (tmp_path / "bad.yaml").write_text(f"title: [{_home()}\n", encoding="utf-8")
    (finding,) = [f for f in scan.check(tmp_path).findings if f.code == "PARSE_FAILED"]
    assert "someone" not in finding.render()


# -- cannot do its job -----------------------------------------------------------------------------


def test_an_empty_root_exits_two_zero_files(scan: Any, tmp_path: Path) -> None:
    report = scan.check(tmp_path)
    assert [f.code for f in report.blocked][:1] == ["ZERO_FILES"] and report.exit_code == 2
    result = _run("--root", str(tmp_path))
    assert result.returncode == 2 and "CONTRACT-CHECK leak_scan: ZERO_FILES" in result.stdout
    assert result.stdout.splitlines()[-1].startswith("counts: files=0 ")


def test_a_missing_root_exits_two(scan: Any, tmp_path: Path) -> None:
    assert [f.code for f in scan.check(tmp_path / "absent").blocked][:1] == ["ZERO_FILES"]


@pytest.mark.parametrize(("case", "empty_class"), [("no_human_values", "human"), ("no_strict_values", "strict")])
def test_a_class_with_no_values_exits_two(scan: Any, case: str, empty_class: str) -> None:
    report = scan.check(FIXTURE_ROOT / "exit2" / case)
    assert [(f.code, f.subject) for f in report.blocked] == [("ZERO_VALUES_IN_CLASS", empty_class)]
    assert report.exit_code == 2


def test_a_scan_that_misses_every_plant_reports_planted_not_detected(scan: Any) -> None:
    def blind(_root: Path) -> list[Any]:
        return []

    findings = scan.run_self_test(blind)
    assert sorted(f.code for f in findings) == ["PLANTED_NOT_DETECTED"] * len(ALL_KINDS)
    assert {f.subject for f in findings} == set(ALL_KINDS)


def test_the_self_test_of_the_real_scan_passes(scan: Any) -> None:
    assert scan.run_self_test(scan.scan_tree) == []


def test_a_scan_that_flags_the_control_fails_the_self_test(scan: Any, builder: ModuleType) -> None:
    def paranoid(root: Path) -> list[Any]:
        flagged: list[Any] = [scan.Finding("HOST_PATH", f"{builder.CONTROL_FILE}:1", "flagged")]
        return flagged + list(scan.scan_tree(root))

    codes = [f.code for f in scan.run_self_test(paranoid)]
    assert "CONTROL_FLAGGED" in codes


def test_planted_not_detected_is_a_failure_of_the_real_command(scan: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(scan, "scan_tree", lambda _root: [])
    report = scan.check(FIXTURE_ROOT / "clean")
    assert report.exit_code == 1 and {f.code for f in report.findings} == {"PLANTED_NOT_DETECTED"}


# -- the real trees ----------------------------------------------------------------------------------


def test_the_self_reference_control_the_real_tools_tree_has_no_finding_and_a_floor(scan: Any) -> None:
    report = scan.check(TOOLS_DIR)
    assert report.findings == [], [f.render() for f in report.findings]
    assert report.blocked == []
    python_files = [p for p in TOOLS_DIR.rglob("*.py") if "__pycache__" not in p.parts]
    assert report.counts["files"] >= len(python_files) > 0


def test_the_whole_real_contracts_tree_has_no_finding() -> None:
    result = _run("--root", str(CONTRACTS))
    assert result.returncode == 0, result.stdout
    counts = dict(pair.split("=") for pair in result.stdout.splitlines()[-1].removeprefix("counts: ").split())
    assert int(counts["files"]) >= 100 and int(counts["values_strict"]) > 0 and int(counts["values_human"]) > 0 and int(counts["values_all"]) > 0


def test_command_line_exit_status_and_grammar_on_a_planted_root(tmp_path: Path, builder: ModuleType) -> None:
    builder.build("email", tmp_path)
    result = _run("--root", str(tmp_path))
    assert result.returncode == 1
    lines = result.stdout.splitlines()
    assert any(line.startswith("CONTRACT-CHECK leak_scan: EMAIL: ") for line in lines)
    assert all(key in lines[-1] for key in ("files=", "values_strict=", "values_human=", "values_all=", "values_artifact_path="))


# -- the artifact-path class (FR-015, AD-19, OD-4) ------------------------------------------------------


def _accented() -> str:
    return "caf" + chr(233) + ".md"


def _icon() -> str:
    return "icon" + AT + "2x.png"


# (path, reason or None): the table the predicate, its restatement below and (in the contract work package) the schema pattern agree on
PATH_CASES: list[tuple[str, str | None]] = [
    ("a.md", None),
    ("dir/a.md", None),
    ("home/someone/notes.md", None),
    ("with space.md", None),
    (_accented(), None),
    (_icon(), None),
    ("~", None),
    ("~user/a.md", None),
    (".hidden", None),
    ("a..b", None),
    ("...", None),
    ("a/.../b", None),
    ("1:a", None),
    ("dir/C:x", None),
    ("x" * 512, None),
    ("", "empty"),
    ("x" * 513, "too_long"),
    ("/a", "absolute"),
    ("/", "absolute"),
    ("~/a", "tilde"),
    ("~/", "tilde"),
    ("C:/a", "drive_letter"),
    ("z:", "drive_letter"),
    ("a" + BACKSLASH + "b", "backslash"),
    ("a" + NUL + "b", "nul"),
    ("a" + chr(10) + "b", "line_break"),
    ("a" + chr(13) + "b", "line_break"),
    ("a" + chr(11) + "b", "line_break"),
    ("a" + chr(12) + "b", "line_break"),
    ("a" + chr(28) + "b", "line_break"),
    ("a" + chr(133) + "b", "line_break"),
    ("a" + chr(0x2028) + "b", "line_break"),
    ("a" + chr(0x2029) + "b", "line_break"),
    ("a" + chr(10), "line_break"),
    ("a" + NUL + chr(10) + "b", "nul"),
    ("a" + BACKSLASH + chr(10) + "b", "backslash"),
    ("/a" + chr(10) + "b", "absolute"),
    ("a//" + chr(10) + "b", "line_break"),
    ("a/" + chr(10), "line_break"),
    ("a/../" + chr(10) + "b", "line_break"),
    ("a//b", "empty_segment"),
    ("a/", "trailing_slash"),
    ("a/b/", "trailing_slash"),
    ("./a", "dot_segment"),
    (".", "dot_segment"),
    ("a/./b", "dot_segment"),
    ("..", "dotdot_segment"),
    ("a/../b", "dotdot_segment"),
    ("../a", "dotdot_segment"),
]


def _spec_malformed(path: str) -> bool:
    """A literal restatement of the spec predicate (data model, ArtifactPath), written differently from the tool."""
    if path == "" or len(path) > 512:
        return True
    if path.startswith("/") or path.startswith("~/"):
        return True
    if len(path) >= 2 and path[1] == ":" and path[0].isascii() and path[0].isalpha():
        return True
    if BACKSLASH in path or NUL in path or any(character.splitlines() != [character] for character in path):
        return True
    segments = path.split("/")
    return path.endswith("/") or any(segment in ("", ".", "..") for segment in segments)


def test_the_table_holds_at_least_thirty_cases() -> None:
    assert len(PATH_CASES) >= 30


@pytest.mark.parametrize(("path", "reason"), PATH_CASES, ids=[f"{index}" for index in range(len(PATH_CASES))])
def test_malformed_artifact_path_gives_the_stable_reason(scan: Any, path: str, reason: str | None) -> None:
    assert scan.malformed_artifact_path(path) == reason


def test_the_predicate_the_restatement_and_the_table_agree_on_every_case(scan: Any) -> None:
    for path, reason in PATH_CASES:
        assert (scan.malformed_artifact_path(path) is not None) == _spec_malformed(path) == (reason is not None), repr(path)


def test_the_artifact_path_code_and_keys_exist(scan: Any) -> None:
    assert frozenset({"path", "artifactPath"}) == scan.ARTIFACT_PATH_KEYS
    assert scan.CODE_ARTIFACT_PATH == MALFORMED


def _write(root: Path, name: str, text: str) -> None:
    (root / name).parent.mkdir(parents=True, exist_ok=True)
    (root / name).write_text(text, encoding="utf-8")


def _with_filler(root: Path) -> Path:
    """A root that holds a value of each class so the floors never block the case under test."""
    _write(root, "ok.yaml", "slug: example\ntitle: Example\n")
    return root


def _subjects(scan: Any, root: Path) -> set[tuple[str, str]]:
    return {(f.code, f.subject) for f in scan.check(root).findings}


def test_a_malformed_artifact_path_is_reported_without_echoing_it_and_a_well_formed_one_is_not(scan: Any, tmp_path: Path) -> None:
    _with_filler(tmp_path)
    _write(tmp_path, "a.yaml", "entries:\n- path: /srv/notes.md\n- path: fine/notes.md\n- artifactPath: a/../b.md\n")
    found = scan.check(tmp_path).findings
    assert {(f.code, f.subject) for f in found} == {(MALFORMED, "a.yaml:entries[0].path"), (MALFORMED, "a.yaml:entries[2].artifactPath")}
    assert all("srv" not in f.render() for f in found)


def test_the_structured_pass_judges_a_path_value_by_the_predicate_and_not_by_the_host_path_patterns(scan: Any, tmp_path: Path) -> None:
    _with_filler(tmp_path)
    _write(tmp_path, "a.yaml", f"entries:\n- path: {_icon()}\n- path: home/someone/notes.md\n- path: {_accented()}\n")
    assert scan.check(tmp_path).findings == []


def test_a_planted_at_sign_path_in_a_control_does_not_fail_the_whole_scan(scan: Any, tmp_path: Path) -> None:
    _with_filler(tmp_path)
    _write(tmp_path, "examples/Thing.example.yaml", f"entries:\n- path: {_icon()}\n  title: Image\n")
    report = scan.check(tmp_path)
    assert report.findings == [] and report.blocked == [] and report.exit_code == 0
    assert report.counts["values_artifact_path"] == 1


def test_the_last_line_names_the_artifact_path_count_after_values_all(scan: Any, tmp_path: Path) -> None:
    _with_filler(tmp_path)
    _write(tmp_path, "a.yaml", "entries:\n- path: x.md\n- artifactPath: y.md\n")
    result = _run("--root", str(tmp_path))
    assert result.returncode == 0, result.stdout
    line = result.stdout.splitlines()[-1]
    keys = [pair.split("=")[0] for pair in line.removeprefix("counts: ").split()]
    assert keys == ["files", "values_strict", "values_human", "values_all", "values_artifact_path"]
    assert line.endswith("values_artifact_path=2")


# the OD-4 mask: bounded to the value of a path key outside x-source and x-derived


def test_a_path_value_alone_with_an_at_sign_is_not_an_e_mail_finding_of_the_text_pass(scan: Any, tmp_path: Path) -> None:
    _with_filler(tmp_path)
    _write(tmp_path, "a.yaml", f"item: {{path: {_icon()}}}\n")
    assert scan.check(tmp_path).findings == []


def test_a_flow_mapping_line_with_an_at_sign_path_and_an_address_in_the_title_reports_the_title_and_not_the_path(scan: Any, tmp_path: Path) -> None:
    _with_filler(tmp_path)
    _write(tmp_path, "a.yaml", f"item: {{path: {_icon()}, title: Contact {_email()} now}}\n")
    found = _subjects(scan, tmp_path)
    assert ("EMAIL", "a.yaml:1") in found, "the text pass still reports the address in the title on that line"
    assert ("EMAIL", "a.yaml:item.title") in found
    assert not [subject for _code, subject in found if subject.endswith("item.path")]


def test_the_mask_ends_at_the_value_so_a_later_line_is_still_scanned(scan: Any, tmp_path: Path) -> None:
    _with_filler(tmp_path)
    _write(tmp_path, "a.yaml", f"path: {_icon()}\nnote: Contact {_email()} now\nother: {_icon()}\n")
    assert ("EMAIL", "a.yaml:2") in _subjects(scan, tmp_path)
    assert ("EMAIL", "a.yaml:3") in _subjects(scan, tmp_path), "a key that is not a path key is not masked"
    assert ("EMAIL", "a.yaml:1") not in _subjects(scan, tmp_path)


def test_an_x_source_path_holding_an_address_is_reported(scan: Any, tmp_path: Path) -> None:
    _with_filler(tmp_path)
    _write(tmp_path, "a.yaml", f"x-source:\n  path: {_email()}\n  symbol: Thing\nx-derived:\n  path: {_email()}\n")
    found = _subjects(scan, tmp_path)
    assert {("EMAIL", "a.yaml:2"), ("EMAIL", "a.yaml:5")} <= found


def test_an_x_source_key_below_a_mapping_does_not_unmask_the_path_next_to_it(scan: Any, tmp_path: Path) -> None:
    _with_filler(tmp_path)
    _write(tmp_path, "a.yaml", f"entries:\n- path: {_icon()}\n  x-source:\n    path: {_email()}\n")
    found = _subjects(scan, tmp_path)
    assert ("EMAIL", "a.yaml:4") in found and ("EMAIL", "a.yaml:2") not in found


def test_a_token_in_a_path_value_is_still_reported(scan: Any, builder: ModuleType, tmp_path: Path) -> None:
    _with_filler(tmp_path)
    _write(tmp_path, "a.yaml", f"entries:\n- path: dir/{builder._github_token()}.md\n")
    found = _subjects(scan, tmp_path)
    assert ("SECRET", "a.yaml:2") in found, "SECRET is judged on the original line, never the blanked one"
    assert ("SECRET", "a.yaml:entries[0].path") in found


def test_a_json_file_is_scanned_unmasked(scan: Any, tmp_path: Path) -> None:
    _with_filler(tmp_path)
    _write(tmp_path, "a.json", json.dumps({"entries": [{"path": _icon()}]}) + "\n")
    assert ("EMAIL", "a.json:1") in _subjects(scan, tmp_path)


def test_a_yaml_file_that_does_not_parse_is_scanned_unmasked(scan: Any, tmp_path: Path) -> None:
    _with_filler(tmp_path)
    _write(tmp_path, "a.yaml", f"path: {_icon()}\nbroken: [unclosed\n")
    found = _subjects(scan, tmp_path)
    assert ("PARSE_FAILED", "a.yaml") in found and ("EMAIL", "a.yaml:1") in found


def test_the_helpers_blank_only_the_given_spans_and_keep_the_line_structure(scan: Any) -> None:
    text = f"a: 1\r\npath: {_icon()}\nb: 2\n"
    spans = scan.artifact_path_spans(text)
    assert len(spans) == 1
    masked = scan.mask_spans(text, spans)
    assert masked.splitlines() == ["a: 1", "path: " + " " * len(_icon()), "b: 2"]
    assert len(masked) == len(text)
    assert scan.artifact_path_spans("x-source: {path: y}\n") == []
    assert scan.artifact_path_spans("a: [unclosed\n") == []


# a line break in a path value is MALFORMED (reason line_break, after nul), so the OD-4 mask cannot hide what follows it


def _home_path() -> str:
    return SLASH + "home" + SLASH + "someone" + SLASH + "notes"


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("entries:\n- path: |-\n    a\n    {home}\n", "HOST_PATH"),
        ('entries:\n- path: "a\\n{home}"\n', ""),
        ('entries:\n- path: "a\\nb{at}c.com"\n', "EMAIL"),
        ("entries:\n- path: |-\n    a\n    b{at}c.com\n", "EMAIL"),
    ],
    ids=["home-in-block-scalar", "home-after-quoted-newline", "email-after-quoted-newline", "email-in-block-scalar"],
)
def test_a_line_break_in_a_path_value_does_not_hide_a_leak(scan: Any, tmp_path: Path, text: str, code: str) -> None:
    _with_filler(tmp_path)
    _write(tmp_path, "a.yaml", text.replace("{home}", _home_path()).replace("{at}", AT))
    found = _subjects(scan, tmp_path)
    assert (MALFORMED, "a.yaml:entries[0].path") in found
    # the text pass reads the line unmasked; a home path glued to the preceding text has no boundary for the host-path pattern, so only the reason reports it
    assert not code or any(c == code and subject.startswith("a.yaml:") and subject[len("a.yaml:") :].isdigit() for c, subject in found), (code, found)


def test_a_path_value_with_a_line_break_is_not_masked_by_the_helpers(scan: Any) -> None:
    assert scan.artifact_path_spans("path: |-\n  a\n  b\n") == []
    assert scan.artifact_path_spans('path: "a\\nb"\n') == []
    assert len(scan.artifact_path_spans("path: a b\n")) == 1


def test_a_single_line_path_with_an_at_sign_and_a_home_segment_still_passes(scan: Any, tmp_path: Path) -> None:
    _with_filler(tmp_path)
    _write(tmp_path, "a.yaml", f"entries:\n- path: home/someone/{_icon()}\n- path: {_icon()}\n")
    assert scan.check(tmp_path).findings == []
