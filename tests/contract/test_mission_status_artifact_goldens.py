"""The artifact conformance goldens are the Python reference reader's current answers (mission mission-status-artifact-reads, #957).

``artifact-conformance/golden.json`` of the pinned ``conformance-fixtures`` asset is what the Java service is compared against
(``ArtifactConformanceTest``). These tests keep it honest: it must equal what ``_mission_status_artifact_goldens`` builds from the
reference now, every case of ``cases.json`` must have answers for each request, and a planted difference must be seen.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.contract import _mission_status_artifact_goldens as goldens
from tests.pinned_service_assets import require_pinned_extra

pytestmark = [pytest.mark.contract, pytest.mark.fast]


@pytest.fixture(scope="module", autouse=True)
def _pinned_fixtures() -> Path:
    """Fail closed (never skip) before any test reads the pinned fixtures: ``make sync-services`` fetches them."""
    return require_pinned_extra("fixtures")


def _can_symlink(tmp_path: Path) -> bool:
    try:
        (tmp_path / "link").symlink_to(tmp_path)
    except OSError:
        return False
    return True


@pytest.fixture(scope="module")
def built(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    if not _can_symlink(tmp_path_factory.mktemp("symlink-probe")):
        pytest.skip("NOT RUN ON THIS LEG: the runner cannot create a symbolic link, which two cases need")
    return goldens.build_goldens(goldens.load_cases())


def test_the_committed_goldens_are_the_reference_answers(built: dict[str, object]) -> None:
    assert goldens.GOLDEN_FILE.read_text(encoding="utf-8") == goldens.render(built)


def test_every_case_has_one_answer_per_request(built: dict[str, object]) -> None:
    cases = goldens.load_cases()["cases"]
    answers = built["cases"]
    assert isinstance(answers, dict)
    assert sorted(answers) == sorted(case["name"] for case in cases)
    for case in cases:
        assert [answer["request"] for answer in answers[case["name"]]] == case["requests"]


def test_every_status_of_both_operations_is_exercised(built: dict[str, object]) -> None:
    answers = built["cases"]
    assert isinstance(answers, dict)
    seen = {(answer["request"]["op"], answer["status"]) for case in answers.values() for answer in case}
    assert {("list", 200), ("list", 404)} <= seen
    assert {("content", status) for status in (200, 400, 404, 413, 415, 422)} <= seen


def test_no_literal_credential_or_host_path_is_committed() -> None:
    text = goldens.CASES_FILE.read_text(encoding="utf-8") + goldens.GOLDEN_FILE.read_text(encoding="utf-8")
    for needle in ("gh" + "p_", "AK" + "IA", "BEGIN " + "RSA", "/" + "home/alice", "alice" + "@"):
        assert needle not in text


def test_a_planted_difference_is_seen(built: dict[str, object], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    planted = json.loads(goldens.render(built))
    planted["cases"]["populated"][1]["body"]["content"] = "# Planted\n"
    target = tmp_path / "golden.json"
    target.write_text(json.dumps(planted, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    monkeypatch.setattr(goldens, "GOLDEN_FILE", target)
    assert goldens.main(["--check"]) == 1


def test_write_needs_an_explicit_root_because_the_pinned_fixtures_are_read_only() -> None:
    with pytest.raises(SystemExit) as raised:
        goldens.main(["--write"])
    assert raised.value.code == 2


def test_write_with_a_root_writes_there_and_check_then_passes(built: dict[str, object], tmp_path: Path) -> None:
    target = tmp_path / "artifact-conformance"
    target.mkdir()
    (target / "cases.json").write_bytes(goldens.CASES_FILE.read_bytes())

    assert goldens.main(["--write", "--root", str(tmp_path)]) == 0
    assert (target / "golden.json").read_text(encoding="utf-8") == goldens.render(built)
    assert goldens.main(["--check", "--root", str(tmp_path)]) == 0


def test_masking_replaces_host_dependent_and_long_values() -> None:
    long_body = goldens.masked({"content": "x" * (goldens.LONG_CONTENT + 1)})
    assert str(long_body["content"]).startswith("<sha256:")
    assert goldens.masked({"content": "short"}) == {"content": "short"}
    listing = goldens.masked({"entries": [{"path": "a", "modifiedAt": "2026-09-22T10:30:00Z"}]})
    assert listing == {"entries": [{"path": "a", "modifiedAt": goldens.MODIFIED_AT_MARKER}]}


def test_tree_entries_decode_every_content_form() -> None:
    assert goldens.entry_bytes({"text": "a"}) == b"a"
    assert goldens.entry_bytes({"base64": "YQBi"}) == b"a\x00b"
    assert goldens.entry_bytes({"repeat": {"byte": 120, "count": 3}}) == b"xxx"
    assert goldens.entry_bytes({"parts": ["a", "b"]}) == b"ab"
    with pytest.raises(ValueError, match="no content"):
        goldens.entry_bytes({"path": "x"})
