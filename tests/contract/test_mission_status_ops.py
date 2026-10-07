"""Tests of the reference Ops reader of the ``mission-status`` contract (FR-016 to FR-021, FR-024; AC-OPS 1 to 14; AC-CROSS 1, 4, 5).

Every rule has a row function that builds fixture directories, calls the production entry point (``list_ops``) and returns the problems it
found; a test asserts the list is empty, and the mutation table (proof kind M) swaps one reader function for its defective twin and asserts
that some row of that mutation goes red (``the mutation was not killed: <name>``). Each row is its own control: the clean input beside the plant
on the same fixture shape, so a probe that sees nothing fails. Directories are written at run time into a temporary directory; faults are
injected through the reader's file-system seam, never through a permission change. Values a leak scan would flag (host paths, addresses,
credentials) are assembled from fragments, so this source holds none of them as a literal. The module reads no corpus directory.

Timed cases follow plan D-P16: each shape is timed as the minimum of several cold repeats (a fresh seam per repeat, with a counter that must be
above zero so the minimum is never a cache hit), and the short-value control is timed the same way.
"""

from __future__ import annotations

import ast
import base64
import json
import re
import subprocess
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import yaml
from jsonschema import Draft202012Validator

from specify_cli.invocation.record import OpStartedEvent
from specify_cli.invocation.writer import InvocationWriter, append_op_closure
from tests.contract import _mission_status_memo as memo_module
from tests.contract import _mission_status_ops as ops
from tests.contract import _mission_status_payloads as helper

pytestmark = [pytest.mark.contract, pytest.mark.corpus]

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_DIR = REPO_ROOT / "contracts" / "mission-status"
READER_FILE = Path(__file__).with_name("_mission_status_ops.py")
NOT_KILLED = "the mutation was not killed"
FAULT_NOT_FIRED = "the injected fault did not fire"
OPS = "kitty-ops"
T0 = "2026-10-01T10:00:00Z"
REPEATS = 7
REDACTION_BOUND = 0.1
LISTING_BOUND = 30.0
BIG = 256 * 1024
SMALL = 32 * 1024
FILE_COUNT = 10_000
SLASH = "/"
HOME_ROOT = SLASH + "ho" + "me" + SLASH
AT = "@"
FIVE_LEFT_OUT = ("request_text", "model_id", "governance_context_hash", "governance_context_available", "router_confidence")


class UnexpectedWrite(AssertionError):
    """A write the reader attempted: the stubs of every writing function raise it."""


@pytest.fixture(scope="module")
def tools() -> Iterator[helper.ContractTools]:
    with pytest.MonkeyPatch.context() as patch:
        yield helper.load_contract_tools(patch, REPO_ROOT)


@pytest.fixture(autouse=True)
def scratch_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Real git (the read-only fingerprint) runs with a scratch HOME and no system or global configuration."""
    home = tmp_path / "scratch-home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / "gitconfig"))


def _titled(tree: Any, found: dict[str, dict[str, Any]]) -> None:
    if isinstance(tree, list):
        for item in tree:
            _titled(item, found)
    elif isinstance(tree, dict):
        title = tree.get("title")
        if isinstance(title, str) and isinstance(tree.get("examples"), list):
            found.setdefault(title, tree)
        for key, value in tree.items():
            if key not in {"examples", "example", "default", "enum", "const"}:
                _titled(value, found)


SCHEMA_OF_STATUS = {200: "OpsInvocationPage", 500: "OpsRefusal"}


@dataclass
class Env:
    """One scratch area for a row: a fresh directory per repository, the contract validators and the leak tools."""

    root: Path
    tools: helper.ContractTools
    validators: Mapping[str, Draft202012Validator]
    made: int = 0

    def fresh(self) -> Path:
        self.made += 1
        directory = self.root / f"repo{self.made}"
        directory.mkdir()
        return directory

    def errors(self, title: str, instance: Any) -> list[str]:
        found = sorted(self.validators[title].iter_errors(instance), key=lambda error: [str(part) for part in error.absolute_path])
        return ["/" + "/".join(str(part) for part in error.absolute_path) + ": " + error.message[:160] for error in found]


@pytest.fixture
def env(tmp_path: Path, tools: helper.ContractTools) -> Env:
    area = tmp_path / "rows"
    area.mkdir()
    nodes: dict[str, dict[str, Any]] = {}
    _titled(tools.resolver.resolve(MODULE_DIR).tree, nodes)
    titles = ("OpsInvocationPage", "OpsInvocation", "OpsEvidence", "OpsRefusal", "PageCursorRefusal")
    validators = {title: Draft202012Validator(nodes[title], format_checker=tools.formats.FORMAT_CHECKER) for title in titles}
    return Env(area, tools, validators)


# ---------------------------------------------------------------------------
# Fixture directories
# ---------------------------------------------------------------------------


def ulid(number: int) -> str:
    return helper.fixture_ulid(number)


def started_event(
    number: int,
    *,
    profile: str = "python-pedro",
    action: str = "implement",
    actor: str = "claude",
    mode: str = "task_execution",
    started_at: str = T0,
    mission: str | None = None,
    wp: str | None = None,
) -> dict[str, Any]:
    """A v2 ``started`` line with every field of the record, the five left-out ones carrying text a leak would show."""
    event: dict[str, Any] = {
        "event": "started",
        "invocation_id": ulid(number),
        "profile_id": profile,
        "action": action,
        "request_text": "request text of the operator",
        "actor": actor,
        "mode_of_work": mode,
        "governance_context_hash": "0123456789abcdef",
        "governance_context_available": True,
        "router_confidence": "exact",
        "started_at": started_at,
        "model_id": "model-of-the-agent",
    }
    if mission is not None:
        event["mission_id"] = mission
    if wp is not None:
        event["wp_id"] = wp
    return event


def completed_event(
    number: int, *, outcome: str = "done", closed_by: str = "agent", at: str = "2026-10-01T11:00:00Z", evidence: str | None = None
) -> dict[str, Any]:
    event: dict[str, Any] = {"event": "completed", "invocation_id": ulid(number), "completed_at": at, "outcome": outcome, "closed_by": closed_by}
    if evidence is not None:
        event["evidence_ref"] = evidence
    return event


def legacy_completed(number: int) -> dict[str, Any]:
    """A completion of the pre-v2 shape: no ``closed_by``."""
    return {"event": "completed", "invocation_id": ulid(number), "completed_at": "2026-10-01T11:00:00Z", "outcome": "done"}


def ops_dir(repo: Path) -> Path:
    directory = repo / OPS
    directory.mkdir(exist_ok=True)
    return directory


def encode(lines: Sequence[Mapping[str, Any] | str | bytes]) -> bytes:
    out = b""
    for line in lines:
        out += line if isinstance(line, bytes) else (line if isinstance(line, str) else json.dumps(line)).encode("utf-8")
        out += b"\n"
    return out


def write_file(repo: Path, name: str, lines: Sequence[Mapping[str, Any] | str | bytes]) -> Path:
    path = ops_dir(repo) / name
    path.write_bytes(encode(lines))
    return path


def write_op(repo: Path, number: int, *, closed: Mapping[str, Any] | None = None, extra: Sequence[Any] = (), **kwargs: Any) -> Path:
    """One Op file: a ``started`` line, an optional ``completed`` line (the fields of ``completed_event``) and any extra lines."""
    lines: list[Any] = [started_event(number, **kwargs)]
    if closed is not None:
        lines.append(completed_event(number, **closed))
    return write_file(repo, f"{ulid(number)}.jsonl", [*lines, *extra])


def write_index(repo: Path, entries: Sequence[Any]) -> Path:
    """The index: an int is a line for that Op (its profile and instant as written by default), anything else is written as given."""
    lines = [{"invocation_id": ulid(entry), "profile_id": "python-pedro", "started_at": T0} if isinstance(entry, int) else entry for entry in entries]
    return write_file(repo, ops.INDEX_NAME, lines)


def write_spine(repo: Path, lines: Sequence[Any]) -> Path:
    return write_file(repo, ops.SPINE_NAME, lines)


def item_of(
    number: int,
    *,
    profile: str = "python-pedro",
    action: str = "implement",
    actor: str | None = "claude",
    mode: str = "task_execution",
    started_at: str = T0,
    mission: str | None = None,
    wp: str | None = None,
    closed: Mapping[str, Any] | None = None,
    evidence: Any = None,
) -> dict[str, Any]:
    """The item the reader must serve, typed independently of the reader."""
    done = closed is not None
    return {
        "invocationId": ulid(number),
        "profileId": profile,
        "action": action,
        "actor": actor,
        "modeOfWork": mode,
        "startedAt": started_at,
        "missionId": mission,
        "wpId": wp,
        "status": "closed" if done else "open",
        "outcome": closed.get("outcome", "done") if done else None,
        "closedBy": closed.get("closed_by", "agent") if done else None,
        "completedAt": closed.get("at", "2026-10-01T11:00:00Z") if done else None,
        "evidence": evidence,
    }


def at_minute(minute: int) -> str:
    return f"2026-10-01T10:{minute:02d}:00Z"


# ---------------------------------------------------------------------------
# The probe, the seam wrappers and the page walker
# ---------------------------------------------------------------------------


class Probe:
    """One row's problem list. Every call of the entry point is validated against its schema, the open and closed invariants and the leak scan."""

    def __init__(self, env: Env) -> None:
        self.env = env
        self.problems: list[str] = []

    def expect(self, condition: bool, message: str) -> None:
        if not condition:
            self.problems.append(message)

    def call(self, repo: Path, **kwargs: Any) -> ops.OpsOutcome:
        outcome = ops.list_ops(repo, tools=self.env.tools, **kwargs)
        body = outcome.body
        if outcome.status == 200:
            self.problems += [f"schema: {error}" for error in self.env.errors("OpsInvocationPage", body)]
            self.problems += [f"invariant: {problem}" for item in body["items"] for problem in ops.invariant_problems(item)]
        elif outcome.status == 500:
            self.problems += [f"schema: {error}" for error in self.env.errors("OpsRefusal", body)]
        elif body.get("code") == ops.CODE_BAD_CURSOR:
            self.problems += [f"schema: {error}" for error in self.env.errors("PageCursorRefusal", body)]
        self.problems += [f"leak: {leak}" for leak in helper.payload_leaks(body, self.env.tools)]
        if outcome.status != 200:
            self.expect(str(repo) not in json.dumps(body), "a refusal names the directory")
        return outcome

    def walk(self, repo: Path, *, profile: str | None = None, page_size: int = 3, between: Callable[[], None] | None = None) -> list[str]:
        """Every page of a read in order, the ids served; ``between`` runs once after the first page."""
        seen: list[str] = []
        cursor: str | None = None
        for page in range(1, 100):
            out = self.call(repo, profile=profile, page_size=page_size, cursor=cursor)
            if out.status != 200:
                self.problems.append(f"page {page} answered {out.status}")
                return seen
            seen += ids(out)
            if page == 1 and between is not None:
                between()
            info = out.body["pageInfo"]
            self.expect(info["pageSize"] == page_size, "the page size applied is not echoed")
            self.expect(info["hasNextPage"] == (info["nextPageCursor"] is not None), "hasNextPage and nextPageCursor disagree")
            if not info["hasNextPage"]:
                return seen
            cursor = info["nextPageCursor"]
        self.problems.append("the walk does not terminate")
        return seen


def ids(outcome: ops.OpsOutcome) -> list[str]:
    return [item["invocationId"] for item in outcome.body.get("items", [])]


