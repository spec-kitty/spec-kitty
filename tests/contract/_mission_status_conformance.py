"""The golden generator of the Mission Status API conformance gate (spec FR-008, plan section 1 "Python additions").

The goldens under ``services/mission-status-api/src/test/resources/conformance/`` are live output of the Python reference
helpers (``_mission_status_payloads.py`` and ``_mission_status_project.py``), written in one canonical form. This module is
not a second oracle: it provisions each committed fixture tree into a temporary directory, calls those helpers and writes
what they answer.

Run from the repository root::

    .venv/bin/python -m tests.contract._mission_status_conformance --write
    .venv/bin/python -m tests.contract._mission_status_conformance --check

``--write`` writes the goldens, ``manifest.json`` and ``leak-patterns.json``; ``--check`` compares and writes nothing.

Provisioning (plan section 1). A committed fixture tree has no ``.git``. A fixture that needs git gets a fresh temporary
repository (one commit of the primary tree; for a coordination Mission a coordination branch and a worktree registered at the
coordination worktree ROOT; a husk is a plain unregistered directory). A ``project-header`` fixture gets no repository: its
``HEAD`` text file is installed as ``.git/HEAD`` (or its ``GITDIR_POINTER`` text as the ``.git`` file). Git runs offline with a
fixed identity and fixed dates, so no temporary path, commit id or git date reaches a golden byte.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.lanes.branch_naming import coord_branch_name, resolve_mid8
from specify_cli.migration import schema_version as schema
from specify_cli.status.tail_reader import EMPTY_DIGEST, TailCursor, poll_once
from tests.contract import _mission_status_payloads as payloads
from tests.contract import _mission_status_project as project
from tests.contract._mission_status_memo import ResolverMemo

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFORMANCE_DIR = Path("services") / "mission-status-api" / "src" / "test" / "resources" / "conformance"
LEAK_PATTERNS_FILE = Path("services") / "mission-status-api" / "src" / "main" / "resources" / "leak-patterns.json"
MANIFEST_NAME = "manifest.json"
RESOLVER_CASES_NAME = "resolver-cases.json"
GOLDEN_DIR = "golden"
MISSIONS_GOLDEN = "missions.json"
PROJECT_GOLDEN = "project.json"
STREAM_GOLDEN = "stream.json"
GOLDEN_FILES = (MISSIONS_GOLDEN, PROJECT_GOLDEN)

# Names inside a fixture tree that are provisioning inputs, never copied into the oracle's project root as they are.
HEAD_TEXT = "HEAD"
POINTER_TEXT = "GITDIR_POINTER"
POINTER_TARGET = "gitdir-target"
COORD_SOURCE = "coord-worktree"
HUSK_SOURCE = "husk-worktree"
SYMLINK_PLAN = "SYMLINK_PLAN"
OUTSIDE_TREE = "outside"
BEFORE_LEDGER = "status.events.before.jsonl"
NOT_COPIED = frozenset({GOLDEN_DIR, HEAD_TEXT, POINTER_TEXT, POINTER_TARGET, COORD_SOURCE, HUSK_SOURCE, SYMLINK_PLAN, OUTSIDE_TREE})

OWN_CLASS = "own"
COORD_CLASS = "coord"
PARITY_GOLDEN = "python-golden"
PARITY_JAVA_ONLY = "java-only"
TAG_JAVA_ONLY = "javaOnly"
TAG_KNOWN_DIVERGENCE = "knownDivergence"

# The comparison ignore-list (spec FR-008, "Comparison scope"): one named constant, empty. `differences()` compares whole documents and
# never consults it; the Java side asserts its own empty constant (CanonicalJsonTest, GoldenSuiteTest).
MissionStatusIgnoreList: tuple[str, ...] = ()

# Git is deterministic and offline: a fixed identity, an empty global configuration, no system configuration, no remote.
GIT_IDENTITY_NAME = "Fixture Author"
GIT_IDENTITY_EMAIL = "fixture.author@fixture.invalid"
DEFAULT_GIT_DATE = "2026-01-01T00:00:00+00:00"
PRIMARY_BRANCH = "main"
# Variables an outer git (a hook, a rebase) may export; any of them would aim the fixture's git at the wrong repository.
_OUTER_GIT_VARIABLES = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_NAMESPACE",
    "GIT_PREFIX",
    "GIT_CEILING_DIRECTORIES",
)
_LINE_OF_ERROR = re.compile(r"\bline (\d+)\b")
_PAGE_SIZE = 50
# Only the event store names a ledger line in its message; other messages (a JSON decoder's "line 1 column 2") are not ledger lines.
_LINE_NUMBERED = frozenset({"StoreError", "DiaryError"})
# How a fixture tree is turned into a project root; recorded in the manifest so the Java fixture factory follows the same steps.
PROVISIONING_NOTES: Mapping[str, str] = {
    COORD_SOURCE: (
        "coord-worktree/<mission-dir>/ holds the contents of that Mission's coordination worktree ROOT (kitty-specs/<mission-dir>/...); "
        "installed at .worktrees/<slug>-<mid8>-coord as a registered git worktree (.worktrees/ is gitignored, so it cannot be committed in place)"
    ),
    HUSK_SOURCE: "husk-worktree/<mission-dir>/ holds a stale coordination worktree; installed at the same .worktrees path as a plain unregistered directory",
    HEAD_TEXT: "exact text installed as .git/HEAD; no git init and no commit run",
    POINTER_TEXT: "exact text installed as the .git pointer file; gitdir-target/ is copied beside it with its own HEAD",
    BEFORE_LEDGER: (
        "a Mission-level status.events.before.jsonl is the earlier state of the log: "
        "the stream scenario polls it first, then polls status.events.jsonl with the resulting cursor"
    ),
    SYMLINK_PLAN: (
        "javaOnly: lines 'link<TAB>target' relative to the project root, created as symlinks at test time; "
        "a target starting with @outside/ points into a sibling directory created from the fixture's outside/ tree"
    ),
    "blank-line": (
        "a Mission whose ledger holds a blank line is served: read_events_raw skips the line and the overview counts the other events. "
        "Its streamCursor is the cursor after the whole file: offset = the file size, invariant = the SHA-256 of the last terminated line, "
        "a blank line included (tail_reader). malformed-rows/blank-line has the blank line mid-file; malformed-rows/blank-line-final ends the file "
        "with it, so its invariant is the digest of the bare newline and validate_resume_cursor and poll_once reject the non-blank digest. "
        "Only poll_once refuses the blank line, which the stream golden records"
    ),
    "not-copied": (
        "golden/, HEAD, GITDIR_POINTER, gitdir-target/, coord-worktree/, husk-worktree/, SYMLINK_PLAN and outside/ "
        "are provisioning inputs and are not copied into the project root as they are"
    ),
}


@dataclass(frozen=True)
class ClassSpec:
    """One row of the FR-008 table: the tag, the property a fixture of the class must show, and the parity."""

    tag: str
    property: str
    parity: str


CLASS_SPECS: tuple[ClassSpec, ...] = (
    ClassSpec(
        "interleaved",
        "equal at with different event_id, file order differing from sort order, a duplicated event_id, text order of at differing from instant order",
        PARITY_GOLDEN,
    ),
    ClassSpec("coordination", "a current ledger under the coordination worktree and a primary ledger whose lane counts differ", PARITY_GOLDEN),
    ClassSpec("coord-husk", "a husk ledger beside the Mission whose counts differ from the primary ledger", PARITY_GOLDEN),
    ClassSpec("absent-topology", "classification differs between the two lanes.json cases only where Python's does", PARITY_GOLDEN),
    ClassSpec("lifecycle-only", "only the seven lifecycle types, wpTotal 0, a lifecycle-derived status", PARITY_GOLDEN),
    ClassSpec("no-ledger", "meta.json only, no ledger file, one Mission discarded", PARITY_GOLDEN),
    ClassSpec("log-truncated", "a shrunken log and a same-length last-line rewrite", PARITY_GOLDEN),
    ClassSpec("malformed-rows", "each variant records the exception class live Python raised", PARITY_GOLDEN),
    ClassSpec("torn-final-line", "an unparseable and a valid-JSON unterminated last line", PARITY_GOLDEN),
    ClassSpec("crlf-and-listing", "CRLF counts equal LF counts with a different streamCursor, page order equals the contract order", PARITY_GOLDEN),
    ClassSpec("project-header", "the Project document for each HEAD and metadata shape", PARITY_GOLDEN),
    ClassSpec("projection", "redaction tokens, nulled strict fields and instants, a refused strict field and a refused project name", PARITY_GOLDEN),
    ClassSpec("secret-canaries", "canary values planted in config, metadata, meta.json and event payload text", PARITY_JAVA_ONLY),
    ClassSpec("symlink", "a symlinked ledger, a symlinked meta.json and a Mission directory symlink escaping the root", PARITY_JAVA_ONLY),
)
CLASS_TAGS = tuple(spec.tag for spec in CLASS_SPECS)
JAVA_ONLY_TAGS = frozenset(spec.tag for spec in CLASS_SPECS if spec.parity == PARITY_JAVA_ONLY)

# Fixture-level manifest tags, keyed by "<class>/<fixture>".
FIXTURE_TAGS: Mapping[str, tuple[str, ...]] = {
    "torn-final-line/valid-json-final-line": (TAG_KNOWN_DIVERGENCE,),
}

# The strict or human class of each projected field (plan section 13, Projection).
PROJECTED_FIELD_CLASSES: Mapping[str, str] = {
    "missionId": "strict",
    "slug": "strict",
    "friendlyName": "human",
    "nextAction": "human",
    "targetBranch": "strict",
    "missionType": "strict",
    "name": "strict",
}


# ---------------------------------------------------------------------------
# Canonical form (NFR-005)
# ---------------------------------------------------------------------------


def canonical_json(document: Any) -> str:
    """Sorted keys, compact separators, UTF-8 without ASCII escaping; no timestamp, ordering or number is normalised."""
    return json.dumps(document, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def canonical_bytes(document: Any) -> bytes:
    return (canonical_json(document) + "\n").encode("utf-8")


# ---------------------------------------------------------------------------
# Fixtures on disk
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Fixture:
    """One committed fixture tree: ``conformance/<tag>/<name>/``."""

    tag: str
    name: str
    path: Path

    @property
    def key(self) -> str:
        return f"{self.tag}/{self.name}"

    @property
    def java_only(self) -> bool:
        return self.tag in JAVA_ONLY_TAGS


def discover_fixtures(conformance: Path) -> list[Fixture]:
    """Every fixture directory below ``conformance``, sorted by class then name (a missing class directory is simply absent)."""
    found: list[Fixture] = []
    for class_dir in sorted(entry for entry in conformance.iterdir() if entry.is_dir()):
        found.extend(Fixture(class_dir.name, entry.name, entry) for entry in sorted(class_dir.iterdir()) if entry.is_dir())
    return found


def mission_dirs(fixture_path: Path) -> list[Path]:
    """The directories below the fixture's ``kitty-specs`` (with or without a ``meta.json``)."""
    root = fixture_path / "kitty-specs"
    return sorted(entry for entry in root.iterdir() if entry.is_dir()) if root.is_dir() else []


