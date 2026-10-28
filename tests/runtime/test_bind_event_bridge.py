"""One composition-root binder for both halves of the EventBridge port (#6675).

``bind_event_bridge`` sets the Mission-state-advance half (the runtime emitter
factory) and the work package transition half together, all or nothing.
Open-core binds neither, so every test resets both halves.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest

from runtime.next._internal_runtime import events
from runtime.next.event_bridge import (
    WorkPackageTransition,
    _reset_work_package_transition_port,
    bind_work_package_transition_port,
    bound_work_package_transition_port,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


class _Port:
    def record_work_package_transition(self, transition: WorkPackageTransition) -> None:
        return None


class _OtherPort:
    def record_work_package_transition(self, transition: WorkPackageTransition) -> None:
        return None


def _factory(**_: Any) -> events.NullEmitter:
    return events.NullEmitter()


def _other_factory(**_: Any) -> events.NullEmitter:
    return events.NullEmitter()


def _reset_both() -> None:
    events.reset_runtime_emitter_factory()
    _reset_work_package_transition_port()


@pytest.fixture(autouse=True)
def _unbound() -> Iterator[None]:
    _reset_both()
    yield
    _reset_both()


def test_binds_both_halves() -> None:
    port = _Port()

    events.bind_event_bridge(emitter_factory=_factory, transition_port=port)

    assert bound_work_package_transition_port() is port
    assert events._registered_factory is _factory


def test_a_conflicting_transition_port_binds_neither_half() -> None:
    bind_work_package_transition_port(_OtherPort())

    with pytest.raises(RuntimeError):
        events.bind_event_bridge(emitter_factory=_factory, transition_port=_Port())

    assert events._registered_factory is None
    assert isinstance(bound_work_package_transition_port(), _OtherPort)


def test_a_conflicting_emitter_factory_binds_neither_half() -> None:
    events.register_runtime_emitter_factory(_other_factory)

    with pytest.raises(RuntimeError):
        events.bind_event_bridge(emitter_factory=_factory, transition_port=_Port())

    assert bound_work_package_transition_port() is None
    assert events._registered_factory is _other_factory


def test_rebinding_the_same_adapter_is_idempotent() -> None:
    events.bind_event_bridge(emitter_factory=_factory, transition_port=_Port())
    second = _Port()

    events.bind_event_bridge(emitter_factory=_factory, transition_port=second)

    assert bound_work_package_transition_port() is second


def _port_class() -> type:
    class _Reloaded:
        def record_work_package_transition(self, transition: WorkPackageTransition) -> None:
            return None

    return _Reloaded


def test_a_reloaded_port_class_is_the_same_adapter() -> None:
    # A module reload mints a new class object with the same module and qualified name;
    # the composite binder judges it as bind_work_package_transition_port does.
    first, reloaded = _port_class(), _port_class()
    bind_work_package_transition_port(first())

    events.bind_event_bridge(emitter_factory=_factory, transition_port=reloaded())

    assert isinstance(bound_work_package_transition_port(), reloaded)
