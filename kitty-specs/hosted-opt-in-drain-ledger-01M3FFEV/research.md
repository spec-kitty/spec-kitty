# Research: Opt-in hosted drain and ledger flags

Sources: pre-spec squad (4 lenses, 2026-09-26) and post-spec squad (reviewer-renata). Every claim
cites live code at HEAD `d04b1de8`.

## R1 — Network edges (where the drain gate must live)
- Relay HTTP: every relay request builds its opener through `zeitgeist_client/budget.py::NoRedirects.build`:
  the control POST (`transport.py:382` via `open_bounded`), stream GETs (`filtered_stream.py:253,458`) and
  history (`history.py:191`). **Decision:** gate in `NoRedirects.build`; one choke point covers all relay traffic.
- SaaS capability: `zeitgeist_client/resolution.py::SaasCapabilityGateway` (httpx, `:169-241`). **Decision:** gate in
  `__init__`, and short-circuit `resolve_credentials`/`resolve_focus_capability` **before** the credential-cache read
  (`:606-612` returns a cached credential with no auth check, so a logged-out machine could keep publishing).
- Existing egress gate `tests/architectural/test_egress_consent_boundary.py` lists `resolution.py`
  (NOT_PROJECT_DATA). The new drain gate test complements it and does not replace it.

## R2 — Kill switches today
`core/env.py::moment_handlers_disabled_reason` (NO_MOMENT_HANDLERS, SYNC_DISABLE, deprecated SYNC_MINIMAL_IMPORT) is
read at import (`status/adapters.py:384`) and per call (runtime `events.py:317`). It stays a narrower. Drain composes
with it and does not replace it. `SPEC_KITTY_ENABLE_SAAS_SYNC` (`core/saas_sync_config.py`) is residue and is not
reused (C-002).

## R3 — Ledger options
- Source of truth, never gated: `status.events.jsonl` (+commit in `coordination/status_transition.py:326-350`),
  tracked `status.json` (committed atomically with events, byte-rolled-back by `transaction.py`), `decisions/` +
  `decisions.events.jsonl`, `run.events.jsonl`, `kitty-ops/`.
- Derived and gitignored: `.kittify/derived/<slug>/` (`status/views.py`, `progress.py`, `lifecycle.py`). Today it is
  produced only on demand (`spec-kitty materialize`); `materialize_if_stale` has no production caller.
- Option (b), gating the log's commit, is rejected: the coordination transaction commits events and status.json atomically.
- **Decision (D-2):** option (c), auto-refresh of the derived projection from a write-free snapshot.
- Caveat: `write_derived_views` calls the *writing* `materialize()` (`views.py:90`), so the new refresh builds the
  snapshot via `reduce(read_events())` instead.

## R4 — Endpoint default
- `auth/config.py:29` `DEFAULT_HOSTED_SAAS_URL`. `server_target.py:171-173` returns `PACKAGED_DEFAULT` when env and
  config are both unset. `get_saas_base_url` falls back to the same default.
- Callers that break when the default goes: `_auth_saas_target.py:60-62` catches only the split-brain error, so
  `auth status` would show a traceback. `tracker/saas_client.py:330` constructor is unguarded. Tolerant callers:
  `saas_readiness.py:195`, `_auth_doctor.py:436`, `auth/http/transport.py:304`.
- Migration `m_4_0_0_retired_hosted_target.py:189-196` rewrites `app.spec-kitty.ai` to the default.
  **Decision:** delete the key instead (R-4).
- ADR gap: the D-5 reversal ADR planned by mission `team-kitty-launch-defaults-01M1XJ4Y` (WP01,
  `2026-09-07-1-packaged-hosted-target-default.md`) was never written. The new ADR records both.
- Test blast radius: about 21 files / 93 hits assert the default (`tests/auth/test_server_target.py`,
  `tests/auth/test_config.py`, `tests/tracker/test_server_target_fail_closed.py`, `tests/cli/commands/test_auth_*`,
  `tests/specify_cli/upgrade/migrations/test_retired_hosted_target.py`, ...).

## R5 — #4311 coupling
The bounded retry is not on main (no `relay_waking`/backoff in `status/`, `decisions/`, `zeitgeist_client/`). C-005 is
met by construction: any future retry calls the gated relay opener.

## R6 — Config homes
Two user-global roots on POSIX: `kernel.paths.get_kittify_home()` → `~/.kittify` (`[moments]`) and
`specify_cli.paths.get_runtime_root().base` → `~/.spec-kitty` (`[sync].server_url`, credentials). They coincide on
Windows and under `SPEC_KITTY_HOME`. **Decision (D-5):** the personal drain activation lives in the runtime root.

## Adversarial dispositions (post-spec squad)
| Finding | Disposition |
|---|---|
| M1 personal scope spoofable via `.kitty.env` | accepted: R-1, no env var enables drain |
| M2 wrong home + `saas-auth.json` URL source | accepted: D-5 runtime root; R-2 saas-auth.json stays an explicit endpoint source |
| M3 edges/callers not enumerated | accepted: NFR-002 floor named; FR-004/005 extended; R-3 all relay traffic gated |
| m1 FR-009 write-free | accepted (FR-009 text) |
| m2 FR-012 command list | accepted (FR-012 text + caller-enumeration test) |
| m3 migration mechanics | accepted: R-4 |
| m4 kill-switch interplay | accepted (edge cases) |
| m5 runtime gate placement | accepted (plan D2) |
| m6 NFR-003 flaky timing | changed: count-based assertion |
| m7 NFR-004 axes | accepted |
| m8 parse-failure semantics | accepted (edge case: both readers treat an unparseable file the same) |
