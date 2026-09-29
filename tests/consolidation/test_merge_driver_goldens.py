"""Golden characterisation of the six registered merge drivers.

Pins each driver's byte-for-byte behavior so the driver body can live in
``consolidation/drivers.py`` -- decoupled from ``cli/commands/merge_driver.py`` --
without silently changing what it writes. Two legs per golden case:

- **subprocess leg** (``@pytest.mark.integration``): runs the registered
  command exactly as git would invoke it (``python -m specify_cli
  merge-driver-X O A B``), reusing :func:`_capture.capture_case`.
- **in-process leg** (``@pytest.mark.unit``): resolves the driver through the
  replay seam ``specify_cli.consolidation.git_probes._resolve_registered_driver_callable``
  -- never through ``specify_cli.cli.commands.merge_driver`` -- so this leg
  stays valid regardless of where the driver body lives.

Plus an all-six-resolve replay test: only ``traces`` is otherwise exercised
through replay (``test_bookkeeping_projection_seam.py``); this proves every
registered ``config_key`` resolves.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import NotRequired, TypedDict

import pytest

from specify_cli.lanes.consolidation import _MERGE_DRIVERS
from specify_cli.consolidation.git_probes import (
    GitProbeError,
    _DRIVER_COMMAND_PATTERN,
    _resolve_registered_driver_callable,
)
from tests.consolidation.merge_driver_goldens._capture import COLD_HOME_TIMEOUT_SECONDS, GoldenCase, capture_case, iter_cases

_GOLDENS_ROOT = Path(__file__).resolve().parent / "merge_driver_goldens"

_SIX_COMMANDS = frozenset(
    {
        "merge-driver-event-log",
        "merge-driver-meta",
        "merge-driver-traces",
        "merge-driver-issue-matrix",
        "merge-driver-acceptance-matrix",
        "merge-driver-review-cycle",
    }
)

_CASES: list[GoldenCase] = iter_cases()
_CASE_IDS: list[str] = [case.full_id for case in _CASES]


class _CaseJson(TypedDict):
    """The committed ``case.json`` shape this suite reads back."""

    exit_code: int
    stdout: str
    stderr: str
    absent: list[str]
    note: str
    argv: NotRequired[list[str]]


@pytest.fixture(scope="session")
def _shared_capture_home(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One ``HOME``/``SPEC_KITTY_HOME`` root reused by every subprocess-leg case.

    Perf: a fresh ``HOME`` pays a one-time ~12s
    cold-install bootstrap (seeding every agent's command/skill directories
    into it); reusing the SAME ``HOME`` across cases means only the first
    case in the session pays that cost, dropping every later case to ~1s.
    Session-scoped so the whole 25-case file pays it exactly once. No manual
    ``os.environ`` mutation: the directory is passed only inside
    :func:`_capture.capture_case`'s explicit subprocess ``env`` mapping, never
    written to this test process's own environment.
    """
    home = tmp_path_factory.mktemp("merge-driver-golden-home")
    # Pay the cold-install bootstrap here, under its own budget, so no case's
    # per-call timeout absorbs it (it timed out on a loaded worker otherwise).
    capture_case(_CASES[0].case_dir, home_dir=home, timeout=COLD_HOME_TIMEOUT_SECONDS)
    return home


def _config_key_for_command(command: str) -> str:
    """Map a golden case's command name to its ``_MERGE_DRIVERS`` config key."""
    spec = next(candidate for candidate in _MERGE_DRIVERS if command in candidate.command)
    return str(spec.config_key)


@pytest.mark.unit
def test_golden_cases_are_discovered_and_cover_all_six_commands() -> None:
    """Vacuity guard: the discovered case set is non-empty and every
    one of the six registered commands has at least one golden case."""
    assert _CASES, f"no golden cases discovered under {_GOLDENS_ROOT}"
    discovered_commands = {case.command for case in _CASES}
    assert discovered_commands == _SIX_COMMANDS


