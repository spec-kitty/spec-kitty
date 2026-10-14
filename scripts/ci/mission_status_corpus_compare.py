#!/usr/bin/env python3
"""Nightly full-corpus comparison of the Python oracle and the Mission Status service (mission mission-status-read-api-overview, WP14).

For every Mission under ``kitty-specs/`` the script builds the Python overview (the reference oracle of
``tests/contract/_mission_status_payloads.py``), reads what the running service answers for ``GET /api/v1/missions`` (every page)
and ``GET /api/v1/project``, and compares RAW BYTES: each Mission's item as the service wrote it against the oracle's canonical form
(sorted keys, compact separators, UTF-8 not escaped), the page frame, the order, and the project document. No timestamp, ordering
or number is normalised.

There is no exemption mechanism (operator decision E-10): ``IGNORED_FIELDS`` is one constant and empty, there is no option that
skips, allows or lowers anything, and the machine-readable report is only ever written, never read. Any differing field, one-sided
Mission, service 500 or oracle refusal makes the exit code non-zero, and when both sides refuse the run still fails.

Mission-detail extension (mission mission-status-read-api-mission-detail, WP17, AC-14.5 and AC-6.4): per Mission the script also
compares ``getMission`` and the artifact listing; per Work Package of every Mission ``getWorkPackage`` (with and without
``includePrompt=true``) and ``getWorkPackageDetail``; per file of each listing ``getArtifactContent``; and the decode class of every
Work Package file (the oracle's frontmatter read against the service's outcome). A 200 is compared as raw bytes; a refusal is compared
as the status and the Problem ``code`` (the human ``detail`` text is the service's own, D-P8-4). The only exemption is the refused list
(``REFUSED_LIST``, E-10 of #5529): the Missions whose Work Package routes the oracle cannot answer the way the service does, derived
by an independent scan of the tracked files and failing the run when the scan and the recorded list part.

Exit codes: 0 every Mission is equal, 1 at least one difference or refusal, 2 the run could not do its job (no Mission, fewer than
the recorded floor, a count that differs from the independent ``git ls-files`` count, an unusable URL, a service that never answers,
an oracle that cannot be built).

The output names Mission slugs, ``mission_id``, the difference class and the field, never a path and never an exception message.
The oracle imports ``pytest``, ``yaml`` and the ``src`` packages, so it needs the fully synced test environment even though no job
step runs ``pytest``; it is imported lazily, so ``--help`` works anywhere.
"""

from __future__ import annotations

import argparse
import http.client
import json
import re
import subprocess
import sys
import time
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote, urlsplit

# Run by path, the script's own directory (and not the repository root) leads sys.path: bootstrap the root for the oracle's ``tests.*``
# imports (mirrors scripts/ci/fleet_verdict.py).
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

EXIT_PASS = 0
EXIT_DIFFERENCE = 1
EXIT_CANNOT = 2

FLOOR = 500
PAGE_SIZE = 200
MAX_PAGES = 10_000
IGNORED_FIELDS: frozenset[str] = frozenset()  # the comparison ignore-list: one constant, and empty (E-10)

# The recorded floors of the detail comparison: counts of what was compared (zero matches, or a corpus that shrank, fails the run).
WORK_PACKAGE_FLOOR = 3000
LISTED_FILE_FLOOR = 10_000
DECODED_FILE_FLOOR = 3000
FLOORS: Mapping[str, int] = {"work_packages": WORK_PACKAGE_FLOOR, "listed_files": LISTED_FILE_FLOOR, "decoded_files": DECODED_FILE_FLOOR}

# The refused list (AC-14.5): Mission directory -> the ledger entry that explains it. It is the ONLY exemption, it is derived again from
# the tracked files by ``refused_scan`` on every run, and a run whose scan differs from this constant cannot do its job. A Mission is
# added here only together with an entry in the Mission's decision record (D-97 for SK-353).
SK_351 = "SK-351"  # a legacy lanes.json that read_lanes_json refuses
SK_353 = "SK-353"  # subtasks written as mappings: the oracle stringifies them, the service refuses (D-97)
REFUSED_LIST: Mapping[str, str] = {
    "064-complete-mission-identity-cutover": SK_351,
    "058-hybrid-prompt-and-shim-agent-surface": SK_353,
}
REFUSED_ROUTES = "getWorkPackage,getWorkPackageDetail,decode"

MISSIONS_ROUTE = "/api/v1/missions"
PROJECT_ROUTE = "/api/v1/project"
LISTING_SLUG = "<listing>"
PROJECT_SLUG = "<project>"
READY_INTERVAL_SECONDS = 2.0
READY_TIMEOUT_SECONDS = 60.0
REQUEST_TIMEOUT_SECONDS = 120.0
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost"})
OUTCOME_EQUAL = "equal"
OUTCOME_FIELD = "field"
OUTCOME_ONE_SIDED = "one_sided"
OUTCOME_REFUSAL = "refusal"
OUTCOME_EXEMPT = "exempt"
SIDE_PYTHON = "python"
SIDE_SERVICE = "service"
BYTES_FIELD = "<bytes>"
_ITEMS_OPEN = b'{"items":['
_FRAME_OPEN = b'],"pageInfo":'
_FRAME_CLOSE = b"}\n"

# Which Problem codes the service answers for an exception class the oracle raised; only the pairs the committed goldens evidence.
REFUSAL_CODES: Mapping[str, frozenset[str]] = {
    "ProjectionError": frozenset({"projection_refused"}),
    "StoreError": frozenset({"ledger_torn_tail", "ledger_unparseable"}),
}


@dataclass(frozen=True)
class Reply:
    """One HTTP answer: the status (0 when nothing answered) and the body bytes exactly as framed."""

    status: int
    body: bytes


