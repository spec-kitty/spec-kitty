---
title: 'Operator configuration resolves through one kernel env-expansion seam; committed provenance stores tokens'
description: 'One kernel ${VAR} expander plus a two-tier .kitty.env seed the process env; committed provenance stores SPEC_KITTY_* tokens, never resolved paths.'
status: Accepted
date: '2026-08-16'
---
# Operator configuration resolves through one kernel env-expansion seam; committed provenance stores tokens

**Filename:** `2026-08-16-5-operator-config-env-expansion-seam.md`

**Status:** Accepted

**Date:** 2026-08-16

**Deciders:** Stijn Dejongh (operator); design squad (architect-alphonso design + paula-patterns adversarial review)

**Technical Story:** Epic #3493 (children #3494 portable provenance, #3495 `.kitty.env`); mission `operator-config-ergonomics-01M04YK8`; related #3047, #3381, #2519, #3251, #3022

---

## Context and Problem Statement

Three operator-facing config frictions shared one root cause: the CLI resolved environment
and directory state through roughly 88 scattered `os.environ.get` reads with no single
authority, and it committed machine-specific absolute paths into governance files.

1. Charter/doctrine catalog `source_path` was emitted as an absolute machine path (the
   `_trim_source_path` normalizer keyed on the dead `src/doctrine/` marker after built-in
   doctrine moved to `packs/built-in/`). Repo-relative was *already* not install-mode
   invariant — an installed wheel emits `site-packages/...`.
2. Opting into hosted SaaS sync required hand-exporting `SPEC_KITTY_ENABLE_SAAS_SYNC`,
   `SPEC_KITTY_SAAS_URL`, and tokens on every shell — there was no config-file home.
3. There was no smooth way to consume rc/internal builds (see the companion
   [rc release-channel ADR](2026-08-16-4-rc-release-channel.md)).

We needed one coherent resolution seam that makes committed provenance portable across all
install modes, gives operators a single file for their knobs, and does so without violating
the kernel's layering floor or the DR-1 single-read invariant.

## Decision Drivers

