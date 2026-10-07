"""The reference Ops reader of the ``mission-status`` contract (plan D-P1, D-P16; spec FR-016 to FR-021).

``list_ops`` is the production entry point of the reference reader for ``GET /ops/invocations``. It returns an ``OpsOutcome``
(an HTTP status and a body), and a refusal is an outcome, never an exception. It reads and never writes: it opens only the index
(``kitty-ops/ops-index.jsonl``), the closure spine (``kitty-ops/op-closures.jsonl``) and the Op files it names, through the
file-system seam, and it starts no process of its own. It never imports the writing side of the invocation package.

The order of decision per record is the one of the data model. A record that is legacy or unreadable is skipped and counted, an
absent file is skipped and counted, and everything that stops the read from knowing the truth (a directory that cannot be
listed, an Op file or the spine that cannot be opened, a spine that is not UTF-8) is a 500, never an empty or partial page. The
evidence of a closure goes through one pipeline whose first step is the credential check on the stored value: a credential is
withheld, never masked, and redaction runs only after that check.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

from kernel.clock import datetime, timedelta
from specify_cli.invocation.errors import LegacyRecordError
from specify_cli.invocation.record import OpCompletedEvent, OpStartedEvent, parse_op_event
from tests.contract._mission_status_payloads import ContractTools, is_wp_id

OPS_DIRECTORY = "kitty-ops"
INDEX_NAME = "ops-index.jsonl"
SPINE_NAME = "op-closures.jsonl"
OK = 200
BAD_REQUEST = 400
UNREADABLE = 500
CODE_BAD_CURSOR = "invalid_page_cursor"
CODE_UNREADABLE = "ops_unreadable"
DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 200
MAX_EVIDENCE = 512
PATH_TOKEN = "[path]"
EMAIL_TOKEN = "[email]"
KIND_REPO_PATH = "repo_path"
KIND_URL = "url"
KIND_TEXT = "text"
STATUS_OPEN = "open"
STATUS_CLOSED = "closed"
CURSOR_VERSION = 1

_ULID = re.compile(r"[0-9A-HJKMNP-TV-Z]{26}")
_OP_FILE = re.compile(r"([0-9A-HJKMNP-TV-Z]{26})\.jsonl")
_PROFILE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}")
_HANDLE = re.compile(r"[A-Za-z0-9._:-]{1,128}")
_INSTANT = re.compile(r"(\d{4})-(\d{2})-(\d{2})[Tt](\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,9}))?([Zz]|[+-]\d{2}:\d{2})", re.ASCII)
_URL_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]+://")
_SCHEME_CHARACTERS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+.-")
_DRIVE = re.compile(r"[A-Za-z]:")
_FILE_URL = re.compile(r"file://", re.IGNORECASE)
_WHITESPACE = re.compile(r"\s")
_EPOCH = datetime(1970, 1, 1)
_MICROSECOND = timedelta(microseconds=1)
_CURSOR_ALPHABET = re.compile(r"[A-Za-z0-9_-]+")

# Skip reasons: why a candidate is counted in ``skippedCount`` (the tests assert the reason, so a plant is never skipped for the wrong one).
SKIP_ABSENT = "absent_file"
SKIP_EMPTY = "empty_file"
SKIP_NOT_JSON = "first_line_not_json"
SKIP_NOT_STARTED = "first_line_not_a_started_event"
SKIP_LEGACY = "legacy_started"
SKIP_STEM = "stem_differs_from_invocation_id"
SKIP_INSTANT = "instant_not_rfc3339_with_offset"
SKIP_FIELD = "field_fails_its_shape"
SKIP_UTF8 = "invalid_utf8"
SKIP_LEGACY_COMPLETION = "legacy_completion_without_spine_record"
SKIP_CLOSURE_INSTANT = "closure_instant_not_rfc3339_with_offset"

BAD_CURSOR = (BAD_REQUEST, "The page cursor was refused", "The pageCursor is malformed, forged or no longer valid.")
BAD_REQUEST_PROBLEMS: dict[str, tuple[int, str, str]] = {
    "profile": (BAD_REQUEST, "The profile is not a profile identifier", "The profile must fit the pattern of a profile identifier."),
    "page_size": (BAD_REQUEST, "The pageSize is out of range", "The pageSize must be an integer from 1 to 200."),
}
UNREADABLE_PROBLEM = (
    UNREADABLE,
    "The Ops directory could not be read",
    "The Ops directory or the closure spine exists but could not be read, so no page is returned.",
)


class OpsUnreadable(Exception):
    """A read the page cannot do its job without: the whole read is refused 500, never partly answered (FR-019)."""


# ---------------------------------------------------------------------------
# The file-system seam and the outcome
# ---------------------------------------------------------------------------


def _list_names(path: Path) -> list[str]:
    with os.scandir(path) as entries:
        return [entry.name for entry in entries]


@dataclass(frozen=True)
class FileSystem:
    """The three calls the reader makes on the files it owns. A test replaces one with a fault or a counter; none of them writes."""

    stat: Callable[[Path], os.stat_result]
    scandir: Callable[[Path], list[str]]
    open_binary: Callable[[Path], bytes]


REAL_FS = FileSystem(stat=os.stat, scandir=_list_names, open_binary=Path.read_bytes)


@dataclass(frozen=True)
class OpsOutcome:
    """What the operation answers, and what the reader's result carries beside it (FR-019, FR-025).

    ``skipped_ids`` names the candidates counted in ``skippedCount`` and ``skip_reasons`` says why each one was skipped.
    """

    status: int
    body: dict[str, Any]
    skipped_ids: tuple[str, ...] = ()
    skip_reasons: Mapping[str, str] = field(default_factory=dict)


def problem(status: int, title: str, detail: str, code: str | None = None) -> OpsOutcome:
    body: dict[str, Any] = {"type": "about:blank", "title": title, "status": status}
    if code is not None:
        body["code"] = code
    body["detail"] = detail
    return OpsOutcome(status, body)


def bad_request(name: str) -> OpsOutcome:
    """The 400 of a ``profile`` or ``pageSize`` that fails its schema (the shared ``Problem`` of ``default``, no code)."""
    return problem(*BAD_REQUEST_PROBLEMS[name])


def bad_cursor() -> OpsOutcome:
    """The 400 ``invalid_page_cursor`` of the existing ``PageCursorRefusal``."""
    return problem(*BAD_CURSOR, code=CODE_BAD_CURSOR)


def unreadable_outcome() -> OpsOutcome:
    """The 500 ``ops_unreadable`` refusal: no host path, no directory and no record content in the body."""
    return problem(*UNREADABLE_PROBLEM, code=CODE_UNREADABLE)


# ---------------------------------------------------------------------------
# Instants (AD-9) and the shape of a field
# ---------------------------------------------------------------------------


def instant_micros(text: str) -> int | None:
    """The instant of an RFC 3339 date-time with an offset, as microseconds since the epoch, or None when ``text`` is not one.

    Whole-number arithmetic on a naive datetime, never a comparison of aware datetimes: a year-1 or year-9999 instant with an offset
    overflows ``datetime``'s own conversion, and a stored value must never raise. A leap second (``:60``) is not representable and is refused.
    """
    found = _INSTANT.fullmatch(text)
    if found is None:
        return None
    year, month, day, hour, minute, second, fraction, offset = found.groups()
    try:
        naive = datetime(int(year), int(month), int(day), int(hour), int(minute), int(second), int((fraction or "0").ljust(9, "0")[:6]))
    except ValueError:
        return None
    shift = 0
    if offset not in {"Z", "z"}:
        offset_hours, offset_minutes = int(offset[1:3]), int(offset[4:6])
        if offset_hours > 23 or offset_minutes > 59:
            return None
        shift = (offset_hours * 60 + offset_minutes) * (-1 if offset[0] == "-" else 1)
    return (naive - _EPOCH) // _MICROSECOND - shift * 60_000_000


def ulid_or_none(value: Any) -> bool:
    return isinstance(value, str) and _ULID.fullmatch(value) is not None


def actor_of(stored: str) -> str | None:
    """``ActorHandle``: the stored value when it is a handle, else null (the one field of an Op that degrades instead of skipping the record)."""
    return stored if _HANDLE.fullmatch(stored) else None


# ---------------------------------------------------------------------------
# The evidence pipeline (FR-020): one place for each rule
# ---------------------------------------------------------------------------


def holds_credential(stored: str, tools: ContractTools) -> bool:
    """Step 0: whether the stored value matches one of the ``SECRET_PATTERNS`` kinds, in any shape."""
    return any(pattern.search(stored) for pattern in tools.leak.SECRET_PATTERNS)


def is_host_path(value: str) -> bool:
    """Step 1(c): a value that begins with a slash, ``~/``, two backslashes, or a drive letter and a colon."""
    return value.startswith(("/", "~/", chr(92) * 2)) or _DRIVE.match(value) is not None


def is_repo_path_candidate(value: str, tools: ContractTools) -> bool:
    """Step 1(d): one line, no whitespace, and accepted by the artifact-path rule."""
    return _WHITESPACE.search(value) is None and tools.scan.malformed_artifact_path(value) is None


def strip_run(run: str) -> str:
    """One ``scheme://`` run without its userinfo, query and fragment (a run holds no whitespace)."""
    head, _, rest = run.partition("://")
    ends = [position for position in (rest.find(mark) for mark in "/?#") if position >= 0]
    boundary = min(ends) if ends else len(rest)
    authority, tail = rest[:boundary], rest[boundary:]
    cuts = [position for position in (tail.find(mark) for mark in "?#") if position >= 0]
    if cuts:
        tail = tail[: min(cuts)]
    return head + "://" + authority.rpartition("@")[2] + tail


