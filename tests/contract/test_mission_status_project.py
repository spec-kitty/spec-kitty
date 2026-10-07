"""Tests of the reference ``Project`` builder of the ``mission-status`` contract (FR-001 to FR-007, FR-015, FR-024; AC-PROJECT, AC-DRIFT 16).

Every rule has a row function that builds fixture repositories, calls the production entry point (``build_project``) and returns the
problems it found; a test asserts the list is empty, and the mutation table (proof kind M) swaps one reader function for its defective
twin and asserts that some row of that mutation goes red (``the mutation was not killed: <name>``). Each row is its own control: the
clean input beside the plant on the same fixture shape, so a probe that sees nothing fails. Repositories are written at run time into a
temporary directory; real git is used where git matters (a branch, a linked worktree, the resolver) under a scratch HOME. Values a leak
scan would flag are assembled from fragments.
"""

from __future__ import annotations

import copy
import json
import re
import subprocess
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import yaml

from specify_cli.coordination.surface_resolver import CoordinationBranchDeleted
from specify_cli.core.git_ops import get_current_branch
from specify_cli.core.version_checker import get_project_version
from specify_cli.migration import schema_version as schema
from specify_cli.status import reducer
from specify_cli.status.aggregate import CoordAuthorityUnavailable, MissionMetadataUnavailable, MissionStatus
from specify_cli.upgrade.metadata import ProjectMetadata
from tests.contract import _mission_status_memo as memo_module
from tests.contract import _mission_status_payloads as helper
from tests.contract import _mission_status_project as project

pytestmark = [pytest.mark.contract, pytest.mark.corpus, pytest.mark.git_repo]

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_DIR = REPO_ROOT / "contracts" / "mission-status"
SCHEMA_FILE = MODULE_DIR / "schemas" / "Project.yaml"
SLASH = chr(47)
PROJECT_NAME = "fixture-project"
VERSION_OK = "4.0.0"
PROPERTIES = ("name", "missionCount", "specKittyVersion", "schemaVersion", "health", "currentBranch", "lastActivityAt")
NEW_PROPERTIES = PROPERTIES[2:]
NOT_KILLED = "the mutation was not killed"
FAULT_NOT_FIRED = "the injected fault did not fire"
MISSION = "alpha-mission"


class UnexpectedProcess(AssertionError):
    """A process the reader's own code started: the stub of ``subprocess.run`` raises it."""


@pytest.fixture(scope="module")
def tools() -> Iterator[helper.ContractTools]:
    with pytest.MonkeyPatch.context() as patch:
        yield helper.load_contract_tools(patch, REPO_ROOT)