def served_numbers(outcome: ops.OpsOutcome) -> list[int]:
    """The fixture numbers of the served Ops (the ULID of a fixture is its number in base 32)."""
    alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    return [sum(alphabet.index(char) * 32**place for place, char in enumerate(reversed(value))) for value in ids(outcome)]


@dataclass
class Counted:
    """A seam that records every path it was asked for; ``faults`` maps a file name to the error its open raises."""

    paths_opened: list[Path] = field(default_factory=list)
    paths_scanned: list[Path] = field(default_factory=list)
    paths_statted: list[Path] = field(default_factory=list)
    faults: Mapping[str, BaseException] = field(default_factory=dict)
    scan_fault: BaseException | None = None
    stat_fault: BaseException | None = None
    fired: int = 0

    def fs(self) -> ops.FileSystem:
        def stat(path: Path) -> Any:
            self.paths_statted.append(path)
            if self.stat_fault is not None:
                self.fired += 1
                raise self.stat_fault
            return ops.REAL_FS.stat(path)

        def scandir(path: Path) -> list[str]:
            self.paths_scanned.append(path)
            if self.scan_fault is not None:
                self.fired += 1
                raise self.scan_fault
            return ops.REAL_FS.scandir(path)

        def open_binary(path: Path) -> bytes:
            self.paths_opened.append(path)
            if path.name in self.faults:
                self.fired += 1
                raise self.faults[path.name]
            return ops.REAL_FS.open_binary(path)

        return ops.FileSystem(stat=stat, scandir=scandir, open_binary=open_binary)


def with_fs(probe: Probe, repo: Path, counted: Counted, **kwargs: Any) -> ops.OpsOutcome:
    return probe.call(repo, fs=counted.fs(), **kwargs)


# ---------------------------------------------------------------------------
# AC-OPS 1: newest first, ties by id descending
# ---------------------------------------------------------------------------


def row1_problems(env: Env) -> list[str]:
    probe = Probe(env)
    equal = env.fresh()
    for number in (1, 2, 3):
        write_op(equal, number, started_at=T0)
    probe.expect(served_numbers(probe.call(equal)) == [3, 2, 1], "equal instants are not ordered by invocationId descending")
    offsets = env.fresh()
    write_op(offsets, 1, started_at="2026-10-01T10:00:00+01:00")
    write_op(offsets, 2, started_at="2026-10-01T09:30:00Z")
    write_op(offsets, 3, started_at="2026-10-01T11:00:00+02:00")
    probe.expect(served_numbers(probe.call(offsets)) == [2, 3, 1], "instants with offsets are not ordered as instants (3 and 1 are the same instant)")
    distinct = env.fresh()
    for number in (1, 2, 3):
        write_op(distinct, number, started_at=at_minute(10 - number))
    probe.expect(served_numbers(probe.call(distinct)) == [1, 2, 3], "control: distinct instants are not ordered newest first")
    return probe.problems


# ---------------------------------------------------------------------------
# AC-OPS 2: paging once, the cursor bound to the filter
# ---------------------------------------------------------------------------

FORGED = ("cGFnZS0y", "", "!!!", "not a cursor at all")


def tampered(cursor: str, profile: str | None) -> list[str]:
    """Forged variants of a real cursor: one character changed, cut, extended, and the position edited under the original digest."""
    padded = cursor + "=" * (-len(cursor) % 4)
    payload = json.loads(base64.urlsafe_b64decode(padded))
    moved = {**payload, "t": payload["t"] + 1}
    other_id = {**payload, "i": ulid(31)}

    def encode_(document: Mapping[str, Any]) -> str:
        return base64.urlsafe_b64encode(json.dumps(document, separators=(",", ":")).encode()).decode().rstrip("=")

    flipped = cursor[:-1] + ("A" if cursor[-1] != "A" else "B")
    inserted = cursor[:8] + "!!!!" + cursor[8:]
    not_objects = [encode_(value) for value in ([1], 5, None, "text")]
    # Forged with the right digest: only the shape of each member can refuse these.
    stringly = {**payload, "t": "5", "d": ops.cursor_digest(profile, "5", payload["i"])}  # type: ignore[arg-type]
    not_ulid = {**payload, "i": "not-a-ulid", "d": ops.cursor_digest(profile, payload["t"], "not-a-ulid")}
    shaped = [encode_(stringly), encode_(not_ulid)]
    return [
        flipped,
        inserted,
        cursor[:-4],
        cursor + "AA",
        encode_(moved),
        encode_(other_id),
        encode_({**payload, "t": True}),
        encode_({**payload, "v": 2}),
        *not_objects,
        *shaped,
    ]


def row2_problems(env: Env) -> list[str]:
    probe = Probe(env)
    repo = env.fresh()
    for number in range(1, 8):
        write_op(repo, number, started_at=at_minute(number))
    expected = [7, 6, 5, 4, 3, 2, 1]
    whole = served_numbers(probe.call(repo, page_size=200))
    probe.expect(whole == expected, "the whole listing is not newest first")
    walked = probe.walk(repo, page_size=3)
    probe.expect(len(walked) == 7 and len(set(walked)) == 7, "control: an unchanged walk repeats or loses an Op")
    probe.expect(walked == [ulid(n) for n in expected], "control: the walk is not the listing in order")
    after_write = probe.walk(repo, page_size=3, between=lambda: write_op(repo, 8, started_at=at_minute(20)))
    probe.expect(after_write == [ulid(n) for n in expected], "an Op written at the head between two pages duplicates or skips an older one")
    probe.expect(ids(probe.call(repo, page_size=200))[0] == ulid(8), "control: the Op written between pages is not listed afterwards")
    mixed = env.fresh()
    for number in range(1, 5):
        write_op(mixed, number, profile="profile-a", started_at=at_minute(number))
    write_op(mixed, 5, profile="profile-b", started_at=at_minute(5))
    first_a = probe.call(mixed, profile="profile-a", page_size=2)
    cursor_a = first_a.body["pageInfo"]["nextPageCursor"]
    probe.expect(cursor_a is not None, "control: a first page of profile-a has no cursor")
    cursor_none = probe.call(mixed, page_size=2).body["pageInfo"]["nextPageCursor"]
    follow = probe.call(mixed, profile="profile-a", page_size=2, cursor=cursor_a)
    probe.expect(follow.status == 200 and served_numbers(follow) == [2, 1], "control: a cursor of profile-a with profile-a is refused or wrong")
    refused: list[tuple[str, dict[str, Any]]] = [
        ("profile-a cursor with profile-b", {"profile": "profile-b", "cursor": cursor_a}),
        ("profile-a cursor without a profile", {"profile": None, "cursor": cursor_a}),
        ("unfiltered cursor with profile-a", {"profile": "profile-a", "cursor": cursor_none}),
    ]
    refused += [(f"forged {value[:12]!r}", {"profile": "profile-a", "cursor": value}) for value in [*FORGED, *tampered(cursor_a or "AAAA", "profile-a")]]
    for label, arguments in refused:
        outcome = probe.call(mixed, page_size=2, **arguments)
        probe.expect(outcome.status == 400 and outcome.body.get("code") == ops.CODE_BAD_CURSOR, f"{label}: not a 400 invalid_page_cursor")
    for bad_size in (0, 201, -1, True):
        outcome = probe.call(mixed, page_size=bad_size)
        probe.expect(outcome.status == 400 and "code" not in outcome.body, f"pageSize {bad_size!r} is not a 400 problem")
    return probe.problems


# ---------------------------------------------------------------------------
# Skippable records (AC-OPS 3, 4, 8)
# ---------------------------------------------------------------------------


def started_without(number: int, name: str) -> dict[str, Any]:
    event = started_event(number)
    del event[name]
    return event


def skip_plants() -> dict[str, tuple[Callable[[Path, int], None], str]]:
    """One plant per way a record is skipped, each with the reason it must be skipped for. Each builder takes the repository and a fixture number."""

    def named(repo: Path, number: int, lines: Sequence[Any], name: str | None = None) -> None:
        write_file(repo, name or f"{ulid(number)}.jsonl", lines)

    valid = started_event
    return {
        "legacy started": (lambda r, n: named(r, n, [started_without(n, "mode_of_work")]), ops.SKIP_LEGACY),
        "empty file": (lambda r, n: ops_dir(r).joinpath(f"{ulid(n)}.jsonl").write_bytes(b""), ops.SKIP_EMPTY),
        "bad json": (lambda r, n: named(r, n, ["{not json"]), ops.SKIP_NOT_JSON),
        "first line a list": (lambda r, n: named(r, n, ["[1, 2]"]), ops.SKIP_NOT_STARTED),
        "first line a completion": (lambda r, n: named(r, n, [completed_event(n)]), ops.SKIP_NOT_STARTED),
        "invalid utf-8 after a valid first line": (lambda r, n: named(r, n, [valid(n), b"\xff\xfe"]), ops.SKIP_UTF8),
        "stem differs from the invocation id": (lambda r, n: named(r, n, [valid(n + 100)], f"{ulid(n)}.jsonl"), ops.SKIP_STEM),
        "instant with a space": (lambda r, n: named(r, n, [valid(n, started_at="2026-10-01 10:00:00Z")]), ops.SKIP_INSTANT),
        "instant without an offset": (lambda r, n: named(r, n, [valid(n, started_at="2026-10-01T10:00:00")]), ops.SKIP_INSTANT),
        "instant that is a word": (lambda r, n: named(r, n, [valid(n, started_at="yesterday")]), ops.SKIP_INSTANT),
        "instant in month 13": (lambda r, n: named(r, n, [valid(n, started_at="2026-13-01T10:00:00Z")]), ops.SKIP_INSTANT),
        "leap second": (lambda r, n: named(r, n, [valid(n, started_at="2026-06-30T23:59:60Z")]), ops.SKIP_INSTANT),
        "offset of 24 hours": (lambda r, n: named(r, n, [valid(n, started_at="2026-10-01T10:00:00+24:00")]), ops.SKIP_INSTANT),
        "completion instant not rfc 3339": (lambda r, n: named(r, n, [valid(n), completed_event(n, at="soon")]), ops.SKIP_INSTANT),
        "bad wp id": (lambda r, n: named(r, n, [valid(n, wp="WPx")]), ops.SKIP_FIELD),
        "bad mission id": (lambda r, n: named(r, n, [valid(n, mission="not-a-ulid")]), ops.SKIP_FIELD),
        "bad profile id": (lambda r, n: named(r, n, [valid(n, profile="-leading-dash")]), ops.SKIP_FIELD),
        "bad action": (lambda r, n: named(r, n, [valid(n, action="has space")]), ops.SKIP_FIELD),
        "nested too deep": (lambda r, n: named(r, n, ["[" * 100_000]), ops.SKIP_NOT_JSON),
        "integer too long": (lambda r, n: named(r, n, ['{"event": "started", "invocation_id": ' + "9" * 5000 + "}"]), ops.SKIP_NOT_JSON),
        "legacy completion without a spine record": (lambda r, n: named(r, n, [valid(n), legacy_completed(n)]), ops.SKIP_LEGACY_COMPLETION),
    }


def write_skippable(repo: Path, first: int) -> dict[str, str]:
    """Every skip plant written under consecutive numbers from ``first``; the reason each id must be skipped for."""
    reasons: dict[str, str] = {}
    for offset, (build, reason) in enumerate(skip_plants().values()):
        build(repo, first + offset)
        reasons[ulid(first + offset)] = reason
    return reasons


