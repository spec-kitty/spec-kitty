"""Contract of the transport-neutral status produce seam (``status/adapters.py``).

Open-core ships no default handler. Every ``fire_*`` is a non-raising no-op
until a transport owner registers a handler, and registration is idempotent by
qualified name. These tests pin that behaviour through the transport-neutral
names (FR-009) and assert the module carries no hosted-transport vocabulary
(SC-003).
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from specify_cli.status import adapters

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def _clean_handlers() -> Any:
    adapters.reset_handlers()
    yield
    adapters.reset_handlers()


def test_empty_registry_fire_functions_are_noops() -> None:
    adapters.fire_status_fanout(repo_root=None, wp_id="WP01")
    adapters.fire_lifecycle_fanout(repo_root=None, envelope={}, log_path=None)
    adapters.fire_resolved_binding_fanout(repo_root=None, wp_id="WP01")


def test_status_stub_receives_kwargs_once_with_repo_root_rejoined(tmp_path: Path) -> None:
    received: list[dict[str, Any]] = []

    def stub(**kwargs: Any) -> None:
        received.append(kwargs)

    adapters.register_status_fanout_handler(stub)
    adapters.fire_status_fanout(repo_root=tmp_path, wp_id="WP01", from_lane="planned", to_lane="claimed")

    assert received == [{"repo_root": tmp_path, "wp_id": "WP01", "from_lane": "planned", "to_lane": "claimed"}]


def test_lifecycle_stub_does_not_receive_repo_root(tmp_path: Path) -> None:
    received: list[dict[str, Any]] = []

    def stub(**kwargs: Any) -> None:
        received.append(kwargs)

    adapters.register_lifecycle_fanout_handler(stub)
    adapters.fire_lifecycle_fanout(repo_root=tmp_path, envelope={"k": "v"}, log_path=None)

    assert received == [{"envelope": {"k": "v"}, "log_path": None}]


def test_resolved_binding_stub_does_not_receive_repo_root(tmp_path: Path) -> None:
    received: list[dict[str, Any]] = []

    def stub(**kwargs: Any) -> None:
        received.append(kwargs)

    adapters.register_resolved_binding_fanout_handler(stub)
    adapters.fire_resolved_binding_fanout(repo_root=tmp_path, wp_id="WP01", mission_slug="m")

    assert received == [{"wp_id": "WP01", "mission_slug": "m"}]


def test_registering_the_same_qualified_function_twice_delivers_once() -> None:
    calls: list[int] = []

    def make() -> Any:
        def handler(**_kwargs: Any) -> None:
            calls.append(1)

        return handler

    # Two distinct function objects sharing one qualified name.
    adapters.register_status_fanout_handler(make())
    adapters.register_status_fanout_handler(make())
    adapters.fire_status_fanout(wp_id="WP01")

    assert calls == [1]


def test_raising_stub_is_swallowed_logged_and_later_stub_still_runs(caplog: pytest.LogCaptureFixture) -> None:
    later: list[str] = []

    def boom(**_kwargs: Any) -> None:
        raise RuntimeError("handler blew up")

    def after(**kwargs: Any) -> None:
        later.append(kwargs["wp_id"])

    adapters.register_status_fanout_handler(boom)
    adapters.register_status_fanout_handler(after)

    with caplog.at_level(logging.WARNING):
        adapters.fire_status_fanout(wp_id="WP01", from_lane="planned", to_lane="claimed")

    assert later == ["WP01"]
    assert any("failed" in r.getMessage() for r in caplog.records)


def test_status_package_carries_no_hosted_transport_vocabulary() -> None:
    # The removed Zeitgeist transport may be named as history; live hosted vocabulary may not.
    for path in sorted(Path(adapters.__file__).parent.rglob("*.py")):
        source = path.read_text(encoding="utf-8").lower()
        for residue in ("saas", "drain_posture", "hosted"):
            assert residue not in source, f"{path.name}: {residue}"


def test_no_handler_is_registered_after_import_in_a_fresh_interpreter() -> None:
    code = (
        "from specify_cli.status import adapters as a; "
        "import specify_cli.status.emit, specify_cli.status.lifecycle_events; "
        "assert not a._status_handlers, a._status_handlers; "
        "assert not a._lifecycle_handlers, a._lifecycle_handlers; "
        "assert not a._resolved_binding_handlers, a._resolved_binding_handlers"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