@pytest.fixture(autouse=True)
def scratch_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Real git runs with a scratch HOME and no system or global configuration."""
    home = tmp_path / "scratch-home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / "gitconfig"))


@dataclass
class Env:
    """One scratch area for a row: a fresh directory per repository, and the leak tool the builder takes."""

    root: Path
    leak: ModuleType
    made: int = 0

    def fresh(self) -> Path:
        self.made += 1
        directory = self.root / f"repo{self.made}"
        directory.mkdir()
        return directory


@pytest.fixture
def env(tmp_path: Path, tools: helper.ContractTools) -> Env:
    area = tmp_path / "rows"
    area.mkdir()
    return Env(area, tools.leak)


# ---------------------------------------------------------------------------
# Fixture repositories
# ---------------------------------------------------------------------------


def _git(repo: Path, *arguments: str) -> None:
    subprocess.run(["git", "-C", str(repo), *arguments], check=True, capture_output=True)


def _write_project(repo: Path, metadata: str | bytes | None, *, slug: str | None = PROJECT_NAME) -> Path:
    """The ``.kittify`` directory of a project: a config with the slug, and the metadata text (None writes no file)."""
    kittify = repo / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    if slug is not None:
        (kittify / "config.yaml").write_text(f"project:\n  slug: {slug}\n", encoding="utf-8")
    if isinstance(metadata, bytes):
        (kittify / "metadata.yaml").write_bytes(metadata)
    elif metadata is not None:
        (kittify / "metadata.yaml").write_text(metadata, encoding="utf-8")
    return kittify


def _metadata(version: str = VERSION_OK, schema_line: str = "schema_version: 3") -> str:
    return f"spec_kitty:\n  version: {version}\n  {schema_line}\n"


def _git_repo(repo: Path, branch: str | None = "main", *, commit: bool = False) -> None:
    """``git init`` with ``HEAD`` pointing at ``branch`` (unborn unless ``commit``)."""
    _git(repo, "init", "-q")
    if branch is not None:
        _git(repo, "symbolic-ref", "HEAD", f"refs/heads/{branch}")
    if commit:
        helper.commit_all(repo)


def _mission(repo: Path, name: str, number: int, at: str | None = None, *, coordinated: bool = False) -> None:
    """One fixture Mission with one work package whose only transition happened ``at`` (no event at all when None)."""
    rows = [helper.transition_row(number, "WP01", "genesis", "planned", at=at)] if at is not None else []
    meta: dict[str, Any] = {"mission_id": helper.fixture_ulid(number)}
    if coordinated:
        meta["coordination_branch"] = f"kitty/coordination-{name}"
    helper.write_fixture_mission(repo, name, meta=meta, rows=rows)


def _build(env: Env, repo: Path, memo: memo_module.ResolverMemo | None = None) -> dict[str, Any]:
    return project.build_project(repo, memo or memo_module.ResolverMemo(), leak=env.leak).body


def _expect(**given: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "name": PROJECT_NAME,
        "missionCount": 0,
        "specKittyVersion": None,
        "schemaVersion": None,
        "health": "schema_drift",
        "currentBranch": None,
        "lastActivityAt": None,
    }
    body.update(given)
    return body


def _differs(label: str, got: Mapping[str, Any], want: Mapping[str, Any]) -> list[str]:
    return [f"{label}: {key} is {got.get(key)!r}, expected {want.get(key)!r}" for key in PROPERTIES if got.get(key) != want.get(key)]


# ---------------------------------------------------------------------------
# AC-PROJECT 1: a metadata file of the wrong shape is null, and the reader never raises
# ---------------------------------------------------------------------------

RAISING_SHAPES = {
    "a list at the top level": "- a\n- b\n",
    "a scalar at the top level": "just some text\n",
    "spec_kitty a list": "spec_kitty:\n  - 1\n",
    "spec_kitty a scalar": "spec_kitty: 4.0.0\n",
    "spec_kitty empty": "spec_kitty:\n",
    "environment a list": f"spec_kitty:\n  version: {VERSION_OK}\nenvironment:\n  - x\n",
    "migrations a list": f"spec_kitty:\n  version: {VERSION_OK}\nmigrations:\n  - x\n",
    "an infinite schema version": f"spec_kitty:\n  version: {VERSION_OK}\n  schema_version: .inf\n",
    "a migrations entry that is not a mapping": f"spec_kitty:\n  version: {VERSION_OK}\nmigrations:\n  applied:\n    - a text entry\n",
}


def row1_problems(env: Env) -> list[str]:
    problems: list[str] = []
    for label, text in RAISING_SHAPES.items():
        repo = env.fresh()
        kittify = _write_project(repo, text)
        try:
            ProjectMetadata.load(kittify)
        except (AttributeError, TypeError, OverflowError):
            pass
        else:
            problems.append(f"{label}: the unguarded load did not raise, so the plant is not real")
        problems += _differs(label, _build(env, repo), _expect())
    control = env.fresh()
    _write_project(control, _metadata())
    ProjectMetadata.load(control / ".kittify")
    problems += _differs("a mapping", _build(env, control), _expect(specKittyVersion=VERSION_OK, schemaVersion=3, health="healthy"))
    return problems


# ---------------------------------------------------------------------------
# AC-PROJECT 2: the sentinel never escapes; a version that is not a matching string is null
# ---------------------------------------------------------------------------

LONG_VERSION = "1" * 64
VERSIONS: dict[str, tuple[str, str | None]] = {
    "no version at all": ("spec_kitty:\n  schema_version: 3\n", None),
    "the product sentinel written out": (_metadata("unknown"), None),
    "a number": (_metadata("4"), None),
    "a float": (_metadata("4.0"), None),
    "path-shaped": (_metadata("../elsewhere/x"), None),
    "sentence-shaped": (_metadata('"four point oh"'), None),
    "a trailing line break": (_metadata('"4.0.0\\n"'), None),
    "65 characters": (_metadata('"' + "1" * 65 + '"'), None),
    "an empty string": (_metadata('""'), None),
    "64 characters": (_metadata(f'"{LONG_VERSION}"'), LONG_VERSION),
    "a release candidate": (_metadata("4.0.0rc5"), "4.0.0rc5"),
    "every allowed punctuation": (_metadata("1!2.0+local_build-3"), "1!2.0+local_build-3"),
    "the control": (_metadata(), VERSION_OK),
}
UNREADABLE_FILES: dict[str, str | bytes | None] = {
    "absent": None,
    "empty": "",
    "not YAML": "spec_kitty: [unclosed\n",
    "not UTF-8": b"spec_kitty:\n  version: \xff\xfe\n",
    "a timestamp the YAML constructor refuses": "spec_kitty:\n  version: 2026-13-45\n",
}


def row2_problems(env: Env) -> list[str]:
    problems: list[str] = []
    for label, (text, expected) in VERSIONS.items():
        repo = env.fresh()
        _write_project(repo, text)
        got = _build(env, repo)["specKittyVersion"]
        if got != expected:
            problems.append(f"{label}: specKittyVersion is {got!r}, expected {expected!r}")
    for label, content in UNREADABLE_FILES.items():
        repo = env.fresh()
        _write_project(repo, content)
        problems += _differs(label, _build(env, repo), _expect())
    return problems


# ---------------------------------------------------------------------------
# AC-PROJECT 3: a schema that is not an integer is null and unhealthy; the CLI's coercion is the contract's
# ---------------------------------------------------------------------------

SCHEMAS: dict[str, tuple[str, int | None]] = {
    "a word": ("schema_version: three", None),
    "a numeric string": ('schema_version: "3"', 3),
    "a float": ("schema_version: 3.9", 3),
    "a boolean": ("schema_version: true", 1),
    "absent": ("", None),
    "an empty value": ("schema_version:", None),
    "the control": ("schema_version: 3", 3),
}


def row3_problems(env: Env) -> list[str]:
    problems: list[str] = []
    for label, (line, expected) in SCHEMAS.items():
        repo = env.fresh()
        _write_project(repo, _metadata(schema_line=line or "other_key: 1"))
        got = _build(env, repo)
        cli = schema.get_project_schema_version(repo)
        if cli != expected:
            problems.append(f"{label}: the CLI reads {cli!r}, the table expects {expected!r}")
        compatible = schema.check_compatibility(cli, schema.REQUIRED_SCHEMA_VERSION or schema.MIN_SUPPORTED_SCHEMA).is_compatible
        problems += _differs(label, got, _expect(specKittyVersion=VERSION_OK, schemaVersion=cli, health="healthy" if compatible else "schema_drift"))
    return problems


# ---------------------------------------------------------------------------
# AC-PROJECT 4: the range boundaries, and range not equality
# ---------------------------------------------------------------------------


def _health_for(env: Env, value: int | None) -> str:
    repo = env.fresh()
    _write_project(repo, _metadata(schema_line="schema_version: null" if value is None else f"schema_version: {value}"))
    return str(_build(env, repo)["health"])


def row4_problems(env: Env) -> list[str]:
    problems: list[str] = []
    low, high = schema.MIN_SUPPORTED_SCHEMA, schema.MAX_SUPPORTED_SCHEMA
    for value, expected in ((low - 1, "schema_drift"), (low, "healthy"), (high, "healthy"), (high + 1, "schema_drift"), (None, "schema_drift")):
        got = _health_for(env, value)
        if got != expected:
            problems.append(f"schema {value!r}: health is {got!r}, expected {expected!r}")
        status = schema.check_compatibility(value, schema.REQUIRED_SCHEMA_VERSION or low)
        if (got == "healthy") != status.is_compatible:
            problems.append(f"schema {value!r}: health {got!r} disagrees with check_compatibility ({status.status.value})")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(schema, "MIN_SUPPORTED_SCHEMA", 2)
        patch.setattr(schema, "MAX_SUPPORTED_SCHEMA", 4)
        for value, expected in ((1, "schema_drift"), (2, "healthy"), (3, "healthy"), (4, "healthy"), (5, "schema_drift")):
            got = _health_for(env, value)
            if got != expected:
                problems.append(f"constants 2 and 4, schema {value}: health is {got!r}, expected {expected!r}")
    return problems


# ---------------------------------------------------------------------------
# AC-PROJECT 5: the branch states
# ---------------------------------------------------------------------------

BRANCH = "topic/x"
LINKED = "linked/y"
LONGEST = "a" * 255


def _head_only(env: Env, content: str | bytes | None) -> Path:
    """A project whose ``.git`` holds nothing but ``HEAD`` with ``content`` (a directory when content is None)."""
    repo = env.fresh()
    _write_project(repo, None)
    head = repo / ".git" / "HEAD"
    head.parent.mkdir()
    if content is None:
        head.mkdir()
    elif isinstance(content, bytes):
        head.write_bytes(content)
    else:
        head.write_text(content, encoding="utf-8")
    return repo


def _real_repo(env: Env, branch: str, *, commit: bool) -> Path:
    repo = env.fresh()
    _write_project(repo, None)
    _git_repo(repo, branch, commit=commit)
    return repo


GIT_PARITY = ("attached", "unborn (the name)", "a linked worktree (.git is a file)")


def _dot_git_file(env: Env, text: str) -> Path:
    repo = env.fresh()
    _write_project(repo, None)
    (repo / ".git").write_text(text, encoding="utf-8")
    return repo


def row5_problems(env: Env) -> list[str]:
    problems: list[str] = []
    host_path = SLASH.join(["home", "user1", "x"])
    if not env.leak.leak_codes(host_path, env.leak.STRICT):
        problems.append("the strict host-path plant is not flagged by the leak patterns, so the plant is not real")
    served: dict[str, tuple[Path, str]] = {}
    attached = _real_repo(env, BRANCH, commit=True)
    served["attached"] = (attached, BRANCH)
    served["unborn (the name)"] = (_real_repo(env, "topic/unborn", commit=False), "topic/unborn")
    detached = _real_repo(env, BRANCH, commit=True)
    _git(detached, "checkout", "-q", "--detach")
    linked_path = env.root / "linked-worktree"
    _git(attached, "worktree", "add", "-q", "-b", LINKED, str(linked_path))
    _write_project(linked_path, None)
    served["a linked worktree (.git is a file)"] = (linked_path, LINKED)
    store = _dot_git_file(env, "gitdir: elsewhere\n")
    (store / "elsewhere").mkdir()
    (store / "elsewhere" / "HEAD").write_text("ref: refs/heads/relative/store\n", encoding="utf-8")
    served["a .git file naming a relative gitdir"] = (store, "relative/store")
    served["the longest name"] = (_head_only(env, f"ref: refs/heads/{LONGEST}\n"), LONGEST)
    for label, (repo, expected) in served.items():
        got = _build(env, repo)["currentBranch"]
        if got != expected:
            problems.append(f"{label}: currentBranch is {got!r}, expected {expected!r}")
        if label in GIT_PARITY and got != get_current_branch(repo):
            problems.append(f"{label}: currentBranch {got!r} differs from get_current_branch {get_current_branch(repo)!r}")
    absent = env.fresh()
    _write_project(absent, None)
    nulls = {
        "detached HEAD": detached,
        "no repository": absent,
        "HEAD a directory": _head_only(env, None),
        "HEAD not UTF-8": _head_only(env, b"ref: refs/heads/\xff\n"),
        "HEAD unparseable": _head_only(env, "not a reference\n"),
        "HEAD empty": _head_only(env, ""),
        "a ref outside refs/heads": _head_only(env, "ref: refs/remotes/origin/main\n"),
        "a name that starts with a hyphen": _head_only(env, "ref: refs/heads/-bad\n"),
        "a name with a space": _head_only(env, "ref: refs/heads/a b\n"),
        "a name of 256 characters": _head_only(env, f"ref: refs/heads/{LONGEST}a\n"),
        "a strict host-path name": _head_only(env, f"ref: refs/heads/{host_path}\n"),
        "a .git file naming no gitdir": _dot_git_file(env, "gitdir: missing-store\n"),
        "a .git file that is no gitdir line": _dot_git_file(env, "something else\n"),
    }
    for label, repo in nulls.items():
        got = _build(env, repo)["currentBranch"]
        if got is not None:
            problems.append(f"{label}: currentBranch is {got!r}, expected null")
    return problems


# ---------------------------------------------------------------------------
# AC-PROJECT 6: the activity is the latest instant, not the latest text
# ---------------------------------------------------------------------------

EARLY_TEXT_LATE_INSTANT = "2026-09-01T09:00:00-05:00"  # 14:00 UTC
LATE_TEXT_EARLY_INSTANT = "2026-09-01T11:00:00+02:00"  # 09:00 UTC
MIDDLE = "2026-09-01T10:00:00+00:00"


def _repo_with_missions(env: Env, stamps: Mapping[str, str | None], *, coordinated: tuple[str, ...] = ()) -> Path:
    repo = env.fresh()
    _write_project(repo, _metadata())
    _git_repo(repo)
    for number, (name, at) in enumerate(stamps.items(), start=1):
        _mission(repo, name, number, at, coordinated=name in coordinated)
    return repo


def row6_problems(env: Env) -> list[str]:
    problems: list[str] = []
    cases: dict[str, tuple[Mapping[str, str | None], str | None]] = {
        "offsets where text order and instant order differ": (
            {"a-mission": MIDDLE, "b-mission": LATE_TEXT_EARLY_INSTANT, "c-mission": EARLY_TEXT_LATE_INSTANT},
            EARLY_TEXT_LATE_INSTANT,
        ),
        "the control, one active Mission": ({"a-mission": MIDDLE}, MIDDLE),
        "a Mission with no activity beside one with": ({"a-mission": None, "b-mission": MIDDLE}, MIDDLE),
        "every Mission without activity": ({"a-mission": None, "b-mission": None}, None),
        "no Mission at all": ({}, None),
    }
    for label, (stamps, expected) in cases.items():
        got = _build(env, _repo_with_missions(env, stamps))
        if got["lastActivityAt"] != expected or got["missionCount"] != len(stamps):
            problems.append(
                f"{label}: lastActivityAt {got['lastActivityAt']!r} (expected {expected!r}), missionCount {got['missionCount']} (expected {len(stamps)})"
            )
    problems.extend(_undecodable_activity_problems(env))
    return problems


def _undecodable_activity_problems(env: Env) -> list[str]:
    """A Mission whose ``status.json`` is not UTF-8 still counts and adds no activity; its clean twin (same repository, no plant) is the control."""
    problems: list[str] = []
    for label, plant in (("an undecodable status.json beside a clean Mission", True), ("the clean twin", False)):
        repo = _repo_with_missions(env, {"a-mission": MIDDLE, "b-mission": EARLY_TEXT_LATE_INSTANT})
        if plant:
            (repo / "kitty-specs" / "b-mission" / "status.json").write_bytes(bytes([0xFF, 0xFE, 0x00]))
        expected = MIDDLE if plant else EARLY_TEXT_LATE_INSTANT
        try:
            got = _build(env, repo)
        except Exception as error:  # the Project read never raises (FR-002, FR-003)
            problems.append(f"{label}: the build raised {type(error).__name__}: {error}")
            continue
        if got["lastActivityAt"] != expected or got["missionCount"] != 2:
            problems.append(f"{label}: lastActivityAt {got['lastActivityAt']!r} (expected {expected!r}), missionCount {got['missionCount']} (expected 2)")
    return problems


# ---------------------------------------------------------------------------
# AC-PROJECT 7: no process of its own, no write, and the v1 build is the control
# ---------------------------------------------------------------------------


def _snapshot(root: Path) -> dict[str, bytes]:
    """The name and bytes of every file below ``root`` except git's own directory."""
    return {
        path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*")) if ".git" not in path.relative_to(root).parts and path.is_file()
    }


