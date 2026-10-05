"""Tests of the reference artifact reader of the ``mission-status`` contract (FR-009 to FR-014, FR-016, FR-020, FR-022).

Every rule of ``_mission_status_artifacts`` has a test with a clean twin: a negative case alone would pass against a
reader that refuses everything, so each refusal is paired with the accepted form of the same shape. Missions are
written at run time into a temporary directory, so no committed Mission is read and nothing under ``kitty-specs/``
of this checkout is touched. Leaking values (host paths, addresses, credentials, NUL, backslash) are assembled from
fragments, so this source holds none of them as a literal.
"""

from __future__ import annotations

import dataclasses
import json
import os
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml

from tests.contract import _mission_status_artifacts as art
from tests.contract import _mission_status_payloads as helper

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

REPO_ROOT = Path(__file__).resolve().parents[2]
SLASH = chr(47)
BACKSLASH = chr(92)
NUL = chr(0)
MISSION = "alpha-mission"
MISSION_ID = helper.fixture_ulid(1)
MISSING_ID = helper.fixture_ulid(2)
CLEAN_TEXT = "# A clean artifact\n"


@pytest.fixture(scope="module")
def tools() -> Iterator[helper.ContractTools]:
    with pytest.MonkeyPatch.context() as mp:
        yield helper.load_contract_tools(mp, REPO_ROOT)


def _put(mission_dir: Path, files: Mapping[str, str | bytes]) -> None:
    """Write ``files`` (relative path to text or bytes) below ``mission_dir``, creating directories."""
    for relative, content in files.items():
        target = mission_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8")


def _build(root: Path, files: Mapping[str, str | bytes] | None = None) -> Path:
    """One fixture Mission under ``root`` with the given files; returns its directory."""
    mission_dir = helper.write_fixture_mission(root, MISSION)
    _put(mission_dir, files or {})
    return mission_dir


def _ctx(root: Path, tools: helper.ContractTools, fs: art.FileSystem = art.REAL_FS) -> art.ReaderContext:
    return art.ReaderContext(repo_root=root, tools=tools, fs=fs)


def _read(ctx: art.ReaderContext, path: str) -> art.ArtifactOutcome:
    return art.read_content(ctx, MISSION_ID, [path])


def _listed_paths(ctx: art.ReaderContext) -> list[str]:
    outcome = art.list_artifacts(ctx, MISSION_ID)
    assert outcome.status == 200, f"the listing answered {outcome.status} {outcome.body.get('code')}"
    return [entry["path"] for entry in outcome.body["entries"]]


# ---------------------------------------------------------------------------
# Eligibility: regular file, no symlink component, not the root status records
# ---------------------------------------------------------------------------


def test_a_regular_file_is_eligible_and_a_symlink_to_it_is_not(tmp_path: Path, tools: helper.ContractTools) -> None:
    mission_dir = _build(tmp_path, {"spec.md": CLEAN_TEXT})
    (mission_dir / "alias.md").symlink_to(mission_dir / "spec.md")
    ctx = _ctx(tmp_path, tools)
    assert art.is_eligible(ctx, mission_dir, "spec.md"), "a regular file of the Mission must be eligible"
    assert not art.is_eligible(ctx, mission_dir, "alias.md"), "a symlink to a regular file must not be eligible"


def test_a_file_below_a_symlinked_directory_is_not_eligible(tmp_path: Path, tools: helper.ContractTools) -> None:
    mission_dir = _build(tmp_path, {"real/notes.md": CLEAN_TEXT, "plain/notes.md": CLEAN_TEXT})
    (mission_dir / "linked").symlink_to(mission_dir / "real", target_is_directory=True)
    ctx = _ctx(tmp_path, tools)
    assert art.is_eligible(ctx, mission_dir, "plain/notes.md"), "the same file below a real directory must be eligible"
    assert not art.is_eligible(ctx, mission_dir, "linked/notes.md"), "a file reached through a symlinked directory must not be eligible"


def test_a_symlinked_tasks_directory_hides_every_file_below_it(tmp_path: Path, tools: helper.ContractTools) -> None:
    mission_dir = _build(tmp_path, {"elsewhere/WP01-first.md": CLEAN_TEXT, "spec.md": CLEAN_TEXT})
    (mission_dir / "tasks").rmdir()
    (mission_dir / "tasks").symlink_to(mission_dir / "elsewhere", target_is_directory=True)
    ctx = _ctx(tmp_path, tools)
    assert art.is_eligible(ctx, mission_dir, "spec.md"), "the root specification stays eligible"
    assert not art.is_eligible(ctx, mission_dir, "tasks/WP01-first.md"), "a symlinked tasks/ makes its files not eligible"


def test_only_the_root_status_records_are_excluded(tmp_path: Path, tools: helper.ContractTools) -> None:
    mission_dir = _build(
        tmp_path,
        {
            "status.json": "{}",
            "status.events.jsonl": "",
            "nested/status.json": "{}",
            "nested/status.events.jsonl": "",
            "Status.JSON": "{}",
            "STATUS.EVENTS.JSONL": "",
            "Status.Events.Jsonl": "",
        },
    )
    ctx = _ctx(tmp_path, tools)
    assert not art.is_eligible(ctx, mission_dir, "status.json")
    assert not art.is_eligible(ctx, mission_dir, "status.events.jsonl")
    assert art.is_eligible(ctx, mission_dir, "nested/status.json"), "a nested status.json is an artifact"
    assert art.is_eligible(ctx, mission_dir, "nested/status.events.jsonl"), "a nested event log is an artifact"
    for variant in ("Status.JSON", "STATUS.EVENTS.JSONL", "Status.Events.Jsonl"):
        assert not art.is_eligible(ctx, mission_dir, variant), f"{variant}: the root records are matched without regard to case"
    assert "nested/status.json" in _listed_paths(ctx)
    assert "status.json" not in _listed_paths(ctx)


def test_a_directory_and_a_missing_path_are_not_eligible(tmp_path: Path, tools: helper.ContractTools) -> None:
    mission_dir = _build(tmp_path, {"folder/inner.md": CLEAN_TEXT})
    ctx = _ctx(tmp_path, tools)
    assert art.is_eligible(ctx, mission_dir, "folder/inner.md")
    assert not art.is_eligible(ctx, mission_dir, "folder"), "a directory is not an artifact"
    assert not art.is_eligible(ctx, mission_dir, "folder/absent.md")
    assert not art.is_eligible(ctx, mission_dir, "folder/inner.md/deeper.md"), "a file used as a directory is not eligible"


# ---------------------------------------------------------------------------
# The malformed-path table: 400 on the request, never a read
# ---------------------------------------------------------------------------


def _malformed_forms() -> dict[str, str]:
    return {
        "empty": "",
        "too-long": "a" * 513,
        "absolute": SLASH + "spec.md",
        "tilde": "~" + SLASH + "spec.md",
        "drive-letter": "C:spec.md",
        "backslash": "tasks" + BACKSLASH + "WP01-first.md",
        "nul": "spec" + NUL + ".md",
        "line-break": "spec" + chr(10) + ".md",
        "empty-segment": "tasks" + SLASH + SLASH + "WP01-first.md",
        "trailing-slash": "tasks" + SLASH,
        "dot-segment": "tasks" + SLASH + "." + SLASH + "WP01-first.md",
        "dotdot-segment": "tasks" + SLASH + ".." + SLASH + "spec.md",
    }