def row3_problems(env: Env) -> list[str]:
    probe = Probe(env)
    repo = env.fresh()
    for number in (1, 2, 3):
        write_op(repo, number, profile="profile-a", started_at=at_minute(number))
    for number in (4, 5):
        write_op(repo, number, profile="profile-b", started_at=at_minute(number))
    reasons = write_skippable(repo, 100)
    whole = probe.call(repo, page_size=200)
    probe.expect(whole.body["totalCount"] == 5 and len(ids(whole)) == 5, "control: totalCount is not the number of served Ops (skipped records must not count)")
    probe.expect(whole.body["skippedCount"] == len(reasons), "control: skippedCount is not the number of skipped records")
    matching = probe.call(repo, profile="profile-a", page_size=2)
    probe.expect(matching.body["totalCount"] == 3, "a profile filter: totalCount is not the number of served Ops of the profile")
    probe.expect(len(probe.walk(repo, profile="profile-a", page_size=2)) == 3, "a profile filter: the served count differs from totalCount")
    none = probe.call(repo, profile="profile-none")
    probe.expect(none.status == 200 and ids(none) == [] and none.body["totalCount"] == 0, "a profile with no Op is not an empty 200")
    probe.expect(none.body["pageInfo"]["hasNextPage"] is False and none.body["pageInfo"]["nextPageCursor"] is None, "an empty page has a next page")
    for bad in ("-bad", "a b", "", "x" * 129, "line\nbreak", "tail\n"):
        outcome = probe.call(repo, profile=bad)
        probe.expect(outcome.status == 400 and "code" not in outcome.body, f"a malformed profile {bad[:10]!r} is not a 400 problem")
    return probe.problems


def row4_problems(env: Env) -> list[str]:
    probe = Probe(env)
    repo = env.fresh()
    for number in (1, 2):
        write_op(repo, number, profile="profile-a", started_at=at_minute(number))
    write_op(repo, 3, profile="profile-b", started_at=at_minute(3))
    skipped = write_skippable(repo, 100)
    expected = len(skipped)
    for profile in (None, "profile-a", "profile-b", "profile-none"):
        outcome = probe.call(repo, profile=profile)
        probe.expect(
            outcome.body["skippedCount"] == expected, f"skippedCount follows the profile filter {profile!r}: {outcome.body['skippedCount']} not {expected}"
        )
        probe.expect(set(outcome.skipped_ids) == set(skipped), f"the skipped ids differ for the filter {profile!r}")
    clean = env.fresh()
    write_op(clean, 1, profile="profile-a")
    for profile in (None, "profile-a", "profile-none"):
        probe.expect(probe.call(clean, profile=profile).body["skippedCount"] == 0, f"control: skippedCount is not 0 with no skipped record ({profile!r})")
    return probe.problems


# ---------------------------------------------------------------------------
# AC-OPS 5: the candidate set, the index as a hint
# ---------------------------------------------------------------------------


def row5_problems(env: Env) -> list[str]:
    probe = Probe(env)
    full = env.fresh()
    for number in range(1, 6):
        write_op(full, number, started_at=at_minute(number))
    write_index(full, [1, 2, 3, 4, 5])
    counted = Counted()
    in_step = with_fs(probe, full, counted)
    probe.expect(served_numbers(in_step) == [5, 4, 3, 2, 1], "control: an index in step does not give every Op")
    probe.expect(not counted.paths_scanned, "an index that can be opened still lists the directory")
    bare = env.fresh()
    for number in range(1, 6):
        write_op(bare, number, started_at=at_minute(number))
    scanned = Counted()
    from_directory = with_fs(probe, bare, scanned)
    probe.expect(served_numbers(from_directory) == served_numbers(in_step), "control: no index differs from an index in step")
    probe.expect(len(scanned.paths_scanned) == 1, "no index: the directory is not listed exactly once")
    probe.expect(from_directory.body["totalCount"] == in_step.body["totalCount"] == 5, "control: totalCount differs between the two candidate sources")
    lag = env.fresh()
    for number in range(1, 6):
        write_op(lag, number, started_at=at_minute(number))
    write_index(lag, [1, 2, 3])
    lagging = probe.call(lag)
    probe.expect(served_numbers(lagging) == [3, 2, 1] and lagging.body["totalCount"] == 3, "a lagging index lists an Op the index does not name")
    probe.expect(lagging.body["skippedCount"] == 0, "an Op absent from the index is counted as skipped")
    stale = env.fresh()
    write_op(stale, 1, started_at=at_minute(1))
    write_index(stale, [1, 9])
    stale_out = probe.call(stale)
    probe.expect(served_numbers(stale_out) == [1] and stale_out.skipped_ids == (ulid(9),), "a stale index entry is not skipped and named")
    probe.expect(
        stale_out.skip_reasons == {ulid(9): ops.SKIP_ABSENT} and stale_out.body["skippedCount"] == 1, "a stale index entry is not counted for the absent file"
    )
    differ = env.fresh()
    write_op(differ, 1, profile="profile-a", started_at=at_minute(1))
    write_op(differ, 2, profile="profile-b", started_at=at_minute(2))
    write_index(differ, [{"invocation_id": ulid(1), "profile_id": "profile-x", "started_at": T0}, 2])
    probe.expect(ids(probe.call(differ, profile="profile-a")) == [ulid(1)], "the filter uses the profile of the index line, not of the file")
    probe.expect(ids(probe.call(differ, profile="profile-x")) == [], "the index profile of an Op still filters it")
    probe.expect(probe.call(differ, profile="profile-a").body["totalCount"] == 1, "totalCount follows the index profile")
    probe.expect(probe.call(differ).body["items"][1]["profileId"] == "profile-a", "an item serves the profile of the index line")
    unreadable = env.fresh()
    for number in range(1, 4):
        write_op(unreadable, number, started_at=at_minute(number))
    ops_dir(unreadable).joinpath(ops.INDEX_NAME).mkdir()
    probe.expect(served_numbers(probe.call(unreadable)) == [3, 2, 1], "an index that exists but cannot be opened is not replaced by the directory")
    faulted = env.fresh()
    for number in range(1, 4):
        write_op(faulted, number, started_at=at_minute(number))
    write_index(faulted, [1])
    fault = Counted(faults={ops.INDEX_NAME: PermissionError("injected")})
    fell_back = with_fs(probe, faulted, fault)
    probe.expect(fault.fired > 0, FAULT_NOT_FIRED)
    probe.expect(served_numbers(fell_back) == [3, 2, 1], "an index that raises on open is not replaced by the directory")
    corrupt = env.fresh()
    write_op(corrupt, 1, started_at=at_minute(1))
    write_op(corrupt, 2, started_at=at_minute(2))
    traversal = SLASH.join(["..", "..", "x"])
    write_index(
        corrupt, [1, "garbage line", "[1, 2]", b"\xff\xfe not utf-8", {"invocation_id": traversal}, {"invocation_id": 5}, {"profile_id": "p"}, "[" * 100_000, 1, 2]
    )
    opened = Counted()
    corrupt_out = with_fs(probe, corrupt, opened)
    probe.expect(served_numbers(corrupt_out) == [2, 1] and corrupt_out.body["skippedCount"] == 0, "a corrupt index line is served, counted or kills the read")
    probe.expect(all(path.parent == corrupt / OPS for path in opened.paths_opened), "an index entry that is not a ULID led the reader outside the Ops directory")
    probe.expect(
        len([path for path in opened.paths_opened if path.name.endswith(".jsonl") and path.name != ops.INDEX_NAME]) == 3,
        "a repeated index entry is read more than once or not at all",
    )
    return probe.problems


# ---------------------------------------------------------------------------
# AC-OPS 6: closure by the spine
# ---------------------------------------------------------------------------


def row6_problems(env: Env) -> list[str]:
    probe = Probe(env)
    repo = env.fresh()
    spine_only = {"outcome": "failed", "closed_by": "doctor_sweep", "at": "2026-10-02T09:00:00Z"}
    own = {"outcome": "done", "closed_by": "agent", "at": "2026-10-01T11:00:00Z"}
    write_op(repo, 1, started_at=at_minute(1))
    write_op(repo, 2, started_at=at_minute(2), closed=own)
    write_op(repo, 3, started_at=at_minute(3), closed=own)
    write_op(repo, 4, started_at=at_minute(4))
    write_op(repo, 5, started_at=at_minute(5), extra=[legacy_completed(5)])
    write_op(repo, 6, started_at=at_minute(6), extra=[legacy_completed(6)])
    write_op(repo, 7, started_at=at_minute(7))
    write_op(repo, 8, started_at=at_minute(8))
    first_of_two = {"outcome": "abandoned", "closed_by": "doctor_sweep", "at": "2026-10-03T09:00:00Z"}
    write_spine(
        repo,
        [
            completed_event(1, **spine_only),
            completed_event(3, outcome="failed", closed_by="doctor_sweep", at="2026-10-05T09:00:00Z"),
            completed_event(4, **first_of_two),
            completed_event(4, outcome="done", closed_by="agent", at="2026-10-04T09:00:00Z"),
            legacy_completed(5),
            "a corrupt line",
            completed_event(6, **spine_only),
            legacy_completed(7),
            completed_event(8, at="soon"),
            completed_event(99, **spine_only),
            started_event(5),
            "[1]",
            "[" * 100_000,
        ],
    )
    out = probe.call(repo, page_size=200)
    by_number = dict(zip(served_numbers(out), out.body["items"], strict=True))
    probe.expect(
        by_number[1] == item_of(1, started_at=at_minute(1), closed=spine_only), "an Op closed only on the spine is not served closed from it (the CLI gap)"
    )
    probe.expect(by_number[2] == item_of(2, started_at=at_minute(2), closed=own), "control: an Op closed in its own file is not served closed")
    probe.expect(by_number[3] == item_of(3, started_at=at_minute(3), closed=own), "an Op closed in both files is not served from its own file")
    probe.expect(by_number[4] == item_of(4, started_at=at_minute(4), closed=first_of_two), "two spine records: the first in file order does not serve")
    probe.expect(
        5 not in by_number and out.skip_reasons.get(ulid(5)) == ops.SKIP_LEGACY_COMPLETION, "a legacy own completion with no usable spine record is not skipped"
    )
    probe.expect(by_number[6] == item_of(6, started_at=at_minute(6), closed=spine_only), "a legacy own completion is not served closed from the spine record")
    probe.expect(by_number[7]["status"] == "open", "a legacy spine line closed an Op")
    probe.expect(
        8 not in by_number and out.skip_reasons.get(ulid(8)) == ops.SKIP_CLOSURE_INSTANT,
        "a spine record with a bad instant is served open, or skipped for another reason",
    )
    probe.expect(ulid(99) not in ids(out) and ulid(99) not in out.skipped_ids, "a spine record with no served Op appears, or is counted")
    probe.expect(
        out.skipped_ids == (ulid(5), ulid(8)) and out.body["skippedCount"] == 2,
        "the skipped ids of the spine fixture are not exactly the legacy completion and the bad instant",
    )
    probe.expect(out.body["totalCount"] == 6, "totalCount of the spine fixture is not the number of served Ops")
    return probe.problems


BAD_INSTANTS = ("soon", "2026-10-01 11:00:00Z", "2026-10-01T11:00:00", "2026-13-01T11:00:00Z", "2026-06-30T23:59:60Z")