def _forbid_own_processes_and_writes(patch: pytest.MonkeyPatch) -> None:
    """``subprocess.run`` raises unless the memo's resolver call is on the stack; every writing function of the reader chain raises."""
    real_run = subprocess.run

    def guarded(*arguments: Any, **options: Any) -> Any:
        if not memo_module.resolver_call_on_stack():
            raise UnexpectedProcess(f"the reader started a process of its own: {arguments[:1]}")
        return real_run(*arguments, **options)

    def forbidden(*arguments: Any, **options: Any) -> Any:
        raise UnexpectedProcess("the reader wrote")

    patch.setattr(subprocess, "run", guarded)
    patch.setattr(reducer, "materialize", forbidden)
    patch.setattr(Path, "write_text", forbidden)
    patch.setattr(Path, "write_bytes", forbidden)


def _resolver_error(kind: str, root: Path) -> Exception:
    place = root / "kitty-specs" / MISSION
    if kind == "CoordAuthorityUnavailable":
        return CoordAuthorityUnavailable(mission_slug=MISSION, coord_candidate=root / "coord", primary_candidate=place)
    if kind == "MissionMetadataUnavailable":
        return MissionMetadataUnavailable(mission_slug=MISSION, meta_path=place / "meta.json", primary_candidate=place, reason="unreadable")
    return CoordinationBranchDeleted(
        repo_root=root, mission_slug=MISSION, mid8="01234567", coordination_branch="kitty/coord", coord_candidate=root / "coord", primary_candidate=place
    )