def leading_run_end(value: str) -> int:
    """The end of the first whitespace-free run of ``value``."""
    found = _WHITESPACE.search(value)
    return found.start() if found else len(value)


def strip_url(stored: str) -> str:
    """Step 1(b): the leading address of ``stored`` without its userinfo, query and fragment; the rest of the value is kept."""
    end = leading_run_end(stored)
    return strip_run(stored[:end]) + stored[end:]


def url_parses(value: str) -> bool:
    """Whether the leading address of ``value`` is a URL the standard parser accepts (a bad bracketed host or a bad port is not)."""
    try:
        _port = urlsplit(value[: leading_run_end(value)]).port
    except ValueError:
        return False
    return True


def embedded_runs_stripped(value: str, start: int) -> str:
    """Every ``scheme://`` run of ``value`` from ``start`` on, without its userinfo, query and fragment (linear: one pass over the ``://`` marks)."""
    parts: list[str] = []
    cursor = start
    search_from = start
    while True:
        mark = value.find("://", search_from)
        if mark < 0:
            break
        begin = mark
        while begin > cursor and value[begin - 1] in _SCHEME_CHARACTERS:
            begin -= 1
        while begin < mark and not (value[begin].isascii() and value[begin].isalpha()):
            begin += 1
        if mark - begin < 2:
            search_from = mark + 3
            continue
        end = mark
        while end < len(value) and _WHITESPACE.match(value, end) is None:
            end += 1
        parts.append(value[cursor:begin])
        parts.append(strip_run(value[begin:end]))
        cursor = end
        search_from = end
    parts.append(value[cursor:])
    return value[:start] + "".join(parts)