@pytest.mark.parametrize("form", sorted(_malformed_forms()))
def test_a_malformed_path_is_refused_400_and_its_clean_twin_is_read(form: str, tmp_path: Path, tools: helper.ContractTools) -> None:
    _build(tmp_path, {"spec.md": CLEAN_TEXT, "tasks/WP01-first.md": CLEAN_TEXT})
    ctx = _ctx(tmp_path, tools)
    refused = _read(ctx, _malformed_forms()[form])
    assert (refused.status, refused.body.get("code")) == (400, "invalid_artifact_path"), f"{form}: {refused.status} {refused.body}"
    assert _read(ctx, "tasks/WP01-first.md").status == 200, "the clean twin of the malformed forms must be read"


# ---------------------------------------------------------------------------
# The classifier: twelve kinds, first match wins
# ---------------------------------------------------------------------------

CLASSIFIER_CASES = [
    ("tasks/WP01-first/review-cycle-1.md", "review_cycle"),
    ("tasks/WP01-first/review-cycle-12.md", "review_cycle"),
    ("tasks/WP01-first/review-cycle-0.md", "other"),
    ("tasks/WP01-first/review-cycle-01.md", "other"),
    ("tasks/WP01-first/review-cycle-1.txt", "other"),
    ("tasks/review-cycle-1.md", "other"),
    ("tasks/a/b/review-cycle-1.md", "other"),
    ("tasks/WP01-first.md", "work_package_prompt"),
    ("tasks/WP123-longer-id.md", "work_package_prompt"),
    ("tasks/WP1-short.md", "other"),
    ("tasks/WP-notes.md", "other"),
    ("tasks/WP01.md", "other"),
    ("tasks/sub/WP01-first.md", "other"),
    ("spec.md", "spec"),
    ("plan.md", "plan"),
    ("tasks.md", "tasks"),
    ("data-model.md", "data_model"),
    ("quickstart.md", "quickstart"),
    ("analysis-report.md", "analysis_report"),
    ("sub/spec.md", "other"),
    ("sub/research.md", "other"),
    ("tasks/research.md", "other"),
    ("contracts/research.md", "contract"),
    ("research.md", "research"),
    ("research/notes.md", "research"),
    ("research/deep/notes.json", "research"),
    ("contracts/api.yaml", "contract"),
    ("contracts/deep/shape.json", "contract"),
    ("checklists/requirements.md", "checklist"),
    ("checklists/deep/more.md", "checklist"),
    ("meta.json", "other"),
    ("notes.txt", "other"),
]


@pytest.mark.parametrize(("path", "kind"), CLASSIFIER_CASES)
def test_the_classifier_gives_the_documented_kind(path: str, kind: str) -> None:
    assert art.classify(path) == kind


def test_the_classifier_table_covers_all_twelve_kinds_in_the_documented_order() -> None:
    assert {kind for _, kind in CLASSIFIER_CASES} == set(art.ARTIFACT_KINDS), "every kind needs a case"
    assert art.ARTIFACT_KINDS[:3] == ("review_cycle", "work_package_prompt", "spec")
    assert len(art.ARTIFACT_KINDS) == 12


# ---------------------------------------------------------------------------
# The listing: byte order of the UTF-8 path
# ---------------------------------------------------------------------------


def test_the_listing_is_sorted_by_path_in_byte_order(tmp_path: Path, tools: helper.ContractTools) -> None:
    accented = "caf" + chr(0xE9) + ".md"
    astral = "z" + chr(0x1F600) + ".md"
    private_use = "z" + chr(0xFFFD) + ".md"
    names = ["b.md", "B.md", "a-b.md", "a/b.md", "a.md", accented, astral, private_use, "Z.md", "z.md"]
    _build(tmp_path, dict.fromkeys(names, CLEAN_TEXT))
    ctx = _ctx(tmp_path, tools)
    listed = _listed_paths(ctx)
    assert sorted([*names, "meta.json"], key=lambda name: name.encode("utf-8")) == listed, "the fixture Mission also holds its meta.json"
    assert listed.index("a-b.md") < listed.index("a/b.md"), "byte order puts the hyphen before the slash; a per-segment order would not"
    assert listed.index("B.md") < listed.index("a.md") < listed.index("b.md"), "byte order is not a case-insensitive order"
    assert listed.index(private_use) < listed.index(astral), "UTF-8 byte order, not UTF-16 code unit order"


def test_the_listing_holds_the_files_and_the_envelope_of_a_mission(tmp_path: Path, tools: helper.ContractTools) -> None:
    _build(tmp_path, {"spec.md": CLEAN_TEXT, "tasks/WP01-first.md": CLEAN_TEXT})
    ctx = _ctx(tmp_path, tools)
    outcome = art.list_artifacts(ctx, MISSION_ID)
    assert outcome.status == 200
    assert outcome.body["missionId"] == MISSION_ID
    assert outcome.body["truncated"] is False
    kinds = {entry["path"]: entry["kind"] for entry in outcome.body["entries"]}
    assert kinds["spec.md"] == "spec"
    assert kinds["tasks/WP01-first.md"] == "work_package_prompt"
    assert art.list_artifacts(ctx, MISSING_ID).status == 404, "an unknown Mission is a 404"


def test_a_tree_nested_without_end_is_listed_without_its_too_deep_paths(tmp_path: Path, tools: helper.ContractTools) -> None:
    mission_dir = _build(tmp_path, {"spec.md": CLEAN_TEXT, "shallow/notes.md": CLEAN_TEXT, "deep/placeholder.md": CLEAN_TEXT})
    deep_root = mission_dir / "deep"
    real = art.REAL_FS

    def below(path: Path) -> bool:
        return Path(path) == deep_root or deep_root in Path(path).parents

    def scandir(path: Path) -> list[str]:
        return ["d"] if below(path) else real.scandir(path)

    def lstat(path: Path) -> os.stat_result:
        return real.lstat(mission_dir / "shallow") if below(path) else real.lstat(path)

    fs = dataclasses.replace(real, scandir=scandir, lstat=lstat)
    schema = yaml.safe_load((Path(__file__).resolve().parents[2] / "contracts" / "mission-status" / "schemas" / "ArtifactPath.yaml").read_text(encoding="utf-8"))
    assert schema["maxLength"] == art.MAX_PATH_LENGTH
    paths = _listed_paths(_ctx(tmp_path, tools, fs))
    assert {"spec.md", "shallow/notes.md"} <= set(paths)
    assert all(len(path) <= 512 for path in paths), "a path over 512 characters is never eligible, so the walk stops before it"


def test_the_listing_never_enters_or_lists_a_symlink(tmp_path: Path, tools: helper.ContractTools) -> None:
    mission_dir = _build(tmp_path, {"real/inner.md": CLEAN_TEXT, "spec.md": CLEAN_TEXT})
    (mission_dir / "linked").symlink_to(mission_dir / "real", target_is_directory=True)
    (mission_dir / "alias.md").symlink_to(mission_dir / "spec.md")
    listed = _listed_paths(_ctx(tmp_path, tools))
    assert "real/inner.md" in listed
    assert not any(path.startswith("linked") or path == "alias.md" for path in listed), listed


# ---------------------------------------------------------------------------
# Shared fixtures of the matrix: the resolved contract, a counting file system, injected faults
# ---------------------------------------------------------------------------