class _Status:
    def __init__(self, read_dir: Path) -> None:
        self.read_dir = read_dir


def _v1_body(env: Env, repo: Path, new: Mapping[str, Any]) -> dict[str, Any]:
    """The v1 build: overviews through ``load_source`` and ``build_overview``, then ``derive_project``; the four non-Mission values are the builder's."""
    overviews = [helper.build_overview(helper.load_source(repo, name), helper.Projector(env.leak, name)) for name in helper.enumerate_missions(repo)]
    return helper.derive_project(
        str(new["name"]),
        overviews,
        spec_kitty_version=new["specKittyVersion"],
        schema_version=new["schemaVersion"],
        health=str(new["health"]),
        current_branch=new["currentBranch"],
    )


def _resolver_plants(env: Env) -> dict[str, tuple[Path, Callable[[pytest.MonkeyPatch, Path], None]]]:
    """Fixture repositories with two Missions, each beside the way the resolver can end (none patched for the plain control)."""

    outside: dict[Path, Path] = {}

    def make(*, coordinated: bool = False) -> Path:
        repo = _repo_with_missions(env, {"a-mission": MIDDLE, "b-mission": EARLY_TEXT_LATE_INSTANT}, coordinated=("b-mission",) if coordinated else ())
        outside[repo] = env.fresh()
        late = helper.transition_row(9, "WP01", "genesis", "planned", at="2030-01-01T00:00:00+00:00")
        helper.write_fixture_mission(outside[repo], "b-mission", meta={"mission_id": helper.fixture_ulid(2)}, rows=[late])
        return repo

    def patched(raise_kind: str | None) -> Callable[[pytest.MonkeyPatch, Path], None]:
        real = vars(MissionStatus)["load"].__func__

        def apply(patch: pytest.MonkeyPatch, repo: Path) -> None:
            def load(cls: Any, repo_root: Path, name: str) -> Any:
                if name != "b-mission":
                    return real(cls, repo_root, name)
                if raise_kind is None:
                    return _Status(outside[repo] / "kitty-specs" / "b-mission")
                raise _resolver_error(raise_kind, repo_root)

            patch.setattr(MissionStatus, "load", classmethod(load))

        return apply

    def plain(patch: pytest.MonkeyPatch, repo: Path) -> None:
        return None

    return {
        "the plain resolver": (make(), plain),
        "a declared coordination branch that is gone": (make(coordinated=True), plain),
        "CoordinationBranchDeleted": (make(), patched("CoordinationBranchDeleted")),
        "CoordAuthorityUnavailable": (make(), patched("CoordAuthorityUnavailable")),
        "MissionMetadataUnavailable": (make(), patched("MissionMetadataUnavailable")),
        "a read directory outside the checkout": (make(), patched(None)),
    }


