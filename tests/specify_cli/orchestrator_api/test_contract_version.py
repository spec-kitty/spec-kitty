"""WP07 (design-phase-orchestrator-api-01M1HE6M) -- CONTRACT_VERSION bump to
1.4.0.

(Superseded repeatedly since. The pin's current value is whatever ``envelope.CONTRACT_VERSION``
is — this module is the only place allowed to spell it, so read the assertion, not this paragraph.
It read ``1.14.0`` after the safe-commit verbs gained three ``SAFE_COMMIT_*`` error codes (#5443);
it read ``1.13.0`` after ``start-implementation`` gained the ``STATUS_LOCK_HELD`` envelope (#5819); it read ``1.12.0`` after
governed planning (#5846) added six verbs; it read ``1.11.0`` after ``accept-mission`` and
``consolidate-mission`` gained ``--origin-check`` and the stale/unreachable-origin refusal with
``data.preflight_error_code(s)`` / ``data.origin_freshness``; it read ``1.10.0`` after
``consolidate-mission`` gained the pre-merge approved-bound refusal and its ``data.preflight_error_code`` (#5668); it read
``1.9.0`` after the failure envelope's ``data`` gained ``teardown_error_code`` (#5613), and
``1.8.0`` after WP06 of requirement-id-grammar-01M3NRCA made the ``tasks`` verb's pass-through
``data`` additive (``parsed_spec_ids`` / ``rejected_requirement_refs`` /
``success_criteria_coverage``) and the ``plan`` verb's ``data`` additive
(``requirement_id_warnings``) plus remapped its previously-unregistered
delegate error codes onto the closed ``PLAN_SETUP_FAILED`` envelope with
``data.reason``; the 1.4.0 narrative is kept as the WP's historical record.
It was previously superseded to ``1.5.0`` by the ``tasks`` pass-through
``planning_commit`` object (#4141), then to ``1.6.0`` by the
``planning_commit.action`` vocabulary gaining ``"repinned"`` (#4827), then to
``1.7.0`` by ``accept-mission`` applying the host readiness verdict (#4934).)

This module is the canonical pin: ``test_contract_version_response_reports_the_current_contract_version``
is the one test allowed to spell the contract version as a literal (#6578), so a forgotten bump cannot
pass, and ``test_only_this_module_spells_a_contract_version`` keeps every other test module reading
``envelope.CONTRACT_VERSION``. It also pins that ``envelope.py``'s changelog comment block names all
11 new verbs added by WP03-WP06/WP08, by their literal Typer command names, matching the existing
1.1.0/1.2.0/1.3.0 changelog-comment precedent already in that file.

``orchestrator_api`` commands always emit JSON (module docstring: "Output is
always JSON (no prose mode)") -- there is no ``--json`` flag on
``contract-version`` itself to pass.

This only inspects an in-memory Typer response and re-reads ``envelope.py``'s
own source text -- no fixture-mission, no real git operations -- so it is
marked ``pytest.mark.fast`` (matching ``test_commands_fail_closed.py``'s
convention, ``pytest.ini:25``).
"""

from __future__ import annotations

import inspect
import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from specify_cli.orchestrator_api import envelope as envelope_module
from specify_cli.orchestrator_api.commands import app

pytestmark = [pytest.mark.fast]

runner = CliRunner()

# The 11 verbs added across WP03 (specify/plan/tasks), WP04
# (check-prerequisites/record-analysis), WP05 (open/resolve/defer/cancel-
# decision), WP06 (design-status), and WP08 (answer-decision) -- literal
# Typer ``@app.command(name=...)`` strings, enumerated from the shipped
# source (``src/specify_cli/orchestrator_api/commands.py``), not taken on
# faith from any planning document.
_NEW_VERBS = (
    "specify",
    "plan",
    "tasks",
    "check-prerequisites",
    "record-analysis",
    "open-decision",
    "resolve-decision",
    "defer-decision",
    "cancel-decision",
    "design-status",
    "answer-decision",
    "artifact-read",
    "artifact-submit",
    "design-validate",
    "design-context",
    "interview-record",
    "next",
)


def test_contract_version_response_reports_the_current_contract_version() -> None:
    result = runner.invoke(app, ["contract-version"])
    assert result.exit_code == 0, result.output
    envelope = json.loads(result.output.strip().split("\n")[0])
    assert envelope["success"] is True
    assert envelope["data"]["api_version"] == "1.21.0"
    assert envelope["contract_version"] == "1.21.0"


def test_min_provider_version_unchanged() -> None:
    """NFR-001: the version bump is purely additive -- MIN_PROVIDER_VERSION
    must NOT move."""
    assert envelope_module.MIN_PROVIDER_VERSION == "0.1.0"


def test_changelog_comment_names_all_design_verbs() -> None:
    """A mismatched/missing verb name in the changelog comment is exactly
    the documentation-vs-code drift this WP exists to prevent (Reviewer
    Guidance, WP07 task file)."""
    source = inspect.getsource(envelope_module)
    changelog_start = source.index("# 1.1.0:")
    changelog_end = source.index(f'CONTRACT_VERSION = "{envelope_module.CONTRACT_VERSION}"')
    changelog_block = source[changelog_start:changelog_end]

    missing = [verb for verb in _NEW_VERBS if verb not in changelog_block]
    assert not missing, f"changelog comment is missing verb name(s): {missing}"


# --------------------------------------------------------------------------- single-source guard