CAP = art.MAX_CONTENT_BYTES
MODULE_DIR = REPO_ROOT / "contracts" / "mission-status"
FAULT_NOT_FIRED = "the injected fault did not fire"
INJECTED_FAULT = "injected fault"


@pytest.fixture(scope="module")
def contract(tools: helper.ContractTools) -> helper.Contract:
    return helper.Contract(tools, MODULE_DIR)


def _home_path(tail: str = "project") -> str:
    return SLASH + "home" + SLASH + "someone" + SLASH + tail


def _email() -> str:
    return "someone" + chr(64) + "example.invalid"


def _tokens() -> dict[str, str]:
    """One credential of each kind the contract names, assembled from fragments."""
    dashes = chr(45) * 5
    return {
        "github-classic": "gh" + "p" + chr(95) + "a" * 36,
        "github-fine-grained": "github" + chr(95) + "pat" + chr(95) + "A" * 40,
        "aws-long-lived": "AK" + "IA" + "B" * 16,
        "aws-temporary": "AS" + "IA" + "C" * 16,
        "private-key-header": dashes + "BEGIN RSA PRIVATE KEY" + dashes,
    }


@dataclass
class Fired:
    """How often an injected fault or a counted call fired; a test that expects it fails, never skips, at zero."""

    count: int = 0
    seen: list[str] = field(default_factory=list)


@dataclass
class Io:
    opens: int = 0
    bytes_read: int = 0
    scandirs: list[Path] = field(default_factory=list)


class _CountingFile:
    def __init__(self, inner: art.OpenFile, io: Io) -> None:
        self._inner = inner
        self._io = io

    def fstat(self) -> os.stat_result:
        return self._inner.fstat()

    def read(self, size: int) -> bytes:
        data = self._inner.read(size)
        self._io.bytes_read += len(data)
        return data

    def close(self) -> None:
        self._inner.close()


def _counting_fs(io: Io) -> art.FileSystem:
    real = art.REAL_FS

    def open_binary(path: Path) -> art.OpenFile:
        io.opens += 1
        return _CountingFile(real.open_binary(path), io)

    def scandir(path: Path) -> list[str]:
        io.scandirs.append(Path(path))
        return real.scandir(path)

    return dataclasses.replace(real, open_binary=open_binary, scandir=scandir)


def _faulting_fs(call: str, target: str, fired: Fired, *, after: int = 0, error: type[OSError] = PermissionError) -> art.FileSystem:
    """Replace one call of the real file system by one that raises ``error`` for paths named ``target`` (after ``after`` calls)."""
    real = getattr(art.REAL_FS, call)
    seen = {"calls": 0}

    def faulty(path: Path) -> Any:
        if Path(path).name == target:
            seen["calls"] += 1
            if seen["calls"] > after:
                fired.count += 1
                raise error(INJECTED_FAULT)
        return real(path)

    return dataclasses.replace(art.REAL_FS, **{call: faulty})


def _fake_handle(*, claimed_size: int, data: bytes, fired: Fired | None = None, read_error: type[OSError] | None = None) -> art.OpenFile:
    """An open file whose stat says ``claimed_size`` while ``read`` answers ``data`` (a file that grows during the read)."""

    class Handle:
        def fstat(self) -> Any:
            return SimpleNamespace(st_size=claimed_size)

        def read(self, size: int) -> bytes:
            if fired is not None:
                fired.count += 1
            if read_error is not None:
                raise read_error(INJECTED_FAULT)
            return data[:size]

        def close(self) -> None:
            return None

    return Handle()


def _json(outcome: art.ArtifactOutcome) -> str:
    return json.dumps([outcome.status, outcome.body], sort_keys=True)


def _only_refusal(outcome: art.ArtifactOutcome, status: int, code: str) -> None:
    assert (outcome.status, outcome.body.get("code")) == (status, code), f"{outcome.status} {outcome.body}"
    assert "content" not in outcome.body, "a refusal never carries content"


# ---------------------------------------------------------------------------
# Containment refusals: status and code, and the answer never repeats the target
# ---------------------------------------------------------------------------


def _containment_cases(root: Path) -> list[tuple[str, list[str], int, str]]:
    """(label, the path parameter values, status, code) over a Mission built by ``_containment_mission``."""
    return [
        ("missing-parameter", [], 400, "invalid_artifact_path"),
        ("repeated-parameter", ["spec.md", "spec.md"], 400, "invalid_artifact_path"),
        ("traversal-to-another-mission", ["..", SLASH, "other", SLASH, "spec.md"], 400, "invalid_artifact_path"),
        ("doubly-encoded-traversal", ["%252e%252e%252fspec.md"], 404, "not_found"),
        ("singly-encoded-traversal", ["%2e%2e/spec.md"], 404, "not_found"),
        ("encoded-slash", ["..%2fspec.md"], 404, "not_found"),
        ("symlink-to-a-file", ["alias.md"], 404, "not_found"),
        ("through-a-symlinked-directory", ["linked/notes.md"], 404, "not_found"),
        ("symlink-to-another-mission", ["foreign.md"], 404, "not_found"),
        ("a-directory", ["folder"], 404, "not_found"),
        ("symlinked-tasks-directory", ["tasks/WP01-first.md"], 404, "not_found"),
        ("absent-file", ["absent.md"], 404, "not_found"),
        ("root-status-record", ["status.json"], 404, "not_found"),
        ("root-event-log", ["status.events.jsonl"], 404, "not_found"),
        ("root-status-record-case-variant", ["Status.JSON"], 404, "not_found"),
        ("root-event-log-case-variant", ["STATUS.EVENTS.JSONL"], 404, "not_found"),
    ]


def _containment_mission(root: Path) -> Path:
    mission_dir = _build(root, {"spec.md": CLEAN_TEXT, "real/notes.md": CLEAN_TEXT, "folder/inner.md": CLEAN_TEXT, "elsewhere/WP01-first.md": CLEAN_TEXT})
    (mission_dir / "status.json").write_text("{}", encoding="utf-8")
    (mission_dir / "status.events.jsonl").write_text("", encoding="utf-8")
    (mission_dir / "Status.JSON").write_text("{}", encoding="utf-8")
    (mission_dir / "STATUS.EVENTS.JSONL").write_text("", encoding="utf-8")
    (mission_dir / "alias.md").symlink_to(mission_dir / "spec.md")
    (mission_dir / "linked").symlink_to(mission_dir / "real", target_is_directory=True)
    other = root / "kitty-specs" / "other-mission"
    other.mkdir(parents=True)
    (other / "secret.md").write_text("another Mission", encoding="utf-8")
    (mission_dir / "foreign.md").symlink_to(other / "secret.md")
    (mission_dir / "tasks").rmdir()
    (mission_dir / "tasks").symlink_to(mission_dir / "elsewhere", target_is_directory=True)
    return mission_dir


@pytest.mark.parametrize("label", [case[0] for case in _containment_cases(Path("."))])
def test_each_containment_refusal_has_its_status_and_code_and_never_leaks_the_target(label: str, tmp_path: Path, tools: helper.ContractTools) -> None:
    _containment_mission(tmp_path)
    ctx = _ctx(tmp_path, tools)
    _label, paths, status, code = next(case for case in _containment_cases(tmp_path) if case[0] == label)
    values = ["".join(paths)] if label == "traversal-to-another-mission" else paths
    outcome = art.read_content(ctx, MISSION_ID, values)
    _only_refusal(outcome, status, code)
    dumped = _json(outcome)
    for forbidden in (str(tmp_path), "another Mission", "kitty-specs", *values):
        assert forbidden not in dumped, f"the refusal repeats {forbidden!r}"
    assert art.read_content(ctx, MISSION_ID, ["spec.md"]).status == 200, "the clean twin: a regular root file is read"