FALLBACK_REASONS: dict[str, dict[str, str]] = {
    "the plain resolver": {},
    "a declared coordination branch that is gone": {"b-mission": "CoordinationBranchDeleted"},
    "CoordinationBranchDeleted": {"b-mission": "CoordinationBranchDeleted"},
    "CoordAuthorityUnavailable": {"b-mission": "CoordAuthorityUnavailable"},
    "MissionMetadataUnavailable": {"b-mission": "MissionMetadataUnavailable"},
    "a read directory outside the checkout": {"b-mission": project.OUTSIDE_ROOT},
}


def row7_problems(env: Env) -> list[str]:
    problems: list[str] = []
    for label, (repo, apply) in _resolver_plants(env).items():
        before = _snapshot(repo)
        memo = memo_module.ResolverMemo()
        with pytest.MonkeyPatch.context() as patch:
            apply(patch, repo)
            with memo_module.counting_subprocesses() as total, pytest.MonkeyPatch.context() as guard:
                _forbid_own_processes_and_writes(guard)
                outcome = project.build_project(repo, memo, leak=env.leak)
            problems += _differs(f"{label} against the v1 build", outcome.body, _v1_body(env, repo, outcome.body))
        recorded = sum(entry.subprocesses for entry in memo.entries())
        if total.started != recorded or (label.startswith("a declared") and recorded == 0):
            problems.append(f"{label}: the build started {total.started} processes, the memo recorded {recorded} (zero is not a control for a gone branch)")
        if _snapshot(repo) != before:
            problems.append(f"{label}: the build changed files below the repository")
        expected_fallback = FALLBACK_REASONS[label]
        if outcome.fallbacks != expected_fallback:
            problems.append(f"{label}: fallbacks are {outcome.fallbacks!r}, expected {expected_fallback!r}")
    return problems


