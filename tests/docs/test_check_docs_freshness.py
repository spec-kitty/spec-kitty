"""Tests for :mod:`scripts.docs.check_docs_freshness`.

Covers the four exit-code paths required by the contract plus link-health
sampling, completeness, and report serialization. Network access is fully
mocked.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest

# SPEC_KITTY_ENABLE_SAAS_SYNC is set collection-wide in tests/conftest.py
# pytest_configure (#3213), not per-module.
os.environ.setdefault("SPEC_KITTY_NO_UPGRADE_CHECK", "1")

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts.docs import check_docs_freshness as orchestrator  # noqa: E402

pytestmark = [pytest.mark.unit, pytest.mark.fast]


FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_PAGES_DIR = FIXTURES_DIR / "sample_pages"


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


@contextmanager
def chdir(path: Path) -> Iterator[None]:
    """Temporarily change cwd to ``path``."""
    previous = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous)


def _stage_clean(tmp_path: Path) -> Path:
    """Stage a clean workspace with inventory + minimal reference docs."""
    workspace = tmp_path / "clean"
    shutil.copytree(SAMPLE_PAGES_DIR / "clean", workspace)
    shutil.copy(FIXTURES_DIR / "clean_inventory.yaml", workspace / "inventory.yaml")
    # Minimal reference files. The CLI reference check is stubbed via
    # monkeypatching the orchestrator's sub-check invocation.
    (workspace / "ref.md").write_text("# clean reference\n", encoding="utf-8")
    (workspace / "agent.md").write_text("# agent ref\n", encoding="utf-8")
    return workspace


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def test_build_parser_defaults() -> None:
    parser = orchestrator.build_parser()
    args = parser.parse_args([])
    assert args.link_check == "spot"
    assert args.report is None
    assert args.strict_mode is False
    assert args.ci is False


def test_build_parser_accepts_all_flags(tmp_path: Path) -> None:
    parser = orchestrator.build_parser()
    args = parser.parse_args(
        [
            "--inventory",
            str(tmp_path / "i.yaml"),
            "--docs-root",
            str(tmp_path / "docs"),
            "--reference",
            str(tmp_path / "ref.md"),
            "--agent-reference",
            str(tmp_path / "agent.md"),
            "--link-check",
            "none",
            "--report",
            str(tmp_path / "report.json"),
            "--ci",
            "--strict-mode",
            "--random-seed",
            "7",
        ]
    )
    assert args.link_check == "none"
    assert args.ci is True
    assert args.strict_mode is True
    assert args.random_seed == 7


# ---------------------------------------------------------------------------
# Exit code 0 — happy path
# ---------------------------------------------------------------------------


def _stub_subchecks_clean(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make both sub-checks report clean payloads and exit 0."""

    def _fake_leakage(argv: list[str]) -> int:
        report_path = Path(argv[argv.index("--report") + 1])
        report_path.write_text(
            json.dumps(
                {
                    "started_at": "2026-05-21T00:00:00+00:00",
                    "inventory_rows_count": 3,
                    "findings": [],
                    "exit_code": 0,
                }
            ),
            encoding="utf-8",
        )
        return 0

    def _fake_ref(argv: list[str]) -> int:
        report_path = Path(argv[argv.index("--report") + 1])
        report_path.write_text(
            json.dumps({"findings": []}), encoding="utf-8"
        )
        return 0

    monkeypatch.setattr(orchestrator, "_invoke_version_leakage", _fake_leakage)
    monkeypatch.setattr(
        orchestrator, "_invoke_cli_reference_freshness", _fake_ref
    )
    # The inventory-lockfile drift sub-check is now default-on (WP14) and would
    # otherwise regenerate against the staged fixture inventory. It has its own
    # dedicated suite (test_inventory_lockfile.py); isolate it here so these
    # orchestration tests stay focused on aggregation, mirroring the leakage/ref
    # sub-check stubs above.
    monkeypatch.setattr(
        orchestrator, "_check_inventory_lockfile_drift", lambda *_a, **_k: []
    )


