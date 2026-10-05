"""Test-side reference reader of the Mission artifacts (FR-009 to FR-014, FR-016, FR-020, FR-022).

The executable form of the rules written in the ``mission-status`` contract for ``listArtifacts`` and
``getArtifactContent``: what an artifact is (eligibility), how it is classed, how a content read decides
between 200 and each refusal, what redaction does and how a listing is walked. Nothing here is a test and
nothing here writes: the module opens, scans and stats through one injectable ``FileSystem`` value, so a
fault or a counting wrapper replaces exactly one call, and it never imports the writing ``materialize``.

Every entry point returns an ``ArtifactOutcome`` (a status and a body); a refusal is an outcome, never an
exception. The listing and the content read run the same single function over a file (``read_file``), so the
``readable`` flag of a listing entry cannot drift from the status of the content read; the independent
oracle that does not trust this equality lives in the reality module.

The Mission directory is the primary planning surface: ``MissionSource.own_dir`` of the projector helper,
that is ``kitty-specs/<mission>`` under the repository root checkout, never the coordination-aware read
directory (ledger SK-310). It is recomputed here without reading a snapshot, and a test pins the equality.
"""

from __future__ import annotations

import json
import math
import os
import re
import stat
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO, Protocol

from kernel.clock import UTC_SECOND_TIMESTAMP_FORMAT, format_stamp, from_epoch
from tests.contract._mission_status_payloads import ContractTools

# ---------------------------------------------------------------------------
# Constants: vocabularies, caps, refusal codes
# ---------------------------------------------------------------------------

ARTIFACT_KINDS: tuple[str, ...] = (
    "review_cycle",
    "work_package_prompt",
    "spec",
    "plan",
    "tasks",
    "data_model",
    "quickstart",
    "analysis_report",
    "research",
    "contract",
    "checklist",
    "other",
)
MAX_CONTENT_BYTES = 262_144
MAX_LISTING_ENTRIES = 1000
MAX_PATH_LENGTH = 512  # the maxLength of ArtifactPath: a longer path is never eligible, so the listing walk does not go below it
ROOT_STATUS_FILES = frozenset({"status.events.jsonl", "status.json"})
ROOT_KIND_FILES = {
    "spec.md": "spec",
    "plan.md": "plan",
    "tasks.md": "tasks",
    "data-model.md": "data_model",
    "quickstart.md": "quickstart",
    "analysis-report.md": "analysis_report",
}
MEDIA_TYPES = {
    "md": "text/markdown",
    "json": "application/json",
    "yaml": "application/yaml",
    "yml": "application/yaml",
    "jsonl": "application/x-ndjson",
    "csv": "text/csv",
}
DEFAULT_MEDIA_TYPE = "text/plain"
ENCODING = "utf-8"
PATH_TOKEN = "[path]"
EMAIL_TOKEN = "[email]"

INVALID_ARTIFACT_PATH = "invalid_artifact_path"
NOT_FOUND = "not_found"
ARTIFACT_TOO_LARGE = "artifact_too_large"
ARTIFACT_NOT_TEXT = "artifact_not_text"
ARTIFACT_SECRET = "artifact_secret"
ARTIFACT_UNREADABLE = "artifact_unreadable"
ARTIFACT_LISTING_UNREADABLE = "artifact_listing_unreadable"
# code -> (status, title, detail); the detail never repeats the requested path, a Mission directory or any content.
REFUSALS: dict[str, tuple[int, str, str]] = {
    INVALID_ARTIFACT_PATH: (400, "The artifact path was refused", "The path is not a relative path of forward-slash segments."),
    NOT_FOUND: (404, "The artifact was not found", "No eligible artifact has this path in the Mission."),
    ARTIFACT_TOO_LARGE: (413, "The artifact is too large", f"The file is larger than {MAX_CONTENT_BYTES} bytes."),
    ARTIFACT_NOT_TEXT: (415, "The artifact is not text", "The file holds a NUL byte or is not valid UTF-8."),
    ARTIFACT_SECRET: (422, "The artifact holds a credential", "The file holds a credential, so its content is not served."),
    ARTIFACT_UNREADABLE: (500, "The artifact could not be read", "The file could not be read."),
    ARTIFACT_LISTING_UNREADABLE: (500, "The artifacts could not be listed", "The Mission directory could not be listed."),
}
OK = 200