class MissionOracle(Protocol):
    def names(self) -> list[str]: ...

    def overview(self, name: str) -> dict[str, Any]: ...

    def mission_id(self, name: str) -> str | None: ...

    def project(self) -> dict[str, Any]: ...

    def order(self, overviews: list[dict[str, Any]]) -> list[dict[str, Any]]: ...


class ServiceClient(Protocol):
    def wait_ready(self) -> bool: ...

    def get(self, route: str) -> Reply: ...


@dataclass(frozen=True)
class Expected:
    """What the oracle answers for one request: a status and a body (a payload for 200, a Problem for a refusal), or the exception it raised."""

    status: int
    body: Mapping[str, Any] = field(default_factory=dict)
    exception: str = ""


@dataclass(frozen=True)
class DecodeRecord:
    """The outcome of the oracle's frontmatter read of one Work Package file (AC-6.4): ``decoded`` and the winner of its id, ``refused``, or ``shadowed``."""

    file: str
    wp_id: str | None
    outcome: str


DECODED = "decoded"
REFUSED = "refused"
SHADOWED = "shadowed"
ABSENT = "absent"


class DetailOracle(Protocol):
    """The Python reference for the five detail routes and the decode class of the Work Package files, asked by Mission name."""

    def mission_id(self, name: str) -> str | None: ...

    def owns_mission_id(self, name: str) -> bool: ...

    def mission_detail(self, name: str) -> Expected: ...

    def work_package_ids(self, name: str) -> list[str]: ...

    def work_package(self, name: str, wp_id: str, *, include_prompt: bool) -> Expected: ...

    def work_package_detail(self, name: str, wp_id: str) -> Expected: ...

    def artifact_listing(self, name: str) -> Expected: ...

    def artifact_paths(self, name: str) -> list[str]: ...

    def artifact_content(self, name: str, path: str) -> Expected: ...

    def decode_records(self, name: str) -> list[DecodeRecord]: ...


@dataclass(frozen=True)
class Row:
    """The outcome for one Mission (or the listing, or the project): ``equal`` or a difference class."""

    slug: str
    mission_id: str | None
    outcome: str
    side: str = ""
    field: str = ""
    route: str = ""
    code: str = ""
    exception: str = ""
    item: str = ""  # the Work Package id or the artifact path the row is about
    file: str = ""  # the Work Package file (AC-6.4)
    klass: str = ""  # the decode class pair, oracle then service (AC-6.4)


@dataclass
class Report:
    rows: list[Row] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)
    compared: int = 0
    exit_code: int = EXIT_PASS
    counts: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Canonical form and raw splitting
# ---------------------------------------------------------------------------