def host_paths_replaced(value: str, tools: ContractTools) -> str:
    """Each human host-path run replaced by ``[path]``, widened to the end of the run as the v1 projector does."""
    for pattern in tools.leak.HUMAN_HOST_PATH_PATTERNS:
        value = re.compile(pattern.pattern + r"\S*", pattern.flags).sub(PATH_TOKEN, value)
    return value


def redact_value(value: str, tools: ContractTools, start: int) -> str:
    """Step 2: embedded addresses, host paths and e-mail addresses removed from ``value`` (``start`` skips an address step 1 already handled)."""
    value = embedded_runs_stripped(value, start)
    value = host_paths_replaced(value, tools)
    return str(tools.leak.redact_emails(value, EMAIL_TOKEN)[0])


def classify_evidence(stored: str, tools: ContractTools) -> dict[str, Any]:
    """Steps 1 to 3 on a stored value that holds no credential: the closed ``{kind, value, redacted}`` object."""
    if _FILE_URL.match(stored):
        return {"kind": KIND_TEXT, "value": PATH_TOKEN, "redacted": True}
    kind, value, start = KIND_TEXT, stored, 0
    if _URL_SCHEME.match(stored):
        value = strip_url(stored)
        kind, start = (KIND_URL, leading_run_end(value)) if url_parses(value) else (KIND_TEXT, 0)
    elif is_host_path(stored):
        return {"kind": KIND_TEXT, "value": PATH_TOKEN, "redacted": True}
    elif is_repo_path_candidate(stored, tools):
        kind = KIND_REPO_PATH
    before_redaction = value
    value = redact_value(value, tools, start)
    if kind == KIND_REPO_PATH and value != before_redaction:
        kind = KIND_TEXT
    if len(value) > MAX_EVIDENCE:
        value, kind = value[:MAX_EVIDENCE], KIND_TEXT
    return {"kind": kind, "value": value, "redacted": value != stored}