_MISSION_ID = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")
_REVIEW_CYCLE_NAME = re.compile(r"^review-cycle-[1-9][0-9]*\.md$")
_PROMPT_NAME = re.compile(r"^WP[0-9]{2,}-[^/]*\.md$")
_TASKS = "tasks"
_ABSENT = (FileNotFoundError, NotADirectoryError)
_NUL = bytes(1)


# ---------------------------------------------------------------------------
# The file-system seam
# ---------------------------------------------------------------------------


class OpenFile(Protocol):
    """What a content read needs of an open file: the stat of the open handle, a bounded read, a close."""

    def fstat(self) -> os.stat_result: ...

    def read(self, size: int) -> bytes: ...

    def close(self) -> None: ...


class _RealFile:
    def __init__(self, handle: BinaryIO) -> None:
        self._handle = handle

    def fstat(self) -> os.stat_result:
        return os.fstat(self._handle.fileno())

    def read(self, size: int) -> bytes:
        return self._handle.read(size)

    def close(self) -> None:
        self._handle.close()


def _real_scandir(path: Path) -> list[str]:
    with os.scandir(path) as entries:
        return [entry.name for entry in entries]


def _real_open(path: Path) -> OpenFile:
    return _RealFile(path.open("rb"))


@dataclass(frozen=True)
class FileSystem:
    """The three calls the reader makes. A test replaces one with a fault or a counter; the real value is the default."""

    scandir: Callable[[Path], list[str]]
    lstat: Callable[[Path], os.stat_result]
    open_binary: Callable[[Path], OpenFile]


REAL_FS = FileSystem(scandir=_real_scandir, lstat=os.lstat, open_binary=_real_open)


@dataclass(frozen=True)
class ReaderContext:
    """The reader's explicit input: the repository root checkout, the loaded contract tools and the file system."""

    repo_root: Path
    tools: ContractTools
    fs: FileSystem = REAL_FS
    mission_dirs: Mapping[str, Path] | None = None


@dataclass(frozen=True)
class ArtifactOutcome:
    """What an operation answers: the status and the body (a payload for 200, a problem for a refusal)."""

    status: int
    body: dict[str, Any]


def refusal(code: str) -> ArtifactOutcome:
    """The problem details outcome of ``code`` (status, title and detail are fixed by the code)."""
    status, title, detail = REFUSALS[code]
    return ArtifactOutcome(status, {"type": "about:blank", "title": title, "status": status, "code": code, "detail": detail})


# ---------------------------------------------------------------------------
# Pure rules: path, classifier, media type, modified time, redaction
# ---------------------------------------------------------------------------


def malformed(tools: ContractTools, path: str) -> str | None:
    """The reason ``path`` is not an artifact path (the tooling predicate, plus a path that has no UTF-8 form), else ``None``."""
    reason: str | None = tools.scan.malformed_artifact_path(path)
    if reason is not None:
        return reason
    try:
        path.encode("utf-8")
    except UnicodeEncodeError:
        return "not_utf8"
    return None


def classify(path: str) -> str:
    """The ordered classifier of the contract: the first match wins, the file is never read."""
    segments = path.split("/")
    name = segments[-1]
    if len(segments) == 3 and segments[0] == _TASKS and _REVIEW_CYCLE_NAME.fullmatch(name):
        return "review_cycle"
    if len(segments) == 2 and segments[0] == _TASKS and _PROMPT_NAME.fullmatch(name):
        return "work_package_prompt"
    if len(segments) == 1 and name in ROOT_KIND_FILES:
        return ROOT_KIND_FILES[name]
    if path == "research.md" or (len(segments) > 1 and segments[0] == "research"):
        return "research"
    if len(segments) > 1 and segments[0] == "contracts":
        return "contract"
    if len(segments) > 1 and segments[0] == "checklists":
        return "checklist"
    return "other"


