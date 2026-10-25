# Contract: EventBridge port (Python)

- `WorkPackageTransitionPort.record_work_package_transition(transition: WorkPackageTransition) -> None`
- `EventBridgePort` = `RuntimeEventEmitter` (Mission state advance) + `WorkPackageTransitionPort`, defined in `runtime/next/_internal_runtime/events.py`; the rest lives in the stdlib-only leaf `runtime/next/event_bridge.py`
- `bind_work_package_transition_port(port)`: reject-on-conflict by `module.qualname`; rebinding the same class is idempotent
- `reset_work_package_transition_port()`: test-only
- `bound_work_package_transition_port() -> WorkPackageTransitionPort | None`

The adapter raises what the underlying append raised; it never swallows.