def row6_instant_problems(env: Env) -> list[str]:
    """Operator ruling at WP08: the record that would close an Op, own or spine, with a bad instant skips the Op and counts it."""
    probe = Probe(env)
    good = {"outcome": "done", "closed_by": "agent", "at": "2026-10-01T11:00:00Z"}
    for offset, bad in enumerate(BAD_INSTANTS, start=1):
        repo = env.fresh()
        write_op(repo, 1, started_at=at_minute(1))
        write_op(repo, 2, started_at=at_minute(2), closed={"at": bad})
        write_op(repo, 3, started_at=at_minute(3), closed={"at": bad})
        write_op(repo, 4, started_at=at_minute(4), extra=[legacy_completed(4)])
        write_op(repo, 5, started_at=at_minute(5))
        write_op(repo, 6, started_at=at_minute(6))
        write_spine(
            repo,
            [
                completed_event(1, at=bad),
                completed_event(1, **good),
                completed_event(3, **good),
                completed_event(4, at=bad),
                completed_event(5, **good),
                completed_event(5, at=bad),
                completed_event(6, at=bad),
            ],
        )
        out = probe.call(repo, page_size=200)
        label = f"instant {bad!r}"
        probe.expect(ids(out) == [ulid(5)], f"{label}: only the Op whose first closing record is good is served")
        probe.expect(out.skip_reasons.get(ulid(1)) == ops.SKIP_CLOSURE_INSTANT, f"{label}: a bad first spine record (a good one after it) does not skip the Op")
        probe.expect(out.skip_reasons.get(ulid(2)) == ops.SKIP_INSTANT, f"{label}: a bad own completion with no spine record does not skip the Op")
        probe.expect(out.skip_reasons.get(ulid(3)) == ops.SKIP_INSTANT, f"{label}: a bad own completion beside a good spine record does not skip the Op")
        probe.expect(out.skip_reasons.get(ulid(4)) == ops.SKIP_CLOSURE_INSTANT, f"{label}: a legacy own completion with a bad spine record does not skip the Op")
        probe.expect(out.skip_reasons.get(ulid(6)) == ops.SKIP_CLOSURE_INSTANT, f"{label}: a bad only spine record does not skip the Op")
        probe.expect(out.body["skippedCount"] == 5 and out.body["totalCount"] == 1, f"{label}: the skipped and total counts are not 5 and 1")
        probe.expect(
            out.body["items"] == [item_of(5, started_at=at_minute(5), closed=good)], f"{label}: the Op with a good first spine record is not served closed from it"
        )
        # clean twin: the same files with a good instant in every bad place serve all six Ops
        twin = env.fresh()
        write_op(twin, 1, started_at=at_minute(1))
        write_op(twin, 2, started_at=at_minute(2), closed=good)
        write_op(twin, 4, started_at=at_minute(4), extra=[legacy_completed(4)])
        write_op(twin, 6, started_at=at_minute(6))
        write_spine(twin, [completed_event(1, **good), completed_event(4, **good), completed_event(6, **good)])
        control = probe.call(twin, page_size=200)
        probe.expect(
            len(ids(control)) == 4 and control.body["skippedCount"] == 0 and {item["status"] for item in control.body["items"]} == {"closed"},
            f"control {offset}: the clean twin is skipped or open",
        )
    return probe.problems


# ---------------------------------------------------------------------------
# AC-OPS 7: the open and closed invariants
# ---------------------------------------------------------------------------


def row7_problems(env: Env) -> list[str]:
    probe = Probe(env)
    repo = env.fresh()
    write_op(repo, 1)
    write_op(repo, 2, closed={"outcome": "done"})
    served = probe.call(repo).body["items"]
    probe.expect(len(served) == 2 and all(ops.invariant_problems(item) == [] for item in served), "control: consistent Ops fail the invariants")
    open_item, closed_item = item_of(1), item_of(2, closed={"outcome": "done"})
    for name, value in (("outcome", "done"), ("closedBy", "agent"), ("completedAt", T0), ("evidence", {"kind": "text", "value": "x", "redacted": False})):
        planted = {**open_item, name: value}
        probe.expect(ops.invariant_problems(planted) == [f"an open Op carries {name}"], f"an open Op carrying {name} is not reported exactly once")
    for name in ("outcome", "closedBy", "completedAt"):
        planted = {**closed_item, name: None}
        probe.expect(ops.invariant_problems(planted) == [f"a closed Op lacks {name}"], f"a closed Op lacking {name} is not reported exactly once")
    probe.expect(ops.invariant_problems({**closed_item, "evidence": None}) == [], "control: a closed Op with null evidence is reported")
    probe.expect(ops.invariant_problems({**open_item, "status": "pending"}) == ["the status is neither open nor closed"], "an unknown status is not reported")
    return probe.problems


# ---------------------------------------------------------------------------
# AC-OPS 8: legacy and unreadable records, non-Op files
# ---------------------------------------------------------------------------

NON_OP_NAMES = (
    "lifecycle.jsonl",
    "notes.yaml",
    "readme.txt",
    ".gitkeep",
    "01KTK4DFAS04MCX5GP1W2R6NEP.jsonl.bak",
    "01ktk4dfas04mcx5gp1w2r6nep.jsonl",
    "01KTK4DFAS04MCX5GP1W2R6NEU.jsonl",
    "0001.jsonl",
)


def row8_problems(env: Env) -> list[str]:
    probe = Probe(env)
    for label, (build, reason) in skip_plants().items():
        repo = env.fresh()
        write_op(repo, 1, started_at=at_minute(1))
        build(repo, 2)
        out = probe.call(repo)
        if out.status != 200:
            probe.expect(False, f"{label}: the read answered {out.status} instead of skipping the record")
            continue
        probe.expect(ids(out) == [ulid(1)] and out.body["totalCount"] == 1, f"{label}: the skipped record is served or counted in totalCount")
        probe.expect(out.skip_reasons == {ulid(2): reason}, f"{label}: skipped for {out.skip_reasons.get(ulid(2))!r}, not {reason!r}")
        probe.expect(out.body["skippedCount"] == 1, f"{label}: skippedCount is not 1")
    extremes = env.fresh()
    write_op(extremes, 1, started_at="0001-01-01T00:00:00+23:59")
    write_op(extremes, 2, started_at="9999-12-31T23:59:59-23:59")
    write_op(extremes, 3, started_at="0001-01-01T00:00:00Z")
    write_op(extremes, 4, started_at="2026-10-01T10:00:00.123456789+05:30")
    write_op(extremes, 5, started_at="2026-10-01t10:00:00z")
    out = probe.call(extremes)
    probe.expect(
        served_numbers(out) == [2, 5, 4, 3, 1] or served_numbers(out) == [2, 4, 5, 3, 1],
        "extreme instants (year 1, year 9999, lowercase letters) are skipped, fail or are misordered",
    )
    probe.expect(out.body["skippedCount"] == 0, "a valid extreme instant is counted as skipped")
    vanished = env.fresh()
    write_op(vanished, 1, started_at=at_minute(1))
    write_op(vanished, 2, started_at=at_minute(2))
    gone = Counted(faults={f"{ulid(2)}.jsonl": FileNotFoundError("injected")})
    gone_out = with_fs(probe, vanished, gone)
    probe.expect(gone.fired > 0, FAULT_NOT_FIRED)
    probe.expect(ids(gone_out) == [ulid(1)] and gone_out.skip_reasons == {ulid(2): ops.SKIP_ABSENT}, "a file gone after listing is not skipped as absent")
    mixed = env.fresh()
    write_op(mixed, 1, started_at=at_minute(1))
    for name in NON_OP_NAMES:
        write_file(mixed, name, [started_event(2)])
    write_spine(mixed, [completed_event(1)])
    ops_dir(mixed).joinpath("evidence").mkdir()
    mixed_out = probe.call(mixed)
    probe.expect(
        ids(mixed_out) == [ulid(1)] and mixed_out.body["totalCount"] == 1 and mixed_out.body["skippedCount"] == 0,
        "a file that is not an Op file is read, served or counted",
    )
    probe.expect(mixed_out.body["items"][0]["status"] == "closed", "control: the clean Op beside the non-Op files is not served")
    first_line_only = env.fresh()
    write_op(
        first_line_only,
        1,
        extra=["not json at all", "[1]", "[" * 100_000, {"event": "artifact_link", "invocation_id": ulid(1)}, started_event(1, profile="other-profile")],
    )
    probe.expect(probe.call(first_line_only).body["items"][0]["profileId"] == "python-pedro", "a later line of the Op file changed the record")
    foreign = env.fresh()
    write_op(foreign, 1, extra=[completed_event(2)])
    foreign_out = probe.call(foreign)
    probe.expect(foreign_out.body["items"][0]["status"] == "open", "a completion that names another invocation closed the Op")
    return probe.problems


# ---------------------------------------------------------------------------
# AC-OPS 9: an empty and a failing directory
# ---------------------------------------------------------------------------


def row9_problems(env: Env) -> list[str]:
    probe = Probe(env)
    absent = env.fresh()
    out = probe.call(absent)
    probe.expect(out.status == 200 and out.body == ops.empty_page(50) and out.skipped_ids == (), "no kitty-ops/ is not a 200 with an empty page and both counts 0")
    probe.expect(
        out.body["totalCount"] == 0 and out.body["skippedCount"] == 0 and out.body["pageInfo"]["hasNextPage"] is False, "the empty page counts or has a next page"
    )
    refused = [
        ("kitty-ops is a file", lambda repo: (repo / OPS).write_text("not a directory"), {}),
        ("an Op file is a directory", lambda repo: (ops_dir(repo) / f"{ulid(2)}.jsonl").mkdir(), {}),
        ("the spine is a directory", lambda repo: (ops_dir(repo) / ops.SPINE_NAME).mkdir(), {}),
        ("the spine is not UTF-8", lambda repo: (ops_dir(repo) / ops.SPINE_NAME).write_bytes(b"\xff\xfe\n"), {}),
        ("the spine cannot be opened", lambda repo: write_spine(repo, [completed_event(1)]), {"faults": {ops.SPINE_NAME: PermissionError("injected")}}),
        ("an Op file cannot be opened", lambda repo: write_op(repo, 2), {"faults": {f"{ulid(2)}.jsonl": PermissionError("injected")}}),
        ("the directory cannot be listed", lambda repo: None, {"scan_fault": PermissionError("injected")}),
        ("the directory cannot be examined", lambda repo: None, {"stat_fault": PermissionError("injected")}),
    ]
    for label, build, faults in refused:
        repo = env.fresh()
        if label != "kitty-ops is a file":
            write_op(repo, 1)
        build(repo)
        counted = Counted(**faults)
        result = with_fs(probe, repo, counted)
        if faults:
            probe.expect(counted.fired > 0, f"{label}: {FAULT_NOT_FIRED}")
        probe.expect(result.status == 500 and result.body.get("code") == ops.CODE_UNREADABLE, f"{label}: answered {result.status}, not a 500 ops_unreadable")
        probe.expect(result.body.get("items") is None, f"{label}: a partial page is served beside the failure")
    corrupt_line = env.fresh()
    write_op(corrupt_line, 1)
    write_spine(corrupt_line, ["a corrupt line", completed_event(1)])
    probe.expect(probe.call(corrupt_line).body["items"][0]["status"] == "closed", "control: a corrupt spine line made the read fail")
    one = env.fresh()
    write_op(one, 1)
    probe.expect(probe.call(one).status == 200 and probe.call(one).body["totalCount"] == 1, "control: one Op is not a 200")
    beside = env.fresh()
    write_op(beside, 1)
    write_op(beside, 2)
    flaky = Counted(faults={f"{ulid(1)}.jsonl": PermissionError("injected")})
    partial = with_fs(probe, beside, flaky)
    probe.expect(
        flaky.fired > 0 and partial.status == 500 and "items" not in partial.body, "one unreadable Op file beside a readable one gives an empty or partial 200"
    )
    return probe.problems


# ---------------------------------------------------------------------------
# AC-OPS 10 and 11: evidence classes, credentials withheld before redaction
# ---------------------------------------------------------------------------