def row7_own_process_problems(env: Env) -> list[str]:
    """A reader that starts a process of its own is refused by the stub (the plant), and the normal build is not (the control)."""
    repo = _repo_with_missions(env, {"a-mission": MIDDLE})
    with pytest.MonkeyPatch.context() as guard:
        _forbid_own_processes_and_writes(guard)
        project.build_project(repo, memo_module.ResolverMemo(), leak=env.leak)
        guard.setattr(project, "current_branch_of", _subprocess_branch)
        try:
            project.build_project(repo, memo_module.ResolverMemo(), leak=env.leak)
        except UnexpectedProcess:
            return []
    return ["a reader that starts git for HEAD was not refused by the stub of subprocess.run"]


def _subprocess_branch(repo_root: Path, leak: ModuleType) -> str | None:
    result = subprocess.run(["git", "-C", str(repo_root), "branch", "--show-current"], check=False, capture_output=True, text=True)
    return result.stdout.strip() or None


# ---------------------------------------------------------------------------
# AC-PROJECT 8: the description, the required list and the cost sentence
# ---------------------------------------------------------------------------

OLD_DESCRIPTION = "The project the service reports on. It carries a name and a count only; it never carries a path, a worktree location or a credential."
COST_WORDS = ("grows with the Mission count", "network probes", "side-effect-free", "not network-free", "no drift scan")
PROPERTY_WORDS = {
    "schemaVersion": ("coercion",),
    "health": ("serving build", "provisional"),
    "currentBranch": ("no branch name this contract can carry", "user-authored"),
    "lastActivityAt": ("no Mission is listed", "null activity"),
}


def schema_problems(document: Mapping[str, Any]) -> list[str]:
    """Every way a ``Project`` schema document misses FR-001 and the descriptions that carry rules."""
    problems: list[str] = []
    if sorted(document.get("required", [])) != sorted(PROPERTIES):
        problems.append(f"required is {document.get('required')!r}, expected the seven properties")
    properties = document.get("properties", {})
    if sorted(properties) != sorted(PROPERTIES):
        problems.append(f"properties are {sorted(properties)!r}")
    if document.get("additionalProperties") is not False:
        problems.append("the schema is not closed")
    description = str(document.get("description", ""))
    problems += [f"description does not name {name}" for name in NEW_PROPERTIES if name not in description]
    if "a name and a count only" in description:
        problems.append("description still says 'a name and a count only'")
    problems += [f"description lacks {words!r}" for words in COST_WORDS if words not in description]
    for name, words in PROPERTY_WORDS.items():
        text = str(properties.get(name, {}).get("description", ""))
        problems += [f"{name} description lacks {word!r}" for word in words if word not in text]
    for name in NEW_PROPERTIES:
        carried = [key for key in ("x-source", "x-derived") if key in properties.get(name, {})]
        if len(carried) != 1:
            problems.append(f"{name} carries {carried!r}, expected exactly one of x-source and x-derived")
    if "x-provisional" not in properties.get("health", {}):
        problems.append("health is not provisional")
    return problems


def row8_problems(env: Env) -> list[str]:
    real = yaml.safe_load(SCHEMA_FILE.read_text(encoding="utf-8"))
    problems = [f"real schema: {problem}" for problem in schema_problems(real)]
    frozen = {
        "title": "Project",
        "type": "object",
        "additionalProperties": False,
        "required": ["name", "missionCount"],
        "description": OLD_DESCRIPTION,
        "properties": {"name": {}, "missionCount": {}},
    }
    short = copy.deepcopy(real)
    short["required"] = ["name", "missionCount"]
    silent = copy.deepcopy(real)
    silent["description"] = silent["description"].replace(COST_WORDS[0], "depends on the Mission count")
    old_text = copy.deepcopy(real)
    old_text["description"] = OLD_DESCRIPTION
    for label, plant in (("the frozen old schema", frozen), ("a short required list", short), ("no cost sentence", silent), ("the old description", old_text)):
        if not schema_problems(plant):
            problems.append(f"{label}: the plant was not refused, so the check proves nothing")
    return problems


# ---------------------------------------------------------------------------
# The rows as tests
# ---------------------------------------------------------------------------

