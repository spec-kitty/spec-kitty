"""Planted-violation tests for ``contracts/tools/verify_pins.py`` (FR-018, NFR-003, C-005).

One committed fixture root, ``contracts/tools/fixtures/verify_pins/``, holds a clean control
(``clean``: a manifest of two tools, a local copy of the first archive that matches its pinned
checksum, and a workflow that is exactly the shared install prelude) and one root per planted
violation. Each rule is asserted by its stable code on its own root while the control stays clean.
The verifier never writes ``pins.json``; these roots are throw-away fixture manifests.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

pytestmark = [pytest.mark.contract, pytest.mark.fast, pytest.mark.corpus]

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOLS_DIR = REPO_ROOT / "contracts" / "tools"
FIXTURE_ROOT = TOOLS_DIR / "fixtures" / "verify_pins"
SCRIPT = TOOLS_DIR / "verify_pins.py"

# fixture root -> exactly the codes it must produce, sorted
PLANTED = {
    "v_checksum_mismatch": ["CHECKSUM_MISMATCH"],
    "v_checksum_missing": ["CHECKSUM_MISSING"],
    "v_not_https": ["NOT_HTTPS"],
    "v_publication_date_missing": ["PUBLICATION_DATE_MISSING"],
    "v_unpinned_uses_tag": ["UNPINNED_USES"],
    "v_unpinned_uses_branch": ["UNPINNED_USES"],
    "v_unpinned_install_pip": ["UNPINNED_INSTALL"],
    "v_unpinned_install_unfrozen": ["UNPINNED_INSTALL"],
    "v_unpinned_install_not_prelude": ["UNPINNED_INSTALL"],
}
EXIT2 = {"empty_manifest": "MANIFEST_EMPTY", "zero_tools_verified": "ZERO_TOOLS_VERIFIED", "zero_uses_lines": "ZERO_USES_LINES"}


@pytest.fixture(scope="module")
def pins() -> Any:
    sys.path.insert(0, str(TOOLS_DIR))
    try:
        spec = importlib.util.spec_from_file_location("verify_pins_under_test", SCRIPT)
        assert spec is not None and spec.loader is not None, f"cannot load {SCRIPT}"
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(TOOLS_DIR))
    return module


def _run(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(SCRIPT), *arguments], capture_output=True, text=True, check=False, cwd=REPO_ROOT)


def _case(case: str) -> list[str]:
    root = FIXTURE_ROOT / case
    return ["--root", str(root), "--artifacts", str(root / "artifacts")]


def _counts(stdout: str) -> dict[str, int]:
    return {key: int(value) for key, value in (pair.split("=") for pair in stdout.splitlines()[-1].removeprefix("counts: ").split())}


@pytest.mark.parametrize(("case", "codes"), sorted(PLANTED.items()))
def test_each_planted_violation_gives_its_stable_code(pins: Any, case: str, codes: list[str]) -> None:
    root = FIXTURE_ROOT / case
    report = pins.check(root, artifacts=root / "artifacts")
    assert sorted(f.code for f in report.findings) == codes
    assert report.blocked == []
    assert report.exit_code == 1


def test_the_clean_control_has_no_finding_and_the_floors_are_met(pins: Any) -> None:
    root = FIXTURE_ROOT / "clean"
    report = pins.check(root, artifacts=root / "artifacts")
    assert report.findings == []
    assert report.blocked == []
    assert report.exit_code == 0
    assert report.counts == {"tools": 2, "uses_lines": 2, "downloads": 1}


def test_a_checksum_mismatch_names_the_tool_and_both_digests(pins: Any) -> None:
    root = FIXTURE_ROOT / "v_checksum_mismatch"
    (finding,) = pins.check(root, artifacts=root / "artifacts").findings
    assert finding.subject.endswith("pins.json")
    assert "gradle" in finding.detail
    assert "b" * 64 in finding.detail


def test_without_artifacts_or_fetch_nothing_is_downloaded_and_the_manifest_is_still_checked(pins: Any) -> None:
    report = pins.check(FIXTURE_ROOT / "v_checksum_mismatch")
    assert report.findings == []
    assert report.counts["downloads"] == 0
    assert [f.code for f in pins.check(FIXTURE_ROOT / "v_checksum_missing").findings] == ["CHECKSUM_MISSING"]


def test_fetch_mode_downloads_through_the_injected_function(pins: Any) -> None:
    clean = FIXTURE_ROOT / "clean"
    payload = (clean / "artifacts" / "tool-1.0.bin").read_bytes()
    fetched: list[str] = []

    def fetch(url: str) -> bytes:
        fetched.append(url)
        return payload

    report = pins.check(clean, fetch=fetch)
    # the payload matches the first tool only; the second tool's pinned digest is a placeholder
    assert [(f.code, "plugin" in f.detail) for f in report.findings] == [("CHECKSUM_MISMATCH", True)]
    assert report.counts["downloads"] == 2
    assert all(url.startswith("https://") for url in fetched)
    bad = pins.check(clean, fetch=lambda _url: b"other bytes")
    assert [f.code for f in bad.findings] == ["CHECKSUM_MISMATCH", "CHECKSUM_MISMATCH"]


def test_a_non_https_url_is_never_fetched(pins: Any) -> None:
    fetched: list[str] = []
    report = pins.check(FIXTURE_ROOT / "v_not_https", fetch=lambda url: fetched.append(url) or b"")
    assert "NOT_HTTPS" in [f.code for f in report.findings]
    assert fetched == ["https://example.invalid/plugin-2.0.jar"]


def test_a_malformed_checksum_counts_as_missing(pins: Any, tmp_path: Path) -> None:
    root = tmp_path / "root"
    shutil.copytree(FIXTURE_ROOT / "clean", root)
    manifest = root / "contracts" / "tools" / "pins.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["tools"][0]["sha256"] = "not-a-digest"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    assert [f.code for f in pins.check(root).findings] == ["CHECKSUM_MISSING"]


def test_a_malformed_publication_date_counts_as_missing(pins: Any, tmp_path: Path) -> None:
    root = tmp_path / "root"
    shutil.copytree(FIXTURE_ROOT / "clean", root)
    manifest = root / "contracts" / "tools" / "pins.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["tools"][1]["published"] = "last spring"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    assert [f.code for f in pins.check(root).findings] == ["PUBLICATION_DATE_MISSING"]


@pytest.mark.parametrize(
    "line",
    [
        "pip install pyyaml",
        "python -m pip install -r requirements.txt",
        "pip3 install jsonschema",
        "uv pip install pyyaml",
        "uv sync",
        "uv sync --frozen",
        "uv sync --no-install-project",
        "uv sync --frozen --no-install-project --all-extras",
        "uv run python contracts/tools/structure_check.py",
    ],
)
def test_every_install_form_other_than_the_prelude_is_unpinned(pins: Any, tmp_path: Path, line: str) -> None:
    root = tmp_path / "root"
    shutil.copytree(FIXTURE_ROOT / "clean", root)
    workflow = root / ".github" / "workflows" / "contracts.yml"
    workflow.write_text(workflow.read_text(encoding="utf-8") + f"      - run: {line}\n", encoding="utf-8")
    assert [f.code for f in pins.check(root).findings] == ["UNPINNED_INSTALL"]


def test_a_sync_without_the_pinned_python_setup_is_unpinned(pins: Any, tmp_path: Path) -> None:
    root = tmp_path / "root"
    shutil.copytree(FIXTURE_ROOT / "clean", root)
    workflow = root / ".github" / "workflows" / "contracts.yml"
    workflow.write_text(workflow.read_text(encoding="utf-8").replace("'3.12'", "'3.13'"), encoding="utf-8")
    assert [f.code for f in pins.check(root).findings] == ["UNPINNED_INSTALL"]


def test_local_and_container_uses_are_judged_by_their_own_rule(pins: Any, tmp_path: Path) -> None:
    root = tmp_path / "root"
    shutil.copytree(FIXTURE_ROOT / "clean", root)
    workflow = root / ".github" / "workflows" / "contracts.yml"
    base = workflow.read_text(encoding="utf-8")
    workflow.write_text(base + "      - uses: ./.github/actions/local\n", encoding="utf-8")
    assert pins.check(root).findings == []
    workflow.write_text(base + "      - uses: docker://alpine:3\n", encoding="utf-8")
    assert [f.code for f in pins.check(root).findings] == ["UNPINNED_USES"]


@pytest.mark.parametrize(("case", "code"), sorted(EXIT2.items()))
def test_a_check_that_cannot_do_its_job_exits_two_with_its_code(pins: Any, case: str, code: str) -> None:
    root = FIXTURE_ROOT / "exit2" / case
    report = pins.check(root)
    assert code in [f.code for f in report.blocked]
    assert report.exit_code == 2
    result = _run("--root", str(root))
    assert result.returncode == 2
    assert f"CONTRACT-CHECK verify_pins: {code}" in result.stdout
    assert result.stdout.rstrip().splitlines()[-1].startswith("counts: tools=")


def test_an_unreadable_manifest_exits_two(pins: Any, tmp_path: Path) -> None:
    root = tmp_path / "root"
    shutil.copytree(FIXTURE_ROOT / "clean", root)
    (root / "contracts" / "tools" / "pins.json").write_text("{not json", encoding="utf-8")
    report = pins.check(root)
    assert "MANIFEST_EMPTY" in [f.code for f in report.blocked]
    assert report.exit_code == 2


def test_command_line_output_grammar_and_exit_status() -> None:
    result = _run(*_case("v_unpinned_uses_tag"))
    assert result.returncode == 1
    lines = result.stdout.splitlines()
    assert lines[-1] == "counts: tools=2 uses_lines=2 downloads=1"
    assert any(line.startswith("CONTRACT-CHECK verify_pins: UNPINNED_USES: ") for line in lines)
    clean = _run(*_case("clean"))
    assert clean.returncode == 0, clean.stdout
    assert clean.stdout.splitlines()[-1] == "counts: tools=2 uses_lines=2 downloads=1"


def test_the_real_manifest_and_workflows_pass_with_floors() -> None:
    result = _run("--root", str(REPO_ROOT))
    assert result.returncode == 0, result.stdout
    counts = _counts(result.stdout)
    assert counts["tools"] >= 2
    assert counts["uses_lines"] >= 6


def test_the_checksum_primitive_carries_its_integrity_rationale() -> None:
    sha_lines = [line for line in SCRIPT.read_text(encoding="utf-8").splitlines() if ".sha256(" in line]
    assert sha_lines
    assert all("noqa: TID251" in line for line in sha_lines)