def canonical_json(document: Any) -> str:
    """Sorted keys, compact separators, UTF-8 without ASCII escaping (NFR-005); nothing is normalised."""
    return json.dumps(document, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def canonical_bytes(document: Any) -> bytes:
    return (canonical_json(document) + "\n").encode("utf-8")


def _object_end(body: bytes, start: int) -> int | None:
    """The index just after the JSON object that begins at ``start``, or None when it does not close."""
    if body[start : start + 1] != b"{":
        return None
    depth, in_string, escaped = 0, False, False
    for index in range(start, len(body)):
        char = body[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == 0x5C:
                escaped = True
            elif char == 0x22:
                in_string = False
            continue
        if char == 0x22:
            in_string = True
        elif char in (0x7B, 0x5B):
            depth += 1
        elif char in (0x7D, 0x5D):
            depth -= 1
            if depth == 0:
                return index + 1
    return None


def split_page(body: bytes) -> tuple[list[bytes], bytes] | None:
    """The raw bytes of each listing item and the remainder after the items array, or None when the frame is not the canonical one."""
    if not body.startswith(_ITEMS_OPEN):
        return None
    position, items = len(_ITEMS_OPEN), []
    while body[position : position + 1] != b"]":
        end = _object_end(body, position)
        if end is None:
            return None
        items.append(body[position:end])
        if body[end : end + 1] == b",":
            end += 1
        elif body[end : end + 1] != b"]":
            return None
        position = end
    return items, body[position:]


def frame_problem(remainder: bytes) -> tuple[dict[str, Any] | None, str]:
    """Parse the ``pageInfo`` of a page remainder; the second value names a frame problem ('' when the frame is canonical)."""
    if not (remainder.startswith(_FRAME_OPEN) and remainder.endswith(_FRAME_CLOSE)):
        return None, "page frame"
    try:
        info = json.loads(remainder[len(_FRAME_OPEN) : -len(_FRAME_CLOSE)])
    except ValueError:
        return None, "page frame"
    if not isinstance(info, dict) or remainder != _FRAME_OPEN + canonical_json(info).encode("utf-8") + _FRAME_CLOSE:
        return None, "page frame"
    return info, ""


def first_difference(expected: Any, actual: Any, path: str = "") -> str | None:
    """The path of the first member at which two parsed documents differ, or None when they are equal as documents."""
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted({*expected, *actual}):
            where = f"{path}.{key}" if path else str(key)
            if key not in expected or key not in actual:
                return where
            found = first_difference(expected[key], actual[key], where)
            if found is not None:
                return found
        return None
    if isinstance(expected, list) and isinstance(actual, list):
        for index, (left, right) in enumerate(zip(expected, actual, strict=False)):
            found = first_difference(left, right, f"{path}[{index}]")
            if found is not None:
                return found
        return None if len(expected) == len(actual) else f"{path}[{min(len(expected), len(actual))}]"
    same = type(expected) is type(actual) and expected == actual
    return None if same else (path or "<root>")


def byte_field(expected: bytes, actual: bytes) -> str | None:
    """The differing field of two byte renderings of a document, ``<bytes>`` when the documents are equal; None when identical."""
    if expected == actual:
        return None
    try:
        found = first_difference(json.loads(expected), json.loads(actual))
    except ValueError:
        return BYTES_FIELD
    return found or BYTES_FIELD


def problem_code(reply: Reply) -> str:
    """The ``code`` of a Problem body (path-free by contract), or a fixed label when the body is not one."""
    try:
        body = json.loads(reply.body)
    except ValueError:
        return "no_problem_body" if reply.status else "no_answer"
    code = body.get("code") if isinstance(body, dict) else None
    return code[:64] if isinstance(code, str) else "no_problem_code"


def refusal_classes_agree(python_refusal: Mapping[str, Any], service_problem: Mapping[str, Any], table: Mapping[str, frozenset[str]] | None = None) -> bool:
    """Library function only (the workflow never exercises it): does the Problem code belong to the exception class the oracle raised?"""
    mapping = REFUSAL_CODES if table is None else table
    refusal = python_refusal.get("refusal")
    exception = refusal.get("exception") if isinstance(refusal, Mapping) else None
    return isinstance(exception, str) and service_problem.get("code") in mapping.get(exception, frozenset())


# ---------------------------------------------------------------------------
# The service and the oracle
# ---------------------------------------------------------------------------


class HttpService:
    """The service over loopback HTTP with the accepted ``Host`` form ``127.0.0.1:<port>``."""

    def __init__(self, base_url: str, *, interval: float = READY_INTERVAL_SECONDS, timeout: float = READY_TIMEOUT_SECONDS) -> None:
        parts = urlsplit(base_url)
        if parts.scheme != "http" or parts.hostname not in LOOPBACK_HOSTS or parts.port is None:
            raise ValueError("the base URL must be http://127.0.0.1:<port>")
        self.port = parts.port
        self.interval = interval
        self.timeout = timeout

    def get(self, route: str) -> Reply:
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=REQUEST_TIMEOUT_SECONDS)
        try:
            connection.request("GET", route, headers={"Host": f"127.0.0.1:{self.port}", "Connection": "close"})
            response = connection.getresponse()
            return Reply(response.status, response.read())
        except (OSError, http.client.HTTPException):
            return Reply(0, b"")
        finally:
            connection.close()

    def wait_ready(self) -> bool:
        """Poll the project route until anything but 0 (no answer) or 403 answers, or the timeout passes."""
        deadline = time.monotonic() + self.timeout
        while True:
            if self.get(PROJECT_ROUTE).status not in (0, 403):
                return True
            if time.monotonic() >= deadline:
                return False
            time.sleep(self.interval)


class PythonOracle:
    """The Python reference reader, built over one checkout."""

    detail: DetailOracle | None = None  # set by open_oracle: the same oracle, asked about the detail routes

    def __init__(self, repo_root: Path, payloads: Any, project: Any, memo: Any, tools: Any) -> None:
        self._root, self._payloads, self._project, self._memo, self._tools = repo_root, payloads, project, memo, tools

    def names(self) -> list[str]:
        return list(self._payloads.enumerate_missions(self._root))

    def overview(self, name: str) -> dict[str, Any]:
        source = self._payloads.load_source(self._root, name)
        return dict(self._payloads.build_overview(source, self._payloads.Projector(leak=self._tools.leak, mission=name)))

    def mission_id(self, name: str) -> str | None:
        try:
            raw = json.loads((self._root / "kitty-specs" / name / "meta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        value = raw.get("mission_id") if isinstance(raw, dict) else None
        return value if isinstance(value, str) else None

    def project(self) -> dict[str, Any]:
        return dict(self._project.build_project(self._root, self._memo.ResolverMemo(), leak=self._tools.leak).body)

    def order(self, overviews: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [dict(item) for item in self._payloads.order_overviews(overviews)]


class PythonDetailOracle:
    """The Python reference for the detail routes, composed from the conformance module, never re-implemented (spec FR-014)."""

    def __init__(self, repo_root: Path, tools: Any, conformance: Any, artifacts: Any, detail: Any) -> None:
        self._root, self._conf, self._art, self._det = repo_root, conformance, artifacts, detail
        self._ctx = artifacts.ReaderContext(repo_root=repo_root, tools=tools)
        self._host = detail.HostCapability(git=False, worktrees=True)  # the service reads no git; it stats lane worktrees
        self._work_packages: dict[tuple[str, bool], dict[str, Any]] = {}
        self._opened: dict[str, Any] = {}
        self._listings: dict[str, Any] = {}

    def _dir(self, name: str) -> Path:
        return self._root / "kitty-specs" / name

    def mission_id(self, name: str) -> str | None:
        try:
            raw = json.loads((self._dir(name) / "meta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        value = raw.get("mission_id") if isinstance(raw, dict) else None
        return value if isinstance(value, str) else None

    def owns_mission_id(self, name: str) -> bool:
        """False when another Mission directory also holds this ``mission_id`` and the id resolves to that one (a copied or backed-up
        directory): a request by id is then about the other directory, so this directory has no route of its own to compare."""
        mission_id = self.mission_id(name)
        if mission_id is None:
            return False
        resolved = self._art.resolve_mission(self._ctx, mission_id)
        return resolved is None or resolved.name == name

    @staticmethod
    def _raised(error: BaseException) -> Expected:
        return Expected(500, exception=type(error).__name__)

    def mission_detail(self, name: str) -> Expected:
        try:
            return Expected(200, self._conf.mission_detail_document(self._ctx, self._dir(name)))
        except Exception as error:  # noqa: BLE001 - the oracle may raise anything; the class name is the evidence
            return self._raised(error)

    def _open(self, name: str) -> Any:
        if name not in self._opened:
            self._opened[name] = self._det.open_mission(self._ctx, self.mission_id(name) or "")
        return self._opened[name]

    def work_package_ids(self, name: str) -> list[str]:
        opened = self._open(name)
        return sorted(opened.index) if isinstance(opened, self._det.OpenedMission) else []

    def work_package(self, name: str, wp_id: str, *, include_prompt: bool) -> Expected:
        key = (name, include_prompt)
        if key not in self._work_packages:
            self._work_packages[key] = self._conf.work_package_documents(self._ctx, self._dir(name), include_prompt=include_prompt)
        documents = self._work_packages[key]
        document = documents.get(wp_id, documents.get(self._conf.MISSION_KEY))
        if isinstance(document, dict) and set(document) == {"refusal"}:
            return Expected(500, exception=str(document["refusal"]["exception"]))
        return Expected(200, document) if document is not None else Expected(404, {"code": "not_found"})

    def work_package_detail(self, name: str, wp_id: str) -> Expected:
        opened = self._open(name)
        try:
            outcome = self._det.build_work_package_detail(
                self._ctx, self.mission_id(name) or "", wp_id, self._host, opened=opened if isinstance(opened, self._det.OpenedMission) else None
            )
        except Exception as error:  # noqa: BLE001 - the oracle may raise anything; the class name is the evidence
            return self._raised(error)
        return Expected(outcome.status, outcome.body)

    def _listing(self, name: str) -> Any:
        if name not in self._listings:
            self._listings[name] = self._art.list_artifacts(self._ctx, self.mission_id(name) or "")
        return self._listings[name]

    def artifact_listing(self, name: str) -> Expected:
        try:
            outcome = self._listing(name)
        except Exception as error:  # noqa: BLE001 - the oracle may raise anything; the class name is the evidence
            return self._raised(error)
        return Expected(outcome.status, outcome.body)

    def artifact_paths(self, name: str) -> list[str]:
        try:
            outcome = self._listing(name)
        except Exception:  # noqa: BLE001 - a listing that raises has no paths; artifact_listing records the exception
            return []
        return [entry["path"] for entry in outcome.body.get("entries", [])] if outcome.status == self._art.OK else []

    def artifact_content(self, name: str, path: str) -> Expected:
        try:
            outcome = self._art.read_content(self._ctx, self.mission_id(name) or "", [path])
        except Exception as error:  # noqa: BLE001 - the oracle may raise anything; the class name is the evidence
            return self._raised(error)
        return Expected(outcome.status, outcome.body)

    def decode_records(self, name: str) -> list[DecodeRecord]:
        from specify_cli.status.wp_metadata import read_authored_wp_frontmatter

        tasks = self._dir(name) / "tasks"
        files = sorted(path for path in tasks.glob("WP*.md") if path.is_file() and not path.is_symlink()) if tasks.is_dir() else []
        opened = self._open(name)
        winners = {wp_id: authored.name for wp_id, authored in opened.index.items()} if isinstance(opened, self._det.OpenedMission) else {}
        records = []
        for path in files:
            try:
                metadata, _body = read_authored_wp_frontmatter(path)
            except Exception:  # noqa: BLE001 - any refusal of the frontmatter read is the class "refused"
                records.append(DecodeRecord(path.name, wp_id_of_file(path.name), REFUSED))
                continue
            wp_id = metadata.work_package_id
            records.append(DecodeRecord(path.name, wp_id, DECODED if winners.get(wp_id) == path.name else SHADOWED))
        return records


def wp_id_of_file(file_name: str) -> str | None:
    """The Work Package id a file name starts with (``WP01-foundation.md`` is ``WP01``), or None."""
    found = re.match(r"(WP[0-9]{2,})", file_name)
    return found.group(1) if found else None


@contextmanager
def open_oracle(repo_root: Path, tools_root: Path | None = None) -> Iterator[PythonOracle]:
    """Build the oracle once.

    The contract tools come from ``tools_root`` (the checkout itself by default); their ``ContractTools`` value is built inside a
    MonkeyPatch context that is held for the whole comparison.
    """
    import pytest  # the oracle module imports pytest at module level, so it is installed whenever the oracle can run

    from tests.contract import _mission_status_artifacts as artifacts
    from tests.contract import _mission_status_conformance as conformance
    from tests.contract import _mission_status_detail as detail
    from tests.contract import _mission_status_memo as memo
    from tests.contract import _mission_status_payloads as payloads
    from tests.contract import _mission_status_project as project

    with pytest.MonkeyPatch.context() as patch:
        tools = payloads.load_contract_tools(patch, tools_root or repo_root)
        oracle = PythonOracle(repo_root, payloads, project, memo, tools)
        oracle.detail = PythonDetailOracle(repo_root, tools, conformance, artifacts, detail)
        yield oracle


def independent_count(repo_root: Path) -> int:
    """The Mission count as git lists it (``git ls-files 'kitty-specs/*/meta.json'``), taken apart from the oracle's directory scan."""
    result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z", "--", "kitty-specs/*/meta.json"],
        capture_output=True,
        check=True,
    )
    return sum(1 for path in result.stdout.split(b"\0") if path and path.count(b"/") == 2)


def _tracked(repo_root: Path) -> list[str]:
    result = subprocess.run(["git", "-C", str(repo_root), "ls-files", "-z", "--", "kitty-specs"], capture_output=True, check=True)
    return [path.decode("utf-8", "surrogateescape") for path in result.stdout.split(b"\0") if path]


def independent_work_package_files(repo_root: Path) -> int:
    """The number of Work Package files as git lists them (``kitty-specs/<mission>/tasks/WP*.md``, directly under ``tasks/``)."""
    count = 0
    for path in _tracked(repo_root):
        parts = path.split("/")
        if len(parts) == 4 and parts[2] == "tasks" and re.fullmatch(r"WP.*\.md", parts[3]):
            count += 1
    return count


def _frontmatter_subtasks(text: str) -> Any:
    import yaml  # the fully synced environment carries it (the oracle imports it too); imported only when the scan runs

    if not text.startswith("---"):
        return None
    end = text.find("\n---", 3)
    try:
        front = yaml.safe_load(text[3:end] if end > 0 else text[3:])
    except yaml.YAMLError:
        return None
    return front.get("subtasks") if isinstance(front, dict) else None


def refused_scan(repo_root: Path) -> dict[str, str]:
    """The Missions the refused list must hold, found from the tracked files and not from the oracle: a ``lanes.json`` of the legacy
    shape (``feature_slug`` and no ``mission_slug``: SK-351) and a Work Package whose ``subtasks`` hold a mapping (SK-353)."""
    found: dict[str, str] = {}
    for path in _tracked(repo_root):
        parts = path.split("/")
        if len(parts) == 3 and parts[2] == "lanes.json":
            try:
                document = json.loads((repo_root / path).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(document, dict) and "feature_slug" in document and "mission_slug" not in document:
                found.setdefault(parts[1], SK_351)
        elif len(parts) == 4 and parts[2] == "tasks" and re.fullmatch(r"WP.*\.md", parts[3]):
            try:
                subtasks = _frontmatter_subtasks((repo_root / path).read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(subtasks, list) and any(isinstance(entry, dict) for entry in subtasks):
                found.setdefault(parts[1], SK_353)
    return found


def refused_list_problem(scanned: Mapping[str, str], recorded: Mapping[str, str] = REFUSED_LIST) -> str | None:
    """None when the independent scan and the recorded list agree; else what parted (a Mission grew onto the list, or one fell off it)."""
    if dict(scanned) == dict(recorded):
        return None
    grown = sorted(set(scanned) - set(recorded))
    gone = sorted(set(recorded) - set(scanned))
    changed = sorted(name for name in set(scanned) & set(recorded) if scanned[name] != recorded[name])
    return f"the refused list and the independent scan part: not recorded {grown}, no longer found {gone}, other reason {changed}"


# ---------------------------------------------------------------------------
# The comparison
# ---------------------------------------------------------------------------


def _refused(oracle: MissionOracle, name: str, error: Exception) -> Row:
    return Row(slug=name, mission_id=oracle.mission_id(name), outcome=OUTCOME_REFUSAL, side=SIDE_PYTHON, exception=type(error).__name__)


def _python_side(oracle: MissionOracle, names: Sequence[str]) -> tuple[list[dict[str, Any]], list[Row]]:
    """The overviews the oracle builds and a refusal row per Mission it cannot build or cannot place in the order."""
    overviews: list[dict[str, Any]] = []
    refusals: list[Row] = []
    for name in names:
        try:
            overview = oracle.overview(name)
            oracle.order([overview])  # a Mission whose ordering key cannot be computed is a refusal of that Mission
        except Exception as error:  # noqa: BLE001 - the oracle may raise anything; the class name is the evidence
            refusals.append(_refused(oracle, name, error))
            continue
        overviews.append(overview)
    return overviews, refusals


@dataclass
class Listing:
    """What the service listed: raw item bytes in listing order, and the rows of every page that was unusable."""

    items: list[bytes] = field(default_factory=list)
    rows: list[Row] = field(default_factory=list)


def _page_route(cursor: str | None, page_size: int) -> str:
    route = f"{MISSIONS_ROUTE}?pageSize={page_size}"
    return route if cursor is None else f"{route}&pageCursor={quote(cursor, safe='')}"


def _read_listing(service: ServiceClient, page_size: int) -> Listing:
    listing = Listing()
    cursor: str | None = None
    seen: set[str] = set()
    for _ in range(MAX_PAGES):
        reply = service.get(_page_route(cursor, page_size))
        if reply.status != 200:
            listing.rows.append(Row(LISTING_SLUG, None, OUTCOME_REFUSAL, SIDE_SERVICE, route=MISSIONS_ROUTE, code=problem_code(reply)))
            return listing
        split = split_page(reply.body)
        info, problem = frame_problem(split[1]) if split else (None, "page frame")
        if split is None or info is None:
            listing.rows.append(Row(LISTING_SLUG, None, OUTCOME_FIELD, field=problem))
            return listing
        listing.items.extend(split[0])
        cursor = info.get("nextPageCursor")
        if not info.get("hasNextPage") or not isinstance(cursor, str) or cursor in seen:
            if info.get("hasNextPage") or cursor is not None:
                listing.rows.append(Row(LISTING_SLUG, None, OUTCOME_FIELD, field="pageInfo"))
            return listing
        seen.add(cursor)
    listing.rows.append(Row(LISTING_SLUG, None, OUTCOME_FIELD, field="pageInfo"))
    return listing


def _identity(raw: bytes) -> tuple[str, str | None, Any]:
    document = json.loads(raw)
    mission_id = document.get("missionId") if isinstance(document, dict) else None
    slug = document.get("slug") if isinstance(document, dict) else None
    return (slug if isinstance(slug, str) else "<unnamed>"), (mission_id if isinstance(mission_id, str) else None), document


def _compare_items(overviews: Sequence[dict[str, Any]], raw_items: Sequence[bytes], refused: Sequence[Row]) -> list[Row]:
    """One row per Mission present on either side: ``equal``, ``field`` (with the differing member) or ``one_sided``."""
    rows: list[Row] = []
    served: dict[str, tuple[str, bytes]] = {}
    unkeyed: list[tuple[str, bytes]] = []
    for raw in raw_items:
        try:
            slug, mission_id, _ = _identity(raw)
        except ValueError:
            rows.append(Row("<unparseable>", None, OUTCOME_FIELD, field=BYTES_FIELD))
            continue
        if mission_id is None or mission_id in served:
            unkeyed.append((slug, raw))
        else:
            served[mission_id] = (slug, raw)
    for overview in overviews:
        mission_id, slug = str(overview.get("missionId")), str(overview.get("slug"))
        expected = canonical_json(overview).encode("utf-8")
        found = served.pop(mission_id, None)
        if found is None:
            rows.append(Row(slug, mission_id, OUTCOME_ONE_SIDED, SIDE_PYTHON))
            continue
        differing = byte_field(expected, found[1])
        rows.append(Row(slug, mission_id, OUTCOME_EQUAL) if differing is None else Row(slug, mission_id, OUTCOME_FIELD, field=differing))
    refused_slugs = {row.slug for row in refused}
    leftovers = [(slug, mission_id) for mission_id, (slug, _) in served.items()] + [(slug, None) for slug, _ in unkeyed]
    rows.extend(Row(slug, mission_id, OUTCOME_ONE_SIDED, SIDE_SERVICE) for slug, mission_id in leftovers if slug not in refused_slugs)
    return rows


def _order_row(oracle: MissionOracle, overviews: Sequence[dict[str, Any]], raw_items: Sequence[bytes]) -> Row | None:
    """A row when the Missions both sides list come in a different order; the first Mission at which the sequences part."""
    expected = [str(item.get("missionId")) for item in oracle.order(list(overviews))]
    actual = []
    for raw in raw_items:
        try:
            actual.append(_identity(raw)[1])
        except ValueError:
            continue
    common = set(expected) & {value for value in actual if value}
    left, right = [value for value in expected if value in common], [value for value in actual if value in common]
    for want, got in zip(left, right, strict=False):
        if want != got:
            slug = next(str(item.get("slug")) for item in overviews if str(item.get("missionId")) == want)
            return Row(slug, want, OUTCOME_FIELD, field="order")
    return None


def _compare_project(oracle: MissionOracle, service: ServiceClient) -> Row:
    reply = service.get(PROJECT_ROUTE)
    if reply.status != 200:
        return Row(PROJECT_SLUG, None, OUTCOME_REFUSAL, SIDE_SERVICE, route=PROJECT_ROUTE, code=problem_code(reply))
    try:
        expected = canonical_bytes(oracle.project())
    except Exception as error:  # noqa: BLE001 - the oracle may raise anything; the class name is the evidence
        return Row(PROJECT_SLUG, None, OUTCOME_REFUSAL, SIDE_PYTHON, exception=type(error).__name__)
    differing = byte_field(expected, reply.body)
    return Row(PROJECT_SLUG, None, OUTCOME_EQUAL) if differing is None else Row(PROJECT_SLUG, None, OUTCOME_FIELD, field=differing)


# ---------------------------------------------------------------------------
# The detail routes (AC-14.5) and the decode class of the Work Package files (AC-6.4)
# ---------------------------------------------------------------------------


def _mission_route(mission_id: str) -> str:
    return f"{MISSIONS_ROUTE}/{quote(mission_id, safe='')}"


def _wp_route(mission_id: str, wp_id: str, suffix: str = "") -> str:
    return f"{_mission_route(mission_id)}/work-packages/{quote(wp_id, safe='')}{suffix}"


def _artifact_content_route(mission_id: str, path: str) -> str:
    return f"{_mission_route(mission_id)}/artifacts/content?path={quote(path, safe='/')}"


def _problem(reply: Reply) -> dict[str, Any]:
    try:
        body = json.loads(reply.body)
    except ValueError:
        return {}
    return body if isinstance(body, dict) else {}


def compare_answer(expected: Expected, reply: Reply, *, slug: str, mission_id: str | None, route: str, item: str = "") -> Row:
    """One request: a 200 is compared as raw bytes; a refusal as the status and the Problem ``code``; an exception of the oracle as the
    codes the evidenced pairs allow (``REFUSAL_CODES``)."""

    def row(outcome: str, **fields: str) -> Row:
        return Row(slug, mission_id, outcome, route=route, item=item, **fields)

    if expected.exception:
        problem = _problem(reply)
        if reply.status != 200 and refusal_classes_agree({"refusal": {"exception": expected.exception}}, problem):
            return row(OUTCOME_EQUAL)
        return row(
            OUTCOME_REFUSAL if reply.status == 0 else OUTCOME_FIELD, side=SIDE_SERVICE, field="refusal", code=problem_code(reply), exception=expected.exception
        )
    if expected.status == 200:
        if reply.status != 200:
            return row(OUTCOME_REFUSAL, side=SIDE_SERVICE, code=problem_code(reply))
        differing = byte_field(canonical_bytes(expected.body), reply.body)
        return row(OUTCOME_EQUAL) if differing is None else row(OUTCOME_FIELD, field=differing)
    wanted = expected.body.get("code")
    if reply.status != expected.status:
        return row(OUTCOME_FIELD, side=SIDE_SERVICE, field="status", code=problem_code(reply))
    if _problem(reply).get("code") != wanted:
        return row(OUTCOME_FIELD, side=SIDE_SERVICE, field="code", code=problem_code(reply))
    return row(OUTCOME_EQUAL)


def _decode_rows(
    detail: DetailOracle, service: ServiceClient, name: str, mission_id: str, records: Sequence[DecodeRecord], winners: set[str]
) -> tuple[list[Row], int, int]:
    """The decode class of each Work Package file: the oracle's frontmatter read against what the service answers for its id."""
    rows: list[Row] = []
    compared = 0
    shadowed = 0
    for record in records:
        if record.outcome == SHADOWED:
            shadowed += 1
        if record.outcome == SHADOWED or record.wp_id is None:
            continue  # another file holds the id (the first wins, FR-006) or the name carries no id: no class of its own to compare
        compared += 1
        route = _wp_route(mission_id, record.wp_id)
        reply = service.get(route)
        service_class = DECODED if reply.status == 200 else ABSENT if reply.status == 404 else f"{REFUSED}:{problem_code(reply)}"
        if record.outcome == REFUSED:
            if record.wp_id in winners or service_class == ABSENT:
                rows.append(Row(name, mission_id, OUTCOME_EQUAL, file=record.file, item=record.wp_id))
            else:
                rows.append(
                    Row(name, mission_id, OUTCOME_FIELD, SIDE_SERVICE, route=route, file=record.file, item=record.wp_id, klass=f"{REFUSED}->{service_class}")
                )
            continue
        if service_class != DECODED:
            rows.append(Row(name, mission_id, OUTCOME_FIELD, SIDE_SERVICE, route=route, file=record.file, item=record.wp_id, klass=f"{DECODED}->{service_class}"))
            continue
        expected = detail.work_package(name, record.wp_id, include_prompt=False)
        served = _problem(reply)
        differing = (
            None
            if expected.status != 200
            else first_difference({key: expected.body.get(key) for key in DECODED_MEMBERS}, {key: served.get(key) for key in DECODED_MEMBERS})
        )
        rows.append(
            Row(name, mission_id, OUTCOME_EQUAL, file=record.file, item=record.wp_id)
            if differing is None
            else Row(
                name, mission_id, OUTCOME_FIELD, SIDE_SERVICE, field=differing, route=route, file=record.file, item=record.wp_id, klass=f"{DECODED}->{DECODED}"
            )
        )
    return rows, compared, shadowed


# The members of a Work Package that the frontmatter decoder produces; their first difference is the decode class difference of AC-6.4.
DECODED_MEMBERS = ("wpId", "title", "authored", "ownedFiles")


def _compare_mission_detail(detail: DetailOracle, service: ServiceClient, name: str, exempt: str | None) -> tuple[list[Row], dict[str, int]]:
    """Every detail request of one Mission. An exempt Mission skips only its Work Package routes and its decode class, and says so."""
    counts = {"missions": 0, "work_packages": 0, "listed_files": 0, "decoded_files": 0, "shadowed_files": 0, "exempt": 0, "duplicate_ids": 0}
    mission_id = detail.mission_id(name)
    if mission_id is None:
        return [], counts  # no route can be asked; the overview refusal row of this Mission already fails the run
    if not detail.owns_mission_id(name):
        counts["duplicate_ids"] = 1  # the id resolves to another directory, whose own comparison covers the route (README: duplicate ids)
        return [], counts
    counts["missions"] = 1
    rows = [compare_answer(detail.mission_detail(name), service.get(_mission_route(mission_id)), slug=name, mission_id=mission_id, route="getMission")]
    rows.append(
        compare_answer(
            detail.artifact_listing(name), service.get(f"{_mission_route(mission_id)}/artifacts"), slug=name, mission_id=mission_id, route="listArtifacts"
        )
    )
    for path in detail.artifact_paths(name):
        counts["listed_files"] += 1
        reply = service.get(_artifact_content_route(mission_id, path))
        rows.append(compare_answer(detail.artifact_content(name, path), reply, slug=name, mission_id=mission_id, route="getArtifactContent", item=path))
    if exempt is not None:
        counts["exempt"] = 1
        rows.append(Row(name, mission_id, OUTCOME_EXEMPT, route=REFUSED_ROUTES, code=exempt))
        return rows, counts
    ids = detail.work_package_ids(name)
    for wp_id in ids:
        counts["work_packages"] += 1
        for route, expected, target in (
            ("getWorkPackage", detail.work_package(name, wp_id, include_prompt=False), _wp_route(mission_id, wp_id)),
            ("getWorkPackage?includePrompt=true", detail.work_package(name, wp_id, include_prompt=True), _wp_route(mission_id, wp_id) + "?includePrompt=true"),
            ("getWorkPackageDetail", detail.work_package_detail(name, wp_id), _wp_route(mission_id, wp_id, "/detail")),
        ):
            rows.append(compare_answer(expected, service.get(target), slug=name, mission_id=mission_id, route=route, item=wp_id))
    decode, compared, shadowed = _decode_rows(detail, service, name, mission_id, detail.decode_records(name), set(ids))
    counts["decoded_files"] = compared
    counts["shadowed_files"] = shadowed
    return rows + decode, counts


def compare_detail(detail: DetailOracle, service: ServiceClient, names: Sequence[str], refused: Mapping[str, str]) -> tuple[list[Row], dict[str, int]]:
    """The detail comparison over every Mission; the counts say how much was compared (the non-vacuity floors read them)."""
    rows: list[Row] = []
    totals = {"missions": 0, "work_packages": 0, "listed_files": 0, "decoded_files": 0, "shadowed_files": 0, "exempt": 0, "duplicate_ids": 0}
    for name in names:
        mission_rows, counts = _compare_mission_detail(detail, service, name, refused.get(name))
        rows.extend(mission_rows)
        for key, value in counts.items():
            totals[key] += value
    return rows, totals


def render_row(row: Row) -> str:
    parts = [f"EXEMPT {row.outcome}" if row.outcome == OUTCOME_EXEMPT else f"FAIL {row.outcome}"]
    for label, value in (
        ("side", row.side),
        ("slug", row.slug),
        ("mission_id", row.mission_id or ""),
        ("field", row.field),
        ("route", row.route),
        ("item", row.item),
        ("file", row.file),
        ("class", row.klass),
        ("code", row.code),
        ("exception", row.exception),
    ):
        if value:
            parts.append(f"{label}={value}")
    return " ".join(parts)


def _non_vacuity(names: Sequence[str], independent: int, floor: int) -> str | None:
    if not names:
        return "no Mission was found, so nothing was compared"
    if len(names) < floor:
        return f"{len(names)} Missions are below the recorded floor of {floor}"
    if len(names) != independent:
        return f"the oracle found {len(names)} Missions but the independent git count is {independent}"
    return None


def _detail_floor_problem(counts: Mapping[str, int], floors: Mapping[str, int], files: int | None) -> str | None:
    for key, minimum in floors.items():
        if counts.get(key, 0) < minimum:
            return f"the detail comparison covered {counts.get(key, 0)} {key.replace('_', ' ')}, below the recorded floor of {minimum}"
    if files is not None and counts.get("decoded_files", 0) + counts.get("shadowed_files", 0) > files:
        return f"the decode class covered more Work Package files ({counts.get('decoded_files', 0)}) than git lists ({files})"
    return None


def compare_corpus(
    oracle: MissionOracle,
    service: ServiceClient,
    *,
    independent_count: int,
    floor: int | None = None,
    page_size: int = PAGE_SIZE,
    detail: DetailOracle | None = None,
    refused: Mapping[str, str] | None = None,
    floors: Mapping[str, int] | None = None,
    work_package_files: int | None = None,
) -> Report:
    """Compare every Mission of the oracle with the service. Nothing is excluded; any row that is not ``equal`` or ``exempt`` fails the run.

    With ``detail`` the five detail routes and the decode class of the Work Package files are compared too; ``refused`` is the refused
    list (the only exemption), ``floors`` the counts that must be reached, and ``work_package_files`` the independent git count of
    the files the decode class must cover.
    """
    report = Report()
    names = oracle.names()
    report.compared = len(names)
    problem = _non_vacuity(names, independent_count, FLOOR if floor is None else floor)
    if problem is not None:
        report.lines.append(f"CANNOT {problem}")
        report.exit_code = EXIT_CANNOT
        return report
    if not service.wait_ready():
        report.lines.append("CANNOT the service never answered on the project route")
        report.exit_code = EXIT_CANNOT
        return report
    overviews, refusals = _python_side(oracle, names)
    listing = _read_listing(service, page_size)
    report.rows.extend(refusals)
    report.rows.extend(listing.rows)
    if not listing.rows:
        report.rows.extend(_compare_items(overviews, listing.items, refusals))
        order = _order_row(oracle, overviews, listing.items)
        if order is not None:
            report.rows = [row for row in report.rows if not (row.mission_id == order.mission_id and row.outcome == OUTCOME_EQUAL)] + [order]
    report.rows.append(_compare_project(oracle, service))
    if detail is not None:
        detail_rows, report.counts = compare_detail(detail, service, names, refused or {})
        report.rows.extend(detail_rows)
        problem = _detail_floor_problem(report.counts, FLOORS if floors is None else floors, work_package_files)
        if problem is not None:
            report.lines.append(f"CANNOT {problem}")
            report.exit_code = EXIT_CANNOT
            return report
    failing = [row for row in report.rows if row.outcome not in (OUTCOME_EQUAL, OUTCOME_EXEMPT)]
    report.lines.extend(render_row(row) for row in report.rows if row.outcome == OUTCOME_EXEMPT or row in failing)
    equal = sum(1 for row in report.rows if row.outcome == OUTCOME_EQUAL)
    report.lines.append(f"compared {report.compared} Missions: {equal} rows equal, {len(failing)} rows not equal")
    if report.counts:
        report.lines.append("detail: " + ", ".join(f"{value} {key.replace('_', ' ')}" for key, value in report.counts.items()))
    report.exit_code = EXIT_DIFFERENCE if failing else EXIT_PASS
    return report


def write_report(report: Report, path: Path) -> None:
    """Write ``nightly-report.json``: outcomes only. It is a workflow artifact and is never read back."""
    document = {"compared": report.compared, "exit": report.exit_code, "rows": [asdict(row) for row in report.rows]}
    path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare the Python oracle with the Mission Status service over the whole corpus (no exemptions).")
    parser.add_argument("--base-url", required=True, help="the service, http://127.0.0.1:<port>")
    parser.add_argument("--repo-root", required=True, type=Path, help="the checkout whose kitty-specs/ is the corpus")
    parser.add_argument("--report", required=True, type=Path, help="where to write nightly-report.json (written, never read)")
    return parser


def _say(message: str) -> None:
    print(message, flush=True)


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        service = HttpService(args.base_url)
    except ValueError as error:
        _say(f"CANNOT {error}")
        return EXIT_CANNOT
    try:
        count = independent_count(args.repo_root)
        scanned = refused_scan(args.repo_root)
        parted = refused_list_problem(scanned)
        if parted is not None:
            _say(f"CANNOT {parted}")
            return EXIT_CANNOT
        with open_oracle(args.repo_root) as oracle:
            if oracle.detail is None:
                _say("CANNOT the oracle has no reader for the detail routes, so five of the routes would go uncompared")
                return EXIT_CANNOT
            report = compare_corpus(
                oracle,
                service,
                independent_count=count,
                floor=FLOOR,
                detail=oracle.detail,
                refused=scanned,
                work_package_files=independent_work_package_files(args.repo_root),
            )
    except (ImportError, OSError, subprocess.CalledProcessError) as error:
        _say(f"CANNOT the oracle or the independent count could not be built ({type(error).__name__})")
        return EXIT_CANNOT
    for line in report.lines:
        _say(line)
    write_report(report, args.report)
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
