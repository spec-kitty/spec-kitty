# Contract: hosted posture

| Repo `hosted.drain` | Personal `[hosted] drain` | Env narrower set | Effective drain |
|---|---|---|---|
| true | true | no | **on** |
| true | true | yes | off (reason: narrower name) |
| true | false/absent/invalid | – | off (reason: personal scope) |
| false/absent/invalid | any | – | off (reason: repository scope) |

- Drain off ⇒ these edges raise `DrainDisabled` (or return the stated sentinel) before any network, thread or
  credential access (plan.md D2, F-1/F-2; `budget.py` stays stdlib-only and is not an edge):
  - `transport.ZeitgeistClient.offer` → returns `OfferOutcome.DRAIN_DISABLED` (no thread; never `DROPPED_UNREACHABLE`);
  - `filtered_stream.FilteredStream.seed_from_snapshot` / `.watch` and `history.read_history` → raise `DrainDisabled`;
  - `resolution.SaasCapabilityGateway.check_repo_admission` / `.mint_capability` → raise `DrainDisabled`
    (`__init__` is not gated).
- Drain off ⇒ `resolve_credentials`, `resolve_focus_capability` (and `resolve_focus_lease`) return `None` before any
  cache or keyring read; fan-out, producers, live-work, the widen prereq probe return silently.
- Drain off ⇒ every relay CLI command and MCP relay tool pre-flights `require_drain("relay")` before any credential read.
- CLI surfaces map `DrainDisabled` to one line, the constant `hosted_posture.DRAIN_GUIDANCE_LINE`:
  `Live drain is off (<reason>). Enable with: spec-kitty moments drain on [--repo]`.
- Authored send/reply refuse with `AuthoredMessageError` code `drain_off`; a drain refusal is never retried.
- Ledger `projection` true ⇒ refresh after each durably persisted transition; false ⇒ no automatic refresh. The lane
  ledger, tracked `status.json`, `decisions/`, `run.events.jsonl` and `kitty-ops/` are unaffected in every case.
- Endpoint unconfigured ⇒ explicit callers get `HostedEndpointUnconfigured` (guidance, exit non-zero, no traceback);
  automatic callers use `resolve_server_target_or_none()` and stay silent.