@pytest.mark.parametrize("mission_id", ["", "not-a-ulid", "x" * 26, helper.fixture_ulid(1)[:25], MISSING_ID])
def test_an_unknown_or_ill_formed_mission_id_is_404_in_both_operations(mission_id: str, tmp_path: Path, tools: helper.ContractTools) -> None:
    _build(tmp_path, {"spec.md": CLEAN_TEXT})
    ctx = _ctx(tmp_path, tools)
    _only_refusal(art.read_content(ctx, mission_id, ["spec.md"]), 404, "not_found")
    _only_refusal(art.list_artifacts(ctx, mission_id), 404, "not_found")
    assert art.read_content(ctx, MISSION_ID, ["spec.md"]).status == 200, "control: the real id is served"


def test_a_mission_id_is_matched_exactly_and_a_lowercase_twin_is_not_the_mission(tmp_path: Path, tools: helper.ContractTools) -> None:
    identity = helper.fixture_ulid(2**40 + 10)
    assert identity != identity.lower(), "the id must hold a letter for the case twin to differ"
    helper.write_fixture_mission(tmp_path, MISSION, meta={"mission_id": identity})
    ctx = _ctx(tmp_path, tools)
    assert art.list_artifacts(ctx, identity).status == 200
    _only_refusal(art.list_artifacts(ctx, identity.lower()), 404, "not_found")
    _only_refusal(art.read_content(ctx, identity.lower(), ["meta.json"]), 404, "not_found")


def test_a_malformed_path_for_an_unknown_mission_is_400_before_the_mission_is_looked_up(tmp_path: Path, tools: helper.ContractTools) -> None:
    _build(tmp_path, {"spec.md": CLEAN_TEXT})
    ctx = _ctx(tmp_path, tools)
    _only_refusal(art.read_content(ctx, MISSING_ID, [SLASH + "spec.md"]), 400, "invalid_artifact_path")
    _only_refusal(art.read_content(ctx, MISSING_ID, ["spec.md"]), 404, "not_found")


# ---------------------------------------------------------------------------
# Boundary and encoding
# ---------------------------------------------------------------------------