def test_happy_path_exits_0(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _stage_clean(tmp_path)
    _stub_subchecks_clean(monkeypatch)
    monkeypatch.setattr(orchestrator, "_SAAS_SYNC_PRESET", True)
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "1")

    with chdir(workspace):
        rc = orchestrator.main(
            [
                "--inventory",
                "inventory.yaml",
                "--docs-root",
                "docs",
                "--reference",
                "ref.md",
                "--agent-reference",
                "agent.md",
                "--link-check",
                "none",
                "--ci",
            ]
        )
    assert rc == 0


def test_happy_path_writes_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _stage_clean(tmp_path)
    _stub_subchecks_clean(monkeypatch)
    monkeypatch.setattr(orchestrator, "_SAAS_SYNC_PRESET", True)

    report_path = workspace / "freshness.json"
    with chdir(workspace):
        rc = orchestrator.main(
            [
                "--inventory",
                "inventory.yaml",
                "--docs-root",
                "docs",
                "--reference",
                "ref.md",
                "--agent-reference",
                "agent.md",
                "--link-check",
                "none",
                "--report",
                str(report_path),
                "--ci",
            ]
        )
    assert rc == 0
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["exit_code"] == 0
    assert payload["saas_sync_flag"] is True
    assert payload["findings"] == []


# ---------------------------------------------------------------------------
# Exit code 1 — sub-check errors aggregate
# ---------------------------------------------------------------------------


