"""Unit cases of ``scripts/ci/mission_status_corpus_compare.py`` (mission mission-status-read-api-overview, WP14, AC-8c, E-10).

The script compares the Python overview of every Mission with what the service answers, byte for byte, and exits non-zero on ANY
difference. Every case here runs against fakes of the service and of the oracle; two cases run the real oracle over a scratch
repository and the script by path from another working directory. There is no exemption mechanism, and the tests pin that.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest

pytestmark = pytest.mark.fast

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "ci" / "mission_status_corpus_compare.py"
PASS, FAIL, CANNOT = 0, 1, 2
ULID_BASE = "01HZZZZZZZZZZZZZZZZZZZZZ"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("mission_status_corpus_compare", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Registered only while the module body runs (dataclasses resolve their own module there), then restored.
    with pytest.MonkeyPatch.context() as patch:
        patch.setitem(sys.modules, spec.name, module)
        spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def cc() -> ModuleType:
    return _load()


def _overview(number: int, **changes: Any) -> dict[str, Any]:
    document: dict[str, Any] = {
        "missionId": f"{ULID_BASE}{number:02d}"[-26:],
        "slug": f"mission-{number:02d}",
        "createdAt": f"2026-09-{number:02d}T10:00:00+00:00",
        "wpTotal": number,
        "progress": {"weightedPercentage": 12.5, "doneCount": 1},
        "lastEventId": None,
    }
    document.update(changes)
    return document


class FakeOracle:
    """The Python side: overviews by Mission name, an exception per refusing Mission, and a project document."""

    detail: Any = None

    def __init__(self, overviews: list[dict[str, Any]], refusing: Mapping[str, Exception] | None = None, project: Any = None) -> None:
        self.documents = {item["slug"]: item for item in overviews}
        self.refusing = dict(refusing or {})
        self.project_document: Any = project if project is not None else {"name": "fixture", "missionCount": len(overviews)}

    def names(self) -> list[str]:
        return sorted([*self.documents, *self.refusing])

    def overview(self, name: str) -> dict[str, Any]:
        if name in self.refusing:
            raise self.refusing[name]
        return self.documents[name]

    def mission_id(self, name: str) -> str | None:
        return self.documents[name]["missionId"] if name in self.documents else f"{ULID_BASE}99"[-26:]

    def order(self, overviews: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return _order(overviews)

    def project(self) -> dict[str, Any]:
        if isinstance(self.project_document, Exception):
            raise self.project_document
        return self.project_document


def _order(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(items, key=lambda item: (-int(item["createdAt"][8:10]), item["missionId"]))


class FakeService:
    """The service side: it pages the given items (raw bytes, canonical) and answers a project document."""

    def __init__(self, cc: ModuleType, items: list[dict[str, Any]], project: Any = None, ready: bool = True, status_of: Mapping[str, int] | None = None) -> None:
        self.cc = cc
        self.items = items
        self.project_document: Any = project if project is not None else {"name": "fixture", "missionCount": len(items)}
        self.ready = ready
        self.status_of = dict(status_of or {})
        self.routes: list[str] = []

    def wait_ready(self) -> bool:
        return self.ready

    def get(self, route: str) -> Any:
        self.routes.append(route)
        path = urlsplit(route).path
        if path in self.status_of:
            body = json.dumps({"code": "projection_refused", "title": "x", "status": self.status_of[path]}).encode()
            return self.cc.Reply(self.status_of[path], body)
        if path == "/api/v1/project":
            return self.cc.Reply(200, self.cc.canonical_bytes(self.project_document))
        query = parse_qs(urlsplit(route).query)
        size = int(query["pageSize"][0])
        start = int(query["pageCursor"][0]) if "pageCursor" in query else 0
        page = self.items[start : start + size]
        more = start + size < len(self.items)
        info = {"hasNextPage": more, "nextPageCursor": str(start + size) if more else None, "pageSize": size}
        return self.cc.Reply(200, self.cc.canonical_bytes({"items": page, "pageInfo": info}))


def _run(cc: ModuleType, oracle: FakeOracle, service: FakeService, *, count: int | None = None, floor: int = 1) -> Any:
    return cc.compare_corpus(oracle, service, independent_count=len(oracle.names()) if count is None else count, floor=floor)


def _twin(cc: ModuleType, count: int = 3) -> tuple[FakeOracle, FakeService]:
    items = _order([_overview(number) for number in range(1, count + 1)])
    return FakeOracle(list(items)), FakeService(cc, list(items))


def _said(report: Any) -> str:
    return "\n".join(report.lines)


# --- the passing run and the report -----------------------------------------------------------------------------------------


def test_identical_sides_pass_and_every_mission_has_an_equal_row(cc: ModuleType) -> None:
    oracle, service = _twin(cc, 3)
    report = _run(cc, oracle, service)
    assert report.exit_code == PASS
    assert report.compared == 3
    assert [row.outcome for row in report.rows if row.slug.startswith("mission-")] == ["equal"] * 3
    assert "compared 3 Missions" in _said(report)


def test_the_comparison_pages_through_the_listing(cc: ModuleType) -> None:
    oracle, service = _twin(cc, 5)
    report = cc.compare_corpus(oracle, service, independent_count=5, floor=1, page_size=2)
    assert report.exit_code == PASS
    assert sum("pageCursor" in route for route in service.routes) == 2


# --- AC-8c: a planted difference ----------------------------------------------------------------------------------------------


def test_a_planted_difference_in_two_missions_exits_non_zero_and_names_slug_and_field(cc: ModuleType) -> None:
    oracle, service = _twin(cc, 4)
    changed = [dict(item) for item in service.items]
    for item in changed:
        if item["slug"] in ("mission-02", "mission-03"):
            item["wpTotal"] = 999
    service.items = changed
    report = _run(cc, oracle, service)
    assert report.exit_code == FAIL
    said = _said(report)
    assert "mission-02" in said and "mission-03" in said and "wpTotal" in said
    assert "mission-01" not in said.replace("compared", "")  # the equal Missions are not reported as failures
    assert {row.slug for row in report.rows if row.outcome == "field"} == {"mission-02", "mission-03"}


def test_a_single_differing_byte_is_reported_even_when_the_documents_are_equal(cc: ModuleType) -> None:
    oracle, service = _twin(cc, 2)
    original = service.get

    def spaced(route: str) -> Any:
        reply = original(route)
        if "/missions" in route:
            return cc.Reply(reply.status, reply.body.replace(b'"wpTotal":1', b'"wpTotal": 1'))
        return reply

    service.get = spaced  # type: ignore[method-assign]
    report = _run(cc, oracle, service)
    assert report.exit_code == FAIL
    assert any(row.slug == "mission-01" and row.outcome == "field" for row in report.rows)


def test_a_number_rendered_differently_is_a_difference_not_normalised(cc: ModuleType) -> None:
    oracle, service = _twin(cc, 1)
    original = service.get
    service.get = lambda route: (  # type: ignore[method-assign]
        cc.Reply(200, original(route).body.replace(b"12.5", b"12.50")) if "/missions" in route else original(route)
    )
    report = _run(cc, oracle, service)
    assert report.exit_code == FAIL


def test_a_difference_of_the_q3_husk_shape_still_exits_non_zero(cc: ModuleType) -> None:
    oracle, service = _twin(cc, 2)
    husk = [dict(item) for item in service.items]
    husk[0]["lastEventId"] = "01HZZZZZZZZZZZZZZZZZZZZZZZ"
    service.items = husk
    report = _run(cc, oracle, service)
    assert report.exit_code == FAIL
    assert "lastEventId" in _said(report)


def test_the_project_document_is_compared_too(cc: ModuleType) -> None:
    oracle, service = _twin(cc, 2)
    service.project_document = {"name": "fixture", "missionCount": 7}
    report = _run(cc, oracle, service)
    assert report.exit_code == FAIL
    assert "missionCount" in _said(report)


def test_a_different_order_of_the_listing_fails(cc: ModuleType) -> None:
    oracle, service = _twin(cc, 3)
    service.items = list(reversed(service.items))
    report = _run(cc, oracle, service)
    assert report.exit_code == FAIL
    assert "order" in _said(report)


# --- non-vacuity ---------------------------------------------------------------------------------------------------------------


def test_an_empty_corpus_does_not_pass(cc: ModuleType) -> None:
    report = _run(cc, FakeOracle([]), FakeService(cc, []), count=0, floor=1)
    assert report.exit_code == CANNOT
    assert "no Mission" in _said(report)


def test_a_count_below_the_floor_fails(cc: ModuleType) -> None:
    oracle, service = _twin(cc, 3)
    report = _run(cc, oracle, service, floor=4)
    assert report.exit_code == CANNOT
    assert "floor" in _said(report)


def test_the_recorded_floor_is_500_and_cannot_be_lowered_from_the_command_line(cc: ModuleType) -> None:
    assert cc.FLOOR == 500
    assert not any("floor" in action.dest for action in cc.build_parser()._actions)


def test_a_count_that_differs_from_the_independent_git_count_fails(cc: ModuleType) -> None:
    oracle, service = _twin(cc, 3)
    report = _run(cc, oracle, service, count=4)
    assert report.exit_code == CANNOT
    assert "independent" in _said(report)


def test_the_independent_count_is_taken_from_git_ls_files(cc: ModuleType, tmp_path: Path) -> None:
    for name in ("one", "two"):
        (tmp_path / "kitty-specs" / name).mkdir(parents=True)
        (tmp_path / "kitty-specs" / name / "meta.json").write_text("{}", encoding="utf-8")
    (tmp_path / "kitty-specs" / "three").mkdir()
    (tmp_path / "kitty-specs" / "three" / "meta.json").write_text("{}", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "add", "kitty-specs/one", "kitty-specs/two"], check=True)
    assert cc.independent_count(tmp_path) == 2


def test_the_ignore_list_is_one_constant_and_empty(cc: ModuleType) -> None:
    assert len(cc.IGNORED_FIELDS) == 0


def test_a_mission_the_listing_lacks_is_never_skipped_silently(cc: ModuleType) -> None:
    oracle, service = _twin(cc, 3)
    service.items = service.items[:-1]
    report = _run(cc, oracle, service)
    assert report.exit_code == FAIL
    assert sum(row.outcome == "one_sided" for row in report.rows) == 1
    assert {row.slug for row in report.rows if row.outcome == "equal"} == {"mission-02", "mission-03"} or report.compared == 3


# --- service failures ------------------------------------------------------------------------------------------------------------


def test_an_unreachable_service_exits_non_zero(cc: ModuleType) -> None:
    oracle, service = _twin(cc, 2)
    service.ready = False
    report = _run(cc, oracle, service)
    assert report.exit_code == CANNOT
    assert "service" in _said(report)


def test_a_one_sided_mission_in_either_listing_fails(cc: ModuleType) -> None:
    oracle, service = _twin(cc, 3)
    service.items = [*service.items, _overview(9)]
    report = _run(cc, oracle, service)
    assert report.exit_code == FAIL
    only_service = [row for row in report.rows if row.outcome == "one_sided"]
    assert only_service and only_service[0].slug == "mission-09" and only_service[0].side == "service"
    oracle2, service2 = _twin(cc, 3)
    service2.items = service2.items[1:]
    report2 = _run(cc, oracle2, service2)
    assert report2.exit_code == FAIL
    assert any(row.outcome == "one_sided" and row.side == "python" for row in report2.rows)


def test_a_service_500_exits_non_zero_naming_the_side_the_route_and_the_code(cc: ModuleType) -> None:
    oracle, service = _twin(cc, 2)
    service.status_of = {"/api/v1/missions": 500}
    report = _run(cc, oracle, service)
    assert report.exit_code == FAIL
    said = _said(report)
    assert "service" in said and "/api/v1/missions" in said and "projection_refused" in said


def test_an_oracle_refusal_exits_non_zero_naming_python_slug_mission_id_and_exception_class(cc: ModuleType) -> None:
    items = _order([_overview(1), _overview(2)])
    oracle = FakeOracle([items[0]], refusing={"mission-02": ValueError("/secret/path/value")})
    service = FakeService(cc, items)
    report = _run(cc, oracle, service)
    assert report.exit_code == FAIL
    said = _said(report)
    assert "python" in said and "mission-02" in said and "ValueError" in said and ULID_BASE[:6] in said
    assert "/secret/path" not in said  # only the class is printed, never the message


def test_both_sides_refusing_still_fails(cc: ModuleType) -> None:
    oracle = FakeOracle([], refusing={"mission-01": ValueError("x")})
    service = FakeService(cc, [], status_of={"/api/v1/missions": 500, "/api/v1/project": 500})
    report = _run(cc, oracle, service, count=1)
    assert report.exit_code == FAIL
    said = _said(report)
    assert "python" in said and "service" in said


def test_a_service_that_refuses_every_mission_fails(cc: ModuleType) -> None:
    oracle, service = _twin(cc, 3)
    service.status_of = {"/api/v1/missions": 500, "/api/v1/project": 500}
    report = _run(cc, oracle, service)
    assert report.exit_code == FAIL


# --- the report cannot flip the exit code --------------------------------------------------------------------------------------


def test_a_planted_all_equal_report_beside_one_differing_mission_still_exits_non_zero(cc: ModuleType, tmp_path: Path) -> None:
    oracle, service = _twin(cc, 2)
    service.items = [dict(item, wpTotal=500) for item in service.items][:1] + service.items[1:]
    planted = tmp_path / "nightly-report.json"
    planted.write_text(json.dumps({"rows": [{"slug": "mission-01", "outcome": "equal"}], "exit": 0}), encoding="utf-8")
    report = _run(cc, oracle, service)
    cc.write_report(report, planted)
    assert report.exit_code == FAIL
    written = json.loads(planted.read_text(encoding="utf-8"))
    assert any(row["outcome"] != "equal" for row in written["rows"])
    assert "--report" in " ".join(action.option_strings[0] for action in cc.build_parser()._actions if action.option_strings)
    assert not hasattr(cc, "read_report")


def test_there_is_no_ignore_allowlist_or_known_differences_option(cc: ModuleType) -> None:
    options = " ".join(option for action in cc.build_parser()._actions for option in action.option_strings)
    for forbidden in ("ignore", "allow", "skip", "exempt", "known", "baseline", "floor"):
        assert forbidden not in options
    source = SCRIPT.read_text(encoding="utf-8")
    assert "known-differences" not in source and "allowlist" not in source.lower()


# --- the refusal library function ------------------------------------------------------------------------------------------------


def test_the_refusal_library_function_agrees_on_the_same_class_and_not_on_another(cc: ModuleType) -> None:
    fake = {"ProjectionError": frozenset({"projection_refused"}), "StoreError": frozenset({"ledger_torn_tail", "ledger_unparseable"})}
    assert cc.refusal_classes_agree({"refusal": {"exception": "StoreError", "line": 3}}, {"code": "ledger_torn_tail"}, fake)
    assert not cc.refusal_classes_agree({"refusal": {"exception": "StoreError", "line": 3}}, {"code": "projection_refused"}, fake)
    assert not cc.refusal_classes_agree({"refusal": {"exception": "Unmapped"}}, {"code": "projection_refused"}, fake)
    assert cc.refusal_classes_agree({"refusal": {"exception": "ProjectionError"}}, {"code": "projection_refused"})


# --- the entry point -----------------------------------------------------------------------------------------------------------


def test_main_writes_the_report_and_returns_the_exit_code(cc: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    oracle, service = _twin(cc, 2)
    service.items = [dict(item, wpTotal=77) for item in service.items]
    from contextlib import nullcontext

    oracle.detail = FakeDetail(cc, [])
    monkeypatch.setattr(cc, "open_oracle", lambda root: nullcontext(oracle))
    monkeypatch.setattr(cc, "HttpService", lambda base_url, **_: service)
    monkeypatch.setattr(cc, "independent_count", lambda root: 2)
    monkeypatch.setattr(cc, "refused_scan", lambda root: dict(cc.REFUSED_LIST))
    monkeypatch.setattr(cc, "independent_work_package_files", lambda root: 0)
    monkeypatch.setattr(cc, "FLOOR", 1)
    monkeypatch.setattr(cc, "FLOORS", {})
    report = tmp_path / "report.json"
    code = cc.main(["--base-url", "http://127.0.0.1:8787", "--repo-root", str(tmp_path), "--report", str(report)])
    assert code == FAIL
    assert json.loads(report.read_text(encoding="utf-8"))["exit"] == FAIL


def test_main_with_a_bad_base_url_cannot_do_its_job(cc: ModuleType, tmp_path: Path) -> None:
    assert cc.main(["--base-url", "http://example.invalid:80", "--repo-root", str(tmp_path), "--report", str(tmp_path / "r.json")]) == CANNOT


def test_the_script_runs_by_path_from_another_working_directory(tmp_path: Path) -> None:
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    result = subprocess.run([sys.executable, str(SCRIPT), "--help"], cwd=tmp_path, env=environment, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert "--base-url" in result.stdout and "--report" in result.stdout


def _fixture_repo(tmp_path: Path) -> Path:
    from tests.contract import _mission_status_payloads as helper

    helper.git_init(tmp_path)
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.yaml").write_text("project:\n  slug: fixture\n", encoding="utf-8")
    helper.write_fixture_mission(tmp_path, "alpha-mission", meta={"mission_id": helper.fixture_ulid(1)})
    helper.write_fixture_mission(tmp_path, "beta-mission", meta={"mission_id": helper.fixture_ulid(2), "created_at": "2026-09-02T10:00:00+00:00"})
    helper.commit_all(tmp_path)
    return tmp_path


def test_the_real_oracle_is_built_through_a_monkeypatch_context_and_matches_a_service_that_replays_it(cc: ModuleType, tmp_path: Path) -> None:
    repo = _fixture_repo(tmp_path)
    with cc.open_oracle(repo, REPO_ROOT) as oracle:
        names = oracle.names()
        assert names == ["alpha-mission", "beta-mission"]
        ordered = oracle.order([oracle.overview(name) for name in names])
        service = FakeService(cc, ordered, project=oracle.project())
        report = cc.compare_corpus(oracle, service, independent_count=cc.independent_count(repo), floor=2)
    assert report.exit_code == PASS, report.lines
    assert report.compared == 2


def test_an_escaped_quote_inside_a_string_does_not_end_the_item_early(cc: ModuleType) -> None:
    body = cc.canonical_bytes({"items": [{"slug": 'a"}],b', "z": 1}, {"slug": "b"}], "pageInfo": {"hasNextPage": False, "nextPageCursor": None, "pageSize": 2}})
    split = cc.split_page(body)
    assert split is not None and len(split[0]) == 2
    assert json.loads(split[0][0])["slug"] == 'a"}],b'
    assert cc.frame_problem(split[1])[1] == ""
    assert cc.split_page(b"[]") is None and cc.split_page(b'{"items":[1]}') is None
    assert cc.frame_problem(b'],"pageInfo": {}}\n')[1] == "page frame"


# --- canonical_json is a deliberate copy of the conformance module's ----------------------------------------------------------------
# The script runs standalone in the nightly job and cannot import tests/ (that imports the CLI and pytest), so the function is duplicated
# and this test pins the two to the same bytes. A lazy import would add a fragile cross-tree dependency to a CI script; an equality
# test on a sample that exercises every knob (key order, separators, non-ASCII, nesting, numbers, null and bool) keeps them honest.

CANONICAL_SAMPLE: list[Any] = [
    {"b": 1, "a": [1, 2.5, None, True, False], "c": {"z": "é日本" + chr(0x2028), "y": {"x": []}}},
    [],
    {},
    "plain",
    {"key with space": "tab\tnewline\n", "10": 10, "2": 2, "é": "ä"},
    [{"b": 2, "a": 1}, {"a": 1, "b": 2}],
    {"n": -0.0, "big": 12345678901234567890, "small": 1e-07},
]


def _conformance_module() -> ModuleType:
    from tests.contract import _mission_status_conformance as conformance

    return conformance


def test_canonical_json_agrees_byte_for_byte_with_the_conformance_module(cc: ModuleType) -> None:
    conformance = _conformance_module()
    for document in CANONICAL_SAMPLE:
        assert cc.canonical_json(document) == conformance.canonical_json(document), document
        assert cc.canonical_bytes(document) == conformance.canonical_bytes(document), document


def test_the_canonical_sample_tells_the_three_json_knobs_apart() -> None:
    """Revert rows: a copy that drops sort_keys, ensure_ascii=False or the compact separators must differ on the sample."""
    variants = {
        "sort_keys": lambda d: json.dumps(d, ensure_ascii=False, separators=(",", ":")),
        "ensure_ascii": lambda d: json.dumps(d, sort_keys=True, separators=(",", ":")),
        "separators": lambda d: json.dumps(d, sort_keys=True, ensure_ascii=False),
    }
    reference = _conformance_module().canonical_json
    for label, variant in variants.items():
        assert any(variant(document) != reference(document) for document in CANONICAL_SAMPLE), label


# --- the detail routes and the decode class of the Work Package files (WP17, AC-14.5, AC-6.4) ---------------------------------------


class FakeDetail:
    """The Python side of the detail routes: per Mission name an id, Work Package payloads, artifacts and decode records.

    A Mission is ``(name, wps, files, records)``: ``wps`` maps a Work Package id to its payload, ``files`` maps an artifact path to its
    content, ``records`` is the list of ``(file, wp_id, outcome)`` the frontmatter read gave.
    """

    def __init__(self, cc: ModuleType, missions: list[tuple[str, dict[str, dict[str, Any]], dict[str, str], list[tuple[str, str | None, str]]]]) -> None:
        self.cc = cc
        self.missions = {name: (wps, files, records) for name, wps, files, records in missions}
        self.refusing: dict[str, Any] = {}  # (route, name, item) -> Expected, for a refusal the oracle gives
        self.shadowed: set[str] = set()  # Missions whose id resolves to another directory

    def mission_id(self, name: str) -> str | None:
        return f"{ULID_BASE}{sorted(self.missions).index(name) + 1:02d}"[-26:] if name in self.missions else None

    def owns_mission_id(self, name: str) -> bool:
        return name not in self.shadowed

    def _expected(self, route: str, name: str, item: str, ok: dict[str, Any]) -> Any:
        return self.refusing.get((route, name, item)) or self.cc.Expected(200, ok)

    def mission_detail(self, name: str) -> Any:
        return self._expected("getMission", name, "", {"missionId": self.mission_id(name), "slug": name, "wpTotal": len(self.missions[name][0])})

    def work_package_ids(self, name: str) -> list[str]:
        return sorted(self.missions[name][0])

    def work_package(self, name: str, wp_id: str, *, include_prompt: bool) -> Any:
        payload = dict(self.missions[name][0][wp_id])
        if include_prompt:
            payload["promptMarkdown"] = f"# Body of {wp_id}\n"
        return self._expected("getWorkPackage?includePrompt=true" if include_prompt else "getWorkPackage", name, wp_id, payload)

    def work_package_detail(self, name: str, wp_id: str) -> Any:
        return self._expected("getWorkPackageDetail", name, wp_id, {"wpId": wp_id, "ownedFiles": []})

    def artifact_listing(self, name: str) -> Any:
        return self._expected("listArtifacts", name, "", {"entries": [{"path": path} for path in sorted(self.missions[name][1])]})

    def artifact_paths(self, name: str) -> list[str]:
        return sorted(self.missions[name][1])

    def artifact_content(self, name: str, path: str) -> Any:
        return self._expected("getArtifactContent", name, path, {"path": path, "content": self.missions[name][1][path]})

    def decode_records(self, name: str) -> list[Any]:
        return [self.cc.DecodeRecord(file, wp_id, outcome) for file, wp_id, outcome in self.missions[name][2]]


class DetailService(FakeService):
    """The service side: the overview routes of ``FakeService`` and the detail routes answered from the same truth as ``FakeDetail``.

    ``changes`` maps a route (path and query) to a replacement: a ``Reply``, or a dict that is served as a 200 document.
    """

    def __init__(self, cc: ModuleType, items: list[dict[str, Any]], detail: FakeDetail, changes: Mapping[str, Any] | None = None) -> None:
        super().__init__(cc, items)
        self.detail = detail
        self.changes = dict(changes or {})
        self.by_id = {detail.mission_id(name): name for name in detail.missions}

    def get(self, route: str) -> Any:
        self.routes.append(route)
        if route in self.changes:
            change = self.changes[route]
            return change if isinstance(change, self.cc.Reply) else self.cc.Reply(200, self.cc.canonical_bytes(change))
        parts = urlsplit(route)
        pieces = parts.path.split("/")
        if len(pieces) < 5 or pieces[3] != "missions" or pieces[4] not in self.by_id:
            if len(pieces) >= 5 and pieces[3] == "missions" and pieces[4] not in ("",):
                return self._problem(404, "not_found")
            return super().get(route)
        name, tail = self.by_id[pieces[4]], pieces[5:]
        wps, files, _ = self.detail.missions[name]
        if not tail:
            return self._served(self.detail.mission_detail(name))
        if tail == ["artifacts"]:
            return self._served(self.detail.artifact_listing(name))
        if tail == ["artifacts", "content"]:
            path = parse_qs(parts.query)["path"][0]
            return self._served(self.detail.artifact_content(name, path)) if path in files else self._problem(404, "not_found")
        if tail[0] == "work-packages" and len(tail) in (2, 3) and tail[1] in wps:
            if len(tail) == 3:
                return self._served(self.detail.work_package_detail(name, tail[1]))
            return self._served(self.detail.work_package(name, tail[1], include_prompt="includePrompt=true" in parts.query))
        return self._problem(404, "not_found")

    def _served(self, expected: Any) -> Any:
        if expected.status == 200:
            return self.cc.Reply(200, self.cc.canonical_bytes(expected.body))
        return self._problem(expected.status, expected.body.get("code", "projection_refused"))

    def _problem(self, status: int, code: str) -> Any:
        return self.cc.Reply(status, json.dumps({"code": code, "status": status, "title": "x"}).encode())


def _mission(name: str, wps: tuple[str, ...] = ("WP01", "WP02"), files: tuple[str, ...] = ("spec.md", "plan.md")) -> tuple[Any, ...]:
    payloads = {wp: {"wpId": wp, "title": f"Title {wp}", "authored": {"model": "sonnet"}, "ownedFiles": ["src/a.py"]} for wp in wps}
    records = [(f"{wp}-fixture.md", wp, "decoded") for wp in wps]
    return name, payloads, {path: f"text of {path}" for path in files}, records


def _detail_world(
    cc: ModuleType, changes: Mapping[str, Any] | None = None, count: int = 2, missions: list[Any] | None = None
) -> tuple[FakeOracle, FakeDetail, DetailService]:
    oracle, service = _twin(cc, count)
    detail = FakeDetail(cc, missions if missions is not None else [_mission(f"mission-{number:02d}") for number in range(1, count + 1)])
    oracle.detail = detail
    return oracle, detail, DetailService(cc, service.items, detail, changes)


def _run_detail(cc: ModuleType, oracle: FakeOracle, detail: FakeDetail, service: Any, **options: Any) -> Any:
    options.setdefault("floors", {})
    return cc.compare_corpus(oracle, service, independent_count=len(oracle.names()), floor=1, detail=detail, **options)


def _route(detail: FakeDetail, name: str, tail: str) -> str:
    return f"/api/v1/missions/{detail.mission_id(name)}{tail}"


def test_identical_detail_sides_pass_and_every_route_is_counted(cc: ModuleType) -> None:
    oracle, detail, service = _detail_world(cc)
    report = _run_detail(cc, oracle, detail, service)
    assert report.exit_code == PASS, report.lines
    assert report.counts == {"missions": 2, "work_packages": 4, "listed_files": 4, "decoded_files": 4, "exempt": 0, "duplicate_ids": 0}
    routes = {row.route for row in report.rows if row.outcome == "equal" and row.route}
    assert {"getMission", "listArtifacts", "getArtifactContent", "getWorkPackage", "getWorkPackage?includePrompt=true", "getWorkPackageDetail"} <= routes
    # both forms of the prompt request, the detail and the content were really asked
    asked = " ".join(service.routes)
    assert "includePrompt=true" in asked and "/detail" in asked and "/artifacts/content?path=spec.md" in asked


@pytest.mark.parametrize(
    ("route_name", "tail", "document", "field"),
    [
        ("getMission", "", {"missionId": "x", "slug": "mission-01", "wpTotal": 99}, "missionId"),
        ("listArtifacts", "/artifacts", {"entries": [{"path": "spec.md"}]}, "entries[0].path"),
        ("getArtifactContent", "/artifacts/content?path=spec.md", {"path": "spec.md", "content": "changed"}, "content"),
        ("getWorkPackage", "/work-packages/WP01", {"wpId": "WP01", "title": "Changed", "authored": {"model": "sonnet"}, "ownedFiles": ["src/a.py"]}, "title"),
        ("getWorkPackage?includePrompt=true", "/work-packages/WP01?includePrompt=true", {"wpId": "WP01", "promptMarkdown": "other"}, "authored"),
        ("getWorkPackageDetail", "/work-packages/WP01/detail", {"wpId": "WP01", "ownedFiles": ["src/b.py"]}, "ownedFiles[0]"),
    ],
)
def test_a_planted_difference_on_each_detail_route_is_named_by_route_item_and_field(
    cc: ModuleType, route_name: str, tail: str, document: dict[str, Any], field: str
) -> None:
    oracle, detail, _ = _detail_world(cc)
    mission_id = detail.mission_id("mission-01")
    service = _detail_world(cc, changes={f"/api/v1/missions/{mission_id}{tail}": document})[2]
    report = _run_detail(cc, oracle, detail, service)
    assert report.exit_code == FAIL
    rows = [row for row in report.rows if row.outcome == "field" and row.route == route_name]
    assert len(rows) == 1, report.lines
    assert rows[0].slug == "mission-01" and rows[0].field == field
    assert f"route={route_name}" in _said(report) and "slug=mission-01" in _said(report)


def test_a_detail_route_the_service_refuses_where_the_oracle_answers_names_the_service_and_the_code(cc: ModuleType) -> None:
    oracle, detail, _ = _detail_world(cc)
    refused = cc.Reply(500, json.dumps({"code": "source_unreadable"}).encode())
    service = _detail_world(cc, changes={_route(detail, "mission-02", "/work-packages/WP02/detail"): refused})[2]
    report = _run_detail(cc, oracle, detail, service)
    assert report.exit_code == FAIL
    assert "side=service" in _said(report) and "code=source_unreadable" in _said(report) and "route=getWorkPackageDetail" in _said(report)


def test_a_refusal_is_compared_as_status_and_problem_code_and_not_as_text(cc: ModuleType) -> None:
    oracle, detail, _ = _detail_world(cc)
    detail.refusing[("getWorkPackageDetail", "mission-01", "WP01")] = cc.Expected(404, {"code": "not_found", "detail": "the oracle's own wording"})
    agree = cc.Reply(404, json.dumps({"code": "not_found", "detail": "the service's own wording"}).encode())
    route = _route(detail, "mission-01", "/work-packages/WP01/detail")
    assert _run_detail(cc, oracle, detail, _detail_world(cc, changes={route: agree})[2]).exit_code == PASS
    wrong_code = cc.Reply(404, json.dumps({"code": "other"}).encode())
    report = _run_detail(cc, oracle, detail, _detail_world(cc, changes={route: wrong_code})[2])
    assert report.exit_code == FAIL and "field=code" in _said(report)
    wrong_status = cc.Reply(500, json.dumps({"code": "not_found"}).encode())
    assert "field=status" in _said(_run_detail(cc, oracle, detail, _detail_world(cc, changes={route: wrong_status})[2]))
    assert _run_detail(cc, oracle, detail, _detail_world(cc, changes={route: {"wpId": "WP01"}})[2]).exit_code == FAIL


def test_an_exception_of_the_oracle_agrees_only_with_the_problem_codes_its_class_allows(cc: ModuleType) -> None:
    oracle, detail, _ = _detail_world(cc)
    detail.refusing[("getMission", "mission-01", "")] = cc.Expected(500, exception="ProjectionError")
    route = _route(detail, "mission-01", "")
    good = cc.Reply(500, json.dumps({"code": "projection_refused"}).encode())
    assert _run_detail(cc, oracle, detail, _detail_world(cc, changes={route: good})[2]).exit_code == PASS
    for bad in (cc.Reply(500, json.dumps({"code": "source_unreadable"}).encode()), cc.Reply(200, cc.canonical_bytes({"missionId": "x"}))):
        report = _run_detail(cc, oracle, detail, _detail_world(cc, changes={route: bad})[2])
        assert report.exit_code == FAIL and "exception=ProjectionError" in _said(report)


def test_the_decode_class_names_the_file_the_side_and_the_class_pair(cc: ModuleType) -> None:
    oracle, detail, _ = _detail_world(cc)
    absent = cc.Reply(404, json.dumps({"code": "not_found"}).encode())
    service = _detail_world(cc, changes={_route(detail, "mission-01", "/work-packages/WP01"): absent})[2]
    report = _run_detail(cc, oracle, detail, service)
    rows = [row for row in report.rows if row.file and row.outcome != "equal"]
    assert report.exit_code == FAIL and len(rows) == 1
    assert (rows[0].file, rows[0].side, rows[0].klass, rows[0].item) == ("WP01-fixture.md", "service", "decoded->absent", "WP01")
    assert "file=WP01-fixture.md" in _said(report) and "side=service" in _said(report) and "class=decoded->absent" in _said(report)


def test_the_decode_class_reports_a_decoded_field_that_differs_and_a_file_the_service_decodes_but_the_oracle_refused(cc: ModuleType) -> None:
    mission = _mission("mission-01", wps=("WP01",))
    mission[3].append(("WP05-broken.md", "WP05", "refused"))
    oracle, detail, plain = _detail_world(cc, count=1, missions=[mission])
    assert _run_detail(cc, oracle, detail, plain).exit_code == PASS  # the refused file is absent on the service, as the oracle has it
    served = {"wpId": "WP05", "title": "decoded after all", "authored": {}, "ownedFiles": []}
    service = _detail_world(cc, changes={_route(detail, "mission-01", "/work-packages/WP05"): served}, count=1, missions=[mission])[2]
    service.by_id = dict(plain.by_id)
    report = _run_detail(cc, oracle, detail, service)
    rows = [row for row in report.rows if row.klass]
    assert report.exit_code == FAIL and [row.klass for row in rows] == ["refused->decoded"]
    changed = {"wpId": "WP01", "title": "Title WP01", "authored": {"model": "opus"}, "ownedFiles": ["src/a.py"]}
    service = _detail_world(cc, changes={_route(detail, "mission-01", "/work-packages/WP01"): changed}, count=1, missions=[mission])[2]
    report = _run_detail(cc, oracle, detail, service)
    decode = [row for row in report.rows if row.klass == "decoded->decoded"]
    assert len(decode) == 1 and decode[0].field == "authored.model" and decode[0].file == "WP01-fixture.md"


def test_a_shadowed_file_has_no_class_of_its_own(cc: ModuleType) -> None:
    mission = _mission("mission-01", wps=("WP01",))
    mission[3].append(("WP01-copy.md", "WP01", "shadowed"))
    oracle, detail, service = _detail_world(cc, count=1, missions=[mission])
    report = _run_detail(cc, oracle, detail, service)
    assert report.exit_code == PASS and report.counts["decoded_files"] == 1


def test_the_refused_list_is_the_only_exemption_and_skips_only_the_work_package_routes_and_the_decode_class(cc: ModuleType) -> None:
    oracle, detail, _ = _detail_world(cc)
    changes = {
        _route(detail, "mission-01", "/work-packages/WP01"): {"wpId": "WP01", "title": "differs"},
        _route(detail, "mission-01", "/work-packages/WP01/detail"): cc.Reply(500, b"{}"),
    }
    service = _detail_world(cc, changes=changes)[2]
    assert _run_detail(cc, oracle, detail, service).exit_code == FAIL  # without the list the differences fail the run
    report = _run_detail(cc, oracle, detail, service, refused={"mission-01": cc.SK_353})
    assert report.exit_code == PASS, report.lines
    assert report.counts["exempt"] == 1 and report.counts["work_packages"] == 2  # the exempt Mission's two Work Packages are not counted
    assert "EXEMPT exempt" in _said(report) and "slug=mission-01" in _said(report) and "code=SK-353" in _said(report)
    # the exemption does not reach getMission, the listing or the content
    changed = _detail_world(cc, changes={_route(detail, "mission-01", ""): {"missionId": "x"}})[2]
    assert _run_detail(cc, oracle, detail, changed, refused={"mission-01": cc.SK_351}).exit_code == FAIL


def test_the_refused_list_is_pinned_to_the_two_ledger_entries(cc: ModuleType) -> None:
    assert dict(cc.REFUSED_LIST) == {"064-complete-mission-identity-cutover": "SK-351", "058-hybrid-prompt-and-shim-agent-surface": "SK-353"}
    assert cc.refused_list_problem(dict(cc.REFUSED_LIST)) is None
    grown = cc.refused_list_problem({**cc.REFUSED_LIST, "100-new-mission": "SK-353"})
    assert grown is not None and "100-new-mission" in grown and "not recorded" in grown
    gone = cc.refused_list_problem({"064-complete-mission-identity-cutover": "SK-351"})
    assert gone is not None and "058-hybrid-prompt-and-shim-agent-surface" in gone
    other = cc.refused_list_problem({**cc.REFUSED_LIST, "064-complete-mission-identity-cutover": "SK-353"})
    assert other is not None and "other reason" in other


def test_the_independent_scan_finds_a_legacy_lanes_json_and_subtasks_written_as_mappings(cc: ModuleType, tmp_path: Path) -> None:
    from tests.contract import _mission_status_payloads as helper

    helper.git_init(tmp_path)
    helper.write_fixture_mission(tmp_path, "plain-mission", work_packages={"WP01": {"subtasks": ["T001"]}}, lanes={"mission_slug": "plain-mission", "lanes": []})
    helper.write_fixture_mission(tmp_path, "legacy-lanes", meta={"mission_id": helper.fixture_ulid(2)}, lanes={"feature_slug": "legacy-lanes", "lanes": []})
    helper.write_fixture_mission(
        tmp_path, "mapped-subtasks", meta={"mission_id": helper.fixture_ulid(3)}, work_packages={"WP01": {"subtasks": [{"id": "T001", "title": "x"}]}}
    )
    helper.commit_all(tmp_path)
    assert cc.refused_scan(tmp_path) == {"legacy-lanes": "SK-351", "mapped-subtasks": "SK-353"}
    assert cc.independent_work_package_files(tmp_path) == 2


def test_an_untracked_file_is_not_part_of_the_independent_scan(cc: ModuleType, tmp_path: Path) -> None:
    from tests.contract import _mission_status_payloads as helper

    helper.git_init(tmp_path)
    helper.write_fixture_mission(tmp_path, "plain-mission", work_packages={"WP01": {}})
    helper.commit_all(tmp_path)
    helper.write_fixture_mission(tmp_path, "later-mission", meta={"mission_id": helper.fixture_ulid(2)}, work_packages={"WP01": {"subtasks": [{"id": "T001"}]}})
    assert cc.refused_scan(tmp_path) == {}
    assert cc.independent_work_package_files(tmp_path) == 1


def test_a_detail_comparison_that_covers_less_than_the_recorded_floor_cannot_do_its_job(cc: ModuleType) -> None:
    oracle, detail, service = _detail_world(cc)
    assert _run_detail(cc, oracle, detail, service, floors={"work_packages": 4, "listed_files": 4, "decoded_files": 4}).exit_code == PASS
    for key in ("work_packages", "listed_files", "decoded_files"):
        report = _run_detail(cc, oracle, detail, service, floors={key: 5})
        assert report.exit_code == CANNOT and "below the recorded floor of 5" in _said(report)


def test_the_recorded_detail_floors_are_not_lowered_and_an_empty_detail_corpus_fails(cc: ModuleType) -> None:
    assert (cc.WORK_PACKAGE_FLOOR, cc.LISTED_FILE_FLOOR, cc.DECODED_FILE_FLOOR) == (3000, 10_000, 3000)
    oracle, detail, service = _detail_world(cc, missions=[_mission("mission-01", wps=(), files=()), _mission("mission-02", wps=(), files=())])
    report = cc.compare_corpus(oracle, service, independent_count=2, floor=1, detail=detail)
    assert report.exit_code == CANNOT and "below the recorded floor" in _said(report)


def test_the_decode_class_cannot_cover_more_files_than_git_lists(cc: ModuleType) -> None:
    oracle, detail, service = _detail_world(cc)
    assert _run_detail(cc, oracle, detail, service, work_package_files=4).exit_code == PASS
    report = _run_detail(cc, oracle, detail, service, work_package_files=3)
    assert report.exit_code == CANNOT and "more Work Package files" in _said(report)


def test_main_refuses_a_detail_oracle_that_is_missing_and_a_refused_list_that_parted(cc: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from contextlib import nullcontext

    oracle, service = _twin(cc, 2)
    monkeypatch.setattr(cc, "HttpService", lambda base_url, **_: service)
    monkeypatch.setattr(cc, "independent_count", lambda root: 2)
    monkeypatch.setattr(cc, "independent_work_package_files", lambda root: 0)
    monkeypatch.setattr(cc, "open_oracle", lambda root: nullcontext(oracle))
    arguments = ["--base-url", "http://127.0.0.1:8787", "--repo-root", str(tmp_path), "--report", str(tmp_path / "r.json")]
    monkeypatch.setattr(cc, "refused_scan", lambda root: {**cc.REFUSED_LIST, "100-new-mission": "SK-353"})
    assert cc.main(arguments) == CANNOT  # the scan found a Mission the decision record does not hold
    monkeypatch.setattr(cc, "refused_scan", lambda root: dict(cc.REFUSED_LIST))
    assert cc.main(arguments) == CANNOT  # no detail reader on the oracle: five routes would go uncompared
    assert not (tmp_path / "r.json").exists()


def _replay_service(cc: ModuleType, oracle: Any, items: list[dict[str, Any]], project: Any) -> Any:
    """A service that answers every route with the real oracle's own answer: the real oracle must then agree with itself, route by route."""

    class Replay(FakeService):
        def get(self, route: str) -> Any:
            parts = urlsplit(route)
            pieces = parts.path.split("/")
            if len(pieces) < 5 or pieces[3] != "missions":
                return super().get(route)
            detail = oracle.detail
            name = next(name for name in oracle.names() if detail.mission_id(name) == pieces[4])
            tail = pieces[5:]
            if not tail:
                expected = detail.mission_detail(name)
            elif tail == ["artifacts"]:
                expected = detail.artifact_listing(name)
            elif tail == ["artifacts", "content"]:
                expected = detail.artifact_content(name, parse_qs(parts.query)["path"][0])
            elif len(tail) == 3:
                expected = detail.work_package_detail(name, tail[1])
            else:
                expected = detail.work_package(name, tail[1], include_prompt="includePrompt=true" in parts.query)
            if expected.status != 200:
                return cc.Reply(expected.status, json.dumps({"code": expected.body["code"]}).encode())
            return cc.Reply(200, cc.canonical_bytes(expected.body))

    return Replay(cc, items, project=project)


