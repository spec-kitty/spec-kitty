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


@dataclass
class Report:
    rows: list[Row] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)
    compared: int = 0
    exit_code: int = EXIT_PASS


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


@contextmanager
def open_oracle(repo_root: Path, tools_root: Path | None = None) -> Iterator[PythonOracle]:
    """Build the oracle once.

    The contract tools come from ``tools_root`` (the checkout itself by default); their ``ContractTools`` value is built inside a
    MonkeyPatch context that is held for the whole comparison.
    """
    import pytest  # the oracle module imports pytest at module level, so it is installed whenever the oracle can run

    from tests.contract import _mission_status_memo as memo
    from tests.contract import _mission_status_payloads as payloads
    from tests.contract import _mission_status_project as project

    with pytest.MonkeyPatch.context() as patch:
        yield PythonOracle(repo_root, payloads, project, memo, payloads.load_contract_tools(patch, tools_root or repo_root))


def independent_count(repo_root: Path) -> int:
    """The Mission count as git lists it (``git ls-files 'kitty-specs/*/meta.json'``), taken apart from the oracle's directory scan."""
    result = subprocess.run(
        ["git", "-C", str(repo_root), "ls-files", "-z", "--", "kitty-specs/*/meta.json"],
        capture_output=True,
        check=True,
    )
    return sum(1 for path in result.stdout.split(b"\0") if path and path.count(b"/") == 2)


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


def render_row(row: Row) -> str:
    parts = [f"FAIL {row.outcome}"]
    for label, value in (
        ("side", row.side),
        ("slug", row.slug),
        ("mission_id", row.mission_id or ""),
        ("field", row.field),
        ("route", row.route),
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


def compare_corpus(
    oracle: MissionOracle,
    service: ServiceClient,
    *,
    independent_count: int,
    floor: int | None = None,
    page_size: int = PAGE_SIZE,
) -> Report:
    """Compare every Mission of the oracle with the service. Nothing is excluded; any row that is not ``equal`` fails the run."""
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
    failing = [row for row in report.rows if row.outcome != OUTCOME_EQUAL]
    report.lines.extend(render_row(row) for row in failing)
    equal = sum(1 for row in report.rows if row.outcome == OUTCOME_EQUAL)
    report.lines.append(f"compared {report.compared} Missions: {equal} rows equal, {len(failing)} rows not equal")
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
        with open_oracle(args.repo_root) as oracle:
            report = compare_corpus(oracle, service, independent_count=count, floor=FLOOR)
    except (ImportError, OSError, subprocess.CalledProcessError) as error:
        _say(f"CANNOT the oracle or the independent count could not be built ({type(error).__name__})")
        return EXIT_CANNOT
    for line in report.lines:
        _say(line)
    write_report(report, args.report)
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