def _declared_coordination(fixture_path: Path) -> bool:
    for mission in mission_dirs(fixture_path):
        try:
            meta = json.loads((mission / "meta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(meta, dict) and meta.get("coordination_branch"):
            return True
    return False


def needs_git(fixture_path: Path) -> bool:
    """Whether the oracle run needs a repository: a coordination worktree, a husk, or a declared coordination branch."""
    return (fixture_path / COORD_SOURCE).is_dir() or (fixture_path / HUSK_SOURCE).is_dir() or _declared_coordination(fixture_path)


def read_directory_class(fixture_path: Path) -> str:
    """``coord`` when the oracle reads a Mission from a registered coordination worktree, else ``own``."""
    return COORD_CLASS if (fixture_path / COORD_SOURCE).is_dir() else OWN_CLASS


def head_text_of(fixture_path: Path) -> str | None:
    """The exact text a project-header fixture installs as ``.git/HEAD`` (or, for the pointer case, the gitdir-target ``HEAD``)."""
    for candidate in (fixture_path / HEAD_TEXT, fixture_path / POINTER_TARGET / HEAD_TEXT):
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8")
    return None


# ---------------------------------------------------------------------------
# Provisioning
# ---------------------------------------------------------------------------


@contextmanager
def git_environment(home: Path, date: str) -> Iterator[None]:
    """Deterministic, offline git for the code inside the context: restores the process environment afterwards."""
    config = home / "empty-gitconfig"
    config.write_text("", encoding="utf-8")
    updates = {
        "HOME": str(home),
        "GIT_CONFIG_GLOBAL": str(config),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_AUTHOR_NAME": GIT_IDENTITY_NAME,
        "GIT_AUTHOR_EMAIL": GIT_IDENTITY_EMAIL,
        "GIT_COMMITTER_NAME": GIT_IDENTITY_NAME,
        "GIT_COMMITTER_EMAIL": GIT_IDENTITY_EMAIL,
        "GIT_AUTHOR_DATE": date,
        "GIT_COMMITTER_DATE": date,
        "GIT_TERMINAL_PROMPT": "0",
    }
    # The outer git variables are dropped and the pinned ones set for the context only; patch.dict(clear=True) restores the whole
    # environment on exit, so no manual save and restore is needed.
    scoped = {name: value for name, value in os.environ.items() if name not in _OUTER_GIT_VARIABLES}
    scoped.update(updates)
    with mock.patch.dict(os.environ, scoped, clear=True):
        yield


def run_git(repo: Path, *arguments: str) -> None:
    """One git call inside the provisioned environment; a failure raises with git's own message."""
    subprocess.run(["git", "-C", str(repo), "-c", "commit.gpgsign=false", *arguments], check=True, capture_output=True, text=True)


def worktree_porcelain(repo: Path) -> str:
    return subprocess.run(["git", "-C", str(repo), "worktree", "list", "--porcelain"], check=True, capture_output=True, text=True).stdout


def copy_primary_tree(fixture_path: Path, root: Path) -> None:
    """Copy the fixture tree into ``root`` without the provisioning inputs (they are installed by their own steps)."""
    for entry in sorted(fixture_path.iterdir()):
        if entry.name in NOT_COPIED:
            continue
        if entry.is_dir():
            shutil.copytree(entry, root / entry.name, symlinks=True)
        else:
            shutil.copy2(entry, root / entry.name)


def install_head(fixture_path: Path, root: Path) -> None:
    """The one project-header step (shared with the Java fixture factory): no ``git init``, no commit, no git binary."""
    pointer = fixture_path / POINTER_TEXT
    head = fixture_path / HEAD_TEXT
    if pointer.is_file():
        shutil.copyfile(pointer, root / ".git")
        shutil.copytree(fixture_path / POINTER_TARGET, root / POINTER_TARGET)
    elif head.is_file():
        (root / ".git").mkdir()
        shutil.copyfile(head, root / ".git" / HEAD_TEXT)


@dataclass(frozen=True)
class MissionIdentity:
    """The identity a worktree name is composed from."""

    directory: str
    slug: str
    mission_id: str | None
    mid8: str


def mission_identities(root: Path) -> list[MissionIdentity]:
    identities: list[MissionIdentity] = []
    for mission in mission_dirs(root):
        meta = json.loads((mission / "meta.json").read_text(encoding="utf-8"))
        slug, mission_id = str(meta.get("mission_slug") or mission.name), meta.get("mission_id")
        identities.append(MissionIdentity(mission.name, slug, mission_id, resolve_mid8(slug, mission_id=mission_id)))
    return identities


def coordination_worktree_root(root: Path, identity: MissionIdentity) -> Path:
    """The coordination worktree ROOT (``.worktrees/<slug>-<mid8>-coord``), not the Mission directory below it."""
    return CoordinationWorkspace.worktree_path(root, identity.slug, identity.mid8)


def _install_source(source: Path, destination: Path) -> None:
    shutil.copytree(source, destination, symlinks=True, dirs_exist_ok=True)


def provision_git(fixture_path: Path, root: Path) -> None:
    """A repository with one commit of the primary tree, a registered coordination worktree per coord Mission, plain husk directories."""
    run_git(root, "init", "-q", "-b", PRIMARY_BRANCH)
    run_git(root, "add", "-A")
    run_git(root, "commit", "-q", "-m", "fixture")
    for identity in mission_identities(root):
        coord_source = fixture_path / COORD_SOURCE / identity.directory
        husk_source = fixture_path / HUSK_SOURCE / identity.directory
        worktree = coordination_worktree_root(root, identity)
        if coord_source.is_dir():
            branch = coord_branch_name(identity.slug, mission_id=identity.mission_id)
            run_git(root, "worktree", "add", "-q", "-b", branch, str(worktree))
            _install_source(coord_source, worktree)
            run_git(worktree, "add", "-A")
            run_git(worktree, "commit", "-q", "--allow-empty", "-m", "coordination")
        elif husk_source.is_dir():
            _install_source(husk_source, worktree)


def provision(fixture: Fixture, root: Path, *, date: str = DEFAULT_GIT_DATE) -> None:
    """Materialise ``fixture`` into the empty directory ``root``; the caller keeps ``git_environment`` open around any oracle call."""
    copy_primary_tree(fixture.path, root)
    install_head(fixture.path, root)
    if needs_git(fixture.path):
        with git_environment(root.parent, date):
            provision_git(fixture.path, root)


# ---------------------------------------------------------------------------
# Resolver cases (spec FR-006, AC-6e)
# ---------------------------------------------------------------------------

RESOLVER_SLUG = "resolver-case"
RESOLVER_MISSION_ID = "01J77000000000000000000001"
_COORD_ROUTING = frozenset({"coord", "lanes_with_coord"})
_LANES_JSON_TEXT = {"valid": json.dumps({"lanes": [{"lane_id": "lane-a", "wp_ids": ["WP01"]}]}, sort_keys=True), "corrupt": "{not json"}
_RESOLVER_EVENT = {
    "actor": "claude",
    "at": "2026-09-01T10:00:00Z",
    "event_id": "01J77000000000000000000009",
    "evidence": None,
    "execution_mode": "worktree",
    "force": False,
    "from_lane": "planned",
    "mission_id": RESOLVER_MISSION_ID,
    "mission_slug": "resolver-case",
    "policy_metadata": None,
    "reason": None,
    "review_ref": None,
    "to_lane": "claimed",
    "wp_id": "WP01",
}


def resolver_mission_dir_name() -> str:
    return f"{RESOLVER_SLUG}-{RESOLVER_MISSION_ID[:8]}"


def _resolver_meta(case: Mapping[str, Any], name: str) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "mission_id": RESOLVER_MISSION_ID,
        "mission_slug": name,
        "slug": name,
        "friendly_name": "Resolver case",
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": PRIMARY_BRANCH,
        "created_at": "2026-09-01T10:00:00+00:00",
    }
    if case["storedTopology"] != "absent":
        meta["topology"] = case["storedTopology"]
    branch = _stored_branch_state(case)
    if branch == "present":
        meta["coordination_branch"] = coord_branch_name(name, mission_id=RESOLVER_MISSION_ID)
    elif branch == "empty":
        meta["coordination_branch"] = ""
    return meta


def _stored_branch_state(case: Mapping[str, Any]) -> str:
    """``present`` | ``empty`` | ``absent``: the stored ``coordination_branch``; a row without the key stores one for a coord-routing topology."""
    default = "present" if case["storedTopology"] in _COORD_ROUTING else "absent"
    return str(case.get("coordinationBranch", default))


def _coord_root_is_registered(case: Mapping[str, Any]) -> bool:
    """A registered git worktree or a plain husk; a row without ``coordRootKind`` is registered for a coord-routing topology only."""
    default = "registered" if case["storedTopology"] in _COORD_ROUTING else "husk"
    return str(case.get("coordRootKind", default)) == "registered"


def materialise_resolver_case(case: Mapping[str, Any], root: Path) -> str:
    """Write one ``resolver-cases.json`` row into the empty ``root`` and return the Mission directory name.

    A coordination root is a REGISTERED worktree for a coord-routing topology and a plain unregistered husk for a coord-less one,
    unless the row says otherwise (``coordRootKind``); ``coordinationBranch`` ("present", "absent", "empty") sets what ``meta.json`` stores;
    ``coordMeta`` ("present", "absent") says whether the coordination copy of the Mission directory holds a ``meta.json``.
    """
    name = resolver_mission_dir_name()
    meta = _resolver_meta(case, name)
    mission = root / "kitty-specs" / name
    mission.mkdir(parents=True)
    (mission / "meta.json").write_text(json.dumps(meta, sort_keys=True), encoding="utf-8")
    (mission / "status.events.jsonl").write_text(json.dumps(_RESOLVER_EVENT | {"mission_slug": name}, sort_keys=True) + "\n", encoding="utf-8")
    if case["lanesJson"] != "absent":
        (mission / "lanes.json").write_text(_LANES_JSON_TEXT[str(case["lanesJson"])], encoding="utf-8")
    run_git(root, "init", "-q", "-b", PRIMARY_BRANCH)
    run_git(root, "add", "-A")
    run_git(root, "commit", "-q", "-m", "fixture")
    if case["coordRootPresent"]:
        worktree = CoordinationWorkspace.worktree_path(root, name, RESOLVER_MISSION_ID[:8])
        if _coord_root_is_registered(case):
            run_git(root, "worktree", "add", "-q", "-b", coord_branch_name(name, mission_id=RESOLVER_MISSION_ID), str(worktree))
        else:
            worktree.mkdir(parents=True)
        in_worktree = worktree / "kitty-specs" / name
        if case["coordMissionDirPresent"]:
            _install_source(mission, in_worktree)
            if str(case.get("coordMeta", "present")) == "absent":
                (in_worktree / "meta.json").unlink()  # the coordination copy holds the ledger only
        elif in_worktree.exists():
            shutil.rmtree(in_worktree)  # a branch checkout carries the Mission directory; this case has none
    return name


def resolved_class_of_case(case: Mapping[str, Any], date: str = DEFAULT_GIT_DATE) -> str:
    """Run the real resolver (``resolve_read_dir``) on one materialised row and return ``own`` or ``coord``."""
    with tempfile.TemporaryDirectory(prefix="resolver-case-") as scratch:
        base = Path(scratch)
        root = base / "project"
        root.mkdir()
        with git_environment(base, date):
            name = materialise_resolver_case(case, root)
            read_dir, _fallback = payloads.resolve_read_dir(root, name)
        return OWN_CLASS if read_dir.resolve() == (root / "kitty-specs" / name).resolve() else COORD_CLASS


# ---------------------------------------------------------------------------
# The oracle run
# ---------------------------------------------------------------------------


def refusal_of(error: BaseException) -> dict[str, Any]:
    """What a refusal records: the exception class Python really raised and the 1-based line when its message names one."""
    name = type(error).__name__
    found = _LINE_OF_ERROR.search(str(error)) if name in _LINE_NUMBERED else None
    return {"refusal": {"exception": name, "line": int(found.group(1)) if found else None}}


def _guarded(build: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        return build()
    except Exception as error:  # the golden records the exception class Python raised, whatever it is
        return refusal_of(error)


def missions_document(root: Path, tools: payloads.ContractTools) -> dict[str, Any]:
    """The ``MissionOverviewPage`` the oracle serves for the whole project (the first page, default page size)."""
    overviews = []
    for name in payloads.enumerate_missions(root):
        source = payloads.load_source(root, name)
        overviews.append(payloads.build_overview(source, payloads.Projector(leak=tools.leak, mission=name)))
    items = payloads.order_overviews(overviews)
    return {"items": items, "pageInfo": {"hasNextPage": False, "nextPageCursor": None, "pageSize": _PAGE_SIZE}}


def project_document(root: Path, tools: payloads.ContractTools) -> dict[str, Any]:
    return project.build_project(root, ResolverMemo(), leak=tools.leak).body


def poll_result_document(path: Path, cursor: TailCursor) -> dict[str, Any]:
    result = poll_once(path, cursor)
    return {
        "events": result.events,
        "filePresent": result.file_present,
        "cursor": payloads.stream_cursor_of(result.cursor),
    }


def stream_document(root: Path) -> dict[str, Any] | None:
    """The tail-poll scenario of every Mission that holds a ``status.events.before.jsonl``: poll it, then poll the current log."""
    scenarios: dict[str, Any] = {}
    for mission in mission_dirs(root):
        before = mission / BEFORE_LEDGER
        if not before.is_file():
            continue
        start = TailCursor(offset=0, content_invariant=EMPTY_DIGEST)
        first = poll_once(before, start)
        scenarios[mission.name] = _guarded(lambda cursor=first.cursor, log=mission / "status.events.jsonl": poll_result_document(log, cursor))
    return {"scenarios": scenarios} if scenarios else None


def run_oracle(root: Path, tools: payloads.ContractTools) -> dict[str, dict[str, Any]]:
    """Every golden document of one provisioned fixture, keyed by file name, each canonicalisable as it is."""
    documents = {
        MISSIONS_GOLDEN: _guarded(lambda: missions_document(root, tools)),
        PROJECT_GOLDEN: _guarded(lambda: project_document(root, tools)),
    }
    stream = _guarded(lambda: stream_document(root) or {})
    if stream:
        documents[STREAM_GOLDEN] = stream
    return documents


def golden_bytes_of(fixture: Fixture, tools: payloads.ContractTools, *, date: str = DEFAULT_GIT_DATE) -> dict[str, bytes]:
    """Provision ``fixture`` into a fresh temporary directory, run the oracle there and return the canonical bytes per golden file."""
    with tempfile.TemporaryDirectory(prefix="conformance-") as scratch:
        base = Path(scratch)
        root = base / "project"
        root.mkdir()
        provision(fixture, root, date=date)
        with git_environment(base, date):
            documents = run_oracle(root, tools)
    return {name: canonical_bytes(document) for name, document in documents.items()}


# ---------------------------------------------------------------------------
# leak-patterns.json and the manifest
# ---------------------------------------------------------------------------

# Probe strings with a Python verdict recorded in the manifest, per pattern id. Synthetic text only.
_PROBES: Mapping[str, tuple[str, ...]] = {
    "strict-host-path-0": ("/srv/data", "~/notes", "C:\\temp", "relative/path"),
    "strict-host-path-1": ("docs/home/someone/file", "plain-name"),
    "strict-host-path-2": ("C:\\Users\\someone", "Users"),
    "human-host-path-0": ("see /home/someone/project", "the home directory"),
    "human-host-path-1": ("wrote /" + "tmp/scratch", "a tmp word"),
    "human-host-path-2": ("C:\\Users\\someone\\file", "Users"),
    "email": ("someone@example.com", "name@localhost", "owner/repo@ref", "@scope/pkg"),
    "email-anchored": ("someone@example.com", "owner/repo@ref"),
    "secret-0": ("ghp_" + "a" * 36, "ghp_short"),
    "secret-1": ("github_pat_" + "A" * 40, "github_pat_short"),
    "secret-2": ("AKIA" + "A" * 16, "AKIA123"),
    "secret-3": ("-----BEGIN " + "RSA PRIVATE KEY-----", "-----BEGIN PUBLIC KEY-----"),
}
# The pattern sources that use a construct whose meaning differs between Python ``re`` and ``java.util.regex`` by default.
_UNICODE_CONSTRUCTS = re.compile(r"\\[wWsSdDbB]")
# DD-86, DD-87, DD-88: the \w \s \d classes differ from java.util.regex even with UNICODE_CHARACTER_CLASS, so the Java side translates them.
DIVERGENCE_CONSTRUCT = (
    r"Python str-pattern \w \s \d differ from java.util.regex even with UNICODE_CHARACTER_CLASS "
    r"(Java \w also matches Mn, Mc, Me, Pc and Join_Control; Java \s omits U+001C to U+001F). "
    r"The Java side translates \w \W \s \S \d \D to Python's classes and guards lookbehind against supplementary characters (DD-86, DD-87); "
    r"\b and \B are refused."
)
_REGEX_FLAG_NAMES = ((re.IGNORECASE, "IGNORECASE"), (re.MULTILINE, "MULTILINE"), (re.DOTALL, "DOTALL"), (re.UNICODE, "UNICODE"))
_HUMAN_WIDENING = r"\S*"


def _flag_names(flags: int) -> list[str]:
    return [name for value, name in _REGEX_FLAG_NAMES if flags & value]


def _pattern_entries(leak: Any) -> list[dict[str, Any]]:
    """Every pattern of ``contracts/tools/leak_patterns.py`` as data: id, field class, kind, source, flags, token."""
    entries: list[tuple[str, str, str, Any, str | None]] = []
    entries += [(f"strict-host-path-{index}", "strict", "host_path", pattern, "[path]") for index, pattern in enumerate(leak.STRICT_HOST_PATH_PATTERNS)]
    entries += [(f"human-host-path-{index}", "human", "host_path", pattern, "[path]") for index, pattern in enumerate(leak.HUMAN_HOST_PATH_PATTERNS)]
    entries += [("email", "any", "email", leak.EMAIL_PATTERN, "[email]"), ("email-anchored", "any", "email", leak._EMAIL_ANCHORED, "[email]")]
    entries += [(f"secret-{index}", "any", "secret", pattern, None) for index, pattern in enumerate(leak.SECRET_PATTERNS)]
    return [
        {
            "id": identifier,
            "fieldClass": field_class,
            "kind": kind,
            "pattern": compiled.pattern,
            "flags": _flag_names(compiled.flags),
            "token": token,
            "redactionSuffix": _HUMAN_WIDENING if field_class == "human" else None,
        }
        for identifier, field_class, kind, compiled, token in entries
    ]


def leak_patterns_document(tools: payloads.ContractTools) -> dict[str, Any]:
    leak = tools.leak
    return {
        "source": "contracts/tools/leak_patterns.py",
        "tokens": {"path": "[path]", "email": "[email]"},
        "emailAnchoredNote": "email-anchored is applied only at the position where the previous email match ended",
        "patterns": _pattern_entries(leak),
        "secretCanaryNote": "fixtures use obviously fake canary values assembled from fragments; none is a real credential",
        "pythonRe": sys.version.split()[0] and "re",
    }


def pattern_probes(tools: payloads.ContractTools) -> dict[str, list[dict[str, Any]]]:
    """Per pattern id the probe strings with Python's verdict (``search`` found a match)."""
    compiled = {entry["id"]: entry for entry in _pattern_entries(tools.leak)}
    patterns = {
        **{f"strict-host-path-{i}": p for i, p in enumerate(tools.leak.STRICT_HOST_PATH_PATTERNS)},
        **{f"human-host-path-{i}": p for i, p in enumerate(tools.leak.HUMAN_HOST_PATH_PATTERNS)},
        "email": tools.leak.EMAIL_PATTERN,
        "email-anchored": tools.leak._EMAIL_ANCHORED,
        **{f"secret-{i}": p for i, p in enumerate(tools.leak.SECRET_PATTERNS)},
    }
    assert set(compiled) == set(patterns) == set(_PROBES), "every pattern needs probes"
    return {
        identifier: [{"text": text, "matches": patterns[identifier].search(text) is not None} for text in _PROBES[identifier]] for identifier in sorted(patterns)
    }


def unicode_divergences(document: Mapping[str, Any]) -> list[dict[str, str]]:
    """Patterns whose meaning differs by default between Python ``re`` (Unicode-aware classes) and ``java.util.regex`` (ASCII)."""
    return [{"id": entry["id"], "construct": DIVERGENCE_CONSTRUCT} for entry in document["patterns"] if _UNICODE_CONSTRUCTS.search(entry["pattern"])]


def leak_patterns_bytes(tools: payloads.ContractTools) -> bytes:
    document = leak_patterns_document(tools)
    document.pop("pythonRe")
    return canonical_bytes(document)


def file_digest(data: bytes) -> str:
    """SHA-256 of a committed data file's bytes (an integrity digest, not the charter content hash)."""
    return hashlib.sha256(data).hexdigest()  # noqa: TID251  # file-integrity digest of a committed data file


def installed_events_version() -> str:
    from importlib.metadata import version

    return version("spec-kitty-events")


def _fixture_entry(fixture: Fixture) -> dict[str, Any]:
    entry: dict[str, Any] = {"name": fixture.name, "readDirectoryClass": read_directory_class(fixture.path)}
    tags = list(FIXTURE_TAGS.get(fixture.key, ()))
    if fixture.java_only:
        tags.append(TAG_JAVA_ONLY)
    if tags:
        entry["tags"] = sorted(tags)
    head = head_text_of(fixture.path)
    if fixture.tag == "project-header" and head is not None:
        entry["headText"] = head
    return entry


def manifest_document(fixtures: Sequence[Fixture], resolver_case_ids: Sequence[str], leak_bytes: bytes, tools: payloads.ContractTools) -> dict[str, Any]:
    """``manifest.json`` (contract notes, "Conformance data formats")."""
    classes = []
    for spec in CLASS_SPECS:
        members = [fixture for fixture in fixtures if fixture.tag == spec.tag]
        classes.append({"tag": spec.tag, "fixtures": [_fixture_entry(member) for member in members], "property": spec.property, "parity": spec.parity})
    patterns = leak_patterns_document(tools)
    return {
        "specKittyEventsVersion": installed_events_version(),
        "supportedSchemaMin": schema.MIN_SUPPORTED_SCHEMA,
        "supportedSchemaMax": schema.MAX_SUPPORTED_SCHEMA,
        "resolverCaseIds": list(resolver_case_ids),
        "classes": classes,
        "leakPatternsSha256": file_digest(leak_bytes),
        "patternProbes": pattern_probes(tools),
        "patternDivergences": unicode_divergences(patterns),
        "projectedFieldClasses": dict(PROJECTED_FIELD_CLASSES),
        "provisioning": dict(PROVISIONING_NOTES),
    }


def resolver_case_ids(conformance: Path) -> list[str]:
    cases = json.loads((conformance / RESOLVER_CASES_NAME).read_text(encoding="utf-8"))
    return [str(case["id"]) for case in cases]


# ---------------------------------------------------------------------------
# Generate, write, check
# ---------------------------------------------------------------------------


def generate(conformance: Path, tools: payloads.ContractTools, *, date: str = DEFAULT_GIT_DATE) -> dict[Path, bytes]:
    """Every generated file, as ``path relative to the repository root`` -> bytes; reads the fixture trees, writes nothing."""
    fixtures = discover_fixtures(conformance)
    out: dict[Path, bytes] = {}
    for fixture in fixtures:
        if fixture.java_only:
            continue
        for name, content in golden_bytes_of(fixture, tools, date=date).items():
            out[CONFORMANCE_DIR / fixture.tag / fixture.name / GOLDEN_DIR / name] = content
    leak_bytes = leak_patterns_bytes(tools)
    out[LEAK_PATTERNS_FILE] = leak_bytes
    out[CONFORMANCE_DIR / MANIFEST_NAME] = canonical_bytes(manifest_document(fixtures, resolver_case_ids(conformance), leak_bytes, tools))
    return out


def stale_goldens(repo_root: Path, generated: Mapping[Path, bytes]) -> list[Path]:
    """Golden files below ``repo_root`` that the generator no longer produces."""
    expected = {repo_root / path for path in generated}
    return sorted(path for path in (repo_root / CONFORMANCE_DIR).glob(f"*/*/{GOLDEN_DIR}/*.json") if path not in expected)


def differences(repo_root: Path, generated: Mapping[Path, bytes]) -> list[str]:
    problems = []
    for relative, content in sorted(generated.items()):
        target = repo_root / relative
        if not target.is_file():
            problems.append(f"missing: {relative.as_posix()}")
        elif target.read_bytes() != content:
            problems.append(f"differs: {relative.as_posix()}")
    problems.extend(f"stale: {path.relative_to(repo_root).as_posix()}" for path in stale_goldens(repo_root, generated))
    return problems


def write_all(repo_root: Path, generated: Mapping[Path, bytes]) -> None:
    for path in stale_goldens(repo_root, generated):
        path.unlink()
    for relative, content in generated.items():
        target = repo_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true", help="write the goldens, manifest.json and leak-patterns.json")
    mode.add_argument("--check", action="store_true", help="compare with the committed files and write nothing")
    arguments = parser.parse_args(argv)
    with pytest.MonkeyPatch.context() as patch:
        tools = payloads.load_contract_tools(patch, REPO_ROOT)
        generated = generate(REPO_ROOT / CONFORMANCE_DIR, tools)
    if arguments.write:
        write_all(REPO_ROOT, generated)
        print(f"wrote {len(generated)} files")
        return 0
    problems = differences(REPO_ROOT, generated)
    for problem in problems:
        print(problem)
    print(f"checked {len(generated)} files: {len(problems)} differences")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