LONG_TEXT = "word " * 120
MID = "mid"
EVIDENCE_TABLE: dict[str, tuple[str, str, str, bool]] = {
    "url with userinfo, query and fragment": ("https://" + "someone:pw" + AT + "example.test/a/b?token=1#frag", "url", "https://example.test/a/b", True),
    "url with userinfo only": ("ssh://" + "git" + AT + "example.test/repo.git", "url", "ssh://example.test/repo.git", True),
    "url with an address in the query": ("https://example.test/a?e=x" + AT + "y.test", "url", "https://example.test/a", True),
    "url with an upper-case scheme, clean": ("HTTPS://example.test/a", "url", "HTTPS://example.test/a", False),
    "file url": ("file:///opt/x", "text", "[path]", True),
    "file url in capitals": ("FILE:///opt/x", "text", "[path]", True),
    "unc path": (chr(92) * 2 + "server" + chr(92) + "share" + chr(92) + "x", "text", "[path]", True),
    "absolute path with whitespace": ("/opt/my dir/x.txt", "text", "[path]", True),
    "absolute path": ("/opt/x", "text", "[path]", True),
    "drive path": ("C:" + chr(92) + "Work" + chr(92) + "x", "text", "[path]", True),
    "drive path in lower case": ("c:/work/x", "text", "[path]", True),
    "tilde path": ("~/notes.md", "text", "[path]", True),
    "text holding an address": ("Reviewed by a" + AT + "b.test today", "text", "Reviewed by [email] today", True),
    "relative path holding an address": ("docs/a" + AT + "b.test/x.md", "text", "docs/[email]/x.md", True),
    "text with an embedded url": ("see https://u:p" + AT + "host.test/x?q=1 and more", "text", "see https://host.test/x and more", True),
    "address of 600 characters": ("https://example.test/" + "a" * 600, "text", ("https://example.test/" + "a" * 600)[:512], True),
    "text with a one-character-scheme run": ("see 1a://u" + AT + "h/x ok", "text", "see 1a://u" + AT + "h/x ok", False),
    "text with a home path": ("wrote " + HOME_ROOT + "someone/x.txt now", "text", "wrote [path] now", True),
    "text of 600 characters": (LONG_TEXT, "text", LONG_TEXT[:512], True),
    "path of 600 characters": ("a/" * 300, "text", ("a/" * 300)[:512], True),
    "path with a double dot": ("docs/../x.md", "text", "docs/../x.md", False),
    "path with a space": ("docs/my file.md", "text", "docs/my file.md", False),
    "two lines of text": ("line one\nline two", "text", "line one\nline two", False),
    "url with a bracketed host left open": ("https://[::1/x", "text", "https://[::1/x", False),
    "url with a bad port": ("https://host.test:zz/x", "text", "https://host.test:zz/x", False),
    "control: clean relative path": ("docs/reports/summary.md", "repo_path", "docs/reports/summary.md", False),
    "control: clean url": ("https://example.test/docs/page", "url", "https://example.test/docs/page", False),
    "control: clean text": ("Reviewed and approved", "text", "Reviewed and approved", False),
    "an empty reference": ("", "text", "", False),
}


def evidence_problems(env: Env, label: str) -> list[str]:
    stored, kind, value, redacted = EVIDENCE_TABLE[label]
    probe = Probe(env)
    repo = env.fresh()
    write_op(repo, 1, closed={"evidence": stored})
    served = probe.call(repo).body["items"][0]["evidence"]
    probe.expect(served == {"kind": kind, "value": value, "redacted": redacted}, f"{label}: served {served!r}")
    return probe.problems


def row10_problems(env: Env) -> list[str]:
    problems: list[str] = []
    for label in EVIDENCE_TABLE:
        problems += [f"{label}: {problem}" for problem in evidence_problems(env, label)]
    probe = Probe(env)
    repo = env.fresh()
    write_op(repo, 1, closed={})
    write_op(repo, 2, closed={"evidence": None})
    write_op(repo, 3)
    out = probe.call(repo, page_size=200)
    probe.expect(
        [item["evidence"] for item in out.body["items"]] == [None, None, None], "a record with no evidence_ref, or an open Op, has evidence that is not null"
    )
    return [*problems, *probe.problems]


def tokens() -> dict[str, str]:
    """One token per ``SECRET_PATTERNS`` kind, assembled at run time so this source holds none."""
    return {
        "classic token": "gh" + "p_" + "A" * 36,
        "fine-grained token": "github_" + "pat_" + "B" * 40,
        "access key id": "AK" + "IA" + "C" * 16,
        "private key header": "-" * 5 + "BEGIN " + "RSA PRIVATE" + " KEY" + "-" * 5,
    }


def shapes_of(token: str) -> dict[str, str]:
    return {
        "url query": "https://example.test/x?t=" + token,
        "userinfo": "https://" + token + AT + "example.test/x",
        "absolute path": "/opt/" + token + "/x",
        "free text": "see " + token + " here",
        "bare relative path": "docs/" + token + ".md",
    }


def credential_problems(env: Env, kind: str, shape: str) -> list[str]:
    token = tokens()[kind]
    stored = shapes_of(token)[shape]
    probe = Probe(env)
    repo = env.fresh()
    base = {"mission": ulid(50), "wp": "WP03", "actor": "claude"}
    write_op(repo, 1, started_at=at_minute(1), closed={"evidence": stored}, mission=base["mission"], wp=base["wp"])
    out = probe.call(repo)
    probe.expect(ids(out) == [ulid(1)] and out.skipped_ids == (), "the Op with a credential in its evidence is dropped, skipped or fails the read")
    expected = item_of(1, started_at=at_minute(1), closed={}, mission=base["mission"], wp=base["wp"], evidence=None)
    probe.expect(out.body["items"] == [expected], "the Op is not served intact with null evidence")
    probe.expect(token not in json.dumps(out.body), "the credential is in the payload")
    clean = shapes_of("harmless")[shape]
    twin = env.fresh()
    write_op(twin, 1, started_at=at_minute(1), closed={"evidence": clean}, mission=base["mission"], wp=base["wp"])
    twin_evidence = probe.call(twin).body["items"][0]["evidence"]
    probe.expect(twin_evidence is not None and twin_evidence["value"] != "", f"control: the clean twin of the {shape} shape is withheld")
    return probe.problems


HANDLE_FIELDS = ("profile", "action")


def near_miss(kind: str) -> str:
    """A value one character short of the ``SECRET_PATTERNS`` kind, so it matches none: the clean twin of a token in a handle."""
    return {
        "classic token": "gh" + "p_" + "A" * 35,
        "fine-grained token": "github_" + "pat_" + "B" * 39,
        "access key id": "AK" + "IA" + "C" * 15,
        "private key header": "harmless",
    }[kind]


def handle_credential_problems(env: Env, field: str, kind: str) -> list[str]:
    """Operator ruling at WP08: a credential-shaped profile or action skips the record (a field defect), never served, never nulled."""
    token = tokens()[kind]
    probe = Probe(env)
    repo = env.fresh()
    write_op(repo, 1, started_at=at_minute(1), **{field: token})
    write_op(repo, 2, started_at=at_minute(2), closed={"evidence": "docs/a.md"})
    out = probe.call(repo, page_size=200)
    probe.expect(ids(out) == [ulid(2)], f"the Op with a credential in its {field} is served")
    probe.expect(out.skip_reasons == {ulid(1): ops.SKIP_FIELD} and out.body["skippedCount"] == 1, f"the {field} credential record is not skipped as a field defect")
    probe.expect(out.body["totalCount"] == 1, f"totalCount counts the skipped {field} record")
    probe.expect(token not in json.dumps(out.body), f"the credential in the {field} is in the payload")
    probe.expect(len(out.body["items"]) == 1 and out.body["items"][0]["actor"] == "claude", f"the neighbour of the {field} plant lost its actor")
    twin = env.fresh()
    write_op(twin, 1, started_at=at_minute(1), **{field: near_miss(kind)})
    served = probe.call(twin)
    probe.expect(ids(served) == [ulid(1)] and served.body["skippedCount"] == 0, f"control: the clean twin of the {kind} in the {field} is skipped or dropped")
    return probe.problems


def actor_credential_problems(env: Env, kind: str) -> list[str]:
    """Operator ruling after the pre-merge squad: a credential-shaped actor is served as null, and the Op stays in items and in totalCount."""
    token = tokens()[kind]
    probe = Probe(env)
    repo = env.fresh()
    write_op(repo, 1, started_at=at_minute(1), actor=token)
    write_op(repo, 2, started_at=at_minute(2), closed={"evidence": "docs/a.md"})
    out = probe.call(repo, page_size=200)
    probe.expect(ids(out) == [ulid(2), ulid(1)], "the Op with a credential in its actor is skipped, dropped or reordered")
    probe.expect(out.body["skippedCount"] == 0 and out.skipped_ids == (), "the actor credential record is counted as skipped")
    probe.expect(out.body["totalCount"] == 2, "totalCount leaves out the Op with an actor credential")
    probe.expect(token not in json.dumps(out.body), "the credential in the actor is in the payload")
    by_id = {item["invocationId"]: item for item in out.body["items"]}
    probe.expect(by_id.get(ulid(1), {}).get("actor", "absent") is None, "the actor credential is not served as null")
    probe.expect(by_id.get(ulid(2), {}).get("actor") == "claude", "the neighbour of the actor plant lost its actor")
    twin = env.fresh()
    write_op(twin, 1, started_at=at_minute(1), actor=near_miss(kind))
    served = probe.call(twin)
    probe.expect(
        ids(served) == [ulid(1)] and served.body["skippedCount"] == 0 and served.body["items"][0]["actor"] == near_miss(kind),
        f"control: the clean twin of the {kind} in the actor is skipped, dropped or nulled",
    )
    return probe.problems


def row11_handles_problems(env: Env) -> list[str]:
    problems = [f"{field} / {kind}: {problem}" for field in HANDLE_FIELDS for kind in tokens() for problem in handle_credential_problems(env, field, kind)]
    return [*problems, *(f"actor / {kind}: {problem}" for kind in tokens() for problem in actor_credential_problems(env, kind))]


def row11_problems(env: Env) -> list[str]:
    problems: list[str] = []
    for kind in tokens():
        for shape in shapes_of("x"):
            problems += [f"{kind} in {shape}: {problem}" for problem in credential_problems(env, kind, shape)]
    probe = Probe(env)
    repo = env.fresh()
    write_op(repo, 1)
    write_spine(repo, [completed_event(1, evidence="see " + tokens()["classic token"])])
    out = probe.call(repo)
    probe.expect(
        out.body["items"][0]["status"] == "closed" and out.body["items"][0]["evidence"] is None,
        "a credential in a spine record's evidence is served or drops the Op",
    )
    return [*problems, *probe.problems]


# ---------------------------------------------------------------------------
# AC-OPS 12 and 13: actor shape, fields left out
# ---------------------------------------------------------------------------


def row12_problems(env: Env) -> list[str]:
    probe = Probe(env)
    repo = env.fresh()
    shaped = {"an e-mail-shaped actor": "someone" + AT + "example.test", "an actor with a space": "two words", "an actor of 129 characters": "a" * 129}
    for offset, (label, actor) in enumerate(shaped.items(), start=1):
        write_op(repo, offset, actor=actor, started_at=at_minute(offset), closed={})
        out = probe.call(repo, page_size=200)
        found = [item for item in out.body["items"] if item["invocationId"] == ulid(offset)]
        probe.expect(
            len(found) == 1 and found[0] == item_of(offset, actor=None, started_at=at_minute(offset), closed={}),
            f"{label} is dropped, kept, or changes another field",
        )
    probe.expect(probe.call(repo).body["skippedCount"] == 0, "an actor that fails its shape skips the record")
    keep = env.fresh()
    for offset, actor in enumerate(("claude", "codex:v2", "a" * 128), start=1):
        write_op(keep, offset, actor=actor, started_at=at_minute(offset))
    probe.expect(
        [item["actor"] for item in probe.call(keep, page_size=200).body["items"]] == ["a" * 128, "codex:v2", "claude"],
        "control: a handle-shaped actor lost its value",
    )
    return probe.problems


