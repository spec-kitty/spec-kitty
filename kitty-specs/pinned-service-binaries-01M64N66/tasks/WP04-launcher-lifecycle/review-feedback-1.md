# WP04 review feedback (cycle 1, reviewer-renata)

These parts are correct, and no change is needed:
- Every exit of `ensure()` is either an endpoint that passed handshake, identity and health checks, or a named refusal.
- `verify_before_exec` runs immediately before the single `Popen`.
- In the concurrency case exactly one instance survives.
- The token does not leak, and the client talks to loopback only.
- Removing the five allowlist entries and setting the baseline to 231 (the live count) is correct and minimal.

There is one blocking item.

**Issue 1 (blocking): `stop()` reports a process that is still alive as `stopped` or `not_running` (FR-009, FR-008).**

There are two paths in `ServiceLauncher.stop`:
1. *After* `/shutdown`: when the pid is still alive at the end of the stop budget, and the handshake no longer answers as the instance, the method returns `StopOutcome.STOPPED` without sending a signal. `test_stop_does_not_signal_a_lingering_process_that_no_longer_answers` pins this outcome.
2. *Before* `/shutdown`: when an endpoint is published but the service does not answer as its instance (for example it is hung, so the handshake times out), the method returns `StopOutcome.NOT_RUNNING` without checking whether the pid is alive.

Not sending a signal is right: identity was not proven, so the pid must not be signalled. Reporting `stopped` or `not_running` is wrong, though. If that process is the hung service, it still holds `service.lock`. The next `ensure()` then spawns a child that exits 0 (lock held), waits out the 15 s budget, and refuses `SERVICE_UNHEALTHY`. The operator was told the service had stopped. That breaks FR-009's acceptance ("after stop, the endpoint is gone and a later resolve starts a new instance"). `stop` exists to make cleanup deterministic, so it must not report a clean stop it did not achieve.

Fix:
- Add a distinct outcome, for example `StopOutcome.UNCONFIRMED` (or raise `ServiceRefusal(UNHEALTHY)` with a remedy). Name the pid and the log path, and tell the operator to check and end that process by hand. Use it in both paths whenever the published pid is still alive and identity cannot be proven.
- Return `not_running` only when the pid is dead, or the endpoint is absent.
- Return `stopped` only when the pid is gone.
- Optional, and recommended by FR-008 ("process identity checked beyond the process id"): compare `psutil.Process(pid).create_time()` with the endpoint's `started_at`. When they agree within a small tolerance, the pid is proven to be the service's, so it may be terminated safely as `forced` even when HTTP no longer answers.
- Update the two tests above, and add one for the hung-before-shutdown path. A fake-service mode that accepts connections but never answers is enough, or monkeypatch `_answers_as` / `pid_alive`.

Non-blocking:
- In `_verified`, `_check_identity` (repositoryId) runs before the `instance_id` comparison. A stale file whose port now serves another clone would refuse `VERSION_MISMATCH` rather than recover. The bearer token makes this unlikely (another service answers 401, which is treated as stale), but checking `instance_id` first would be more robust.
- An alive but draining or not-ready instance (it still holds the lock) leads to a 15 s wait and then `SERVICE_UNHEALTHY` reporting "did not become ready". That is acceptable, but the message could say that an existing instance holds the lock.
- Windows: one lifecycle smoke test under `windows_ci` is acceptable as Windows coverage for the launcher. NFR-006's Windows coverage of resolution and cache (WP02/WP03 tests are unmarked) remains a mission-level gap.