def test_the_real_detail_oracle_agrees_with_a_service_that_replays_it_over_a_scratch_repository(cc: ModuleType, tmp_path: Path) -> None:
    from tests.contract import _mission_status_payloads as helper

    helper.git_init(tmp_path)
    (tmp_path / ".kittify").mkdir()
    (tmp_path / ".kittify" / "config.yaml").write_text("project:\n  slug: fixture\n", encoding="utf-8")
    helper.write_fixture_mission(
        tmp_path,
        "alpha-mission",
        work_packages={"WP01": {"subtasks": ["T001"], "owned_files": ["src/app/**"]}, "WP02": {}},
        planning_files=["spec.md", "plan.md"],
    )
    helper.write_fixture_mission(
        tmp_path, "beta-mission", meta={"mission_id": helper.fixture_ulid(2), "created_at": "2026-09-02T10:00:00+00:00"}, work_packages={"WP01": {}}
    )
    (tmp_path / "kitty-specs" / "beta-mission" / "tasks" / "WP09-broken.md").write_text(
        "---\nwork_package_id: WP09\nmystery_key: 1\n---\n\nbody\n", encoding="utf-8"
    )
    helper.commit_all(tmp_path)
    with cc.open_oracle(tmp_path, REPO_ROOT) as oracle:
        detail = oracle.detail
        records = {name: [(record.file, record.wp_id, record.outcome) for record in detail.decode_records(name)] for name in oracle.names()}
        assert records["alpha-mission"] == [("WP01-fixture.md", "WP01", "decoded"), ("WP02-fixture.md", "WP02", "decoded")]
        assert records["beta-mission"] == [("WP01-fixture.md", "WP01", "decoded"), ("WP09-broken.md", "WP09", "refused")]
        assert detail.work_package_ids("alpha-mission") == ["WP01", "WP02"]
        assert detail.artifact_paths("alpha-mission") == sorted(detail.artifact_paths("alpha-mission")) and "spec.md" in detail.artifact_paths("alpha-mission")
        ordered = oracle.order([oracle.overview(name) for name in oracle.names()])
        service = _replay_service(cc, oracle, ordered, oracle.project())
        report = cc.compare_corpus(
            oracle,
            service,
            independent_count=cc.independent_count(tmp_path),
            floor=2,
            detail=detail,
            floors={"work_packages": 3, "listed_files": 6, "decoded_files": 4},
            work_package_files=cc.independent_work_package_files(tmp_path),
        )
    assert report.exit_code == PASS, report.lines
    assert report.counts["work_packages"] == 3 and report.counts["decoded_files"] == 4


def test_the_work_package_id_of_a_file_name_is_its_prefix(cc: ModuleType) -> None:
    assert cc.wp_id_of_file("WP01-foundation.md") == "WP01"
    assert cc.wp_id_of_file("WP120.md") == "WP120"
    assert cc.wp_id_of_file("notes.md") is None


def test_a_mission_whose_id_resolves_to_another_directory_has_no_route_of_its_own_and_is_counted(cc: ModuleType) -> None:
    oracle, detail, service = _detail_world(cc)
    detail.shadowed.add("mission-02")
    report = _run_detail(cc, oracle, detail, service)
    assert report.exit_code == PASS
    assert report.counts["duplicate_ids"] == 1 and report.counts["missions"] == 1 and report.counts["work_packages"] == 2
    assert "1 duplicate ids" in _said(report)
