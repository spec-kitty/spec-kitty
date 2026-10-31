"""The committed service pins gate (#6590, F2): every ``pins/*.source.yaml`` must load and pass ``check_pin``.

The gate parametrizes over the pins committed in ``pins/`` (none until
spec-kitty-events cuts its first ``service-v*`` release, so it starts empty) and
runs the offline checks on each: :func:`kernel.service_pin.load_service_pin` and
``spec-kitty service vendor --check --offline`` (:func:`check_pin`). A planted
malformed pin is the non-vacuity control: the same check must report it.

It also pins the routing: a pull request that touches only a pin, the sync script
or the sync-services action runs this gate (``ci``) and the service owner tests
(``core_misc``), and ``src/specify_cli/cli/commands/service.py`` fans out to
``core_misc``, where ``tests/specify_cli/services`` runs.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kernel.service_pin import PIN_SUFFIX, load_service_pin, write_service_pin
from scripts.ci.gate_selection import select_modules
from specify_cli.services.vendor import check_pin
from tests.kernel.service_release_fixture import build_release, pin_path

pytestmark = pytest.mark.fast

_REPO = Path(__file__).resolve().parents[2]
_PINS = _REPO / "pins"
_COMMITTED = sorted(_PINS.glob(f"*{PIN_SUFFIX}"))


def pin_problems(path: Path) -> list[str]:
    """What is wrong with the lockfile at *path* (empty when it is sound): it loads, and ``check_pin`` passes offline."""
    try:
        pin = load_service_pin(path)
    except ValueError as exc:
        return [str(exc)]
    return check_pin(pins_dir=path.parent, service=pin.service, online=False)


@pytest.mark.parametrize("path", _COMMITTED, ids=[path.name for path in _COMMITTED])
def test_every_committed_pin_is_sound(path: Path) -> None:
    """One case per committed pin. Until spec-kitty-events cuts its first ``service-v*`` release
    ``pins/`` holds no lockfile, so pytest reports this as skipped (empty parameter set); the planted
    tests below prove the check itself is not vacuous."""
    assert pin_problems(path) == []


def test_a_planted_malformed_pin_is_reported(tmp_path: Path) -> None:
    """Non-vacuity: the check the gate runs does catch a broken pin (and passes a good one)."""
    pin, _ = build_release(tmp_path / "release")
    good = pin_path(tmp_path / "good", pin.service)
    good.parent.mkdir(parents=True)
    write_service_pin(pin, good)
    assert pin_problems(good) == []

    bad = pin_path(tmp_path / "bad", pin.service)
    bad.parent.mkdir(parents=True)
    bad.write_text(good.read_text(encoding="utf-8").replace(pin.commit, "0" * 40), encoding="utf-8")
    problems = pin_problems(bad)
    assert problems and "commit" in problems[0]


def test_a_pin_with_an_unparseable_requires_core_is_reported(tmp_path: Path) -> None:
    pin, _ = build_release(tmp_path / "release")
    path = pin_path(tmp_path / "repo", pin.service)
    path.parent.mkdir(parents=True)
    write_service_pin(pin, path)
    path.write_text(path.read_text(encoding="utf-8").replace(pin.requires_core, "not a specifier"), encoding="utf-8")
    assert any("requires_core" in problem for problem in pin_problems(path))


@pytest.mark.parametrize(
    "path",
    [
        "pins/write-service.source.yaml",
        "pins/README.md",
        "scripts/sync_services.py",
        ".github/actions/sync-services/action.yml",
    ],
)
def test_a_pin_or_sync_change_runs_the_gate_and_the_service_tests(path: str) -> None:
    selected = select_modules([path])
    assert {"core_misc", "ci"} <= selected, f"{path} selects {sorted(selected)}"


def test_the_service_command_fans_out_to_the_service_tests() -> None:
    selected = select_modules(["src/specify_cli/cli/commands/service.py"])
    assert {"cli", "core_misc"} <= selected, sorted(selected)
