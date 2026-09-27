# Data Model: Opt-in hosted drain and ledger flags

## Configuration (operator-facing contract)

`.kittify/config.yaml` (repository, committed):
```yaml
hosted:
  drain: false        # repository permits live drain (default false/absent)
ledger:
  projection: true    # auto-refresh .kittify/derived/<mission>/ (default true)
```

Runtime-root `config.toml` (personal; `~/.spec-kitty/config.toml` on POSIX, `$SPEC_KITTY_HOME/config.toml` when set):
```toml
[hosted]
drain = true          # personal activation (default false/absent)

[sync]
server_url = "https://team.example"   # hosted endpoint (no built-in default)
```

## Value objects
- **DrainPosture** — `enabled: bool`, `repo_value: bool | None`, `repo_source: str`, `personal_value: bool | None`,
  `personal_source: str`, `narrowed_by: str | None` (env kill switch), `reason: str`.
  Invariant: `enabled == (repo_value is True and personal_value is True and narrowed_by is None)`.
- **LedgerPosture** — `enabled: bool` (default True), `source: str`.
- **ResolvedServerTarget** — unchanged shape (`resolved_server_url: str`); `PACKAGED_DEFAULT` is removed. An unconfigured machine yields `HostedEndpointUnconfigured` (explicit callers) or `None` from `resolve_server_target_or_none()` (automatic callers).

## Errors
- `DrainDisabled(RuntimeError)` — raised at a network edge; carries a one-line human reason.
- `HostedEndpointUnconfigured(ConfigurationError)` — raised by the resolver for explicit callers; carries the guidance line with the resolved config path.

## State: execution-state projection
`.kittify/derived/<mission_slug>/status.json`, `board-summary.json` (+ `progress.json`, `lifecycle.json` when write-free
generators allow). Gitignored, derived, rebuildable with `spec-kitty materialize`; never read as authority.
