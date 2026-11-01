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

from tests.pinned_service_assets import contract_tools_dir, service_cache_root

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


def _preflight_on_the_real_cache(cc: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    """In-process ``main`` runs under the per-worker test HOME: point the bundle preflight at the real service cache."""
    real = cc.preflight_contract_bundle
    monkeypatch.setattr(cc, "preflight_contract_bundle", lambda: real(cache_root=service_cache_root()))


def test_main_writes_the_report_and_returns_the_exit_code(cc: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _preflight_on_the_real_cache(cc, monkeypatch)
    oracle, service = _twin(cc, 2)
    service.items = [dict(item, wpTotal=77) for item in service.items]
    from contextlib import nullcontext

    monkeypatch.setattr(cc, "open_oracle", lambda root, tools_root=None: nullcontext(oracle))
    monkeypatch.setattr(cc, "default_tools_root", lambda root: tmp_path / "tools")
    monkeypatch.setattr(cc, "HttpService", lambda base_url, **_: service)
    monkeypatch.setattr(cc, "independent_count", lambda root: 2)
    monkeypatch.setattr(cc, "FLOOR", 1)
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
    with cc.open_oracle(repo, contract_tools_dir()) as oracle:
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


# --- where the contract tools come from (#6915) ----------------------------------------------------------------------------------


def test_the_default_tools_root_is_the_pinned_contract_tools_extra(cc: ModuleType) -> None:
    assert cc.default_tools_root(REPO_ROOT, cache_root=service_cache_root()) == contract_tools_dir()
    assert (cc.default_tools_root(REPO_ROOT, cache_root=service_cache_root()) / "contract_resolver.py").is_file()


def test_a_tools_extra_missing_from_the_cache_is_refused_with_its_service_code(cc: ModuleType, tmp_path: Path) -> None:
    with pytest.raises(cc.ToolsRootUnavailable) as refused:
        cc.default_tools_root(REPO_ROOT, cache_root=tmp_path / "empty-cache")
    assert refused.value.code.startswith("SERVICE_"), refused.value.code


def _main_capturing_the_tools_root(cc: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *extra: str) -> list[Path | None]:
    from contextlib import nullcontext

    _preflight_on_the_real_cache(cc, monkeypatch)
    oracle, service = _twin(cc, 2)
    seen: list[Path | None] = []

    def capture(root: Path, tools_root: Path | None = None) -> Any:
        seen.append(tools_root)
        return nullcontext(oracle)

    monkeypatch.setattr(cc, "open_oracle", capture)
    monkeypatch.setattr(cc, "HttpService", lambda base_url, **_: service)
    monkeypatch.setattr(cc, "independent_count", lambda root: 2)
    monkeypatch.setattr(cc, "FLOOR", 1)
    code = cc.main(["--base-url", "http://127.0.0.1:8787", "--repo-root", str(tmp_path), "--report", str(tmp_path / "r.json"), *extra])
    assert code == PASS
    return seen


def test_main_hands_the_tools_root_flag_to_the_oracle(cc: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    planted = tmp_path / "planted-tools"
    monkeypatch.setattr(cc, "default_tools_root", lambda root: pytest.fail("the default must not be resolved when --tools-root is given"))
    assert _main_capturing_the_tools_root(cc, tmp_path, monkeypatch, "--tools-root", str(planted)) == [planted]


def test_main_defaults_to_the_pinned_tools_of_the_repo_root(cc: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    default = tmp_path / "pinned-tools"
    asked: list[Path] = []

    def pinned(root: Path) -> Path:
        asked.append(root)
        return default

    monkeypatch.setattr(cc, "default_tools_root", pinned)
    assert _main_capturing_the_tools_root(cc, tmp_path, monkeypatch) == [default]
    assert asked == [tmp_path]


def test_main_without_the_pinned_tools_cannot_do_its_job_and_names_the_code(
    cc: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def missing(root: Path) -> Path:
        raise cc.ToolsRootUnavailable("SERVICE_BINARY_MISSING")

    _preflight_on_the_real_cache(cc, monkeypatch)
    monkeypatch.setattr(cc, "default_tools_root", missing)
    monkeypatch.setattr(cc, "independent_count", lambda root: 2)
    code = cc.main(["--base-url", "http://127.0.0.1:8787", "--repo-root", str(tmp_path), "--report", str(tmp_path / "r.json")])
    assert code == CANNOT
    out = capsys.readouterr().out
    assert "SERVICE_BINARY_MISSING" in out and str(tmp_path) not in out


def test_the_bundle_preflight_passes_on_the_pinned_cache_and_refuses_an_empty_one(cc: ModuleType, tmp_path: Path) -> None:
    cc.preflight_contract_bundle(cache_root=service_cache_root())
    with pytest.raises(cc.PinnedExtraUnavailable) as refused:
        cc.preflight_contract_bundle(cache_root=tmp_path / "empty-cache")
    assert refused.value.code.startswith("SERVICE_") and refused.value.extra == "contracts"


def _cache_with_only_the_tools_extra(cache: Path) -> None:
    """A service cache holding the pinned contract-tools archive and nothing else (no contract bundle)."""
    import shutil

    tools_archive = next(path for path in (service_cache_root() / "read-service").glob("*/contract-tools-*.tar.gz"))
    target = cache / "spec-kitty" / "services" / tools_archive.relative_to(service_cache_root())
    target.parent.mkdir(parents=True)
    shutil.copy2(tools_archive, target)


@pytest.mark.parametrize("given_tools_root", [True, False], ids=["tools-root-given", "tools-only-cache"])
def test_a_missing_contract_bundle_is_exit_2_naming_its_code_and_no_path(tmp_path: Path, given_tools_root: bool) -> None:
    cache = tmp_path / "cache"
    cache.mkdir()
    arguments = ["--base-url", "http://127.0.0.1:9", "--repo-root", str(REPO_ROOT), "--report", str(tmp_path / "r.json")]
    if given_tools_root:
        arguments += ["--tools-root", str(contract_tools_dir())]
    else:
        _cache_with_only_the_tools_extra(cache)
    environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    environment["XDG_CACHE_HOME"] = str(cache)
    result = subprocess.run([sys.executable, str(SCRIPT), *arguments], cwd=tmp_path, env=environment, capture_output=True, text=True, check=False)
    assert result.returncode == CANNOT, (result.stdout, result.stderr)
    assert "contracts extra" in result.stdout and "SERVICE_" in result.stdout, result.stdout
    assert str(tmp_path) not in result.stdout + result.stderr and str(service_cache_root()) not in result.stdout + result.stderr
    assert "Traceback" not in result.stderr


def test_the_oracle_loads_its_tools_from_a_planted_tools_root(cc: ModuleType, tmp_path: Path) -> None:
    import shutil

    planted = tmp_path / "planted-tools"
    shutil.copytree(contract_tools_dir(), planted)
    (tmp_path / "repo").mkdir()
    repo = _fixture_repo(tmp_path / "repo")
    with cc.open_oracle(repo, planted) as oracle:
        assert Path(oracle._tools.resolver.__file__).resolve().parent == planted.resolve()
