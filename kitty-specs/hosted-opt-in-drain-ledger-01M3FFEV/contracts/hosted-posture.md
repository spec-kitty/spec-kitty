# Contract: hosted posture

| Repo `hosted.drain` | Personal `[hosted] drain` | Env narrower set | Effective drain |
|---|---|---|---|
| true | true | no | **on** |
| true | true | yes | off (reason: narrower name) |
| true | false/absent/invalid | – | off (reason: personal scope) |
| false/absent/invalid | any | – | off (reason: repository scope) |

- Drain off ⇒ `NoRedirects.build` and `SaasCapabilityGateway()` raise `DrainDisabled`; `resolve_credentials`,
  `resolve_focus_capability` return `None` before any cache or keyring read; fan-out and producers return silently.
- CLI surfaces map `DrainDisabled` to one line: `Live drain is off (<reason>). Enable with: spec-kitty moments drain on [--repo]`.
- Ledger `projection` true ⇒ refresh after each durably persisted transition; false ⇒ no automatic refresh. The lane
  ledger, tracked `status.json`, `decisions/`, `run.events.jsonl` and `kitty-ops/` are unaffected in every case.
- Endpoint unconfigured ⇒ explicit callers get `HostedEndpointUnconfigured` (guidance, exit non-zero, no traceback);
  automatic callers use `resolve_server_target_or_none()` and stay silent.