def evidence_of(stored: str | None, tools: ContractTools) -> dict[str, Any] | None:
    """The served evidence of a closure: null without a reference, null when it holds a credential (checked on the stored value first), else the pipeline."""
    if stored is None or holds_credential(stored, tools):
        return None
    return classify_evidence(stored, tools)


# ---------------------------------------------------------------------------
# One Op file
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Skipped:
    """A candidate that is legacy or unreadable, and the reason."""

    reason: str


def skip(reason: str) -> Skipped:
    """The one place a record is skipped for its shape (the 'legacy is a failure' mutation replaces it)."""
    return Skipped(reason)


@dataclass(frozen=True)
class Closure:
    """The completion that closes an Op, from its own file or from the spine."""

    outcome: str
    closed_by: str
    completed_at: str
    evidence_ref: str | None


@dataclass(frozen=True)
class OwnFile:
    """What the Op's own file says: its started event, and its first completion (a closure, the legacy marker, or nothing)."""

    started: OpStartedEvent
    started_micros: int
    completion: Closure | None
    legacy_completion: bool


@dataclass(frozen=True)
class ServedOp:
    """One served Op: the payload, its position in the order and the profile of its own started event."""

    item: dict[str, Any]
    micros: int
    profile: str


def parse_line(line: str) -> OpStartedEvent | OpCompletedEvent | None:
    """A v2 event of one JSON line, or None for a line that is not JSON, not an object, not an event or of the legacy shape."""
    try:
        data = json.loads(line)
    except (ValueError, RecursionError):
        return None
    if not isinstance(data, dict):
        return None
    try:
        return parse_op_event(data)
    except (ValueError, LegacyRecordError):
        return None


def is_valid_completion_shape(event: OpCompletedEvent) -> bool:
    return instant_micros(event.completed_at) is not None


def handle_holds_credential(started: OpStartedEvent, tools: ContractTools) -> bool:
    """Whether ``profile_id``, ``action`` or ``actor`` holds a ``SECRET_PATTERNS`` credential, checked on the stored values (operator ruling at WP08)."""
    return any(holds_credential(value, tools) for value in (started.profile_id, started.action, started.actor))