def description_lacks(description: str, names: Sequence[str]) -> list[str]:
    return [name for name in names if name not in description]


def row13_problems(env: Env) -> list[str]:
    probe = Probe(env)
    repo = env.fresh()
    write_op(repo, 1, closed={})
    served = probe.call(repo).body["items"][0]
    probe.expect(not set(FIVE_LEFT_OUT) & set(served), "a field left out on purpose is served")
    probe.expect(set(served) == set(item_of(1)), "the served members are not exactly the thirteen of the schema")
    probe.expect(len(served) == 13, "OpsInvocation has not 13 members")
    for name in FIVE_LEFT_OUT:
        planted = {**served, name: "value"}
        probe.expect(env.errors("OpsInvocation", planted) != [], f"the closed schema accepts a payload carrying {name}")
    probe.expect(env.errors("OpsInvocation", served) == [], "control: the real item fails its schema")
    description = yaml.safe_load((MODULE_DIR / "schemas" / "OpsInvocation.yaml").read_text(encoding="utf-8"))["description"]
    probe.expect(description_lacks(description, FIVE_LEFT_OUT) == [], "the real description lacks a name of a left-out field")
    for name in FIVE_LEFT_OUT:
        probe.expect(description_lacks(description.replace(name, "x"), FIVE_LEFT_OUT) == [name], f"a description lacking {name} is not reported")
    return probe.problems


# ---------------------------------------------------------------------------
# AC-OPS 14: read-only, no agent, linear redaction (timed, cold, minimum of repeats)
# ---------------------------------------------------------------------------


def writer_stubs(patch: pytest.MonkeyPatch) -> list[str]:
    """Every writing function of the invocation package replaced by one that raises; the names patched."""

    def raiser(*arguments: Any, **options: Any) -> None:
        raise UnexpectedWrite("a writer was called")

    names = [name for name in dir(InvocationWriter) if name.startswith(("write", "append", "_append", "_write"))]
    for name in names:
        patch.setattr(InvocationWriter, name, raiser)
    patch.setattr("specify_cli.invocation.writer.append_op_closure", raiser)
    patch.setattr(subprocess.Popen, "__init__", raiser)
    for name in ("write_bytes", "write_text", "mkdir", "unlink", "rename", "touch"):
        patch.setattr(Path, name, raiser)
    return names


def row14_writers_problems(env: Env) -> list[str]:
    probe = Probe(env)
    repo = env.fresh()
    write_op(repo, 1, closed={})
    write_op(repo, 2)
    write_index(repo, [1, 2])
    write_spine(repo, [completed_event(2)])
    with pytest.MonkeyPatch.context() as patch:
        names = writer_stubs(patch)
        probe.expect({"write_started", "write_completed", "_append_to_index"} <= set(names), "the writer stubs do not cover the writing methods")
        try:
            InvocationWriter(repo / OPS).write_started(OpStartedEvent.model_validate(started_event(9)))
            probe.problems.append("control: a patched writer did not raise, so the probe cannot see a write")
        except UnexpectedWrite:
            pass
        try:
            append_op_closure(repo, None)  # type: ignore[arg-type]
            probe.problems.append("control: the patched spine writer did not raise")
        except UnexpectedWrite:
            pass
        out = probe.call(repo, page_size=200)
    probe.expect(out.status == 200 and len(ids(out)) == 2, "the read under raising writers did not serve the two Ops")
    return probe.problems


@dataclass
class Timing:
    """The repeats of one timed shape: every duration, and whether every repeat opened files (cold)."""

    seconds: list[float]
    cold: bool

    @property
    def minimum(self) -> float:
        return min(self.seconds)


def timed(tools: helper.ContractTools, repo: Path, *, repeats: int = REPEATS, expect_opens: int = 1, **kwargs: Any) -> Timing:
    """The entry point called ``repeats`` times on the same input, each with a fresh seam; cold only if every repeat opened at least ``expect_opens`` files."""
    seconds: list[float] = []
    cold = True
    for _ in range(repeats):
        counted = Counted()
        started = time.perf_counter()
        outcome = ops.list_ops(repo, tools=tools, fs=counted.fs(), **kwargs)
        seconds.append(time.perf_counter() - started)
        cold = cold and len(counted.paths_opened) >= expect_opens and outcome.status == 200
    return Timing(seconds, cold)