def media_type_of(path: str) -> str:
    """The media type of the file name's extension from the fixed table (case-sensitive, never sniffed)."""
    name = path.rsplit("/", 1)[-1]
    extension = name.rpartition(".")[2] if "." in name else ""
    return MEDIA_TYPES.get(extension, DEFAULT_MEDIA_TYPE)


def modified_at(st_mtime: float) -> str:
    """RFC 3339 UTC with ``Z`` and whole seconds: the modification time floored, never rounded."""
    return format_stamp(from_epoch(math.floor(st_mtime)), UTC_SECOND_TIMESTAMP_FORMAT)


def has_credential(tools: ContractTools, text: str) -> bool:
    """True when a credential pattern of ``leak_patterns`` matches ``text``."""
    return any(pattern.search(text) for pattern in tools.leak.SECRET_PATTERNS)


def _widened(patterns: Sequence[re.Pattern[str]]) -> tuple[re.Pattern[str], ...]:
    """Each host-path pattern plus the non-space characters that follow it, so the whole path is replaced."""
    return tuple(re.compile(pattern.pattern + r"\S*", pattern.flags) for pattern in patterns)


def redact(tools: ContractTools, text: str) -> tuple[str, bool]:
    """Host paths become ``[path]``, e-mail addresses ``[email]``; also whether the substitution changed the text."""
    redacted = text
    for pattern in _widened(tools.leak.HUMAN_HOST_PATH_PATTERNS):
        redacted = pattern.sub(PATH_TOKEN, redacted)
    redacted = tools.leak.redact_emails(redacted, EMAIL_TOKEN)[0]
    return redacted, redacted != text


# ---------------------------------------------------------------------------
# Mission and eligibility
# ---------------------------------------------------------------------------


def index_missions(repo_root: Path) -> dict[str, Path]:
    """Mission id to its primary-surface directory, from the ``meta.json`` of every directory under ``kitty-specs/``.

    The first directory in name order wins for an id two directories hold (a data defect the reality check reports elsewhere).
    """
    base = repo_root / "kitty-specs"
    index: dict[str, Path] = {}
    try:
        names = sorted(os.listdir(base))
    except OSError:
        return index
    for name in names:
        try:
            meta = json.loads((base / name / "meta.json").read_bytes())
        except (OSError, ValueError):
            continue
        identity = meta.get("mission_id") if isinstance(meta, dict) else None
        if isinstance(identity, str):
            index.setdefault(identity, base / name)
    return index


def resolve_mission(ctx: ReaderContext, mission_id: str) -> Path | None:
    """The primary-surface directory of the Mission with this id, or ``None`` for an unknown or ill-formed id.

    The directory is ``kitty-specs/<name>`` under the repository root checkout, the same value as ``MissionSource.own_dir``.
    A caller that reads many files passes a prebuilt ``ctx.mission_dirs``; otherwise the index is built for the call.
    """
    if not isinstance(mission_id, str) or not _MISSION_ID.fullmatch(mission_id):
        return None
    index = ctx.mission_dirs if ctx.mission_dirs is not None else index_missions(ctx.repo_root)
    return index.get(mission_id)


def is_eligible(ctx: ReaderContext, mission_dir: Path, path: str) -> bool:
    """The one eligibility rule over one path (listing, content read, ``artifactPath`` and the references all call it).

    A file is eligible when its path is not malformed, it is not the root ``status.events.jsonl`` or ``status.json`` (matched without regard to case), it
    is a regular file, and no component of the path below the Mission directory is a symlink: every component is
    lstat-ed and nothing is resolved. A missing component and a file used as a directory make it not eligible; any
    other failure of the file system is raised, so the caller answers 500 and never a wrong 404.
    """
    if malformed(ctx.tools, path) is not None or path.casefold() in ROOT_STATUS_FILES:
        return False
    segments = path.split("/")
    current = mission_dir
    for index, segment in enumerate(segments):
        current = current / segment
        try:
            mode = ctx.fs.lstat(current).st_mode
        except _ABSENT:
            return False
        if stat.S_ISLNK(mode):
            return False
        if index == len(segments) - 1:
            return stat.S_ISREG(mode)
        if not stat.S_ISDIR(mode):
            return False
    return False