def read_own_file(invocation_id: str, data: bytes, tools: ContractTools) -> OwnFile | Skipped:
    """The started event and the first completion of one Op file, or the reason the record is skipped."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return skip(SKIP_UTF8)
    lines = text.split("\n")
    if not lines[0].strip():
        return skip(SKIP_EMPTY)
    try:
        first = json.loads(lines[0])
    except (ValueError, RecursionError):
        return skip(SKIP_NOT_JSON)
    if not isinstance(first, dict) or first.get("event") != "started":
        return skip(SKIP_NOT_STARTED)
    try:
        started = cast(OpStartedEvent, parse_op_event(first))
    except LegacyRecordError:
        return skip(SKIP_LEGACY)
    if started.invocation_id != invocation_id:
        return skip(SKIP_STEM)
    micros = instant_micros(started.started_at)
    if micros is None:
        return skip(SKIP_INSTANT)
    if _PROFILE.fullmatch(started.profile_id) is None or _PROFILE.fullmatch(started.action) is None:
        return skip(SKIP_FIELD)
    if handle_holds_credential(started, tools):
        return skip(SKIP_FIELD)
    if started.mission_id is not None and not ulid_or_none(started.mission_id):
        return skip(SKIP_FIELD)
    if started.wp_id is not None and not is_wp_id(started.wp_id):
        return skip(SKIP_FIELD)
    completion, legacy = own_completion(invocation_id, lines[1:])
    if isinstance(completion, Skipped):
        return completion
    return OwnFile(started, micros, completion, legacy)


def own_completion(invocation_id: str, lines: list[str]) -> tuple[Closure | Skipped | None, bool]:
    """The first completion line of an Op's own file: a closure, a skip (its instant is not RFC 3339), or the legacy marker."""
    for line in lines:
        try:
            data = json.loads(line)
        except (ValueError, RecursionError):
            continue
        if not isinstance(data, dict) or data.get("event") != "completed" or data.get("invocation_id") != invocation_id:
            continue
        try:
            event = cast(OpCompletedEvent, parse_op_event(data))
        except LegacyRecordError:
            return None, True
        if not is_valid_completion_shape(event):
            return skip(SKIP_INSTANT), False
        return closure_of_event(event), False
    return None, False


def closure_of_event(event: OpCompletedEvent) -> Closure:
    return Closure(event.outcome, event.closed_by, event.completed_at, event.evidence_ref)


def closure_of(own: OwnFile, spine: Mapping[str, Closure]) -> Closure | Skipped | None:
    """The closure of an Op (OR-5): its own completion wins, else the first spine record.

    A closing record whose instant is not RFC 3339 skips the Op (operator ruling at WP08), whichever source it is from; a legacy own
    completion with no spine record skips the Op.
    """
    if own.completion is not None:
        return own.completion
    from_spine = spine.get(own.started.invocation_id)
    if from_spine is not None:
        return from_spine if instant_micros(from_spine.completed_at) is not None else skip(SKIP_CLOSURE_INSTANT)
    return skip(SKIP_LEGACY_COMPLETION) if own.legacy_completion else None


def served_op(own: OwnFile, closure: Closure | None, tools: ContractTools) -> ServedOp:
    """The payload of one Op (FR-017); ``request_text``, ``model_id`` and the routing fields never leave the reader."""
    started = own.started
    item: dict[str, Any] = {
        "invocationId": started.invocation_id,
        "profileId": started.profile_id,
        "action": started.action,
        "actor": actor_of(started.actor),
        "modeOfWork": started.mode_of_work,
        "startedAt": started.started_at,
        "missionId": started.mission_id,
        "wpId": started.wp_id,
        "status": STATUS_CLOSED if closure else STATUS_OPEN,
        "outcome": closure.outcome if closure else None,
        "closedBy": closure.closed_by if closure else None,
        "completedAt": closure.completed_at if closure else None,
        "evidence": evidence_of(closure.evidence_ref, tools) if closure else None,
    }
    return ServedOp(item, own.started_micros, started.profile_id)


def invariant_problems(item: Mapping[str, Any]) -> list[str]:
    """The open and closed invariants of FR-017, which the closed schema cannot express: an open Op has no outcome, closer, completion or evidence."""
    problems: list[str] = []
    if item.get("status") == STATUS_OPEN:
        problems += [f"an open Op carries {name}" for name in ("outcome", "closedBy", "completedAt", "evidence") if item.get(name) is not None]
    elif item.get("status") == STATUS_CLOSED:
        problems += [f"a closed Op lacks {name}" for name in ("outcome", "closedBy", "completedAt") if item.get(name) is None]
    else:
        problems.append("the status is neither open nor closed")
    return problems


# ---------------------------------------------------------------------------
# The directory: candidates, spine, order and cursor
# ---------------------------------------------------------------------------