SHAPES: dict[str, Callable[[int], str]] = {
    "no whitespace": lambda size: "a" * size,
    "repeated address starts": lambda size: ("a" + AT) * (size // 2),
    "repeated host path roots": lambda size: "see " + (HOME_ROOT + "a ") * (size // 8),
}


TIMING_LINES: list[str] = []
TIMING_PROPERTY = "timing_margin"


def report_timing(label: str, timing: Timing, bound: float) -> None:
    """Print the minimum of the timed repeats and its margin to ``bound``, so a CI log shows how close a run came (plan D-P16)."""
    TIMING_LINES.append(f"{label}: minimum {timing.minimum:.4f} s of {REPEATS} cold repeats, margin {bound / max(timing.minimum, 1e-9):.1f}x to {bound} s")


@pytest.fixture(autouse=True)
def record_timing_lines(request: pytest.FixtureRequest, record_property: Callable[[str, object], None]) -> Iterator[None]:
    """Record the margin lines of a test as properties; the conftest prints them in the terminal summary, which survives xdist and a passing run."""
    TIMING_LINES.clear()
    yield
    for line in [] if "mutation" in request.node.name else TIMING_LINES:  # a mutant's timings are meant to fail the bound
        record_property(TIMING_PROPERTY, line)
    TIMING_LINES.clear()


def timing_problems(env: Env, size: int, *, shapes: Sequence[str] = tuple(SHAPES)) -> list[str]:
    """The three shapes at ``size`` against the redaction bound, each with the short control timed the same way, each cold."""
    probe = Probe(env)
    control_repo = env.fresh()
    write_op(control_repo, 1, closed={"evidence": "a short value with " + AT + " in it"})
    control = timed(env.tools, control_repo)
    report_timing("redaction control (short value)", control, REDACTION_BOUND)
    probe.expect(control.cold, "control: a repeat of the short value did not read the file (a cache hit)")
    probe.expect(control.minimum <= REDACTION_BOUND, f"control: short value min of {REPEATS} = {control.minimum:.4f} s > {REDACTION_BOUND} s")
    for name in shapes:
        repo = env.fresh()
        write_op(repo, 1, closed={"evidence": SHAPES[name](size)})
        timing = timed(env.tools, repo)
        report_timing(f"redaction {name} at {size}", timing, REDACTION_BOUND)
        probe.expect(timing.cold, f"{name}: a repeat did not read the file, so its time is a cache hit")
        probe.expect(timing.minimum <= REDACTION_BOUND, f"{name}: min of {REPEATS} = {timing.minimum:.4f} s > {REDACTION_BOUND} s")
    return probe.problems


def row14_problems(env: Env) -> list[str]:
    return [*row14_writers_problems(env), *timing_problems(env, BIG)]


def row14_small_problems(env: Env) -> list[str]:
    """The timed shapes at a size where the planted quadratic form is still decisive and the mutation run stays short."""
    return timing_problems(env, SMALL)


# ---------------------------------------------------------------------------
# AC-CROSS 1 and 4 (fixture-built halves)
# ---------------------------------------------------------------------------


def cross1_problems(env: Env) -> list[str]:
    probe = Probe(env)
    repo = env.fresh()
    for number in range(1, 8):
        write_op(repo, number, started_at=at_minute(number), closed={} if number % 2 else None)
    write_index(repo, [1, 2, 3, 4, 5, 6, 7])
    first = probe.call(repo, page_size=3)
    second = probe.call(repo, page_size=3)
    probe.expect(json.dumps(first.body, sort_keys=True) == json.dumps(second.body, sort_keys=True), "two reads of an unchanged tree are not byte-equal")
    cursor = first.body["pageInfo"]["nextPageCursor"]
    probe.expect(cursor is not None and cursor == second.body["pageInfo"]["nextPageCursor"], "two reads give different cursors")
    later_one = probe.call(repo, page_size=3, cursor=cursor)
    later_two = probe.call(repo, page_size=3, cursor=cursor)
    probe.expect(json.dumps(later_one.body, sort_keys=True) == json.dumps(later_two.body, sort_keys=True), "two reads of a later page are not byte-equal")
    write_op(repo, 8, started_at=at_minute(30))
    probe.expect(
        probe.call(repo, page_size=3).body != first.body or ids(probe.call(repo, page_size=3)) == ids(first), "control: the probe cannot see a changed tree"
    )
    return probe.problems


def cross4_problems(env: Env) -> list[str]:
    """Bounded reads: only the index, the spine and the Op files are opened, each Op file once; no process is started."""
    probe = Probe(env)
    repo = env.fresh()
    for number in range(1, 11):
        write_op(repo, number, started_at=at_minute(number), closed={} if number % 2 else None)
    write_file(repo, "lifecycle.jsonl", [started_event(30)])
    write_spine(repo, [completed_event(2)])
    ops_dir(repo).joinpath("evidence").mkdir()
    counted = Counted()
    with memo_module.counting_subprocesses() as processes:
        out = with_fs(probe, repo, counted)
    allowed = {repo / OPS / ops.INDEX_NAME, repo / OPS / ops.SPINE_NAME} | {repo / OPS / f"{ulid(n)}.jsonl" for n in range(1, 11)}
    probe.expect(out.body["totalCount"] == 10, "control: the fixture has not 10 served Ops")
    probe.expect(set(counted.paths_opened) <= allowed, "a file other than the index, the spine and the Op files was opened")
    probe.expect(
        sorted(path.name for path in counted.paths_opened if path.name.endswith(".jsonl") and path.name not in {ops.INDEX_NAME, ops.SPINE_NAME})
        == sorted(f"{ulid(n)}.jsonl" for n in range(1, 11)),
        "an Op file was opened not exactly once",
    )
    probe.expect(len(counted.paths_scanned) == 1, "the directory was not listed exactly once")
    probe.expect(processes.started == 0, "the reader started a process")
    with memo_module.counting_subprocesses() as control:
        subprocess.run(["git", "--version"], check=True, capture_output=True)
    probe.expect(control.started == 1, "control: the process counter cannot see a process")
    return probe.problems


def write_many(repo: Path, count: int) -> None:
    """``count`` Op files without an index, written fast: one ``started`` line each, instants cycling through an hour."""
    directory = ops_dir(repo)
    for number in range(1, count + 1):
        (directory / f"{ulid(number)}.jsonl").write_bytes(encode([started_event(number, started_at=at_minute(number % 60))]))


def listing_problems(env: Env) -> list[str]:
    """AC-CROSS 4, fixture-built: a directory of 10,000 Op files and no index, listed within the bound as the minimum of cold repeats, with a small control."""
    probe = Probe(env)
    small = env.fresh()
    write_many(small, 10)
    control = timed(env.tools, small, expect_opens=10)
    probe.expect(control.cold, "control: a repeat on the small directory did not read its files (a cache hit)")
    probe.expect(control.minimum <= LISTING_BOUND, f"control: small directory min of {REPEATS} = {control.minimum:.3f} s > {LISTING_BOUND} s")
    big = env.fresh()
    write_many(big, FILE_COUNT)
    counted = Counted()
    out = ops.list_ops(big, tools=env.tools, fs=counted.fs())
    probe.expect(
        out.status == 200 and out.body["totalCount"] == FILE_COUNT and out.body["skippedCount"] == 0, "the 10,000-file directory is not served and counted in full"
    )
    probe.expect(len(out.body["items"]) == ops.DEFAULT_PAGE_SIZE, "the first page of the 10,000-file directory is not one page")
    opened = [path.name for path in counted.paths_opened if path.name not in {ops.INDEX_NAME, ops.SPINE_NAME}]
    probe.expect(len(opened) == FILE_COUNT == len(set(opened)), "an Op file of the 10,000-file directory was not opened exactly once")
    probe.expect(len(counted.paths_scanned) == 1, "the 10,000-file directory was not listed exactly once")
    timing = timed(env.tools, big, expect_opens=FILE_COUNT)
    report_timing(f"listing {FILE_COUNT} files", timing, LISTING_BOUND)
    probe.expect(timing.cold, "a repeat on the 10,000-file directory did not read every file, so its time is a cache hit")
    probe.expect(timing.minimum <= LISTING_BOUND, f"10,000 files: min of {REPEATS} = {timing.minimum:.3f} s > {LISTING_BOUND} s")
    return probe.problems


# ---------------------------------------------------------------------------
# The rows
# ---------------------------------------------------------------------------

ROWS: dict[str, Callable[[Env], list[str]]] = {
    "row1": row1_problems,
    "row2": row2_problems,
    "row3": row3_problems,
    "row4": row4_problems,
    "row5": row5_problems,
    "row6": row6_problems,
    "row6_instant": row6_instant_problems,
    "row7": row7_problems,
    "row8": row8_problems,
    "row9": row9_problems,
    "row10": row10_problems,
    "row11": row11_problems,
    "row11_handles": row11_handles_problems,
    "row12": row12_problems,
    "row13": row13_problems,
    "row14": row14_problems,
    "row14_writers": row14_writers_problems,
    "row14_small": row14_small_problems,
    "cross1": cross1_problems,
    "cross4": cross4_problems,
    "listing": listing_problems,
}
SLOW_ROWS = {"row14", "row14_small", "listing"}


@pytest.mark.parametrize("row", sorted(set(ROWS) - SLOW_ROWS))
def test_the_ops_rows_hold(row: str, env: Env) -> None:
    assert ROWS[row](env) == []


@pytest.mark.parametrize("label", sorted(EVIDENCE_TABLE))
def test_each_evidence_class_is_served_as_the_table_says(label: str, env: Env) -> None:
    assert evidence_problems(env, label) == []


@pytest.mark.parametrize("shape", sorted(shapes_of("x")))
@pytest.mark.parametrize("kind", sorted(tokens()))
def test_a_credential_withholds_the_evidence_and_nothing_else(kind: str, shape: str, env: Env) -> None:
    assert credential_problems(env, kind, shape) == []


@pytest.mark.parametrize("kind", sorted(tokens()))
@pytest.mark.parametrize("field", HANDLE_FIELDS)
def test_a_credential_in_a_handle_skips_the_record(field: str, kind: str, env: Env) -> None:
    assert handle_credential_problems(env, field, kind) == []


@pytest.mark.parametrize("kind", sorted(tokens()))
def test_a_credential_in_the_actor_is_served_as_null_and_the_op_is_kept(kind: str, env: Env) -> None:
    assert actor_credential_problems(env, kind) == []


# ---------------------------------------------------------------------------
# The timed cases (D-P16): the minimum of cold repeats, each shape with its short control
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_a_256_kib_value_is_redacted_in_under_a_tenth_of_a_second(shape: str, env: Env) -> None:
    assert timing_problems(env, BIG, shapes=(shape,)) == []


def test_the_writers_raise_and_the_read_still_serves(env: Env) -> None:
    assert row14_writers_problems(env) == []


def test_ten_thousand_files_are_listed_within_the_bound(env: Env) -> None:
    assert listing_problems(env) == []


def test_the_timing_probe_sees_a_slow_call_and_a_cache_hit(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    """The probe is itself probed: a call that sleeps exceeds the bound, and a memoised call is reported as not cold."""
    repo = env.fresh()
    write_op(repo, 1, closed={"evidence": "short"})
    real = ops.list_ops

    def slow(*arguments: Any, **options: Any) -> ops.OpsOutcome:
        time.sleep(REDACTION_BOUND * 1.5)
        return real(*arguments, **options)

    monkeypatch.setattr(ops, "list_ops", slow)
    assert timed(env.tools, repo, repeats=2).minimum > REDACTION_BOUND
    monkeypatch.undo()
    memo: dict[Path, ops.OpsOutcome] = {}

    def cached(repo_root: Path, **options: Any) -> ops.OpsOutcome:
        if repo_root not in memo:
            memo[repo_root] = real(repo_root, **options)
        return memo[repo_root]

    monkeypatch.setattr(ops, "list_ops", cached)
    assert timed(env.tools, repo, repeats=3).cold is False


def test_the_repeat_count_is_at_least_five() -> None:
    assert REPEATS >= 5


# ---------------------------------------------------------------------------
# The mutations (proof kind M)
# ---------------------------------------------------------------------------

# The e-mail pattern as it stood before it was made linear-time (the same text as in the leak-pattern tests).
QUADRATIC_EMAIL = re.compile(
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+"
    r"|(?<![\w.%+/@-])[A-Za-z0-9._%+-]+@[A-Za-z][A-Za-z-]*(?![\w@-]|\.[A-Za-z0-9])"
)


def _ascending_order(patch: pytest.MonkeyPatch, env: Env) -> None:
    patch.setattr(ops, "order_ops", lambda served: sorted(served, key=lambda op: (op.micros, op.item["invocationId"])))


def _index_profile_filters(patch: pytest.MonkeyPatch, env: Env) -> None:
    real = ops.candidates_of
    profiles: dict[str, str] = {}

    def candidates(fs: ops.FileSystem, directory: Path) -> list[str]:
        profiles.clear()
        try:
            data = fs.open_binary(directory / ops.INDEX_NAME)
        except OSError:
            data = b""
        for raw in data.split(b"\n"):
            try:
                entry = json.loads(raw.decode("utf-8"))
            except (ValueError, RecursionError):
                continue
            if isinstance(entry, dict) and isinstance(entry.get("profile_id"), str):
                profiles[str(entry.get("invocation_id"))] = entry["profile_id"]
        return real(fs, directory)

    patch.setattr(ops, "candidates_of", candidates)
    patch.setattr(ops, "matches_profile", lambda op, profile: profile is None or profiles.get(op.item["invocationId"], op.profile) == profile)


def _cli_closure_gap(patch: pytest.MonkeyPatch, env: Env) -> None:
    patch.setattr(ops, "closure_of", lambda own, spine: own.completion)


def _drop_skipped_from_count(patch: pytest.MonkeyPatch, env: Env) -> None:
    real = ops.page_counts
    patch.setattr(ops, "page_counts", lambda served, skipped, profile: (real(served, skipped, profile)[0], 0))


def _count_follows_filter(patch: pytest.MonkeyPatch, env: Env) -> None:
    real = ops.page_counts
    patch.setattr(ops, "page_counts", lambda served, skipped, profile: (real(served, skipped, profile)[0], len(skipped) if profile is None else 0))


def _total_includes_skipped(patch: pytest.MonkeyPatch, env: Env) -> None:
    real = ops.page_counts
    patch.setattr(ops, "page_counts", lambda served, skipped, profile: (real(served, skipped, profile)[0] + len(skipped), len(skipped)))


def _redact_before_the_credential_check(patch: pytest.MonkeyPatch, env: Env) -> None:
    def defective(stored: str | None, tools: helper.ContractTools) -> dict[str, Any] | None:
        if stored is None:
            return None
        built = ops.classify_evidence(stored, tools)
        return None if ops.holds_credential(built["value"], tools) else built

    patch.setattr(ops, "evidence_of", defective)


def _mask_the_credential(patch: pytest.MonkeyPatch, env: Env) -> None:
    def defective(stored: str | None, tools: helper.ContractTools) -> dict[str, Any] | None:
        if stored is None:
            return None
        if ops.holds_credential(stored, tools):
            masked = stored
            for pattern in tools.leak.SECRET_PATTERNS:
                masked = pattern.sub("[credential]", masked)
            return {"kind": "text", "value": masked, "redacted": True}
        return ops.classify_evidence(stored, tools)

    patch.setattr(ops, "evidence_of", defective)


def _skip_url_userinfo(patch: pytest.MonkeyPatch, env: Env) -> None:
    patch.setattr(ops, "strip_url", lambda stored: stored)


def _skip_the_host_path_class(patch: pytest.MonkeyPatch, env: Env) -> None:
    patch.setattr(ops, "is_host_path", lambda value: False)


def _eager_500_on_legacy(patch: pytest.MonkeyPatch, env: Env) -> None:
    def defective(reason: str) -> ops.Skipped:
        raise ops.OpsUnreadable(reason)

    patch.setattr(ops, "skip", defective)


def _empty_on_oserror(patch: pytest.MonkeyPatch, env: Env) -> None:
    patch.setattr(ops, "unreadable_outcome", lambda: ops.OpsOutcome(200, ops.empty_page(ops.DEFAULT_PAGE_SIZE)))


def _quadratic_redaction(patch: pytest.MonkeyPatch, env: Env) -> None:
    def redact(text: str, token: str) -> tuple[str, int]:
        return QUADRATIC_EMAIL.sub(token, text), len(QUADRATIC_EMAIL.findall(text))

    patch.setattr(env.tools.leak, "redact_emails", redact)


def _cache_the_result(patch: pytest.MonkeyPatch, env: Env) -> None:
    real = ops.list_ops
    memo: dict[tuple[Path, str | None, int, str | None], ops.OpsOutcome] = {}

    def cached(
        repo_root: Path,
        *,
        tools: helper.ContractTools,
        profile: str | None = None,
        page_size: int = 50,
        cursor: str | None = None,
        fs: ops.FileSystem = ops.REAL_FS,
    ) -> ops.OpsOutcome:
        key = (repo_root, profile, page_size, cursor)
        if key not in memo:
            memo[key] = real(repo_root, tools=tools, profile=profile, page_size=page_size, cursor=cursor, fs=fs)
        return memo[key]

    patch.setattr(ops, "list_ops", cached)


def _cursor_without_a_digest(patch: pytest.MonkeyPatch, env: Env) -> None:
    patch.setattr(ops, "cursor_digest", lambda profile, micros, invocation_id: "constant")


def _ignore_a_bad_spine_instant(patch: pytest.MonkeyPatch, env: Env) -> None:
    original = ops.read_spine

    def without_bad_instants(fs: Any, directory: Path) -> dict[str, Any]:
        return {key: value for key, value in original(fs, directory).items() if ops.instant_micros(value.completed_at) is not None}

    patch.setattr(ops, "read_spine", without_bad_instants)


def _serve_a_credential_handle(patch: pytest.MonkeyPatch, env: Env) -> None:
    patch.setattr(ops, "handle_holds_credential", lambda started, tools: False)


def _serve_a_credential_actor(patch: pytest.MonkeyPatch, env: Env) -> None:
    patch.setattr(ops, "actor_of", lambda stored, tools: stored if ops._HANDLE.fullmatch(stored) else None)


MUTATIONS: dict[str, tuple[Callable[[pytest.MonkeyPatch, Env], None], tuple[str, ...]]] = {
    "ascending-order": (_ascending_order, ("row1", "row2")),
    "index-profile-filters": (_index_profile_filters, ("row5",)),
    "cli-closure-gap": (_cli_closure_gap, ("row6",)),
    "drop-skipped-record-from-count": (_drop_skipped_from_count, ("row3", "row4")),
    "count-follows-filter": (_count_follows_filter, ("row4",)),
    "total-includes-skipped": (_total_includes_skipped, ("row3",)),
    "redact-before-credential-check": (_redact_before_the_credential_check, ("row11",)),
    "mask-credential": (_mask_the_credential, ("row11",)),
    "skip-url-userinfo": (_skip_url_userinfo, ("row10",)),
    "skip-host-path-class": (_skip_the_host_path_class, ("row10",)),
    "eager-500-on-legacy": (_eager_500_on_legacy, ("row8",)),
    "empty-on-oserror": (_empty_on_oserror, ("row9",)),
    "quadratic-redaction": (_quadratic_redaction, ("row14_small",)),
    "cache-the-result": (_cache_the_result, ("row14_small", "listing")),
    "cursor-without-digest": (_cursor_without_a_digest, ("row2",)),
    "bad-spine-instant-served-open": (_ignore_a_bad_spine_instant, ("row6_instant",)),
    "credential-handle-served": (_serve_a_credential_handle, ("row11_handles",)),
    "credential-actor-served": (_serve_a_credential_actor, ("row11_handles",)),
}
CATALOGUE_NAMES = {
    "ascending-order",
    "index-profile-filters",
    "cli-closure-gap",
    "drop-skipped-record-from-count",
    "count-follows-filter",
    "redact-before-credential-check",
    "mask-credential",
    "skip-url-userinfo",
    "eager-500-on-legacy",
    "empty-on-oserror",
    "quadratic-redaction",
    "cache-the-result",
    "credential-handle-served",
}


# The mutations whose intended kill is a raise (the reader is forbidden to write, spawn or fail): a crash of the mutant itself is no kill for any other.
CRASH_KILLS: frozenset[str] = frozenset()


def _problems_or_raised(row: Callable[[Env], list[str]], env: Env) -> list[str]:
    try:
        return row(env)
    except Exception as error:  # a mutant may crash the read: that is a red row, not an error of the test
        return [f"raised {type(error).__name__}: {error}"]


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_every_reader_mutation_turns_its_rows_red(name: str, env: Env) -> None:
    apply, rows = MUTATIONS[name]
    for row in rows:
        assert ROWS[row](env) == [], f"control: row {row} is not clean before the mutation"
    with pytest.MonkeyPatch.context() as patch:
        apply(patch, env)
        problems = [problem for row in rows for problem in _problems_or_raised(ROWS[row], env)]
    kills = problems if name in CRASH_KILLS else [problem for problem in problems if not problem.startswith("raised ")]
    detail = " (no problem line)" if not problems else "" if kills else f" (killed only by its own crash: {problems[0]})"
    assert kills, f"{NOT_KILLED}: {name}{detail}"


def test_the_mutation_table_holds_the_whole_catalogue_and_names_only_known_rows_and_functions() -> None:
    assert set(MUTATIONS) >= CATALOGUE_NAMES
    assert len(MUTATIONS) == 18
    assert all(row in ROWS for _, rows in MUTATIONS.values() for row in rows)
    assert {"order_ops", "candidates_of", "matches_profile", "closure_of", "page_counts", "evidence_of", "strip_url", "is_host_path", "skip"} <= set(dir(ops))
    assert {"unreadable_outcome", "list_ops", "cursor_digest", "classify_evidence", "holds_credential"} <= set(dir(ops))


# ---------------------------------------------------------------------------
# Direct tests of the helpers
# ---------------------------------------------------------------------------

MICROS = 1_000_000


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1970-01-01T00:00:00Z", 0),
        ("1970-01-01T00:00:01Z", MICROS),
        ("1970-01-01T01:00:00+01:00", 0),
        ("1969-12-31T23:00:00-01:00", 0),
        ("1970-01-01T00:00:00.5Z", MICROS // 2),
        ("1970-01-01T00:00:00.123456789Z", 123_456),
        ("1970-01-01t00:00:00z", 0),
        ("2026-10-01T10:00:00+00:00", 1_790_848_800 * MICROS),
    ],
)
def test_a_valid_instant_is_whole_microseconds_since_the_epoch(text: str, expected: int) -> None:
    assert ops.instant_micros(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "2026-10-01",
        "2026-10-01T10:00:00",
        "2026-10-01 10:00:00Z",
        "2026-10-01T10:00Z",
        "2026-13-01T10:00:00Z",
        "2026-02-30T10:00:00Z",
        "2026-10-01T24:00:00Z",
        "2026-06-30T23:59:60Z",
        "2026-10-01T10:00:00+24:00",
        "2026-10-01T10:00:00+01:60",
        "2026-10-01T10:00:00+0100",
        "0000-01-01T00:00:00Z",
        "２０２６-10-01T10:00:00Z",
        "2026-10-01T10:00:00Z\n",
    ],
)
def test_a_text_that_is_not_an_rfc_3339_instant_with_an_offset_is_refused(text: str) -> None:
    assert ops.instant_micros(text) is None


def test_the_extreme_instants_do_not_overflow() -> None:
    low = ops.instant_micros("0001-01-01T00:00:00+23:59")
    high = ops.instant_micros("9999-12-31T23:59:59-23:59")
    assert low is not None and high is not None and low < 0 < high


@pytest.mark.parametrize(
    ("stored", "expected"),
    [
        ("claude", "claude"),
        ("codex:v2", "codex:v2"),
        ("a.b_c-d", "a.b_c-d"),
        ("a" * 128, "a" * 128),
        ("a" * 129, None),
        ("", None),
        ("two words", None),
        ("a" + AT + "b.test", None),
        ("x\n", None),
    ],
)
def test_an_actor_is_a_handle_or_null(stored: str, expected: str | None, tools: helper.ContractTools) -> None:
    assert ops.actor_of(stored, tools) == expected


@pytest.mark.parametrize("kind", sorted(tokens()))
def test_an_actor_holding_a_credential_is_null(kind: str, tools: helper.ContractTools) -> None:
    assert ops.actor_of(tokens()[kind], tools) is None
    assert ops.actor_of(near_miss(kind), tools) == near_miss(kind)


@pytest.mark.parametrize(
    ("run", "expected"),
    [
        ("https://u:p" + AT + "h.test/a?q=1#f", "https://h.test/a"),
        ("https://h.test", "https://h.test"),
        ("https://h.test?q=1", "https://h.test"),
        ("https://h.test#f", "https://h.test"),
        ("https://a" + AT + "b" + AT + "h.test/x", "https://h.test/x"),
        ("https://h.test/a" + AT + "b", "https://h.test/a" + AT + "b"),
    ],
)
def test_a_run_loses_its_userinfo_query_and_fragment(run: str, expected: str) -> None:
    assert ops.strip_run(run) == expected


@pytest.mark.parametrize(
    ("value", "start", "expected"),
    [
        ("see https://u:p" + AT + "h.test/a?q=1 and ssh://k" + AT + "g.test/r#f ok.", 0, "see https://h.test/a and ssh://g.test/r ok."),
        ("no address here", 0, "no address here"),
        ("a://u" + AT + "h/x", 0, "a://u" + AT + "h/x"),
        ("x1http://u:p" + AT + "h.test/a?q", 0, "x1http://h.test/a"),
        ("https://h.test/a?q=1 https://u:p" + AT + "h2.test/b?q=2", 21, "https://h.test/a?q=1 https://h2.test/b"),
        ("://u" + AT + "h", 0, "://u" + AT + "h"),
    ],
)
def test_every_embedded_address_run_is_stripped_from_the_start_on(value: str, start: int, expected: str) -> None:
    assert ops.embedded_runs_stripped(value, start) == expected


def test_a_value_with_many_marks_and_long_scheme_runs_is_scanned_in_linear_time(env: Env) -> None:
    for value in ("a" * BIG + "://", ("a" * 5 + "://") * (BIG // 8), "1" * BIG + "://x", ("x://" + "b" * 3 + " ") * (BIG // 8)):
        started = time.perf_counter()
        ops.embedded_runs_stripped(value, 0)
        assert time.perf_counter() - started <= REDACTION_BOUND


def test_a_url_that_the_parser_refuses_is_not_a_url() -> None:
    assert ops.url_parses("https://host.test/a") is True
    assert ops.url_parses("https://host.test:8080/a") is True
    assert ops.url_parses("https://[::1/x") is False
    assert ops.url_parses("https://host.test:zz/x") is False
    assert ops.url_parses("https://host.test:99999/x") is False


def test_the_started_record_is_served_or_left_out_field_by_field() -> None:
    served = {"invocation_id", "profile_id", "action", "actor", "mode_of_work", "started_at", "mission_id", "wp_id"}
    assert set(OpStartedEvent.model_fields) == served | set(FIVE_LEFT_OUT) | {"event"}


def test_the_cursor_round_trips_only_for_its_own_filter() -> None:
    served = ops.ServedOp(item_of(5), 1_790_848_800 * MICROS, "python-pedro")
    token = ops.keyset_cursor("profile-a", served)
    assert ops.cursor_position(token, "profile-a") == (served.micros, ulid(5))
    assert ops.cursor_position(token, "profile-b") is None
    assert ops.cursor_position(token, None) is None
    assert ops.cursor_position("", "profile-a") is None
    assert ops.cursor_position(token + "!", "profile-a") is None
    assert ops.cursor_position(token[:8] + "!!!!" + token[8:], "profile-a") is None
    assert ops.cursor_position(ops.keyset_cursor(None, served), None) == (served.micros, ulid(5))


# ---------------------------------------------------------------------------
# The reader's own source: no write path, no private import
# ---------------------------------------------------------------------------

WRITING_NAMES = {"materialize", "InvocationWriter", "append_op_closure", "write_started", "write_completed", "append_to_index"}


def forbidden_in(source: str) -> list[str]:
    """What a reader source must not contain: an import of the writing module, a private name imported from the product or its tests, a writing name."""
    found: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            if node.module.endswith("invocation.writer"):
                found.append(f"imports {node.module}")
            found += [
                f"imports the private name {alias.name} from {node.module}"
                for alias in node.names
                if alias.name.startswith("_") and not node.module.startswith("tests.contract._")
            ]
        elif isinstance(node, ast.Import):
            found += [f"imports {alias.name}" for alias in node.names if alias.name.endswith("invocation.writer")]
        names = {node.id} if isinstance(node, ast.Name) else {node.attr} if isinstance(node, ast.Attribute) else set()
        found += [f"uses {name}" for name in sorted(names & WRITING_NAMES)]
    return found


def test_the_reader_has_no_write_path_and_no_private_import() -> None:
    reader = READER_FILE.read_text(encoding="utf-8")
    assert forbidden_in(reader) == []
    assert forbidden_in("from specify_cli.invocation.writer import InvocationWriter\n") == ["imports specify_cli.invocation.writer"]
    assert forbidden_in("from specify_cli.invocation.writer import read_op_closures\n") == ["imports specify_cli.invocation.writer"]
    assert forbidden_in("from specify_cli.status.reducer import _private\n") == ["imports the private name _private from specify_cli.status.reducer"]
    assert forbidden_in("reducer.materialize(path)\n") == ["uses materialize"]
    assert forbidden_in("from tests.contract._mission_status_payloads import is_wp_id\n") == []
    assert len(reader.splitlines()) > 100


def test_the_new_modules_hold_no_raw_nul_byte() -> None:
    for path in (READER_FILE, Path(__file__)):
        assert b"\x00" not in path.read_bytes()