* Committed governance files must be byte-identical across editable checkout, installed
  wheel, and future externally-extracted packs (#3022).
* Operators must configure path/sync/beta knobs once, not per shell.
* DR-1: exactly one env read per var at the kernel floor; no second resolver.
* Layering: `kernel ← doctrine ← charter ← specify_cli`; kernel may gain no upward imports.
* Preserve the deliberate dual-root split `.kittify` (assets) vs `.spec-kitty` (state).
* Secrets must never be committed, slurped into agent context, or printed.

## Considered Options

* **A.** Repo-relative provenance only; no env-file (narrow bug fix).
* **B.** Env-templated provenance (`${SPEC_KITTY_PACKS_ROOT}/...`) with NO central expander.
* **C. (chosen)** One kernel `${VAR}` expander + token provenance + a two-tier `.kitty.env`
  (located via the existing `SPEC_KITTY_HOME`) seeded into `os.environ` by a pre-import shim.
* **D.** Introduce a new `SPEC_KITTY_CONFIG_HOME` locator var for the env-file.

## Decision Outcome

**Chosen option: "C"**, because it is the only option that makes committed provenance
invariant across all install modes while retiring the scattered-read problem behind one
authority, and it reuses the token-preservation pattern the codebase had already proved for
org-pack `local_path`.

Concretely, as shipped:

- **Committed provenance stores the token** `${SPEC_KITTY_PACKS_ROOT}/built-in/...`, never a
  resolved path. `.kitty.env` may set `SPEC_KITTY_PACKS_ROOT` as a per-machine *resolution*
  override; because provenance stores the symbol, the machine path is never baked in. The
  emit side runs through one shared path→token normalizer consumed by both carriers — the
  charter catalog source (`src/charter/compiler.py`) and the agent-profile manifest source
  (`src/specify_cli/tool_surface/profiles/projection.py`) — so the two emit sites cannot
  drift. An idempotent heal migration
  (`src/specify_cli/upgrade/migrations/m_3_2_7_heal_provenance_paths.py`) rewrites existing
  absolute paths in already-committed `charter.yaml` / `agent_profiles_manifest.json`, and a
  doctor sibling (`src/specify_cli/cli/commands/_provenance_doctor.py`, `doctor provenance`)
  flags any leak with a heal hint.
- **One expander at the kernel floor** (`src/kernel/env_expand.py`): `expand_env_template(raw,
  *, inject_defaults)` — fail-loud for resolution fields, default-inject for
  provenance/config fields. `get_packs_root_default()` (`src/kernel/paths.py`) =
  `get_built_in_pack_root().parent` (the token names the parent; the resolver returns the
  `built-in` child). `doctrine.drg.org_pack_config` delegates the pure transform and
  detection primitives (not the raising composition), preserving its own
  `OrgPackEnvVarUnsetError` exception type.
- **`.kitty.env` is the one home** for path (excl. `SPEC_KITTY_HOME`) / sync / beta knobs.
  Two tiers: user-global `${SPEC_KITTY_HOME}/.kitty.env` (the state root — `.spec-kitty` on
  POSIX, `%LOCALAPPDATA%\spec-kitty` on Windows) overridden by `<repo>/.kittify/.kitty.env`.
  `config.yaml` carries one expansion `env_file: ${SPEC_KITTY_HOME}/.kitty.env`, resolved
  once at bootstrap via a targeted top-level-key scan (not a full YAML/model load, so it
  cannot collide with `org_pack_config.PackRegistry`'s `extra="forbid"` `doctrine.org`
  section). **Reusing `SPEC_KITTY_HOME` as the locator** (option D rejected) avoids an
  invented var and any bootstrap circularity, since the env file never *sets* `SPEC_KITTY_HOME`
  — a line defining it inside the file is dropped with a `UserWarning` (locator-recursion
  guard).
- **Loaded by a pre-import shim** (`src/specify_cli/bootstrap/env_file.py`, invoked as the
  very first statements of `specify_cli/__init__.py` — before that module's own
  `SPEC_KITTY_TEST_MODE` read), `os.environ.setdefault` so real env always wins. Tiers are
  merged `{**home, **repo}` first, then exactly one `setdefault` pass — real-env >
  per-repo > home. The loader is stdlib + `kernel` only, no `specify_cli.core` import, kept
  off the startup critical path (NFR-001).
- **Fail policy**: an absent `.kitty.env` warns and continues (the default state for almost
  every project); a present-but-unreadable file fails loud, naming the path, because it
  gates auth. A malformed `KEY=VALUE` line is skipped with a debug log.
- **Provisioning**: an idempotent migration
  (`src/specify_cli/upgrade/migrations/m_3_2_8_provision_kitty_env.py`) creates the per-repo
  scaffold, registers the `env_file` pointer, and adds `.gitignore`/`.claudeignore` rules —
  seeding only values already set in the environment/legacy config, **never**
  `SPEC_KITTY_PACKS_ROOT` (it would silently flip the `kernel/paths.py` TEMPLATE_ROOT
  presence gate), and never a secret *value* (secret-shaped vars are emitted as a commented,
  blank template line). A doctor sibling
  (`src/specify_cli/cli/commands/_env_file_doctor.py`, `doctor env-file`) reports presence,
  tier, and ignore coverage — values never printed for anything off the fail-closed
  printable-var allowlist (`src/specify_cli/core/secret_redaction.py`).

### Consequences

#### Positive
* Committed charter/manifest provenance is identical across editable/wheel/extracted layouts;
  a regression test forbids any absolute pack path in committed artifacts, including the
  `SPEC_KITTY_PACKS_ROOT=<abs>`-exported re-bake case.
* Operators configure once; the ~88 downstream reads work unchanged against the seeded env.
* One expansion authority; kernel keeps DR-1 and gains no upward imports.

#### Negative
* Provenance tokens are less human-legible in committed YAML than a literal path (accepted:
  provenance is metadata; matches the existing org-pack convention).
* An always-set `SPEC_KITTY_PACKS_ROOT` flips the `kernel/paths.py` TEMPLATE_ROOT presence
  gate — documented and regression-tested; the provision migration categorically excludes
  seeding it for exactly this reason.
* Mixing secrets and portable knobs in one file forces the whole file to be treated as secret
  (mitigated: fully gitignored + `.claudeignore`d + a redaction allowlist).

#### Neutral
* A pre-import shim is a new, tiny startup surface; kept stdlib-only for the TAB-completion
  performance budget.

### Confirmation

Success signals, all met at ship time: (1) a portable-provenance regression test stays green
across editable and wheel installs; (2) `spec-kitty sync opt-in` works after a single
`.kitty.env` edit with no shell exports; (3) `doctor env-file` reports env-file health and
never prints token values; (4) architectural tests confirm the kernel has no upward import and
the home-owner pins are undisturbed.

## Pros and Cons of the Options

### A. Repo-relative provenance, no env-file
**Pros:** smallest change. **Cons:** not install-mode invariant (wheel → site-packages
absolute); breaks under #3022; does nothing for SaaS opt-in ergonomics.

### B. Env-templated provenance, no expander
**Pros:** portable string. **Cons:** nothing expands these fields without the expander — the
token renders literally and is unresolvable; strictly worse than a concrete path absent the
expander.

### C. Kernel expander + token provenance + two-tier `.kitty.env` (chosen)
**Pros:** install-mode invariant; one authority; reuses a proven pattern; solves all three
frictions coherently. **Cons:** more moving parts (expander, shim, two migrations); token
legibility.

### D. New `SPEC_KITTY_CONFIG_HOME` locator var
**Pros:** explicit config-home. **Cons:** invents a var that collides conceptually with
`SPEC_KITTY_HOME`; adds a bootstrap circularity surface. Rejected in favour of reusing HOME.

## More Information
- Design source: `kitty-specs/operator-config-ergonomics-01M04YK8/design-record.md` +
  `spec.md` / `plan.md` / `research.md`.
- Companion: [ADR: Default-off rc release channel](2026-08-16-4-rc-release-channel.md)
  (T3 / #3496), scoped against the rc-cadence producer half in #3047.
- Architecture: [Team Kitty](../../context/team-kitty.md); the end-to-end hosted-sync flow
  this seam underpinned was removed in #6164 (code preserved in `spec-kitty/event-router`).
- Cross-refs: #3251 (PACKS_ROOT fail-closed), #3381 (auto-run migration lesson), #2519.