def index_candidates(fs: FileSystem, ops_dir: Path) -> list[str] | None:
    """The distinct invocation ids of the index in file order, or None when the index is absent or cannot be opened (the directory is read instead).

    A line that is not valid UTF-8, not JSON, not an object or whose ``invocation_id`` is not a ULID is skipped without being counted: it names no candidate.
    """
    try:
        data = fs.open_binary(ops_dir / INDEX_NAME)
    except OSError:
        return None
    found: dict[str, None] = {}
    for raw in data.split(b"\n"):
        try:
            entry = json.loads(raw.decode("utf-8"))
        except (ValueError, RecursionError):
            continue
        if isinstance(entry, dict) and ulid_or_none(entry.get("invocation_id")):
            found.setdefault(entry["invocation_id"], None)
    return list(found)


def directory_candidates(fs: FileSystem, ops_dir: Path) -> list[str]:
    """The ids of the Op files of the directory (a 26-character ULID and ``.jsonl``); the index, the spine and every other file are not records."""
    try:
        names = fs.scandir(ops_dir)
    except OSError as error:
        raise OpsUnreadable("the Ops directory cannot be listed") from error
    return [found.group(1) for found in map(_OP_FILE.fullmatch, names) if found is not None]


def candidates_of(fs: FileSystem, ops_dir: Path) -> list[str]:
    """One candidate set for items, ``totalCount`` and ``skippedCount`` (FR-018): the index when it can be opened, else the directory. Sorted, distinct."""
    from_index = index_candidates(fs, ops_dir)
    return sorted(from_index if from_index is not None else set(directory_candidates(fs, ops_dir)))


def read_spine(fs: FileSystem, ops_dir: Path) -> dict[str, Closure]:
    """The first closure record per invocation id, in file order, whatever its instant (``closure_of`` judges it).

    A corrupt or legacy line is skipped; an unreadable or non-UTF-8 spine is a 500.
    """
    try:
        data = fs.open_binary(ops_dir / SPINE_NAME)
    except FileNotFoundError:
        return {}
    except OSError as error:
        raise OpsUnreadable("the closure spine cannot be read") from error
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise OpsUnreadable("the closure spine is not valid UTF-8") from error
    records: dict[str, Closure] = {}
    for line in text.split("\n"):
        event = parse_line(line)
        if isinstance(event, OpCompletedEvent):
            records.setdefault(event.invocation_id, closure_of_event(event))
    return records


def order_ops(served: list[ServedOp]) -> list[ServedOp]:
    """Newest first as instants, ties by invocation id descending (a total key)."""
    return sorted(served, key=lambda op: (op.micros, op.item["invocationId"]), reverse=True)


def matches_profile(op: ServedOp, profile: str | None) -> bool:
    """The filter uses the profile of the Op's own started event, never the index line's."""
    return profile is None or op.profile == profile


def cursor_digest(profile: str | None, micros: int, invocation_id: str) -> str:
    """A short digest of the cursor's content, so a token edited by hand no longer matches (integrity, not secrecy)."""
    return hashlib.blake2b(f"{CURSOR_VERSION}|{profile}|{micros}|{invocation_id}".encode(), digest_size=8).hexdigest()


def keyset_cursor(profile: str | None, op: ServedOp) -> str:
    """The opaque cursor after ``op``: its position and a digest of the position and the filter (an edited or re-used token no longer matches)."""
    invocation_id = op.item["invocationId"]
    payload = {"v": CURSOR_VERSION, "t": op.micros, "i": invocation_id, "d": cursor_digest(profile, op.micros, invocation_id)}
    return base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")


def cursor_position(token: str, profile: str | None) -> tuple[int, str] | None:
    """The position of a cursor issued for ``profile``, or None when it is malformed, forged or issued for another filter."""
    if _CURSOR_ALPHABET.fullmatch(token) is None:
        return None
    padded = token + "=" * (-len(token) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(padded))
    except (ValueError, RecursionError):
        return None
    if not isinstance(payload, dict) or payload.get("v") != CURSOR_VERSION:
        return None
    micros, invocation_id = payload.get("t"), payload.get("i")
    if not isinstance(micros, int) or not ulid_or_none(invocation_id):
        return None
    if payload.get("d") != cursor_digest(profile, micros, str(invocation_id)):
        return None
    return micros, str(invocation_id)