# ---------------------------------------------------------------------------
# The content read: one order of decision
# ---------------------------------------------------------------------------


def read_file(ctx: ReaderContext, mission_dir: Path, path: str) -> ArtifactOutcome:
    """The single order of decision for one path below an existing Mission directory (the listing runs it per entry).

    not eligible 404; open read-only and fstat the OPEN handle; size over the cap 413 (the file is not read); read at most
    cap plus one byte; open or read failure 500; a byte past the cap 413; a NUL byte then strict UTF-8 failure 415; a
    credential 422 (no content in the body); else 200 with the redacted text.
    """
    try:
        eligible = is_eligible(ctx, mission_dir, path)
    except OSError:
        return refusal(ARTIFACT_UNREADABLE)
    if not eligible:
        return refusal(NOT_FOUND)
    try:
        handle = ctx.fs.open_binary(mission_dir / path)
    except OSError:
        return refusal(ARTIFACT_UNREADABLE)
    with closing(handle):
        try:
            size = handle.fstat().st_size
            if size > MAX_CONTENT_BYTES:
                return refusal(ARTIFACT_TOO_LARGE)
            data = handle.read(MAX_CONTENT_BYTES + 1)
        except OSError:
            return refusal(ARTIFACT_UNREADABLE)
    return _decide_bytes(ctx.tools, path, size, data)


def _decide_bytes(tools: ContractTools, path: str, size: int, data: bytes) -> ArtifactOutcome:
    if len(data) > MAX_CONTENT_BYTES:
        return refusal(ARTIFACT_TOO_LARGE)
    if _NUL in data:
        return refusal(ARTIFACT_NOT_TEXT)
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return refusal(ARTIFACT_NOT_TEXT)
    if has_credential(tools, text):
        return refusal(ARTIFACT_SECRET)
    content, changed = redact(tools, text)
    body = {
        "path": path,
        "kind": classify(path),
        "mediaType": media_type_of(path),
        "encoding": ENCODING,
        "sizeBytes": size,
        "redacted": changed,
        "content": content,
    }
    return ArtifactOutcome(OK, body)


def _mission_directory(ctx: ReaderContext, mission_id: str) -> tuple[Path | None, str | None]:
    """The Mission directory, or the refusal code: 404 for an unknown Mission, 500 when the directory cannot be statted."""
    mission_dir = resolve_mission(ctx, mission_id)
    if mission_dir is None:
        return None, NOT_FOUND
    try:
        mode = ctx.fs.lstat(mission_dir).st_mode
    except _ABSENT:
        return None, NOT_FOUND
    except OSError:
        return None, ARTIFACT_UNREADABLE
    return (mission_dir, None) if stat.S_ISDIR(mode) else (None, NOT_FOUND)


def read_content(ctx: ReaderContext, mission_id: str, paths: Sequence[str]) -> ArtifactOutcome:
    """``getArtifactContent``: 400 for a malformed, missing or repeated path, 404 for an unknown Mission, then ``read_file``.

    ``paths`` is the list of values of the ``path`` query parameter after the one decoding the HTTP layer does.
    """
    if len(paths) != 1 or malformed(ctx.tools, paths[0]) is not None:
        return refusal(INVALID_ARTIFACT_PATH)
    mission_dir, code = _mission_directory(ctx, mission_id)
    if mission_dir is None:
        return refusal(code or NOT_FOUND)
    return read_file(ctx, mission_dir, paths[0])


# ---------------------------------------------------------------------------
# The listing walk
# ---------------------------------------------------------------------------


def path_sort_key(path: str) -> bytes:
    """The one ordering of a listing: the byte order of the UTF-8 path, never the modified time and never a locale."""
    return path.encode("utf-8")