ROWS: dict[str, Callable[[Env], list[str]]] = {
    "row1": row1_problems,
    "row2": row2_problems,
    "row3": row3_problems,
    "row4": row4_problems,
    "row5": row5_problems,
    "row6": row6_problems,
    "row7": row7_problems,
    "row7-own-process": row7_own_process_problems,
    "row8": row8_problems,
}


@pytest.mark.parametrize("row", sorted(ROWS))
def test_the_project_rows_hold(row: str, env: Env) -> None:
    assert ROWS[row](env) == []


def test_every_built_project_validates_against_the_contract_and_leaks_nothing(env: Env, tools: helper.ContractTools) -> None:
    contract = helper.Contract(tools, MODULE_DIR)
    repo = _repo_with_missions(env, {"a-mission": MIDDLE})
    body = _build(env, repo)
    assert body == _expect(missionCount=1, specKittyVersion=VERSION_OK, schemaVersion=3, health="healthy", currentBranch="main", lastActivityAt=MIDDLE)
    assert contract.errors(helper.SCHEMA_PROJECT, body) == []
    assert helper.payload_leaks(body, tools) == []
    empty = env.fresh()
    _write_project(empty, None)
    all_null = _build(env, empty)
    assert all_null == _expect() and contract.errors(helper.SCHEMA_PROJECT, all_null) == []
    assert json.loads(json.dumps(body)) == body


# ---------------------------------------------------------------------------
# The mutations (proof kind M)
# ---------------------------------------------------------------------------


def _wrap_cli_version(patch: pytest.MonkeyPatch) -> None:
    patch.setattr(project, "project_version", lambda repo_root: get_project_version(repo_root))


def _unguarded_load(patch: pytest.MonkeyPatch) -> None:
    def defective(repo_root: Path) -> str | None:
        metadata = ProjectMetadata.load(repo_root / ".kittify")
        return metadata.version if metadata is not None and isinstance(metadata.version, str) and metadata.version != "unknown" else None

    patch.setattr(project, "project_version", defective)


def _strict_coercion(patch: pytest.MonkeyPatch) -> None:
    def defective(repo_root: Path) -> int | None:
        document = project.parsed_metadata(repo_root)
        raw = document.get("spec_kitty", {}).get("schema_version") if isinstance(document, dict) and isinstance(document.get("spec_kitty"), dict) else None
        return raw if type(raw) is int else None

    patch.setattr(project, "schema_version_of", defective)


def _equality_health(patch: pytest.MonkeyPatch) -> None:
    patch.setattr(project, "health_of", lambda value: "healthy" if value is not None and value == schema.MIN_SUPPORTED_SCHEMA else "schema_drift")


def _one_sided_health(patch: pytest.MonkeyPatch) -> None:
    patch.setattr(project, "health_of", lambda value: "healthy" if value is not None and value >= schema.MIN_SUPPORTED_SCHEMA else "schema_drift")


def _null_on_unborn(patch: pytest.MonkeyPatch) -> None:
    real = project.read_head

    def defective(repo_root: Path) -> str | None:
        head = project.head_file(repo_root)
        name = real(repo_root)
        return name if head is not None and name is not None and (head.parent / "refs" / "heads" / name).exists() else None

    patch.setattr(project, "read_head", defective)


def _subprocess_for_head(patch: pytest.MonkeyPatch) -> None:
    patch.setattr(project, "current_branch_of", _subprocess_branch)


def _string_max_activity(patch: pytest.MonkeyPatch) -> None:
    patch.setattr(project, "last_activity_of", lambda instants: max((stamp for stamp in instants if stamp), default=None))


def _no_fallback_outside_root(patch: pytest.MonkeyPatch) -> None:
    real = project.read_dir_of

    def defective(repo_root: Path, name: str, entry: memo_module.MemoEntry) -> tuple[Path, str | None]:
        if isinstance(entry.outcome, Path) and entry.outcome.resolve() != (repo_root / "kitty-specs" / name).resolve():
            return entry.outcome, None
        return real(repo_root, name, entry)

    patch.setattr(project, "read_dir_of", defective)


def _no_exception_fallback(patch: pytest.MonkeyPatch) -> None:
    real = project.read_dir_of

    def defective(repo_root: Path, name: str, entry: memo_module.MemoEntry) -> tuple[Path, str | None]:
        if isinstance(entry.outcome, CoordAuthorityUnavailable):
            raise entry.outcome
        return real(repo_root, name, entry)

    patch.setattr(project, "read_dir_of", defective)


def _unguarded_activity(patch: pytest.MonkeyPatch) -> None:
    def defective(read_dir: Path) -> str | None:
        snapshot = project.materialize_snapshot(read_dir)
        return project.last_activity_of(state.get("last_transition_at") for state in snapshot.work_packages.values())

    patch.setattr(project, "_mission_activity", defective)


MUTATIONS: dict[str, tuple[Callable[[pytest.MonkeyPatch], None], tuple[str, ...]]] = {
    "wrap-cli-version": (_wrap_cli_version, ("row1", "row2")),
    "unguarded-load": (_unguarded_load, ("row1",)),
    "strict-schema-coercion": (_strict_coercion, ("row3",)),
    "equality-health": (_equality_health, ("row4",)),
    "one-sided-health": (_one_sided_health, ("row4",)),
    "null-on-unborn": (_null_on_unborn, ("row5",)),
    "subprocess-for-head": (_subprocess_for_head, ("row7-own-process", "row7")),
    "string-max-activity": (_string_max_activity, ("row6",)),
    "unguarded-activity": (_unguarded_activity, ("row6",)),
    "no-fallback-outside-root": (_no_fallback_outside_root, ("row7",)),
    "no-exception-fallback": (_no_exception_fallback, ("row7",)),
}