def page_counts(served: list[ServedOp], skipped: Mapping[str, str], profile: str | None) -> tuple[int, int]:
    """``totalCount`` (served Ops matching the filter) and ``skippedCount`` (over the candidate set, whatever the filter)."""
    return sum(1 for op in served if matches_profile(op, profile)), len(skipped)


# ---------------------------------------------------------------------------
# The entry point
# ---------------------------------------------------------------------------


def read_candidates(fs: FileSystem, ops_dir: Path, ids: list[str], spine: Mapping[str, Closure], tools: ContractTools) -> tuple[list[ServedOp], dict[str, str]]:
    """Every candidate read once: the served Ops and the skipped ids with their reasons. An ``OSError`` other than a vanished file raises ``OpsUnreadable``."""
    served: list[ServedOp] = []
    skipped: dict[str, str] = {}
    for invocation_id in ids:
        try:
            data = fs.open_binary(ops_dir / f"{invocation_id}.jsonl")
        except FileNotFoundError:
            skipped[invocation_id] = SKIP_ABSENT
            continue
        except OSError as error:
            raise OpsUnreadable("an Op file cannot be read") from error
        own = read_own_file(invocation_id, data, tools)
        closure = closure_of(own, spine) if isinstance(own, OwnFile) else own
        if isinstance(own, Skipped):
            skipped[invocation_id] = own.reason
        elif isinstance(closure, Skipped):
            skipped[invocation_id] = closure.reason
        else:
            served.append(served_op(own, closure, tools))
    return served, skipped


def list_ops(
    repo_root: Path,
    *,
    tools: ContractTools,
    profile: str | None = None,
    page_size: int = DEFAULT_PAGE_SIZE,
    cursor: str | None = None,
    fs: FileSystem = REAL_FS,
) -> OpsOutcome:
    """``GET /ops/invocations``: one page of the Op invocations of ``repo_root``, newest first. Never raises for a refusal; never writes; starts no process."""
    if profile is not None and _PROFILE.fullmatch(profile) is None:
        return bad_request("profile")
    if isinstance(page_size, bool) or not isinstance(page_size, int) or not 1 <= page_size <= MAX_PAGE_SIZE:
        return bad_request("page_size")
    after: tuple[int, str] | None = None
    if cursor is not None:
        after = cursor_position(cursor, profile)
        if after is None:
            return bad_cursor()
    ops_dir = repo_root / OPS_DIRECTORY
    try:
        outcome = _list_ops(fs, ops_dir, tools, profile, page_size, after)
    except OpsUnreadable:
        return unreadable_outcome()
    return outcome


def _list_ops(fs: FileSystem, ops_dir: Path, tools: ContractTools, profile: str | None, page_size: int, after: tuple[int, str] | None) -> OpsOutcome:
    try:
        fs.stat(ops_dir)
    except FileNotFoundError:
        return OpsOutcome(OK, empty_page(page_size))
    except OSError as error:
        raise OpsUnreadable("the Ops directory cannot be examined") from error
    ids = candidates_of(fs, ops_dir)
    spine = read_spine(fs, ops_dir)
    served, skipped = read_candidates(fs, ops_dir, ids, spine, tools)
    matching = order_ops([op for op in served if matches_profile(op, profile)])
    total, skipped_count = page_counts(served, skipped, profile)
    remaining = matching if after is None else [op for op in matching if (op.micros, op.item["invocationId"]) < after]
    page, more = remaining[:page_size], len(remaining) > page_size
    body = {
        "items": [op.item for op in page],
        "pageInfo": {"hasNextPage": more, "nextPageCursor": keyset_cursor(profile, page[-1]) if more else None, "pageSize": page_size},
        "totalCount": total,
        "skippedCount": skipped_count,
    }
    return OpsOutcome(OK, body, tuple(sorted(skipped)), dict(skipped))


def empty_page(page_size: int) -> dict[str, Any]:
    """No ``kitty-ops/``: a 200 with no Op, both counts 0 and no next page."""
    return {"items": [], "pageInfo": {"hasNextPage": False, "nextPageCursor": None, "pageSize": page_size}, "totalCount": 0, "skippedCount": 0}