def _walk(ctx: ReaderContext, mission_dir: Path, prefix: str) -> Iterator[str]:
    """Every regular, non-symlink file below ``prefix``: lstat each name, never follow or enter a symlink.

    Iterative, with an explicit stack. A directory whose own relative path already has ``MAX_PATH_LENGTH`` characters is
    not entered, since every path below it is longer than the limit and so never eligible.
    """
    pending = [prefix]
    while pending:
        current = pending.pop()
        directory = mission_dir / current if current else mission_dir
        try:
            names = ctx.fs.scandir(directory)
        except _ABSENT:
            continue
        for name in sorted(names):
            relative = f"{current}/{name}" if current else name
            try:
                mode = ctx.fs.lstat(mission_dir / relative).st_mode
            except _ABSENT:
                continue
            if stat.S_ISDIR(mode):
                if len(relative) < MAX_PATH_LENGTH:
                    pending.append(relative)
            elif stat.S_ISREG(mode):
                yield relative


def _entry(ctx: ReaderContext, mission_dir: Path, path: str) -> dict[str, Any] | None:
    """One listing entry, or ``None`` when the file vanished; any other stat failure is raised."""
    try:
        info = ctx.fs.lstat(mission_dir / path)
    except _ABSENT:
        return None
    # a file over the cap is decided from its size alone: it is not opened
    readable = info.st_size <= MAX_CONTENT_BYTES and read_file(ctx, mission_dir, path).status == OK
    return {"path": path, "kind": classify(path), "sizeBytes": info.st_size, "modifiedAt": modified_at(info.st_mtime), "readable": readable}


def list_artifacts(ctx: ReaderContext, mission_id: str) -> ArtifactOutcome:
    """``listArtifacts``: the eligible files in byte order of the UTF-8 path, the first 1000, ``readable`` per entry."""
    mission_dir, code = _mission_directory(ctx, mission_id)
    if mission_dir is None:
        return refusal(ARTIFACT_LISTING_UNREADABLE if code == ARTIFACT_UNREADABLE else NOT_FOUND)
    try:
        found = [path for path in _walk(ctx, mission_dir, "") if is_eligible(ctx, mission_dir, path)]
        found.sort(key=path_sort_key)
        entries = [entry for path in found[:MAX_LISTING_ENTRIES] if (entry := _entry(ctx, mission_dir, path)) is not None]
    except OSError:
        return refusal(ARTIFACT_LISTING_UNREADABLE)
    return ArtifactOutcome(OK, {"missionId": mission_id, "entries": entries, "truncated": len(found) > MAX_LISTING_ENTRIES})


# ---------------------------------------------------------------------------
# Artifact references (reused by the detail reader)
# ---------------------------------------------------------------------------


def prompt_file_name(ctx: ReaderContext, mission_dir: Path, wp_id: str) -> str | None:
    """The prompt file name of a work package: the first regular, non-symlink ``WP<digits>-*.md`` whose name starts with ``<wp_id>-``.

    One read of the ``tasks/`` directory and one lstat per candidate; no file is opened.
    """
    try:
        names = sorted(ctx.fs.scandir(mission_dir / _TASKS))
    except _ABSENT:
        return None
    for name in names:
        if name.startswith(wp_id + "-") and _PROMPT_NAME.fullmatch(name) and is_eligible(ctx, mission_dir, f"{_TASKS}/{name}"):
            return name
    return None


def artifact_references(ctx: ReaderContext, mission_dir: Path, wp_id: str) -> dict[str, dict[str, str] | None]:
    """``{prompt, spec}`` pointers from the eligibility rule alone: a directory read and lstats, no walk, no content open."""
    prompt = prompt_file_name(ctx, mission_dir, wp_id)
    spec = "spec.md" if is_eligible(ctx, mission_dir, "spec.md") else None
    return {
        "prompt": None if prompt is None else {"path": f"{_TASKS}/{prompt}", "kind": "work_package_prompt"},
        "spec": None if spec is None else {"path": spec, "kind": "spec"},
    }