def test_one_leak_plus_one_reference_miss_exits_1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _stage_clean(tmp_path)
    monkeypatch.setattr(orchestrator, "_SAAS_SYNC_PRESET", True)

    def _fake_leakage(argv: list[str]) -> int:
        report_path = Path(argv[argv.index("--report") + 1])
        report_path.write_text(
            json.dumps(
                {
                    "started_at": "2026-05-21T00:00:00+00:00",
                    "inventory_rows_count": 3,
                    "findings": [
                        {
                            "rule_id": "LEAK-MISSING-BANNER",
                            "severity": "error",
                            "location": "docs/archive/no-banner.md",
                            "message": "archival page missing banner",
                            "suggested_action": "add banner",
                        }
                    ],
                    "exit_code": 1,
                }
            ),
            encoding="utf-8",
        )
        return 1

    def _fake_ref(argv: list[str]) -> int:
        report_path = Path(argv[argv.index("--report") + 1])
        report_path.write_text(
            json.dumps(
                {
                    "findings": [
                        {
                            "rule_id": "REF-MISSING",
                            "severity": "error",
                            "path": ["foo", "bar"],
                            "detail": "missing in reference",
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        return 1

    monkeypatch.setattr(orchestrator, "_invoke_version_leakage", _fake_leakage)
    monkeypatch.setattr(
        orchestrator, "_invoke_cli_reference_freshness", _fake_ref
    )

    with chdir(workspace):
        rc = orchestrator.main(
            [
                "--inventory",
                "inventory.yaml",
                "--docs-root",
                "docs",
                "--reference",
                "ref.md",
                "--agent-reference",
                "agent.md",
                "--link-check",
                "none",
                "--ci",
            ]
        )
    assert rc == 1


# ---------------------------------------------------------------------------
# Exit code 2 — missing inventory
# ---------------------------------------------------------------------------


def test_missing_inventory_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(orchestrator, "_SAAS_SYNC_PRESET", True)
    (tmp_path / "ref.md").write_text("# ref\n", encoding="utf-8")
    (tmp_path / "agent.md").write_text("# agent\n", encoding="utf-8")

    rc = orchestrator.main(
        [
            "--inventory",
            str(tmp_path / "absent.yaml"),
            "--docs-root",
            str(tmp_path),
            "--reference",
            str(tmp_path / "ref.md"),
            "--agent-reference",
            str(tmp_path / "agent.md"),
            "--link-check",
            "none",
            "--ci",
        ]
    )
    assert rc == 2


def test_missing_reference_exits_2(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(orchestrator, "_SAAS_SYNC_PRESET", True)
    workspace = _stage_clean(tmp_path)
    rc = orchestrator.main(
        [
            "--inventory",
            str(workspace / "inventory.yaml"),
            "--docs-root",
            str(workspace / "docs"),
            "--reference",
            str(workspace / "absent.md"),
            "--agent-reference",
            str(workspace / "agent.md"),
            "--link-check",
            "none",
            "--ci",
        ]
    )
    assert rc == 2


def test_missing_inventory_writes_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(orchestrator, "_SAAS_SYNC_PRESET", True)
    (tmp_path / "ref.md").write_text("# ref\n", encoding="utf-8")
    (tmp_path / "agent.md").write_text("# agent\n", encoding="utf-8")

    report_path = tmp_path / "report.json"
    rc = orchestrator.main(
        [
            "--inventory",
            str(tmp_path / "absent.yaml"),
            "--docs-root",
            str(tmp_path),
            "--reference",
            str(tmp_path / "ref.md"),
            "--agent-reference",
            str(tmp_path / "agent.md"),
            "--link-check",
            "none",
            "--report",
            str(report_path),
            "--ci",
        ]
    )
    assert rc == 2
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["exit_code"] == 2
    assert any(
        f["rule_id"] == "INPUT-MISSING" for f in payload["findings"]
    )


# ---------------------------------------------------------------------------
# Exit code 3 — SaaS sync off
# ---------------------------------------------------------------------------


def test_saas_sync_off_exits_3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _stage_clean(tmp_path)
    monkeypatch.setattr(orchestrator, "_SAAS_SYNC_PRESET", False)
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")

    rc = orchestrator.main(
        [
            "--inventory",
            str(workspace / "inventory.yaml"),
            "--docs-root",
            str(workspace / "docs"),
            "--reference",
            str(workspace / "ref.md"),
            "--agent-reference",
            str(workspace / "agent.md"),
            "--link-check",
            "none",
            "--ci",
        ]
    )
    assert rc == 3


def test_saas_sync_off_writes_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _stage_clean(tmp_path)
    monkeypatch.setattr(orchestrator, "_SAAS_SYNC_PRESET", False)
    monkeypatch.setenv("SPEC_KITTY_ENABLE_SAAS_SYNC", "0")

    report_path = workspace / "report.json"
    rc = orchestrator.main(
        [
            "--inventory",
            str(workspace / "inventory.yaml"),
            "--docs-root",
            str(workspace / "docs"),
            "--reference",
            str(workspace / "ref.md"),
            "--agent-reference",
            str(workspace / "agent.md"),
            "--link-check",
            "none",
            "--report",
            str(report_path),
            "--ci",
        ]
    )
    assert rc == 3
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["exit_code"] == 3
    assert payload["saas_sync_flag"] is False
    assert any(
        f["rule_id"] == "ENV-SAAS-SYNC-OFF" for f in payload["findings"]
    )


# ---------------------------------------------------------------------------
# Link health
# ---------------------------------------------------------------------------


def test_link_check_none_returns_no_findings(tmp_path: Path) -> None:
    findings = orchestrator._check_link_health(
        inventory=tmp_path / "absent.yaml",
        reference=tmp_path / "absent.md",
        mode="none",
        random_seed=None,
    )
    assert findings == []


def test_link_check_spot_emits_warning_for_bad_url(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _stage_clean(tmp_path)
    # Inject an http link into a current page.
    current_page = workspace / "docs" / "current" / "index.md"
    current_page.write_text(
        current_page.read_text(encoding="utf-8")
        + "\n\nSee https://example.invalid/foo\n",
        encoding="utf-8",
    )

    def _fake_probe(url: str) -> str | None:
        if "example.invalid" in url:
            return "HTTP 500"
        return None

    monkeypatch.setattr(orchestrator, "_probe_url", _fake_probe)

    with chdir(workspace):
        findings = orchestrator._check_link_health(
            inventory=Path("inventory.yaml"),
            reference=Path("ref.md"),
            mode="spot",
            random_seed=0,
        )
    assert any(f.rule_id == "LINK-HEALTH-FAILED" for f in findings)
    # Warning severity per contract.
    for f in findings:
        if f.rule_id == "LINK-HEALTH-FAILED":
            assert f.severity == "warning"


def test_link_check_full_visits_all_current_pages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _stage_clean(tmp_path)
    current_page = workspace / "docs" / "current" / "index.md"
    current_page.write_text(
        current_page.read_text(encoding="utf-8")
        + "\n\nhttps://example.test/a\nhttps://example.test/b\n",
        encoding="utf-8",
    )
    probed: list[str] = []

    def _fake_probe(url: str) -> str | None:
        probed.append(url)
        return None

    monkeypatch.setattr(orchestrator, "_probe_url", _fake_probe)

    with chdir(workspace):
        orchestrator._check_link_health(
            inventory=Path("inventory.yaml"),
            reference=Path("ref.md"),
            mode="full",
            random_seed=None,
        )
    assert "https://example.test/a" in probed
    assert "https://example.test/b" in probed


def test_iter_http_links_dedups() -> None:
    text = "see https://example.test/x and https://example.test/x again"
    urls = list(orchestrator._iter_http_links(text))
    assert urls == ["https://example.test/x"]


def test_select_link_check_paths_samples_when_oversize(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    docs = tmp_path / "docs" / "current"
    docs.mkdir(parents=True)
    inventory_lines = []
    for idx in range(25):
        page = docs / f"page-{idx:02d}.md"
        page.write_text("# page\n", encoding="utf-8")
        inventory_lines.append(
            f"- path: docs/current/page-{idx:02d}.md\n"
            f"  tag: current\n  divio_type: how-to\n"
            f"  owning_workstream: E\n  current_target: true\n"
            f"  citation_refs: []\n  notes: null\n"
        )
    inventory = tmp_path / "inventory.yaml"
    inventory.write_text("".join(inventory_lines), encoding="utf-8")
    ref = tmp_path / "ref.md"
    ref.write_text("# ref\n", encoding="utf-8")

    with chdir(tmp_path):
        selected = orchestrator._select_link_check_paths(
            inventory=Path("inventory.yaml"),
            reference=Path("ref.md"),
            mode="spot",
            random_seed=42,
        )
    # 20 sampled + reference appended (deterministic with the seed).
    assert len(selected) == 21  # (sample-size, seed-driven membership)
    assert Path("ref.md") in selected


# ---------------------------------------------------------------------------
# Inventory completeness
# ---------------------------------------------------------------------------


def test_inventory_completeness_flags_orphan(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "orphan.md").write_text("# orphan\n", encoding="utf-8")
    inventory = tmp_path / "inventory.yaml"
    inventory.write_text(
        "- path: docs/other.md\n"
        "  tag: current\n  divio_type: how-to\n"
        "  owning_workstream: E\n  current_target: true\n"
        "  citation_refs: []\n  notes: null\n",
        encoding="utf-8",
    )
    with chdir(tmp_path):
        findings = orchestrator._check_page_inventory_completeness(
            Path("inventory.yaml"), Path("docs")
        )
    assert any(
        f.rule_id == "INVENTORY-INCOMPLETE" and "orphan" in f.location
        for f in findings
    )


def test_inventory_completeness_skips_when_inventory_unreadable(
    tmp_path: Path,
) -> None:
    findings = orchestrator._check_page_inventory_completeness(
        tmp_path / "absent.yaml", tmp_path / "docs"
    )
    assert findings == []


def test_inventory_completeness_skips_when_docs_root_missing(
    tmp_path: Path,
) -> None:
    inventory = tmp_path / "inventory.yaml"
    inventory.write_text("[]\n", encoding="utf-8")
    findings = orchestrator._check_page_inventory_completeness(
        inventory, tmp_path / "absent"
    )
    assert findings == []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def test_coerce_severity_defaults_to_error() -> None:
    assert orchestrator._coerce_severity(None) == "error"
    assert orchestrator._coerce_severity("warning") == "warning"
    assert orchestrator._coerce_severity("anything-else") == "error"


def test_load_report_payload_returns_empty_on_missing(tmp_path: Path) -> None:
    payload = orchestrator._load_report_payload(tmp_path / "absent.json")
    assert payload == {}


def test_load_report_payload_returns_empty_on_malformed(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("not json", encoding="utf-8")
    payload = orchestrator._load_report_payload(path)
    assert payload == {}


def test_load_report_payload_returns_empty_for_non_dict(tmp_path: Path) -> None:
    path = tmp_path / "arr.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    assert orchestrator._load_report_payload(path) == {}


def test_findings_from_payload_skips_non_dict_entries() -> None:
    payload: dict[str, object] = {
        "findings": [
            {"rule_id": "X", "severity": "warning", "location": "l", "message": "m", "suggested_action": "a"},
            "not-a-dict",
            42,
        ]
    }
    out = orchestrator._findings_from_payload(payload)
    assert frozenset(f.rule_id for f in out) == frozenset({"X"})
    assert out[0].severity == "warning"


def test_findings_from_payload_handles_missing_findings() -> None:
    assert orchestrator._findings_from_payload({}) == []


def test_findings_from_cli_reference_payload_normalizes_path_list() -> None:
    payload: dict[str, object] = {
        "findings": [
            {
                "rule_id": "REF-EXTRA",
                "severity": "error",
                "path": ["a", "b"],
                "detail": "stray",
            },
            {
                "rule_id": "REF-MISSING",
                "severity": "error",
                "path": "string-path",
                "detail": "lost",
            },
        ]
    }
    out = orchestrator._findings_from_cli_reference_payload(payload)
    assert out[0].location == "a b"
    assert out[1].location == "string-path"


def test_findings_from_cli_reference_payload_handles_empty() -> None:
    assert orchestrator._findings_from_cli_reference_payload({}) == []


def test_load_inventory_rows_returns_empty_on_bad_yaml(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("not: [valid\n", encoding="utf-8")
    assert orchestrator._load_inventory_rows(bad) == []


def test_load_inventory_rows_returns_empty_on_non_list(tmp_path: Path) -> None:
    not_list = tmp_path / "scalar.yaml"
    not_list.write_text("hello: world\n", encoding="utf-8")
    assert orchestrator._load_inventory_rows(not_list) == []


def test_load_inventory_rows_drops_non_mapping_entries(tmp_path: Path) -> None:
    mixed = tmp_path / "mixed.yaml"
    mixed.write_text("- path: a\n- not-a-mapping\n", encoding="utf-8")
    rows = orchestrator._load_inventory_rows(mixed)
    assert rows == [{"path": "a"}]


def test_cli_version_returns_string() -> None:
    version = orchestrator._cli_version()
    assert isinstance(version, str) and version


def test_now_iso_is_iso8601() -> None:
    from kernel.clock import parse_iso

    s = orchestrator._now_iso()
    parsed = parse_iso(s)
    assert parsed.tzinfo is not None


def test_tempfile_path_is_unique(tmp_path: Path) -> None:
    a = orchestrator._tempfile_path()
    b = orchestrator._tempfile_path()
    assert a != b
    a.unlink(missing_ok=True)
    b.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# run_orchestrator direct
# ---------------------------------------------------------------------------


def test_run_orchestrator_clean_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _stage_clean(tmp_path)
    _stub_subchecks_clean(monkeypatch)
    with chdir(workspace):
        report = orchestrator.run_orchestrator(
            inventory=Path("inventory.yaml"),
            docs_root=Path("docs"),
            reference=Path("ref.md"),
            agent_reference=Path("agent.md"),
            link_check="none",
            strict_mode=False,
            saas_sync_enabled=True,
        )
    assert report.exit_code == 0
    assert report.saas_sync_flag is True


def test_run_orchestrator_strict_mode_flag_propagates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = _stage_clean(tmp_path)
    seen_argv: dict[str, list[str]] = {}

    def _fake_leakage(argv: list[str]) -> int:
        report_path = Path(argv[argv.index("--report") + 1])
        report_path.write_text(
            json.dumps(
                {"inventory_rows_count": 0, "findings": [], "exit_code": 0}
            ),
            encoding="utf-8",
        )
        return 0

    def _fake_ref(argv: list[str]) -> int:
        seen_argv["ref"] = list(argv)
        report_path = Path(argv[argv.index("--report") + 1])
        report_path.write_text(json.dumps({"findings": []}), encoding="utf-8")
        return 0

    monkeypatch.setattr(orchestrator, "_invoke_version_leakage", _fake_leakage)
    monkeypatch.setattr(
        orchestrator, "_invoke_cli_reference_freshness", _fake_ref
    )
    monkeypatch.setattr(
        orchestrator, "_check_inventory_lockfile_drift", lambda *_a, **_k: []
    )

    with chdir(workspace):
        report = orchestrator.run_orchestrator(
            inventory=Path("inventory.yaml"),
            docs_root=Path("docs"),
            reference=Path("ref.md"),
            agent_reference=Path("agent.md"),
            link_check="none",
            strict_mode=True,
            saas_sync_enabled=True,
        )
    assert "--strict-mode" in seen_argv["ref"]
    assert report.exit_code == 0


def test_emit_report_in_ci_mode_writes_to_stdout(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    report = orchestrator.FreshnessReport(
        started_at="2026-05-21T00:00:00+00:00",
        cli_version="test",
        visible_paths_count=0,
        reference_entries_count=0,
        inventory_rows_count=0,
        findings=[
            orchestrator.FreshnessFinding(
                rule_id="X",
                severity="warning",
                location="l",
                message="m",
                suggested_action="a",
            )
        ],
        saas_sync_flag=True,
        exit_code=0,
    )
    report_path = tmp_path / "r.json"
    orchestrator._emit_report(report, ci=True, report_path=report_path)
    out = capsys.readouterr().out
    assert "WARNING X" in out
    assert "exit=0" in out
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["findings"][0]["rule_id"] == "X"


def test_probe_url_handles_bad_url() -> None:
    err = orchestrator._probe_url("not-a-url")
    assert err is not None


def test_probe_url_handles_url_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import urllib.error

    def _raise(*_args: object, **_kwargs: object) -> object:
        raise urllib.error.URLError("boom")

    monkeypatch.setattr(orchestrator.urllib.request, "urlopen", _raise)
    err = orchestrator._probe_url("https://example.test/")
    assert err is not None and "boom" in err


def test_probe_url_handles_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import io
    import urllib.error

    def _raise(*_args: object, **_kwargs: object) -> object:
        raise urllib.error.HTTPError(
            url="https://example.test/",
            code=500,
            msg="server error",
            hdrs=None,  # type: ignore[arg-type]
            fp=io.BytesIO(b""),
        )

    monkeypatch.setattr(orchestrator.urllib.request, "urlopen", _raise)
    err = orchestrator._probe_url("https://example.test/")
    assert err == "HTTP 500"


def test_probe_url_handles_2xx(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Resp:
        status = 200

        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def getcode(self) -> int:
            return 200

    monkeypatch.setattr(
        orchestrator.urllib.request, "urlopen", lambda *a, **k: _Resp()
    )
    assert orchestrator._probe_url("https://example.test/") is None
