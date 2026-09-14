---
title: Environment Variables Reference
description: Environment variable reference for Spec Kitty 3.2 runtime, CI, hosted sync, tracker, dashboard, and test configuration.
doc_status: active
updated: '2026-08-16'
related:
- docs/api/cli-commands.md
- docs/api/configuration.md
- docs/adr/3.x/2026-08-16-5-operator-config-env-expansion-seam.md
---
# Environment Variables Reference

This page lists the user-facing environment variables that are active in the current `3.2` CLI surface.

Most of the variables below can now be set **once**, in a `.kitty.env` file, instead of
per-shell `export`. See [The `.kitty.env` file](#the-kittyenv-file) below and the
[operator config env-expansion seam ADR](../adr/3.x/2026-08-16-5-operator-config-env-expansion-seam.md)
for the mechanism.

---

## Runtime and Installation

### SPEC_KITTY_HOME

Override the runtime home directory used for shared Spec Kitty state.

**Purpose**: Change where the CLI stores shared state such as runtime files and
upgrade-managed assets. This is also the **locator** for the home-tier `.kitty.env` file
(`${SPEC_KITTY_HOME}/.kitty.env`) — see [The `.kitty.env` file](#the-kittyenv-file). Because
it locates that file, `SPEC_KITTY_HOME` itself cannot be set *inside* `.kitty.env`; a line
defining it there is dropped with a warning (locator-recursion guard).

**Example**:
```bash
export SPEC_KITTY_HOME="$HOME/.spec-kitty-dev"
spec-kitty verify-setup
```

### SPEC_KITTY_PACKS_ROOT

Override the root directory the CLI resolves built-in doctrine packs from.

**Purpose**: Committed governance files (`charter.yaml`'s catalog,
`agent_profiles_manifest.json`) store built-in pack paths as the portable token
`${SPEC_KITTY_PACKS_ROOT}/built-in/...`, never a resolved absolute path, so the same
committed file is byte-identical across an editable checkout, an installed wheel, or a
future externally-extracted pack. `SPEC_KITTY_PACKS_ROOT` is the *resolution* override for
that token on one machine; leaving it unset resolves through the normal built-in-pack
discovery (`get_built_in_pack_root()`), and the token in committed files is unaffected
either way.

**Do not set this in the provisioned `.kitty.env` scaffold.** The `spec-kitty upgrade`
provision migration deliberately never seeds it: an always-present
`SPEC_KITTY_PACKS_ROOT` would silently flip the `kernel/paths.py` TEMPLATE_ROOT presence
gate for every subsequent invocation of the project, even for an operator who never meant
to override the pack root. Set it explicitly, only when you actually need a non-default
pack root.

**Example**:
```bash
export SPEC_KITTY_PACKS_ROOT=/opt/spec-kitty-packs
spec-kitty doctor provenance
```

**See also**: [ADR: operator config env-expansion seam](../adr/3.x/2026-08-16-5-operator-config-env-expansion-seam.md).

### SPEC_KITTY_TEMPLATE_ROOT

Point Spec Kitty at a local checkout for bundled templates and mission assets.

**Purpose**: Useful when developing Spec Kitty itself, testing template changes from source, or running in an environment where packaged resources are unavailable.

**Example**:
```bash
export SPEC_KITTY_TEMPLATE_ROOT=/path/to/spec-kitty
spec-kitty init my-project --ai claude
```

### SPEC_KITTY_PACK_HOME

Not read directly by Spec Kitty — this is the conventional variable name used
in org-pack `local_path` indirection examples (see
[Create an Org Doctrine Pack](../guides/how-to/governance/create-an-org-doctrine-pack.md)). Any
environment variable name works; `${VAR}`/`$VAR` tokens in
`doctrine.org.packs[].local_path` (and the legacy `organisation_packs[].path`)
are expanded at pack-resolution time, not stored expanded on disk.

**Purpose**: Let each operator/machine point a shared, portable
`.kittify/config.yaml` at a machine-local org-pack checkout without editing
the config file per machine.

**Example**:
```bash
export SPEC_KITTY_PACK_HOME=/opt/acme-doctrine
```
```yaml
# .kittify/config.yaml
doctrine:
  org:
    packs:
      - name: acme
        local_path: "${SPEC_KITTY_PACK_HOME}/acme-doctrine"
```

If the referenced variable is unset or empty, resolution fails closed with a
named error identifying the variable and the pack — it never silently
produces a literal `${...}`-token path or an empty org layer.

### SPECIFY_TEMPLATE_REPO

Override the remote template repository slug (`owner/name`).

**Purpose**: Use a custom remote template source when you explicitly want to bootstrap or repair from a different repository.

**Example**:
```bash
export SPECIFY_TEMPLATE_REPO=my-org/custom-spec-kitty
spec-kitty upgrade
```

### SPEC_KITTY_NON_INTERACTIVE

Force non-interactive mode for commands that normally prompt.

**Purpose**: Equivalent to passing `--non-interactive` / `--yes` on commands such as `spec-kitty init`.

**Example**:
```bash
export SPEC_KITTY_NON_INTERACTIVE=1
spec-kitty init my-project --ai codex --non-interactive
```

### SPEC_KITTY_WORKTREE_REMOVAL_DELAY

Adjust the delay before completed worktrees are removed.

**Purpose**: Useful when debugging merge/worktree cleanup behavior.

**Example**:
```bash
export SPEC_KITTY_WORKTREE_REMOVAL_DELAY=10
spec-kitty merge
```

---

## Hosted Auth and Sync

!!! warning "A shell `export` of either variable is machine-global"

    `SPEC_KITTY_ENABLE_SAAS_SYNC` and `SPEC_KITTY_SAAS_URL` are ordinary process
    environment variables. **Exported in a shell**, they have no project-scoped form —
    a single `export` affects every project that shell subsequently touches, not just the
    repository you were standing in when you ran it.

    Hosted sync is **on by default** (#3980, Team Kitty launch defaults);
    `SPEC_KITTY_ENABLE_SAAS_SYNC` is now an opt-out. A shell `export` of the
    opt-out (or of `SPEC_KITTY_SAAS_URL`) is still machine-global with no
    project-scoped form.

    **The scoped alternative is the per-repo `.kitty.env` tier** (see
    [The `.kitty.env` file](#the-kittyenv-file) below): a value in
    `<repo>/.kittify/.kitty.env` only takes effect for `spec-kitty` invocations
    whose resolved project root is that repo, so setting either variable there
    does not affect any other checkout on the machine.

    ```bash
    # Scoped to one invocation
    SPEC_KITTY_ENABLE_SAAS_SYNC=0 spec-kitty dashboard

    # Scoped to this repo only — write once, no per-shell export
    echo 'SPEC_KITTY_ENABLE_SAAS_SYNC=0' >> .kittify/.kitty.env

    # Affects every project this shell touches afterwards — know what you are doing
    export SPEC_KITTY_ENABLE_SAAS_SYNC=0
    ```

    Run `spec-kitty doctor env-file` to see which tier is actually supplying
    each governed variable.

### SPEC_KITTY_ENABLE_SAAS_SYNC

Opt **out** of hosted auth, tracker, and sync flows. On by default (#3980,
Team Kitty launch defaults): unset or `1` means hosted sync is on; `0` (or any
non-truthy non-empty value) is the explicit opt-out.

**Scope**: machine-global (see the warning above). Opting out is not a
per-repository decision unless written to the per-repo `.kitty.env` tier.

**Purpose**: Restores the fully local CLI workflow on a launch build.

**Example**:
```bash
export SPEC_KITTY_ENABLE_SAAS_SYNC=0
spec-kitty auth login
```

**See also**:
- [Internal Hosted-Readiness (Pre-Launch)](../operations/internal-hosted-readiness.md)
  for the operator walkthrough of the pre-launch opt-in era this
  flag used to gate.
- [Launch-Readiness Behavior (Coming Soon)](../architecture/launch-readiness-future.md)
  for the launch-coordinator playbook behind the default flip.

### SPEC_KITTY_SAAS_URL

Override the packaged default Spec Kitty SaaS base URL
(`https://team.spec-kitty.ai`, #3980 — the env var is a dev/self-host
override, not a requirement).

An explicitly exported value is always a real opinion (#4259): it wins over
`config.toml [sync].server_url` even when it equals the packaged default, so
exporting the canonical URL is a positive way to pin the target on a machine
whose saved target is stale. (`spec-kitty upgrade` migrates a saved retired
first-party address to the canonical one; self-hosted values are never
rewritten.)

**Scope**: machine-global when **exported**; repo-scoped when set in a per-repo
`.kitty.env` (see the warning at the top of this section). Exporting this in a
shell points every project that shell touches at the named instance.

**Purpose**: Point auth, tracker discovery, and sync clients at a specific hosted environment such as a dev deployment.

**Example**:
```bash
export SPEC_KITTY_SAAS_URL=https://spec-kitty-dev.example.internal
spec-kitty auth login
```

**See also**:
- [Internal Hosted-Readiness (Pre-Launch)](../operations/internal-hosted-readiness.md)
  -- this URL override is a dev / staging tool used by internal
  operators, not user behavior.
- [Launch-Readiness Behavior (Coming Soon)](../architecture/launch-readiness-future.md)
  -- the override remains internal-only after launch; only the
  user-facing default URL changes.

### SPEC_KITTY_SYNC_DISABLE

The single process-wide kill switch for sync-adjacent work (#3980): truthy
disarms hosted sync outright (`sync_active()`) and also suppresses
moment-handler registration. Nothing else reads it.

```bash
export SPEC_KITTY_SYNC_DISABLE=1
```

### SPEC_KITTY_NO_MOMENT_HANDLERS

Register no Zeitgeist moment handlers at import time (#3980) — the
moment-handler import gate's own name. `SPEC_KITTY_SYNC_MINIMAL_IMPORT` is a
deprecated alias of this gate and warns once when honored.

```bash
export SPEC_KITTY_NO_MOMENT_HANDLERS=1
```

### SPEC_KITTY_SKIP_PRE_REVIEW_GATE

Skip the pre-review regression gate that `agent tasks move-task --to
for_review` runs synchronously (#3980) — the gate's own process-wide opt-out;
it no longer reads the sync-disable vocabulary. The per-invocation form is
`--skip-pre-review-gate`.

```bash
export SPEC_KITTY_SKIP_PRE_REVIEW_GATE=1
```

### SPEC_KITTY_MACHINE_CLIENT_ID / SPEC_KITTY_MACHINE_CLIENT_SECRET / SPEC_KITTY_MACHINE_CLIENT_SECRET_FILE

The CI/machine credential for `spec-kitty auth login --machine` (#3277): a
ServicePrincipal's `client_id` plus its `client_secret`, exchanged via the
OAuth `client_credentials` grant with no browser, device flow, or prompt.

**Scope**: process environment of the runner only. These are **never**
candidates for `.kitty.env` — the secret is never committed — and
`SPEC_KITTY_MACHINE_CLIENT_SECRET` is treated as secret-shaped everywhere
(provisioning emits at most a commented blank template; diagnostics report
name/presence only, never the value).

**Purpose**: lets an unattended CI runner authenticate and run hosted
commands with a machine identity the SaaS attributes and can revoke as a
unit. The target server is selected by `SPEC_KITTY_SAAS_URL` exactly as for
every other hosted flow.

**Example**:
```bash
export SPEC_KITTY_SAAS_URL=https://team.spec-kitty.ai
export SPEC_KITTY_MACHINE_CLIENT_ID=01J...
export SPEC_KITTY_MACHINE_CLIENT_SECRET=...   # or SPEC_KITTY_MACHINE_CLIENT_SECRET_FILE=/run/secrets/...
spec-kitty auth login --machine
```

A missing or rejected credential fails closed with a precise remediation —
never a device-flow or browser prompt — and the secret value never appears
in output, logs, or errors.

**See also**: [CI Machine Authentication](../operations/ci-machine-auth.md)
for the full runbook — the three authentication modes, provisioning,
rotation, and revocation.

---

## Release Channel

### SPEC_KITTY_PRERELEASE

Opt in to the pre-release (rc) consumer channel.

**Purpose**: Default-off. Unset (the default), every "latest version" surface —
`spec-kitty upgrade --agent-check`, the throttled startup nag — reports the newest
**stable** release only, even when a newer release candidate exists on the configured
index. Set to a truthy value and the newest PEP 440 pre-release is surfaced instead, with
the proposed upgrade command a **pinned** `spec-kitty-cli==<rc>` install — never a floating
`--pre` flag. See [ADR: default-off rc release channel](../adr/3.x/2026-08-16-4-rc-release-channel.md).

**Example**:
```bash
export SPEC_KITTY_PRERELEASE=1
spec-kitty upgrade --agent-check
```

Or, once, in `.kitty.env` — no per-shell export needed:
```bash
# .kittify/.kitty.env or ${SPEC_KITTY_HOME}/.kitty.env
SPEC_KITTY_PRERELEASE=1
```

**Check the active channel**:
```bash
spec-kitty doctor channel
```

**See also**: [ADR: default-off rc release channel](../adr/3.x/2026-08-16-4-rc-release-channel.md).

---

## The `.kitty.env` file

Most `SPEC_KITTY_*` variables above can be set **once** in `.kitty.env` instead of a
per-shell `export`. This is not a new mechanism per variable — it is a single, generic
pre-import loader that seeds `os.environ` before any other `spec-kitty` module is imported,
so every existing reader (all ~88 of them) sees the value with no code change.

**Two tiers**, later overriding earlier:

| Tier | Location | Scope |
|---|---|---|
| Home | `${SPEC_KITTY_HOME}/.kitty.env` | Machine-wide default (all projects) |
| Repo | `<repo>/.kittify/.kitty.env` | This repository only — overrides the home tier |

Precedence is **real shell env > per-repo tier > home tier**: an already-exported shell
variable always wins over anything in either file. `.kittify/config.yaml` carries the single
pointer `env_file: ${SPEC_KITTY_HOME}/.kitty.env`, resolved once at bootstrap; there is no
separate `CONFIG_HOME`-style variable.

**Format** is plain `KEY=VALUE`, one per line; `#` comments and blank lines are ignored; an
optional leading `export ` is stripped so the file stays shell-sourceable; one layer of
surrounding quotes is stripped from the value:

```bash
# .kittify/.kitty.env
SPEC_KITTY_ENABLE_SAAS_SYNC=0
SPEC_KITTY_SAAS_URL=https://spec-kitty-dev.example.internal
# SPEC_KITTY_SAAS_TOKEN=       (secret-shaped vars are provisioned as commented templates —
#                                fill in by hand; never auto-populated with a live value)
```

**Fail policy**: an absent file is normal (the default state for almost every project) and
is silently skipped; a *present but unreadable* file fails loud, naming the path — because it
gates authentication. A malformed line is skipped with a debug log, never aborts startup.
`SPEC_KITTY_HOME` — the variable that *locates* the home-tier file — cannot be set from
inside the file it locates; a line defining it there is dropped with a warning.

**The repo tier is checkout-controlled — treat it like a shell export from that repo, not
like a scoped secret.** A committed `<repo>/.kittify/.kitty.env` is read and seeded into
`os.environ` for anyone who clones the repo and runs `spec-kitty` inside it, on the same
trust footing as a variable they exported themselves — including `SPEC_KITTY_SAAS_URL` and
`SPEC_KITTY_TEAM_SLUG`. This is different from `.kittify/saas-auth.json`, which
`load_auth_context` (`specify_cli/saas_client/auth.py`) explicitly refuses to pair with an
already-set env token (#237/#264): the repo-tier `.kitty.env` carries no such refusal, because
by the time `load_auth_context` runs its values are indistinguishable from the real shell
environment. Do not run `spec-kitty` commands that touch a `SPEC_KITTY_SAAS_TOKEN` inside a
freshly cloned, unreviewed repository without checking `.kittify/.kitty.env` first (`spec-kitty
doctor env-file` shows what each tier supplies). Tracked as #289.

**Provisioning**: `spec-kitty upgrade` runs an idempotent migration that creates the
per-repo scaffold, registers the `env_file` pointer, and adds `.kitty.env` to both
`.gitignore` and `.claudeignore` — it never seeds `SPEC_KITTY_PACKS_ROOT` (see that
variable's entry above) and never writes a secret *value*.

**Check health**:
```bash
spec-kitty doctor env-file
```
Reports presence, resolved tier, and ignore-rule coverage per file; a governed var's value
is only ever printed when it is on the fail-closed printable-var allowlist — everything else
shows presence and tier only.

**See also**: [ADR: operator config env-expansion seam](../adr/3.x/2026-08-16-5-operator-config-env-expansion-seam.md),
[Configuration Reference § env_file Pointer](configuration.md#env_file-pointer),
[Team Kitty (SaaS) architecture](../architecture/team-kitty-saas.md).

---

## Output and UX

### SPEC_KITTY_NO_NAG

Disable CLI upgrade check notices.

**Purpose**: Suppress human upgrade notices for the current shell. This also
keeps JSON, quiet, help, version, CI, and non-TTY output clean.

**Example**:
```bash
export SPEC_KITTY_NO_NAG=1
spec-kitty next --agent claude --mission my-mission --json
```

### SPEC_KITTY_NAG_THROTTLE_SECONDS

Override the minimum interval between upgrade checks.

**Purpose**: Tune local upgrade-check cadence. Values outside the supported
range fall back to the default silently.

**Example**:
```bash
export SPEC_KITTY_NAG_THROTTLE_SECONDS=86400
spec-kitty upgrade --cli
```

### SPEC_KITTY_UPGRADE_DISABLED

Disable the launch-readiness upgrade UX.

**Purpose**: Hard kill switch for the interactive readiness prompt and
auto-upgrade path. It is evaluated per invocation and is not persisted.

**Example**:
```bash
export SPEC_KITTY_UPGRADE_DISABLED=1
spec-kitty upgrade --cli
```

### SPEC_KITTY_UPGRADE_AUTO

Attempt safe auto-upgrade without prompting when an upgrade is available.

**Purpose**: Per-invocation override equivalent to choosing "Always keep me up
to date". Auto-upgrade still only runs for known-safe install methods such as
`pipx`, `uv tool`, Homebrew, and pip installs. Unknown or source installs print
manual guidance instead of mutating anything.

**Example**:
```bash
export SPEC_KITTY_UPGRADE_AUTO=1
spec-kitty upgrade --cli
```

### SPEC_KITTY_UPGRADE_NEVER_ASK

Suppress the launch-readiness upgrade prompt.

**Purpose**: Per-invocation override equivalent to choosing "Never ask again".
It does not rewrite the persisted cache unless the user chooses that option at
the interactive prompt.

**Example**:
```bash
export SPEC_KITTY_UPGRADE_NEVER_ASK=1
spec-kitty upgrade --cli
```

### SPEC_KITTY_SIMPLE_HELP

Request a simpler help presentation.

**Purpose**: Reduce the formatted help surface for terminals or wrappers that prefer plainer output.

**Example**:
```bash
export SPEC_KITTY_SIMPLE_HELP=1
spec-kitty --help
```

### SPEC_KITTY_NO_BANNER

Suppress the startup banner.

**Purpose**: Useful for scripts, screenshots, or wrappers that want less decorative output.

**Example**:
```bash
export SPEC_KITTY_NO_BANNER=1
spec-kitty init my-project --ai claude
```

---

## Selector / Compatibility Toggles

### SPECIFY_REPO_ROOT

Override repository-root discovery for certain internal path-resolution flows.

**Purpose**: Primarily useful for advanced development or unusual wrapper setups.

**Example**:
```bash
export SPECIFY_REPO_ROOT=/path/to/repo
spec-kitty verify-setup
```

### SPEC_KITTY_SUPPRESS_FEATURE_DEPRECATION

This variable is now inert. The `--feature` alias has been hard-removed from all
user-facing commands as of this release. No deprecation warnings are emitted;
this variable has no effect. Operators who have this set in their environment may
safely unset it.

**Previously**: Suppressed warnings for the deprecated `--feature` alias.

### SPEC_KITTY_SUPPRESS_MISSION_TYPE_DEPRECATION

Suppress warnings for the deprecated mission-type alias surfaces.

**Purpose**: Only for transitional automation or compatibility harnesses.

---

## External Tool Convention

### CODEX_HOME (legacy only)

Legacy Codex prompt-home override.

This is a **Codex CLI convention**, not a Spec Kitty variable. Current Spec
Kitty Codex support uses project-local agent skills under
`.agents/skills/spec-kitty.<command>/SKILL.md`; do not set `CODEX_HOME` for
current Spec Kitty command-skill installs.

**Legacy-only example**:
```bash
export CODEX_HOME="/path/to/legacy/codex-home"
```

---

## Test-Only Variables

The codebase also contains test and harness overrides such as `SPEC_KITTY_TEST_MODE`, `SPEC_KITTY_CLI_VERSION`, and `SPEC_KITTY_AUTORETRY`. Those are intentionally omitted from day-to-day operator guidance because they exist for tests, CI fixtures, or internal retry harnesses rather than normal end-user workflows.

---

## Summary Table

| Variable | Purpose | Example Value |
|----------|---------|---------------|
| `SPEC_KITTY_HOME` | Override shared runtime home; locates the home-tier `.kitty.env` | `$HOME/.spec-kitty-dev` |
| `SPEC_KITTY_PACKS_ROOT` | Override built-in pack root resolution (never seeded by the `.kitty.env` scaffold) | `/opt/spec-kitty-packs` |
| `SPEC_KITTY_TEMPLATE_ROOT` | Use a local template checkout | `/path/to/spec-kitty` |
| `SPECIFY_TEMPLATE_REPO` | Use a custom remote template repo | `org/templates` |
| `SPEC_KITTY_NON_INTERACTIVE` | Disable prompts | `1` |
| `SPEC_KITTY_WORKTREE_REMOVAL_DELAY` | Delay worktree cleanup | `10` |
| `SPEC_KITTY_ENABLE_SAAS_SYNC` | Opt out of hosted sync/auth flows (on by default) | `0` |
| `SPEC_KITTY_SAAS_URL` | Override the packaged default hosted base URL | `https://spec-kitty-dev.example.internal` |
| `SPEC_KITTY_SYNC_DISABLE` | Process-wide kill switch for sync-adjacent work | `1` |
| `SPEC_KITTY_NO_MOMENT_HANDLERS` | Register no moment handlers at import | `1` |
| `SPEC_KITTY_SKIP_PRE_REVIEW_GATE` | Skip the pre-review regression gate | `1` |
| `SPEC_KITTY_PRERELEASE` | Opt in to the pre-release (rc) consumer channel | `1` |
| `SPEC_KITTY_NO_NAG` | Disable upgrade notices | `1` |
| `SPEC_KITTY_NAG_THROTTLE_SECONDS` | Override upgrade-check cadence | `86400` |
| `SPEC_KITTY_UPGRADE_DISABLED` | Disable upgrade readiness UX | `1` |
| `SPEC_KITTY_UPGRADE_AUTO` | Enable safe auto-upgrade override | `1` |
| `SPEC_KITTY_UPGRADE_NEVER_ASK` | Suppress upgrade prompt override | `1` |
| `SPEC_KITTY_SIMPLE_HELP` | Use simpler help output | `1` |
| `SPEC_KITTY_NO_BANNER` | Suppress startup banner | `1` |
| `SPECIFY_REPO_ROOT` | Override repo-root discovery | `/path/to/repo` |
| `SPEC_KITTY_SUPPRESS_FEATURE_DEPRECATION` | **Inert** — `--feature` alias removed; no warnings emitted | N/A |
| `SPEC_KITTY_SUPPRESS_MISSION_TYPE_DEPRECATION` | Silence deprecated mission-type warnings | `1` |
| `CODEX_HOME` | Legacy Codex CLI prompt-home override | Legacy only; current Codex skills live under `.agents/skills/` |

---

## See Also

- [Configuration](configuration.md) — Configuration file reference, including the `env_file` pointer
- [CLI Commands](cli-commands.md) — Command line reference
- [Non-Interactive Init](../guides/how-to/installation/non-interactive-init.md) — Common automation patterns
- [ADR: operator config env-expansion seam](../adr/3.x/2026-08-16-5-operator-config-env-expansion-seam.md) — the `.kitty.env` / provenance-token mechanism
- [ADR: default-off rc release channel](../adr/3.x/2026-08-16-4-rc-release-channel.md) — `SPEC_KITTY_PRERELEASE`
- [Team Kitty (SaaS) architecture](../architecture/team-kitty-saas.md) — the end-to-end hosted-sync flow these variables gate

## Getting Started

- [Claude Code Workflow](../guides/tutorials/claude-code-workflow.md)

## Practical Usage

- [Non-Interactive Init](../guides/how-to/installation/non-interactive-init.md)
- [Install Spec Kitty](../guides/how-to/installation/install-spec-kitty.md)