# #6578: ``tests/orchestrator_api/test_origin_freshness_envelopes.py`` used to carry its own
# ``_CONTRACT_VERSION`` literal and compared the emitted envelope against it, so every
# ``CONTRACT_VERSION`` bump had to be hand-copied into a file whose subject is origin freshness
# (the literal was re-pinned eleven times before the issue was filed). This module owns the one
# legitimate literal pin; everything else must read ``envelope.CONTRACT_VERSION``.
#
# Deliberate scope and known blind spots (documented, as the sibling gate
# ``tests/architectural/test_no_assert_swallowed_by_own_handler.py`` documents its own). The scan
# pairs a contract-version token with a quoted ``X.Y.Z`` on ONE line, which catches both historical
# shapes — ``_CONTRACT_VERSION = "1.21.0"`` (the constant name carries the token) and
# ``assert envelope["contract_version"] == "1.21.0"``. It does NOT catch single indirection
# (``_EXPECTED = "1.21.0"`` then ``== _EXPECTED``), implicit string concatenation across lines, or a
# version inside a multi-line JSON string. Closing those would need a data-flow reading of arbitrary
# test code; the one-line rule keeps the gate cheap, explanation-free and free of false reds.
#
# It also cannot tell a payload from a comparison, so a test that must carry a DIFFERENT version
# (a ``CONTRACT_VERSION_MISMATCH`` fixture) is flagged by design: build that payload from the
# constant (``f"{CONTRACT_VERSION}-bogus"``) instead of spelling a number, so the suite keeps one
# source of truth. The canonical pin above is exempt by path, and it is exempt rather than reported.
_CANONICAL_PIN = Path(__file__).resolve()
_REPO_ROOT = _CANONICAL_PIN.parents[3]
_TESTS_DIR = _REPO_ROOT / "tests"
_CONTRACT_VERSION_TOKEN = re.compile(r"contract_version", re.IGNORECASE)
_QUOTED_SEMVER = re.compile(r"""["']\d+\.\d+\.\d+["']""")
#: Floor: a walk that finds (almost) nothing must go red, not pass vacuously — the same
#: non-vacuity rule ``tests/architectural/test_no_assert_swallowed_by_own_handler.py`` uses.
MIN_SCANNED_FILES = 3000


def _contract_version_literals_in(text_lines: list[str]) -> list[int]:
    """Line numbers that spell a quoted version on a line that also names a contract version."""
    return [lineno for lineno, line in enumerate(text_lines, 1) if _CONTRACT_VERSION_TOKEN.search(line) and _QUOTED_SEMVER.search(line)]


def _contract_version_pins(tests_dir: Path) -> tuple[list[tuple[Path, int]], int]:
    """Every ``(path, line)`` literal pin under *tests_dir*, and how many ``.py`` files were read.

    Formatting is deliberately kept out of the walk, so a ``tmp_path`` fixture can prove the
    walk/read wiring end-to-end without ``relative_to`` refusing a directory outside the repo.
    """
    pins: list[tuple[Path, int]] = []
    scanned = 0
    for path in sorted(tests_dir.rglob("*.py")):
        scanned += 1
        if path == _CANONICAL_PIN:
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        pins.extend((path, lineno) for lineno in _contract_version_literals_in(lines))
    return pins, scanned


def _offending_files(tests_dir: Path) -> tuple[list[str], int]:
    """Offending repo-relative ``path:line`` strings, and how many ``.py`` files the walk read."""
    pins, scanned = _contract_version_pins(tests_dir)
    return [f"{path.relative_to(_REPO_ROOT).as_posix()}:{lineno}" for path, lineno in pins], scanned


def test_only_this_module_spells_a_contract_version() -> None:
    """#6578: the contract version has one source of truth in the test suite.

    Only this module may pin it by literal; every other test module must compare against
    ``specify_cli.orchestrator_api.envelope.CONTRACT_VERSION`` so that a bump cannot leave a
    stale pin behind. A literal here is what made ``test_origin_freshness_envelopes.py`` go red
    a release after the envelope moved.
    """
    offending, scanned = _offending_files(_TESTS_DIR)

    assert scanned >= MIN_SCANNED_FILES, f"the contract-version scan read only {scanned} test files; it must walk tests/ (floor {MIN_SCANNED_FILES})"
    assert not offending, (
        "test module(s) spell a contract version instead of importing envelope.CONTRACT_VERSION:\n  "
        + "\n  ".join(offending)
        + "\nReplace the literal with `from specify_cli.orchestrator_api.envelope import CONTRACT_VERSION`;"
        " only tests/specify_cli/orchestrator_api/test_contract_version.py may pin the value."
    )


def test_the_contract_version_scan_reports_a_pin_and_ignores_a_reference() -> None:
    """The scan above must be able to fail (DIRECTIVE_043), and must not flag legitimate references."""
    pin = '    assert envelope["contract_version"] == "9.9.9"'

    assert _contract_version_literals_in([pin]) == [1]
    # A module-constant read and an error code are references, not pins.
    assert (
        _contract_version_literals_in(
            [
                '    assert envelope["contract_version"] == CONTRACT_VERSION',
                "    changelog_end = source.index(f'CONTRACT_VERSION = \"{envelope_module.CONTRACT_VERSION}\"')",
                '    assert envelope["error_code"] == "CONTRACT_VERSION_MISMATCH"',
            ]
        )
        == []
    )


def test_the_contract_version_scan_reads_a_planted_file(tmp_path: Path) -> None:
    """The gate's real data path (walk -> read -> (path, line)) is exercised, not just the line helper.

    A no-op in the comprehension above would leave every real-tree assertion green while the gate
    reported "clean" forever; the sibling `tests/architectural` gate carries the same planted-file
    control for exactly that reason.
    """
    planted = tmp_path / "test_planted.py"
    planted.write_text('assert envelope["contract_version"] == "9.9.9"\n', encoding="utf-8")

    pins, scanned = _contract_version_pins(tmp_path)

    assert [(path.name, lineno) for path, lineno in pins] == [("test_planted.py", 1)]
    assert scanned == 1
