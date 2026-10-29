# Contract: owned refusal envelope (C2)

Status: proposed by mission `owned-refusal-shape-and-issue-matrix-migration-01M5ZBD5`;
recorded by ADR `docs/adr/4.x/2026-10-27-2-owned-refusals-use-the-c2-error-contract.md`.
Supersedes the line "`emit_owned_refusal` keeps each command's existing JSON envelope
keys" in `kitty-specs/owned-checkout-lifecycle-authority-01M3M2ZB/contracts/cli-owned-checkout-surface.md`.

## Rule

Every owned-checkout refusal a command emits in `--json` mode is printed on stdout as:

```json
{
  "ok": false,
  "error": {"code": "<OWNED_REFUSAL_CODE>", "message": "<text>"},
  "context": {"...": "optional command-specific facts"},
  "spec_kitty_version": "<optional, commands that stamp every payload>"
}
```

and the command exits 1. The core (`ok`, `error.code`, `error.message`) is the adopted
CLI error contract C2 (`specify_cli.cli.json_contract.json_error`). `context` and
`spec_kitty_version` are the only other top-level keys allowed, and each is present only
for the commands listed in `data-model.md`.

## Examples

`agent issue-verdict --owned-checkout <P> --mission no-such-mission-01ZZZZZZ --json`:

```json
{"ok": false, "error": {"code": "MISSION_CONTEXT_UNRESOLVED", "message": "No mission found for handle \"no-such-mission-01ZZZZZZ\". ..."}}
```

`agent tasks mark-status ... --owned-checkout <R> --json` (repository root refused):

```json
{
  "ok": false,
  "error": {"code": "OWNED_CHECKOUT_IS_REPOSITORY_ROOT", "message": "..."},
  "context": {"state_applied": false, "event_ids": [], "applied_wps": [], "destination_ref": null,
              "status_events_path": null, "status_snapshot_path": null, "dirty": null}
}
```

## Consumers

- orchestrator-api `check-prerequisites` reads `error.code` / `error.message` from the
  host payload; `next` embeds the host payload in `data`. orchestrator-api
  `contract_version` is `1.19.0` from this change.
- Human mode is not part of this contract and is unchanged.