def _problems_or_raised(row: Callable[[Env], list[str]], env: Env) -> list[str]:
    try:
        return row(env)
    except Exception as error:  # a mutant may crash the build: that is a red row, not an error of the test
        return [f"raised {type(error).__name__}: {error}"]


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_every_reader_mutation_turns_its_rows_red(name: str, env: Env) -> None:
    apply, rows = MUTATIONS[name]
    for row in rows:
        assert ROWS[row](env) == [], f"control: row {row} is not clean before the mutation"
    with pytest.MonkeyPatch.context() as patch:
        apply(patch)
        killed = any(_problems_or_raised(ROWS[row], env) for row in rows)
    assert killed, f"{NOT_KILLED}: {name}"


def test_the_mutation_table_names_only_known_rows_and_functions() -> None:
    assert all(row in ROWS for _, rows in MUTATIONS.values() for row in rows)
    assert {"project_version", "schema_version_of", "health_of", "current_branch_of", "last_activity_of", "read_dir_of"} <= set(dir(project))


# ---------------------------------------------------------------------------
# AC-DRIFT 16: the memo is keyed by the repository root and the Mission directory
# ---------------------------------------------------------------------------


def test_two_repositories_with_one_mission_name_and_different_outcomes_keep_their_own_result(env: Env) -> None:
    first = _repo_with_missions(env, {MISSION: MIDDLE})
    second = _repo_with_missions(env, {MISSION: MIDDLE})
    real = vars(MissionStatus)["load"].__func__
    seen: list[Path] = []

    def load(cls: Any, repo_root: Path, name: str) -> Any:
        seen.append(Path(repo_root))
        if Path(repo_root).resolve() == second.resolve():
            raise _resolver_error("CoordinationBranchDeleted", Path(repo_root))
        return real(cls, repo_root, name)

    memo = memo_module.ResolverMemo()
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(MissionStatus, "load", classmethod(load))
        first_entry = memo_module.memo_resolve(memo, first, MISSION)
        second_entry = memo_module.memo_resolve(memo, second, MISSION)
        outcomes = project.build_project(first, memo, leak=env.leak), project.build_project(second, memo, leak=env.leak)
    assert first_entry.outcome == first / "kitty-specs" / MISSION
    assert isinstance(second_entry.outcome, CoordinationBranchDeleted)
    assert outcomes[0].fallbacks == {} and outcomes[1].fallbacks == {MISSION: "CoordinationBranchDeleted"}
    assert len(seen) == 2, f"the resolver ran {len(seen)} times for two repositories read twice each"
    assert memo.runs == 2 and len(memo.entries()) == 2


def test_one_repository_read_twice_runs_the_resolver_once(env: Env) -> None:
    repo = _repo_with_missions(env, {MISSION: MIDDLE}, coordinated=(MISSION,))
    memo = memo_module.ResolverMemo()
    first = project.build_project(repo, memo, leak=env.leak)
    runs_after_first = memo.runs
    second = project.build_project(repo, memo, leak=env.leak)
    assert runs_after_first == 1 and memo.runs == 1, f"the resolver ran {memo.runs} times for one Mission read twice"
    assert first == second
    entry = memo.entries()[0]
    assert entry.subprocesses > 0, "the resolver started no process, so the count proves nothing"


def test_the_subprocess_counter_counts_a_started_process_and_only_inside_its_context(tmp_path: Path) -> None:
    with memo_module.counting_subprocesses() as count:
        subprocess.run(["git", "--version"], check=True, capture_output=True)
        subprocess.run(["git", "--version"], check=True, capture_output=True)
    assert count.started == 2, FAULT_NOT_FIRED
    subprocess.run(["git", "--version"], check=True, capture_output=True)
    assert count.started == 2


def test_the_resolver_marker_is_true_only_inside_the_memo_call(env: Env) -> None:
    repo = _repo_with_missions(env, {MISSION: MIDDLE})
    marks: list[bool] = []
    real = vars(MissionStatus)["load"].__func__

    def load(cls: Any, repo_root: Path, name: str) -> Any:
        marks.append(memo_module.resolver_call_on_stack())
        return real(cls, repo_root, name)

    assert memo_module.resolver_call_on_stack() is False
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(MissionStatus, "load", classmethod(load))
        memo_module.memo_resolve(memo_module.ResolverMemo(), repo, MISSION)
    assert marks == [True] and memo_module.resolver_call_on_stack() is False


def test_the_counting_wrapper_leaves_no_trace_in_popen() -> None:
    before = subprocess.Popen.__init__
    with memo_module.counting_subprocesses():
        assert subprocess.Popen.__init__ is not before
    assert subprocess.Popen.__init__ is before
    assert re.fullmatch(r"[A-Za-z_]+", memo_module.RESOLVER_FRAME)