def _sized(size: int, *, fill: bytes | None = None, last: bytes | None = None) -> bytes:
    """``size`` bytes of words separated by spaces (or ``fill`` repeated), the last byte replaced by ``last``.

    The default filler has no long run of letters: the e-mail pattern of ``leak_patterns`` backtracks quadratically on one
    (about a minute for 256 KiB of the same letter), which is not what these boundary tests are about.
    """
    data = fill * size if fill is not None else (b"ab " * (size // 3 + 1))[:size]
    return data if last is None or size == 0 else data[:-1] + last


def test_the_cap_is_inclusive_at_262144_bytes_and_262145_is_refused(tmp_path: Path, tools: helper.ContractTools) -> None:
    _build(tmp_path, {"at-cap.md": _sized(CAP), "over-cap.md": _sized(CAP + 1)})
    ctx = _ctx(tmp_path, tools)
    served = _read(ctx, "at-cap.md")
    assert (served.status, served.body["sizeBytes"], len(served.body["content"])) == (200, CAP, CAP)
    _only_refusal(_read(ctx, "over-cap.md"), 413, "artifact_too_large")
    entries = {entry["path"]: entry for entry in art.list_artifacts(ctx, MISSION_ID).body["entries"]}
    assert entries["at-cap.md"]["readable"] is True
    assert entries["over-cap.md"]["readable"] is False
    assert entries["over-cap.md"]["sizeBytes"] == CAP + 1


def test_an_oversize_file_that_is_not_utf8_is_413_not_415(tmp_path: Path, tools: helper.ContractTools) -> None:
    _build(tmp_path, {"big.bin": _sized(CAP + 1, fill=bytes([0xFF])), "small.bin": _sized(10, fill=bytes([0xFF]))})
    ctx = _ctx(tmp_path, tools)
    _only_refusal(_read(ctx, "big.bin"), 413, "artifact_too_large")
    _only_refusal(_read(ctx, "small.bin"), 415, "artifact_not_text")


def test_a_file_that_grows_during_the_read_is_413_and_a_stable_twin_is_200(tmp_path: Path, tools: helper.ContractTools) -> None:
    _build(tmp_path, {"growing.md": CLEAN_TEXT})
    fired = Fired()
    opener = dataclasses.replace(art.REAL_FS, open_binary=lambda _path: _fake_handle(claimed_size=10, data=_sized(CAP + 1), fired=fired))
    outcome = _read(_ctx(tmp_path, tools, opener), "growing.md")
    assert fired.count > 0, FAULT_NOT_FIRED
    _only_refusal(outcome, 413, "artifact_too_large")
    stable = dataclasses.replace(art.REAL_FS, open_binary=lambda _path: _fake_handle(claimed_size=5, data=b"hello"))
    served = _read(_ctx(tmp_path, tools, stable), "growing.md")
    assert (served.status, served.body["content"], served.body["sizeBytes"]) == (200, "hello", 5)


def test_the_size_is_the_stat_of_the_open_handle_and_never_the_length_of_what_was_read(tmp_path: Path, tools: helper.ContractTools) -> None:
    _build(tmp_path, {"spec.md": CLEAN_TEXT})
    opener = dataclasses.replace(art.REAL_FS, open_binary=lambda _path: _fake_handle(claimed_size=7, data=b"hello"))
    outcome = _read(_ctx(tmp_path, tools, opener), "spec.md")
    assert (outcome.status, outcome.body["sizeBytes"], outcome.body["content"]) == (200, 7, "hello")
    real = _read(_ctx(tmp_path, tools), "spec.md")
    assert real.body["sizeBytes"] == len(CLEAN_TEXT.encode("utf-8")), "control: on a real file the two agree"


def test_a_byte_order_mark_is_kept_and_a_zero_byte_file_is_a_200_with_empty_content(tmp_path: Path, tools: helper.ContractTools) -> None:
    bom = bytes([0xEF, 0xBB, 0xBF])
    _build(tmp_path, {"bom.md": bom + b"# title\n", "empty.md": b""})
    ctx = _ctx(tmp_path, tools)
    assert _read(ctx, "bom.md").body["content"] == chr(0xFEFF) + "# title\n", "no signature stripping"
    empty = _read(ctx, "empty.md")
    assert (empty.status, empty.body["content"], empty.body["sizeBytes"], empty.body["redacted"]) == (200, "", 0, False)


@pytest.mark.parametrize(
    ("label", "last_byte", "status", "code"),
    [("nul", bytes(1), 415, "artifact_not_text"), ("invalid-utf8", bytes([0xFF]), 415, "artifact_not_text"), ("clean", b"a", 200, "")],
)
def test_a_nul_or_an_invalid_byte_at_the_last_byte_of_a_cap_sized_file_makes_it_unreadable(
    label: str, last_byte: bytes, status: int, code: str, tmp_path: Path, tools: helper.ContractTools
) -> None:
    _build(tmp_path, {"edge.md": _sized(CAP, last=last_byte)})
    ctx = _ctx(tmp_path, tools)
    outcome = _read(ctx, "edge.md")
    assert outcome.status == status, label
    if status != 200:
        _only_refusal(outcome, status, code)
    entry = art.list_artifacts(ctx, MISSION_ID).body["entries"]
    assert [e["readable"] for e in entry if e["path"] == "edge.md"] == [status == 200], label


def test_a_nul_byte_is_checked_before_the_utf8_decode_and_both_refuse_415(tmp_path: Path, tools: helper.ContractTools) -> None:
    _build(tmp_path, {"nul.md": b"a" + bytes(1) + b"b", "latin.md": b"caf" + bytes([0xE9]), "fine.md": "caf" + chr(0xE9)})
    ctx = _ctx(tmp_path, tools)
    _only_refusal(_read(ctx, "nul.md"), 415, "artifact_not_text")
    _only_refusal(_read(ctx, "latin.md"), 415, "artifact_not_text")
    assert _read(ctx, "fine.md").body["content"] == "caf" + chr(0xE9)


def test_a_listing_of_1001_files_is_truncated_to_1000_and_1000_files_are_not(tmp_path: Path, tools: helper.ContractTools) -> None:
    mission_dir = _build(tmp_path)
    files = {f"bulk/f{number:04d}.md": "x" for number in range(1001)}
    _put(mission_dir, files)
    ctx = _ctx(tmp_path, tools)
    over = art.list_artifacts(ctx, MISSION_ID).body
    assert over["truncated"] is True and len(over["entries"]) == art.MAX_LISTING_ENTRIES
    assert [entry["path"] for entry in over["entries"]] == sorted(entry["path"] for entry in over["entries"])
    (mission_dir / "bulk" / "f1000.md").unlink()
    (mission_dir / "bulk" / "f0999.md").unlink()
    exact = art.list_artifacts(ctx, MISSION_ID).body
    assert exact["truncated"] is False and len(exact["entries"]) == 1000 - 1 + 1, "meta.json plus 999 files"


def test_odd_but_legal_names_are_listed_and_read_and_a_backslash_or_overlong_name_is_neither(tmp_path: Path, tools: helper.ContractTools) -> None:
    legal = ["scale" + chr(64) + "2x.png.md", "notes/home/someone/file.md", "with space.md", ".hidden.md"]
    backslash = "a" + BACKSLASH + "b.md"
    segment = "d" * 100
    nested_512 = SLASH.join([segment] * 4 + ["f" * 105 + ".md"])
    nested_513 = SLASH.join([segment] * 4 + ["f" * 106 + ".md"])
    assert (len(nested_512), len(nested_513)) == (512, 513)
    _build(tmp_path, dict.fromkeys([*legal, backslash, nested_512, nested_513], CLEAN_TEXT))
    ctx = _ctx(tmp_path, tools)
    listed = _listed_paths(ctx)
    for name in [*legal, nested_512]:
        assert name in listed, f"{name!r} is a legal artifact path"
        assert _read(ctx, name).status == 200, name
    for name in (backslash, nested_513):
        assert name not in listed, "a malformed path is never listed"
        _only_refusal(_read(ctx, name), 400, "invalid_artifact_path")


@pytest.mark.parametrize(
    ("name", "media_type"),
    [
        ("a.md", "text/markdown"),
        ("a.json", "application/json"),
        ("a.yaml", "application/yaml"),
        ("a.yml", "application/yaml"),
        ("a.jsonl", "application/x-ndjson"),
        ("a.csv", "text/csv"),
        ("a.txt", "text/plain"),
        ("no-extension", "text/plain"),
        ("dir.md/inner", "text/plain"),
        ("a.MD", "text/plain"),
        ("a.tar.json", "application/json"),
    ],
)
def test_the_media_type_comes_from_the_extension_table_and_never_from_the_content(name: str, media_type: str) -> None:
    assert art.media_type_of(name) == media_type
    assert art.ENCODING == "utf-8"


def test_the_media_type_is_the_table_value_even_when_the_content_looks_like_something_else(tmp_path: Path, tools: helper.ContractTools) -> None:
    _build(tmp_path, {"data.txt": '{"json": true}', "notes.md": "plain words"})
    ctx = _ctx(tmp_path, tools)
    assert _read(ctx, "data.txt").body["mediaType"] == "text/plain"
    assert _read(ctx, "notes.md").body["mediaType"] == "text/markdown"


def test_the_modified_time_is_floored_to_whole_seconds_in_utc_and_never_rounded(tmp_path: Path, tools: helper.ContractTools) -> None:
    assert art.modified_at(1_700_000_000.0) == "2023-11-14T22:13:20Z"
    assert art.modified_at(1_700_000_000.999999) == "2023-11-14T22:13:20Z", "floored, not rounded"
    assert art.modified_at(1_700_000_001.0) == "2023-11-14T22:13:21Z"
    mission_dir = _build(tmp_path, {"a.md": CLEAN_TEXT})
    os.utime(mission_dir / "a.md", (1_700_000_000.9, 1_700_000_000.9))
    entries = {entry["path"]: entry for entry in art.list_artifacts(_ctx(tmp_path, tools), MISSION_ID).body["entries"]}
    assert entries["a.md"]["modifiedAt"] == "2023-11-14T22:13:20Z"


# ---------------------------------------------------------------------------
# Credentials, redaction and the reader-level planted pairs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("kind", sorted(_tokens()))
def test_each_credential_kind_is_422_without_content_and_its_clean_twin_is_200(kind: str, tmp_path: Path, tools: helper.ContractTools) -> None:
    secret = _tokens()[kind]
    near_miss = secret[: len(secret) // 3]
    _build(tmp_path, {"dirty.md": "before " + secret + " after\n", "clean.md": "before " + near_miss + " after\n"})
    ctx = _ctx(tmp_path, tools)
    refused = _read(ctx, "dirty.md")
    _only_refusal(refused, 422, "artifact_secret")
    assert secret not in _json(refused) and "before" not in _json(refused), "the refusal repeats nothing of the file"
    assert _read(ctx, "clean.md").status == 200, "the clean twin must be read"
    readable = {entry["path"]: entry["readable"] for entry in art.list_artifacts(ctx, MISSION_ID).body["entries"]}
    assert readable["dirty.md"] is False and readable["clean.md"] is True


def test_a_host_path_and_an_address_are_replaced_and_redacted_says_so(tmp_path: Path, tools: helper.ContractTools) -> None:
    windows = "C:" + BACKSLASH + "Users" + BACKSLASH + "someone" + BACKSLASH + "file.md"
    dirty = f"open {_home_path('x/y.md')} now, mail {_email()}, tmp {SLASH}tmp{SLASH}scratch{SLASH}a.txt, win {windows}.\n"
    _build(tmp_path, {"dirty.md": dirty, "clean.md": "open [path] now, mail [email].\n", "tilde.md": "see ~/notes and the word tmp\n"})
    ctx = _ctx(tmp_path, tools)
    redacted = _read(ctx, "dirty.md")
    assert redacted.body["content"] == "open [path] now, mail [email], tmp [path] win [path]\n"
    assert redacted.body["redacted"] is True
    assert redacted.body["sizeBytes"] == len(dirty.encode("utf-8")), "the size is the file's, measured before redaction"
    clean = _read(ctx, "clean.md")
    assert (clean.body["redacted"], clean.body["content"]) == (False, "open [path] now, mail [email].\n"), "a file that already holds the markers is unchanged"
    assert _read(ctx, "tilde.md").body["redacted"] is False, "a leading tilde and a bare temp word are not host paths in text"


def test_redact_leaves_no_address_of_a_glued_pair(tools: helper.ContractTools) -> None:
    glued = "x" + chr(64) + "y.z+w" + chr(64) + "v.u"

    assert art.redact(tools, glued) == ("[email][email]", True)


def test_redact_and_has_credential_are_pure_functions_of_the_text(tools: helper.ContractTools) -> None:
    assert art.redact(tools, "nothing here") == ("nothing here", False)
    assert art.redact(tools, _email()) == ("[email]", True)
    assert not art.has_credential(tools, "ghp_short")
    assert all(art.has_credential(tools, "x " + token) for token in _tokens().values())


def test_a_redacted_body_validates_and_has_no_leak_and_a_reader_that_stops_redacting_is_caught(
    tmp_path: Path, tools: helper.ContractTools, contract: helper.Contract, monkeypatch: pytest.MonkeyPatch
) -> None:
    dirty = f"open {_home_path('x/y.md')} and write {_email()}\n"
    _build(tmp_path, {"dirty.md": dirty, "clean.md": CLEAN_TEXT})
    ctx = _ctx(tmp_path, tools)
    clean_body = _read(ctx, "clean.md").body
    assert helper.payload_leaks(clean_body, tools) == [] and contract.errors("ArtifactContent", clean_body) == []
    body = _read(ctx, "dirty.md").body
    assert helper.payload_leaks(body, tools) == [], "the redacted body of a dirty file carries no leak"
    assert contract.errors("ArtifactContent", body) == []
    monkeypatch.setattr(art, "redact", lambda _tools, text: (text, False))
    unredacted = _read(ctx, "dirty.md").body
    found = [finding.rsplit(": ", 1)[1] for finding in helper.payload_leaks(unredacted, tools)]
    assert found == ["HOST_PATH", "EMAIL"], "a reader that stops redacting must be reported by the leak scan"


def test_every_refusal_and_the_listing_validate_against_the_contract(tmp_path: Path, tools: helper.ContractTools, contract: helper.Contract) -> None:
    _containment_mission(tmp_path)
    _put(tmp_path / "kitty-specs" / MISSION, {"big.md": _sized(CAP + 1), "bin.md": bytes([0xFF]), "secret.md": _tokens()["github-classic"]})
    ctx = _ctx(tmp_path, tools)
    seen = set()
    for paths in (["secret.md"], ["bin.md"], ["big.md"], ["absent.md"], [], ["spec.md"]):
        outcome = art.read_content(ctx, MISSION_ID, paths)
        if outcome.status == 200:
            assert contract.errors("ArtifactContent", outcome.body) == []
        else:
            assert contract.errors("ArtifactRefusal", outcome.body) == [], outcome.body
            seen.add(outcome.body["code"])
    unreadable = art.read_content(_ctx(tmp_path, tools, _faulting_fs("lstat", "spec.md", Fired())), MISSION_ID, ["spec.md"])
    listing_failure = art.list_artifacts(_ctx(tmp_path, tools, _faulting_fs("scandir", MISSION, Fired())), MISSION_ID)
    for outcome in (unreadable, listing_failure):
        assert contract.errors("ArtifactRefusal", outcome.body) == [], outcome.body
        seen.add(outcome.body["code"])
    assert seen == set(art.REFUSALS), f"every refusal code of the contract must be produced: {sorted(set(art.REFUSALS) - seen)}"
    listing = art.list_artifacts(ctx, MISSION_ID)
    assert listing.status == 200 and contract.errors("ArtifactListing", listing.body) == []


# ---------------------------------------------------------------------------
# Bounded reads and the fault-injected file system
# ---------------------------------------------------------------------------


def test_a_content_read_opens_one_file_and_reads_at_most_one_byte_past_the_cap(tmp_path: Path, tools: helper.ContractTools) -> None:
    _build(tmp_path, {"at-cap.md": _sized(CAP), "huge.md": _sized(CAP * 2), "small.md": CLEAN_TEXT})
    for name, expected_status in (("at-cap.md", 200), ("huge.md", 413), ("small.md", 200)):
        io = Io()
        outcome = _read(_ctx(tmp_path, tools, _counting_fs(io)), name)
        assert outcome.status == expected_status, name
        assert io.opens == 1, f"{name}: one file is opened"
        assert io.bytes_read <= CAP + 1, f"{name}: {io.bytes_read} bytes read"
    io = Io()
    _read(_ctx(tmp_path, tools, _counting_fs(io)), "huge.md")
    assert io.bytes_read == 0, "a file over the cap is decided from the open handle's size and is not read"


def test_the_listing_never_opens_a_file_over_the_cap(tmp_path: Path, tools: helper.ContractTools) -> None:
    _build(tmp_path, {"huge.md": _sized(CAP + 1), "small-a.md": CLEAN_TEXT, "small-b.md": CLEAN_TEXT})
    io = Io()
    entries = art.list_artifacts(_ctx(tmp_path, tools, _counting_fs(io)), MISSION_ID).body["entries"]
    assert io.opens == 3, "meta.json and the two small files are read; the huge one is not opened"
    assert {entry["path"]: entry["readable"] for entry in entries}["huge.md"] is False


def test_the_references_open_no_file_and_read_one_directory(tmp_path: Path, tools: helper.ContractTools) -> None:
    mission_dir = _build(
        tmp_path, {"spec.md": CLEAN_TEXT, "tasks/WP01-first.md": CLEAN_TEXT, "tasks/WP01-second.md": CLEAN_TEXT, "tasks/WP010-other.md": CLEAN_TEXT}
    )
    io = Io()
    references = art.artifact_references(_ctx(tmp_path, tools, _counting_fs(io)), mission_dir, "WP01")
    assert io.opens == 0 and io.bytes_read == 0, "no content is opened"
    assert io.scandirs == [mission_dir / "tasks"], "one directory read: no listing walk"
    assert references == {"prompt": {"path": "tasks/WP01-first.md", "kind": "work_package_prompt"}, "spec": {"path": "spec.md", "kind": "spec"}}


def test_the_prompt_reference_skips_symlinks_and_directories_and_is_null_without_a_prompt(tmp_path: Path, tools: helper.ContractTools) -> None:
    mission_dir = _build(tmp_path, {"real.md": CLEAN_TEXT, "tasks/WP02-second.md": CLEAN_TEXT, "tasks/WP-notes.md": CLEAN_TEXT, "tasks/WP03.md": CLEAN_TEXT})
    (mission_dir / "tasks" / "WP01-aliased.md").symlink_to(mission_dir / "real.md")
    (mission_dir / "tasks" / "WP01-folder.md").mkdir()
    (mission_dir / "spec.md").symlink_to(mission_dir / "real.md")
    ctx = _ctx(tmp_path, tools)
    assert art.artifact_references(ctx, mission_dir, "WP01") == {"prompt": None, "spec": None}, "a symlink or a directory is neither prompt nor spec"
    assert art.artifact_references(ctx, mission_dir, "WP02")["prompt"] == {"path": "tasks/WP02-second.md", "kind": "work_package_prompt"}
    assert art.artifact_references(ctx, mission_dir, "WP03")["prompt"] is None, "WP03.md has no hyphen name: it is no prompt file"
    assert art.artifact_references(ctx, mission_dir, "WP-notes")["prompt"] is None


def test_an_injected_lstat_failure_is_500_and_never_a_wrong_404(tmp_path: Path, tools: helper.ContractTools) -> None:
    _build(tmp_path, {"spec.md": CLEAN_TEXT, "other.md": CLEAN_TEXT})
    fired = Fired()
    ctx = _ctx(tmp_path, tools, _faulting_fs("lstat", "spec.md", fired))
    _only_refusal(_read(ctx, "spec.md"), 500, "artifact_unreadable")
    assert fired.count > 0, FAULT_NOT_FIRED
    assert _read(ctx, "other.md").status == 200, "a path the fault does not touch is still served"
    listing_fired = Fired()
    _only_refusal(art.list_artifacts(_ctx(tmp_path, tools, _faulting_fs("lstat", "spec.md", listing_fired)), MISSION_ID), 500, "artifact_listing_unreadable")
    assert listing_fired.count > 0, FAULT_NOT_FIRED


def test_an_injected_scandir_failure_on_the_mission_directory_is_a_listing_500(tmp_path: Path, tools: helper.ContractTools) -> None:
    _build(tmp_path, {"spec.md": CLEAN_TEXT})
    fired = Fired()
    outcome = art.list_artifacts(_ctx(tmp_path, tools, _faulting_fs("scandir", MISSION, fired)), MISSION_ID)
    assert fired.count > 0, FAULT_NOT_FIRED
    _only_refusal(outcome, 500, "artifact_listing_unreadable")
    assert art.list_artifacts(_ctx(tmp_path, tools), MISSION_ID).status == 200, "control: the same Mission lists without the fault"


def test_an_unreadable_mission_directory_is_500_for_the_content_read_too(tmp_path: Path, tools: helper.ContractTools) -> None:
    _build(tmp_path, {"spec.md": CLEAN_TEXT})
    fired = Fired()
    ctx = _ctx(tmp_path, tools, _faulting_fs("lstat", MISSION, fired))
    _only_refusal(_read(ctx, "spec.md"), 500, "artifact_unreadable")
    _only_refusal(art.list_artifacts(ctx, MISSION_ID), 500, "artifact_listing_unreadable")
    assert fired.count > 0, FAULT_NOT_FIRED


def test_an_injected_open_failure_is_500_and_the_listing_marks_the_file_unreadable(tmp_path: Path, tools: helper.ContractTools) -> None:
    _build(tmp_path, {"locked.md": CLEAN_TEXT, "open.md": CLEAN_TEXT})
    fired = Fired()
    ctx = _ctx(tmp_path, tools, _faulting_fs("open_binary", "locked.md", fired))
    _only_refusal(_read(ctx, "locked.md"), 500, "artifact_unreadable")
    assert fired.count > 0, FAULT_NOT_FIRED
    assert _read(ctx, "open.md").status == 200
    readable = {entry["path"]: entry["readable"] for entry in art.list_artifacts(ctx, MISSION_ID).body["entries"]}
    assert readable["locked.md"] is False and readable["open.md"] is True


@pytest.mark.parametrize("failing_call", ["fstat", "read"])
def test_an_injected_failure_of_the_open_handle_is_500(failing_call: str, tmp_path: Path, tools: helper.ContractTools) -> None:
    _build(tmp_path, {"spec.md": CLEAN_TEXT})
    fired = Fired()

    class Failing:
        def fstat(self) -> Any:
            if failing_call == "fstat":
                fired.count += 1
                raise OSError(INJECTED_FAULT)
            return SimpleNamespace(st_size=3)

        def read(self, size: int) -> bytes:
            fired.count += 1
            raise OSError(INJECTED_FAULT)

        def close(self) -> None:
            return None

    opener = dataclasses.replace(art.REAL_FS, open_binary=lambda _path: Failing())
    _only_refusal(_read(_ctx(tmp_path, tools, opener), "spec.md"), 500, "artifact_unreadable")
    assert fired.count > 0, FAULT_NOT_FIRED


def test_a_file_that_vanishes_between_the_walk_and_its_stat_is_omitted_and_the_listing_stays_200(tmp_path: Path, tools: helper.ContractTools) -> None:
    _build(tmp_path, {"vanishing.md": CLEAN_TEXT, "staying.md": CLEAN_TEXT})
    fired = Fired()
    # lstat calls on the file: the walk, the eligibility rule, then the entry's own stat (the third) is the one that finds it gone
    ctx = _ctx(tmp_path, tools, _faulting_fs("lstat", "vanishing.md", fired, after=2, error=FileNotFoundError))
    outcome = art.list_artifacts(ctx, MISSION_ID)
    assert fired.count > 0, FAULT_NOT_FIRED
    assert outcome.status == 200
    paths = [entry["path"] for entry in outcome.body["entries"]]
    assert "vanishing.md" not in paths and "staying.md" in paths


# ---------------------------------------------------------------------------
# Mutations killed: each plants one defect in the reader and a target check must then fail
# ---------------------------------------------------------------------------


def _problems_order_of_decision(tmp_path: Path, tools: helper.ContractTools) -> list[str]:
    mission_dir = _build(
        tmp_path, {"nul-secret.md": bytes(1) + _tokens()["github-classic"].encode(), "secret.md": _tokens()["github-classic"], "plain.md": CLEAN_TEXT}
    )
    (mission_dir / "huge-secret.md").write_bytes(_tokens()["github-classic"].encode() + b" " + _sized(CAP))
    ctx = _ctx(tmp_path, tools)
    expected = [
        (["nul-secret.md"], MISSION_ID, 415),
        (["secret.md"], MISSION_ID, 422),
        (["huge-secret.md"], MISSION_ID, 413),
        ([SLASH + "x"], MISSING_ID, 400),
        (["plain.md"], MISSING_ID, 404),
        (["plain.md"], MISSION_ID, 200),
    ]
    return [f"{paths} {mission}: {got} not {want}" for paths, mission, want in expected if (got := art.read_content(ctx, mission, paths).status) != want]


def _problems_credential_rule(tmp_path: Path, tools: helper.ContractTools) -> list[str]:
    _build(tmp_path, {f"{kind}.md": token for kind, token in _tokens().items()} | {"clean.md": CLEAN_TEXT})
    ctx = _ctx(tmp_path, tools)
    problems = [f"{kind}: {got}" for kind in _tokens() if (got := _read(ctx, f"{kind}.md").status) != 422]
    return problems + ([] if _read(ctx, "clean.md").status == 200 else ["clean twin refused"])


def _problems_nul_rule(tmp_path: Path, tools: helper.ContractTools) -> list[str]:
    _build(tmp_path, {"nul.md": b"a" + bytes(1) + b"b", "plain.md": CLEAN_TEXT})
    ctx = _ctx(tmp_path, tools)
    return [f"nul: {got}" for got in [_read(ctx, "nul.md").status] if got != 415] + ([] if _read(ctx, "plain.md").status == 200 else ["plain refused"])


def _problems_symlinks(tmp_path: Path, tools: helper.ContractTools) -> list[str]:
    _containment_mission(tmp_path)
    ctx = _ctx(tmp_path, tools)
    problems = [f"{name}: {got}" for name in ("alias.md", "linked/notes.md") if (got := _read(ctx, name).status) != 404]
    listed = _listed_paths(ctx)
    problems += [f"{name} is listed" for name in ("alias.md", "linked/notes.md", "foreign.md") if name in listed]
    return problems + ([] if _read(ctx, "spec.md").status == 200 else ["spec.md refused"])


def _problems_cap(tmp_path: Path, tools: helper.ContractTools) -> list[str]:
    _build(tmp_path, {"at-cap.md": _sized(CAP), "over-cap.md": _sized(CAP + 1)})
    ctx = _ctx(tmp_path, tools)
    got = (_read(ctx, "at-cap.md").status, _read(ctx, "over-cap.md").status)
    return [] if got == (200, 413) else [f"statuses {got} not (200, 413)"]


def _problems_sort(tmp_path: Path, tools: helper.ContractTools) -> list[str]:
    mission_dir = _build(tmp_path, {"b.md": CLEAN_TEXT, "a.md": CLEAN_TEXT, "c.md": CLEAN_TEXT})
    for age, name in enumerate(("b.md", "c.md", "a.md")):  # modified order b, c, a: not the path order
        os.utime(mission_dir / name, (1_700_000_000 + age * 10, 1_700_000_000 + age * 10))
    os.utime(mission_dir / "meta.json", (1_700_000_100, 1_700_000_100))
    listed = _listed_paths(_ctx(tmp_path, tools))
    return [] if listed == sorted(listed, key=lambda path: path.encode("utf-8")) else [f"order {listed}"]


def _mutation_order(mp: pytest.MonkeyPatch, tmp_path: Path) -> None:
    original = art._decide_bytes

    def credential_first(tools: helper.ContractTools, path: str, size: int, data: bytes) -> art.ArtifactOutcome:
        if art.has_credential(tools, data.decode("utf-8", "ignore")):
            return art.refusal(art.ARTIFACT_SECRET)
        return original(tools, path, size, data)

    mp.setattr(art, "_decide_bytes", credential_first)


def _mutation_credential(mp: pytest.MonkeyPatch, tmp_path: Path) -> None:
    mp.setattr(art, "has_credential", lambda tools, text: bool(tools.leak.SECRET_PATTERNS[0].search(text)))


def _mutation_nul(mp: pytest.MonkeyPatch, tmp_path: Path) -> None:
    mp.setattr(art, "_NUL", bytes([0xFE, 0xFE, 0xFE]))


def _mutation_symlink_followed(mp: pytest.MonkeyPatch, tmp_path: Path) -> None:
    mp.setattr(
        art,
        "is_eligible",
        lambda ctx, mission_dir, path: art.malformed(ctx.tools, path) is None and (mission_dir / path).is_file() and path not in art.ROOT_STATUS_FILES,
    )


def _mutation_cap_off_by_one(mp: pytest.MonkeyPatch, tmp_path: Path) -> None:
    mp.setattr(art, "MAX_CONTENT_BYTES", CAP + 1)


def _mutation_sort_by_modified_time(mp: pytest.MonkeyPatch, tmp_path: Path) -> None:
    mission_dir = tmp_path / "kitty-specs" / MISSION
    mp.setattr(art, "path_sort_key", lambda path: (os.lstat(mission_dir / path).st_mtime_ns, path.encode("utf-8")))


MUTATIONS: dict[str, tuple[Callable[[pytest.MonkeyPatch, Path], None], Callable[[Path, helper.ContractTools], list[str]]]] = {
    "wrong order of decision": (_mutation_order, _problems_order_of_decision),
    "wrong credential rule": (_mutation_credential, _problems_credential_rule),
    "wrong NUL rule": (_mutation_nul, _problems_nul_rule),
    "symlink followed": (_mutation_symlink_followed, _problems_symlinks),
    "cap off by one": (_mutation_cap_off_by_one, _problems_cap),
    "sort by modifiedAt": (_mutation_sort_by_modified_time, _problems_sort),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_the_unmutated_reader_passes_the_check_each_mutation_must_fail(name: str, tmp_path: Path, tools: helper.ContractTools) -> None:
    problems = MUTATIONS[name][1](tmp_path, tools)
    assert problems == [], f"{name}: the check fails on the correct reader: {problems}"


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_a_planted_defect_is_killed_by_its_check(name: str, tmp_path: Path, tools: helper.ContractTools) -> None:
    mutate, check = MUTATIONS[name]
    with pytest.MonkeyPatch.context() as mp:
        mutate(mp, tmp_path)
        problems = check(tmp_path, tools)
    if not problems:
        pytest.fail(f"the mutation was not killed: {name}")


# ---------------------------------------------------------------------------
# Determinism, the primary surface, the Mission index and the open operations
# ---------------------------------------------------------------------------


def test_two_listings_and_two_contents_of_an_unchanged_mission_are_byte_identical(tmp_path: Path, tools: helper.ContractTools) -> None:
    _build(tmp_path, {"spec.md": CLEAN_TEXT, "tasks/WP01-first.md": "see " + _home_path() + "\n", "notes/a.json": "{}"})
    ctx = _ctx(tmp_path, tools)
    assert _json(art.list_artifacts(ctx, MISSION_ID)) == _json(art.list_artifacts(ctx, MISSION_ID))
    for name in ("spec.md", "tasks/WP01-first.md", "notes/a.json"):
        assert _json(_read(ctx, name)) == _json(_read(ctx, name)), name


def test_the_mission_directory_is_the_primary_surface_own_dir_of_the_projector(tmp_path: Path, tools: helper.ContractTools) -> None:
    helper.git_init(tmp_path)
    helper.write_fixture_mission(tmp_path, MISSION)
    ctx = _ctx(tmp_path, tools)
    assert art.resolve_mission(ctx, MISSION_ID) == helper.load_source(tmp_path, MISSION).own_dir
    assert art.resolve_mission(ctx, MISSING_ID) is None


def test_the_mission_index_serves_the_first_directory_for_a_duplicated_id_and_a_prebuilt_index_is_used(tmp_path: Path, tools: helper.ContractTools) -> None:
    first = helper.write_fixture_mission(tmp_path, "a-first")
    helper.write_fixture_mission(tmp_path, "b-second")
    assert art.index_missions(tmp_path) == {MISSION_ID: first}, "the first directory in name order wins"
    sentinel = tmp_path / "somewhere"
    assert art.resolve_mission(art.ReaderContext(repo_root=tmp_path, tools=tools, mission_dirs={MISSION_ID: sentinel}), MISSION_ID) == sentinel
    assert art.index_missions(tmp_path / "absent") == {}, "no kitty-specs directory is an empty index"


def _security_keys(node: Any, where: str = "") -> list[str]:
    if isinstance(node, dict):
        found = [f"{where}/security"] if "security" in node else []
        for key, value in node.items():
            found += _security_keys(value, f"{where}/{key}")
        return found
    if isinstance(node, list):
        return [hit for index, item in enumerate(node) for hit in _security_keys(item, f"{where}/{index}")]
    return []


def test_the_root_and_the_three_operations_declare_no_security() -> None:
    assert _security_keys({"get": {"security": []}}) == ["/get/security"], "control: a planted security member is found"
    documents = [MODULE_DIR / "openapi.yaml"] + [
        MODULE_DIR / "paths" / name
        for name in ("missions_missionId_artifacts.yaml", "missions_missionId_artifacts_content.yaml", "missions_missionId_work-packages_wpId_detail.yaml")
    ]
    for document in documents:
        assert document.is_file(), document.name
        assert _security_keys(yaml.safe_load(document.read_text(encoding="utf-8"))) == [], f"{document.name} must carry no security"
