"""NFR-006 back-compat regression (mission cli-error-surface-seam-01M2WJD2, WP01/T005).

Proves the 7 legacy typed reader errors, re-parented onto
:class:`kernel.errors.GuardedReadError` in T004, still satisfy every
pre-existing ``except`` contract the ~85-site caller census
(``research.md``) found — the single regression WP02-WP07 rely on without
re-verifying the base themselves.

Census counts recorded 2026-09-19 (grep over ``src/`` + ``tests/``,
including tuple-catches and ``pytest.raises`` sites):

| Legacy error              | except (src) | except (tests) | pytest.raises (tests) |
|----------------------------|-------------:|----------------:|-----------------------:|
| MissionMetaReadError       | 49           | 6               | 40                     |
| DecisionIndexReadError     | 12           | 0               | 3                      |
| CorruptLanesError          | 12           | 0               | 5                      |
| MissingLanesError          | 10           | 0               | 3                      |
| AgentConfigError           | 13           | 0               | 6                      |
| UnsafePathSegmentError     | 4            | 0               | 3                      |
| IntakeFileUnreadableError  | 5            | 0               | 9                      |
| MetaDecodeError            | 6            | 0               | 18                     |

Representative tuple-catch shapes found live in ``src/``:
``(MissingLanesError, CorruptLanesError)`` (``merge/forecast.py``,
``cli/commands/merge.py``, ``orchestrator_api/commands.py``,
``cli/commands/mission_type.py``) and
``(ValueError, FileNotFoundError, MissingLanesError, CorruptLanesError)``
(``cli/commands/agent/tasks_move_task.py``, two sites) — the coupled pair
research.md flags is exercised as one tuple below, not just the bare types.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.errors import GuardedReadError
from kernel.meta_decode import MetaDecodeError
from specify_cli.core.agent_config import AgentConfigError
from specify_cli.core.paths import MissionMetaReadError, UnsafePathSegmentError
from specify_cli.decisions.store import DecisionIndexReadError
from specify_cli.intake.errors import IntakeFileUnreadableError
from specify_cli.lanes.persistence import CorruptLanesError, MissingLanesError

ALL_LEGACY_ERRORS: tuple[type[GuardedReadError], ...] = (
    MissionMetaReadError,
    DecisionIndexReadError,
    CorruptLanesError,
    MissingLanesError,
    AgentConfigError,
    UnsafePathSegmentError,
    IntakeFileUnreadableError,
    MetaDecodeError,
)


def _make_instance(cls: type[GuardedReadError]) -> GuardedReadError:
    """Construct one instance of *cls* mirroring its real call sites."""
    if cls is MissionMetaReadError:
        return MissionMetaReadError(Path("meta.json"), ValueError("bad json"))
    if cls is DecisionIndexReadError:
        return DecisionIndexReadError(Path("index.json"), ValueError("bad json"))
    if cls is IntakeFileUnreadableError:
        return IntakeFileUnreadableError(path="candidate.txt", cause=OSError("denied"))
    # CorruptLanesError, MissingLanesError, AgentConfigError,
    # UnsafePathSegmentError, MetaDecodeError all take a single positional message.
    return cls("legacy positional message")  # type: ignore[call-arg]


@pytest.mark.parametrize("error_cls", ALL_LEGACY_ERRORS)
def test_every_legacy_error_is_a_guarded_read_error(error_cls: type[GuardedReadError]) -> None:
    exc = _make_instance(error_cls)

    assert isinstance(exc, GuardedReadError)


@pytest.mark.parametrize("error_cls", ALL_LEGACY_ERRORS)
def test_bare_except_of_the_legacy_type_still_matches(error_cls: type[GuardedReadError]) -> None:
    exc = _make_instance(error_cls)

    try:
        raise exc
    except error_cls as caught:
        assert caught is exc
    else:
        pytest.fail(f"except {error_cls.__name__} did not catch its own instance")


def test_unsafe_path_segment_error_still_caught_by_bare_except_value_error() -> None:
    """Live sites (``core/paths.py:152,733``) catch via bare ``except ValueError``."""
    exc = UnsafePathSegmentError("not a safe path segment")

    try:
        raise exc
    except ValueError as caught:
        assert caught is exc
    else:
        pytest.fail("except ValueError did not catch UnsafePathSegmentError")


def test_meta_decode_error_still_caught_by_bare_except_value_error() -> None:
    """MetaDecodeError's docstring promises this — L2/L3 boundaries rely on it."""
    exc = MetaDecodeError("Expected JSON object, got list")

    try:
        raise exc
    except ValueError as caught:
        assert caught is exc
    else:
        pytest.fail("except ValueError did not catch MetaDecodeError")


def test_missing_lanes_and_corrupt_lanes_coupled_tuple_catch() -> None:
    """Mirrors ``merge/forecast.py:177`` / ``cli/commands/merge.py:546`` etc."""
    for exc in (
        MissingLanesError("lanes.json is required for kitty-specs/x"),
        CorruptLanesError("lanes.json at kitty-specs/x is corrupt"),
    ):
        try:
            raise exc
        except (MissingLanesError, CorruptLanesError) as caught:
            assert caught is exc
        else:
            pytest.fail(f"tuple-catch (MissingLanesError, CorruptLanesError) did not catch {exc!r}")


def test_missing_lanes_and_corrupt_lanes_four_way_tuple_catch() -> None:
    """Mirrors ``cli/commands/agent/tasks_move_task.py:798,1269``."""
    for exc in (
        MissingLanesError("lanes.json is required"),
        CorruptLanesError("lanes.json is corrupt"),
    ):
        try:
            raise exc
        except (ValueError, FileNotFoundError, MissingLanesError, CorruptLanesError) as caught:
            assert caught is exc
        else:
            pytest.fail(f"four-way tuple-catch (ValueError, FileNotFoundError, MissingLanesError, CorruptLanesError) did not catch {exc!r}")


def test_pytest_raises_sites_still_match_legacy_type() -> None:
    """A representative ``pytest.raises(<LegacyError>)`` ripple site."""
    with pytest.raises(AgentConfigError):
        raise AgentConfigError("Invalid YAML in config.yaml")

    with pytest.raises(MetaDecodeError):
        raise MetaDecodeError("Expected JSON object, got list")


def test_mission_meta_read_error_preserves_its_own_attributes() -> None:
    """Re-parenting must not disturb ``meta_path``/``cause`` other callers read."""
    cause = ValueError("bad json")
    exc = MissionMetaReadError(Path("meta.json"), cause)

    assert exc.meta_path == Path("meta.json")
    assert exc.cause is cause
    assert "Cannot read meta.json" in str(exc)


def test_intake_file_unreadable_error_preserves_code_and_detail_contract() -> None:
    """Re-parenting must not disturb the ``IntakeError.code``/``detail`` contract."""
    from specify_cli.intake.errors import INTAKE_FILE_UNREADABLE, IntakeError

    cause = OSError("denied")
    exc = IntakeFileUnreadableError(path="candidate.txt", cause=cause)

    assert isinstance(exc, IntakeError)
    assert exc.code == INTAKE_FILE_UNREADABLE
    assert exc.detail["path"] == "candidate.txt"
    assert exc.__cause__ is cause
