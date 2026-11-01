"""The events cut-over is complete: core holds no copy of the events domain's service and contracts (ADR 2026-10-29-1, #6915).

The read and write services, the ``mission-status`` / ``mission-write`` contract modules and the contract tools live in
``spec-kitty/spec-kitty-events``; core pins one release of them (``pins/read-service.source.yaml``) and reads the released
assets from the shared cache. This gate keeps the copies gone:

* ``services/`` and the three workflows that built and released the copies do not exist;
* ``contracts/`` holds only the five core-owned client fixtures;
* no CI, build, packaging or script file names a removed path by its repository-root spelling. A path below an unpacked
  extra (``"$(... --extras-path read-service:contract_tools)/contracts/tools/..."``) is the pinned asset, not a copy, so
  the scan anchors on root spellings, as the oracle's own gate does (``tests/contract/test_mission_status_payloads.py``).

It replaces the freeze gate (``test_events_import_frozen.py``, ADR D-9) on the always-on ``architectural-fast`` roster.
Non-vacuity: the scanner is run on planted text, positive and negative.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from kernel.service_pin import PINS_DIR, load_service_pin, pin_file

pytestmark = pytest.mark.architectural

REPO_ROOT = Path(__file__).resolve().parents[2]
REMOVED_WORKFLOWS = ("mission-status-api.yml", "contracts.yml", "contracts-release.yml")
CORE_FIXTURES = frozenset(
    {
        "fixture_01_single_wp_status_changed.json",
        "fixture_02_mixed_batch.json",
        "fixture_03_duplicate_event.json",
        "fixture_04_rejected_event.json",
        "fixture_05_http_400_error.json",
    }
)
_ROOT = "contracts"
_SERVICE_ROOT = "services/mission-status-api"
# Root-anchored paths: either bare and not preceded by a path character, a closing parenthesis (a command substitution's
# result, e.g. the unpacked extra) or a placeholder's ``>``, or with a leading ``/`` (CODEOWNERS) at the start of a line or after
# whitespace or a quote.
_REMOVED = "(?:" + re.escape(_SERVICE_ROOT) + "|" + _ROOT + r"/(?:tools|mission-status|mission-write))\b"
_ROOT_PATHS = re.compile(r"(?<![\w/.)$>-])" + _REMOVED + r"|(?:^|(?<=[\s'\"`]))/" + _REMOVED, re.MULTILINE)
# Workflow file names: anywhere, as a whole name (``.github/workflows/contracts.yml`` included).
_WORKFLOW_NAMES = re.compile(r"(?<![\w.-])(?:" + "|".join(re.escape(name) for name in REMOVED_WORKFLOWS) + r")(?![\w.-])")
_TEXT_SUFFIXES = frozenset({".py", ".sh"})


def leftover_references(text: str) -> list[str]:
    """Every root spelling of a removed path or workflow in *text*."""
    return [match.group(0) for pattern in (_ROOT_PATHS, _WORKFLOW_NAMES) for match in pattern.finditer(text)]


def _scanned_files(root: Path) -> list[Path]:
    # Every .github file except its Markdown pages (CHANGELOG, CONTRIBUTING, templates: prose and history, WP08's).
    files = [path for path in (root / ".github").rglob("*") if path.is_file() and path.suffix != ".md"]
    files += [root / name for name in ("Makefile", "pyproject.toml", ".gitattributes", "NOTICE") if (root / name).is_file()]
    files += [path for path in (root / "scripts").rglob("*") if path.is_file() and path.suffix in _TEXT_SUFFIXES]
    files += [path for path in (root / "acceptance-jvm").rglob("*") if path.is_file() and "build" not in path.relative_to(root / "acceptance-jvm").parts[:1]]
    return sorted(files)


def leftovers_under(root: Path) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for path in _scanned_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        hits = leftover_references(text)
        if hits:
            found[str(path.relative_to(root))] = sorted(set(hits))
    return found


def test_services_and_the_three_workflows_are_gone() -> None:
    assert not (REPO_ROOT / "services").exists(), "services/ moved to spec-kitty-events"
    present = [name for name in REMOVED_WORKFLOWS if (REPO_ROOT / ".github" / "workflows" / name).exists()]
    assert present == [], present


def test_contracts_holds_only_the_core_owned_fixtures() -> None:
    assert sorted(path.name for path in (REPO_ROOT / _ROOT).iterdir()) == ["fixtures"]
    fixtures = REPO_ROOT / _ROOT / "fixtures"
    assert {path.name for path in fixtures.iterdir()} == CORE_FIXTURES


def test_no_ci_build_or_script_file_names_a_removed_path() -> None:
    assert leftovers_under(REPO_ROOT) == {}


def test_the_scan_covers_the_named_places() -> None:
    scanned = {str(path.relative_to(REPO_ROOT)) for path in _scanned_files(REPO_ROOT)}
    for expected in (
        ".github/workflows/ci-router.yml",
        ".github/actions/sync-services/action.yml",
        ".github/CODEOWNERS",
        "Makefile",
        "pyproject.toml",
        ".gitattributes",
        "NOTICE",
        "scripts/sync_services.py",
        "acceptance-jvm/build.gradle",
    ):
        assert expected in scanned, expected


@pytest.mark.parametrize(
    "planted",
    [
        "python " + _ROOT + "/tools/install_tools.py --pins x",
        "  - '" + _SERVICE_ROOT + "/**'",
        "read " + _ROOT + "/mission-status/openapi.yaml",
        "/" + _ROOT + "/mission-write/ @owner",
        "uses: ./.github/workflows/" + REMOVED_WORKFLOWS[1],
        "workflows: [" + REMOVED_WORKFLOWS[0] + "]",
        "on: workflow_run: " + REMOVED_WORKFLOWS[2],
    ],
)
def test_the_scanner_sees_a_planted_reference(planted: str) -> None:
    assert leftover_references(planted), planted


@pytest.mark.parametrize(
    "clean",
    [
        'tools="$(python scripts/sync_services.py --extras-path read-service:contract_tools)/' + _ROOT + '/tools"',
        "<extra>/" + _ROOT + "/tools/codeowners_check.py",
        "- '" + _ROOT + "/fixtures/**'",
        "tests/ci/test_" + _ROOT + "_routing.py",
        "mission-status-api-0.1.0-rc.1-linux-x64",
    ],
)
def test_the_scanner_lets_a_pinned_extra_path_and_unrelated_names_through(clean: str) -> None:
    assert leftover_references(clean) == [], clean


def test_a_planted_file_in_a_scanned_place_is_reported(tmp_path: Path) -> None:
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("run: python " + _ROOT + "/tools/x.py\n", encoding="utf-8")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "clean.py").write_text("print('fine')\n", encoding="utf-8")
    assert leftovers_under(tmp_path) == {".github/workflows/ci.yml": [_ROOT + "/tools"]}


def test_the_replacement_pin_loads() -> None:
    pin = load_service_pin(pin_file(REPO_ROOT / PINS_DIR, "read-service"))
    assert pin.service == "read-service"
    assert pin.extras, "the pin names the contract and fixture extras the copies were replaced by"