@pytest.mark.integration
@pytest.mark.parametrize("case", _CASES, ids=_CASE_IDS)
def test_subprocess_leg_matches_golden(case: GoldenCase, _shared_capture_home: Path) -> None:
    """Replay *case* through the real subprocess entrypoint; compare against
    the committed golden (bytes + exit code + stdout + stderr).

    Reuses the session-scoped ``_shared_capture_home`` (perf: see that
    fixture's docstring) -- this changes nothing about the captured bytes,
    since ``HOME``/``SPEC_KITTY_HOME`` never appear in a driver's stdout,
    stderr, or written ``ours`` content (only the per-case working directory
    is normalized to ``<TMP>``, and that stays private per case either way).
    """
    golden_case_json = _read_case_json(case.case_dir)
    result = capture_case(case.case_dir, home_dir=_shared_capture_home)

    expected_a = (case.case_dir / "expected_A").read_bytes()
    assert result.expected_a == expected_a, f"{case.full_id}: written A bytes drifted from golden"
    assert result.exit_code == golden_case_json["exit_code"], f"{case.full_id}: exit code drifted"
    assert result.stdout == golden_case_json["stdout"], f"{case.full_id}: stdout drifted"
    assert result.stderr == golden_case_json["stderr"], f"{case.full_id}: stderr drifted"


@pytest.mark.unit
@pytest.mark.parametrize("case", _CASES, ids=_CASE_IDS)
def test_in_process_leg_matches_golden(case: GoldenCase, tmp_path: Path) -> None:
    """Replay *case* through the replay seam (never ``cli.commands.merge_driver``).

    On success: the driver's written ``ours`` bytes equal the golden. On any
    exception: the golden must record a non-zero exit code (an exception
    replaying a case the golden expects to succeed is a failure). Stdout/stderr
    are never inspected on this leg (the review-cycle notice is a
    subprocess-entrypoint-only concern).
    """
    golden_case_json = _read_case_json(case.case_dir)
    config_key = _config_key_for_command(case.command)
    driver = _resolve_registered_driver_callable(config_key)

    argv_names: tuple[str, ...] = tuple(golden_case_json.get("argv", ["O", "A", "B"]))
    base, ours, theirs = (tmp_path / name for name in argv_names)
    for name, target in zip(argv_names, (base, ours, theirs), strict=True):
        source = case.case_dir / name
        if not source.exists():
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)

    expected_exit_code = golden_case_json["exit_code"]
    try:
        driver(str(base), str(ours), str(theirs))
    except Exception as exc:  # noqa: BLE001 - any exception counts as "raised" for this leg
        assert expected_exit_code != 0, f"{case.full_id}: in-process leg raised {exc!r} but golden expects success"
        return

    assert expected_exit_code == 0, f"{case.full_id}: in-process leg succeeded but golden expects exit {expected_exit_code}"
    expected_a = (case.case_dir / "expected_A").read_bytes()
    assert ours.read_bytes() == expected_a, f"{case.full_id}: in-process written bytes drifted from golden"


def _read_case_json(case_dir: Path) -> _CaseJson:
    data: _CaseJson = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    return data


# ---------------------------------------------------------------------------
# All-six-resolve replay test
# ---------------------------------------------------------------------------

_DISTINCT_CONFIG_KEYS: tuple[str, ...] = tuple(dict.fromkeys(spec.config_key for spec in _MERGE_DRIVERS))


@pytest.mark.unit
def test_unknown_config_key_fails_closed_through_replay() -> None:
    with pytest.raises(GitProbeError):
        _resolve_registered_driver_callable("spec-kitty-does-not-exist")


@pytest.mark.unit
def test_distinct_config_key_count_matches_six_registered_commands() -> None:
    """A 7th driver added to ``_MERGE_DRIVERS`` without new goldens trips this
    test -- the message tells the implementer exactly what is missing."""
    commands_from_registry = {match.group(1) for spec in _MERGE_DRIVERS if (match := _DRIVER_COMMAND_PATTERN.match(spec.command))}
    assert len(_DISTINCT_CONFIG_KEYS) == 6, (
        f"expected exactly 6 distinct merge-driver config keys, found {len(_DISTINCT_CONFIG_KEYS)} "
        f"({sorted(_DISTINCT_CONFIG_KEYS)!r}) -- add goldens for the new driver "
        "(tests/consolidation/merge_driver_goldens/<command>/) and extend this test's expectations"
    )
    assert commands_from_registry == _SIX_COMMANDS, (
        f"the commands derived from _MERGE_DRIVERS ({sorted(commands_from_registry)!r}) no longer match "
        f"the six commands this golden suite covers ({sorted(_SIX_COMMANDS)!r}) -- add goldens for the "
        "new driver (tests/consolidation/merge_driver_goldens/<command>/) and extend this test's expectations"
    )
