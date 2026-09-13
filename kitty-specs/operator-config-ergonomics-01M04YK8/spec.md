# Mission Specification: Operator Config & Install Ergonomics

**Mission Branch**: `fix/operator-config-ergonomics`
**Created**: 2026-08-16
**Status**: Draft
**Input**: Unified operator-config mission (epic #3493 / #3494 / #3495 / #3496), designed by a 6-agent research/design squad and hardened by a 3-lens post-spec squad. Design record: [design-record.md](./design-record.md).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Portable committed governance files (Priority: P1)

A maintainer generates or regenerates the charter on their machine and commits `charter.yaml`. A teammate on a different machine (or a CI job running an installed wheel) checks out the repo. The committed governance files must be identical regardless of whose machine or which install mode produced them — no absolute `/home/...`, `/Users/...`, or `site-packages/...` paths.

**Why this priority**: Absolute paths in committed governance files are a live portability defect (they leak one developer's filesystem into shared source) and block clean review. Smallest, lowest-risk slice; ships first.

**Independent Test**: Generate `charter.yaml` on an editable checkout and on an installed wheel; assert the catalog `source_path` values are identical and contain no absolute path — only portable `${SPEC_KITTY_PACKS_ROOT}/built-in/...` tokens.

**Acceptance Scenarios**:

1. **Given** a fresh charter compile on an editable checkout, **When** the catalog is written, **Then** every built-in `source_path` is a `${SPEC_KITTY_PACKS_ROOT}/built-in/...` token, not an absolute path.
2. **Given** an existing `charter.yaml` (or `agent_profiles_manifest.json`) that already contains absolute built-in paths, **When** the operator runs the heal migration, **Then** those entries are rewritten to portable tokens and re-running the migration changes nothing.
3. **Given** `SPEC_KITTY_PACKS_ROOT` is unset, **When** provenance is resolved for display, **Then** the token resolves via the same authority (ancestor-walk) and never renders literally or raises.
4. **Given** `SPEC_KITTY_PACKS_ROOT` is exported to an arbitrary absolute path at emit time, **When** `charter.yaml` and `agent_profiles_manifest.json` are written, **Then** both still store the `${SPEC_KITTY_PACKS_ROOT}/built-in/...` token byte-identical to the unset case (the machine path is never serialized — the re-bake footgun).

---

### User Story 2 - One-file SaaS opt-in (Priority: P1)

An operator wants hosted sync. Today they must export `SPEC_KITTY_ENABLE_SAAS_SYNC`, `SPEC_KITTY_SAAS_URL`, and tokens on every shell. Instead, they write these once into a single `.kitty.env` file; the CLI applies them everywhere, so `sync opt-in` / `sync now` work with no per-shell exports.

**Why this priority**: The headline operator-ergonomics pain (it directly blocked hosted-sync testing). Unlocks the smooth SaaS-opt-in experience.

**Independent Test**: With no env vars exported in the shell, place the sync vars in `.kitty.env`; run `sync doctor` and confirm the vars are seen (by name/presence) and sync commands proceed to the drain/delivery stage without a config error.

**Acceptance Scenarios**:

1. **Given** a `.kitty.env` in the home tier holding sync vars and no exported shell vars, **When** any `spec-kitty` command runs, **Then** those vars are present in the process environment and honored by the sync/auth readers.
2. **Given** the same var set in both real env and `.kitty.env`, **When** the CLI loads, **Then** the real-env value wins (file is fill-only, applied via a single `os.environ.setdefault` over the merged tiers).
3. **Given** a var defined in real env, per-repo `.kittify/.kitty.env`, and home-tier `${SPEC_KITTY_HOME}/.kitty.env`, **When** the CLI loads, **Then** precedence is real-env > per-repo > home-tier (tiers merged `{**home, **repo}` *before* the `setdefault` pass, so per-repo wins over home).
4. **Given** `SPEC_KITTY_SYNC_MINIMAL_IMPORT` (an import-time-read var) set only in `.kitty.env`, **When** a `spec-kitty` process starts, **Then** the import-time-gated behavior is active — proving the loader seeds before `import specify_cli` (`__init__.py:36`), not at `main()`.
5. **Given** a `.kitty.env` that exists but is unreadable (mode 000), **When** any `spec-kitty` command loads, **Then** it exits non-zero with a diagnostic naming the file (present-but-unreadable fails loud); an *absent* file warns-and-continues.
6. **Given** `.kitty.env` holds `SPEC_KITTY_SAAS_TOKEN`, **When** `doctor`/`sync status` render, **Then** the token value is never printed — only its presence (allowlist of printable var names).
7. **Given** a `.kitty.env` line defining `SPEC_KITTY_HOME` (the locator), **When** the CLI loads, **Then** that line is ignored with a warning (the locator cannot be redefined by the file it locates).

---

### User Story 3 - Opt-in unstable/rc release channel (Priority: P2)

An early adopter or dev-team member wants to catfood rc/internal builds. They opt in (default off); the CLI proposes and can install the latest rc. A normal consumer, never opted in, is only ever advised about stable releases.

**Why this priority**: Smooth catfooding for the team and early adopters, strictly gated so it never disrupts stable users. Consumer slice of #3047.

**Independent Test**: With the channel off, assert `upgrade --agent-check` reports the latest *stable* even when a newer rc exists on the configured index. With the channel on, assert it surfaces the newer rc and emits a pinned `spec-kitty-cli==<rc>` upgrade command.

**Acceptance Scenarios**:

1. **Given** the channel preference is unset (default), **When** the update check runs and a newer rc exists on the index, **Then** the operator is NOT advised to upgrade to it.
2. **Given** the channel is opted in, **When** the update check runs, **Then** the newest pre-release (PEP 440 pre-release on the configured index) is surfaced and the upgrade command is a pinned `spec-kitty-cli==<rc>` install command.
3. **Given** the channel is opted in via `.kitty.env` (`SPEC_KITTY_PRERELEASE`), **When** the CLI loads, **Then** the preference is honored without a shell export.
4. **Given** the channel state (on/off), **When** `doctor` runs, **Then** it reports the active channel as an info line.

---

### User Story 4 - Self-healing upgrade (Priority: P2)

An operator upgrades an existing project. Two independently-idempotent migrations run: one heals absolute provenance paths (WP1), one provisions the `.kitty.env` scaffold + registers the single `config.yaml` pointer + adds the ignore rules (WP2) — with no manual steps. Doctor reports the health of all of the above.

**Why this priority**: Existing projects (like this repo) already carry the defects; without remediation the generator fix alone leaves them broken.

**Independent Test**: Seed a project with absolute provenance and no `.kitty.env`; run upgrade; assert paths healed, `.kitty.env` created, pointer + ignore lines added; re-run and assert no changes (each migration idempotent).

**Acceptance Scenarios**:

1. **Given** a pre-migration project, **When** `spec-kitty upgrade` runs, **Then** provenance is healed (heal migration), `.kitty.env` is created, the `env_file` pointer is added to `config.yaml`, and `.kitty.env` is added to `.gitignore` and `.claudeignore` (provision migration).
2. **Given** the provision migration, **When** it seeds `.kitty.env`, **Then** it writes only values already set in the environment/legacy config, **never** invents secret values, and **never** seeds `SPEC_KITTY_PACKS_ROOT` (so the TEMPLATE_ROOT gate is not silently flipped).
3. **Given** an already-migrated project, **When** either migration runs again, **Then** it makes no changes.
4. **Given** a migrated project, **When** `doctor` runs, **Then** it reports env-file presence, resolved tier, readability, pointer registration, and ignore-rule presence (config-health facet), plus the provenance-leak check (0 absolute paths).

---

### User Story 5 - Documented Team Kitty (SaaS) architecture (Priority: P3)

A contributor needs to understand the hosted-sync flow. A dedicated Team Kitty (SaaS) architecture section with interaction diagrams documents opt-in/consent → store migration → admission/delivery-target → auth → drain-to-ledger → sync to `team.spec-kitty.ai`, plus ADR(s) recording the config-resolution, provenance-form, kernel-layering, and channel decisions.

**Why this priority**: Documentation/architecture debt — high onboarding value, not blocking the functional slices.

**Independent Test**: The architecture corpus contains a Team Kitty (SaaS) section with the end-to-end interaction diagram; the env-var and install/opt-in docs reference `.kitty.env` and the rc channel; the ADR(s) exist under `docs/adr/3.x/`.

**Acceptance Scenarios**:

1. **Given** the architecture corpus, **When** a reader looks for hosted-sync, **Then** a dedicated Team Kitty (SaaS) section with the opt-in→sync interaction diagram exists (this repo's `docs/architecture/`, not the sibling SaaS repo).
2. **Given** the config/env-resolution decision, **When** a reader consults the ADRs, **Then** the corresponding ADR(s) record the decision, drivers, and rejected options.

### Edge Cases

- **Missing/unreadable env file**: absent `.kitty.env` (fresh init, CI) warns-and-continues; present-but-unreadable `env_file` fails loud (it gates auth) — see FR-004a / US2.5.
- **Locator recursion**: `SPEC_KITTY_HOME` (the env-file locator) is ignored-with-warning if defined inside `.kitty.env` — US2.7.
- **Import-time reads**: `SPEC_KITTY_TEST_MODE` (`__init__.py:36`), `SPEC_KITTY_SYNC_MINIMAL_IMPORT` (`sync/__init__.py:455`) are read at import; the loader seeds before any spec-kitty import — US2.4.
- **PACKS_ROOT set flips the TEMPLATE_ROOT presence gate** (`kernel/paths.py:324`) — the scaffold must not seed it; regression-gated (C-003a).
- **Secret in subprocess**: a spawned daemon inherits `os.environ`; token values are never printed on any surface (NFR-004).
- **Malformed `.kitty.env` line**: skipped with a debug log, never aborts bootstrap — US2 (covered by FR-004 parser behavior; tested).
- **Windows**: home-tier location resolves under `%LOCALAPPDATA%\spec-kitty`.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Portable token provenance emit via a single shared normalizer | As a maintainer, I want charter-catalog and profile-manifest `source_path` emitted as `${SPEC_KITTY_PACKS_ROOT}/built-in/...` tokens through ONE shared path→token normalizer (both carriers), so committed files are machine-independent and the two emit sites cannot drift. | High | Open |
| FR-002 | Heal migration for existing provenance (WP1, standalone) | As an operator, I want an independently-idempotent migration that rewrites existing absolute built-in `source_path`s to portable tokens in `charter.yaml` and `agent_profiles_manifest.json`. | High | Open |
| FR-003 | Doctor provenance-leak check | As an operator, I want a doctor check that flags any committed absolute built-in path with a heal recovery hint. | Medium | Open |
| FR-004 | Two-tier `.kitty.env` pre-import loader | As an operator, I want `.kitty.env` (home-tier `${SPEC_KITTY_HOME}/.kitty.env`, overridden by per-repo `.kittify/.kitty.env`) loaded into the process env BEFORE any spec-kitty import; tiers merged per-repo-over-home, then a single `os.environ.setdefault` so real env wins. Hand-rolled `KEY=VALUE`, `is_truthy` grammar reused, malformed lines skipped with a debug log. | High | Open |
| FR-004a | Fail policy for the env file | As an operator, I want an absent `.kitty.env` to warn-and-continue but a present-but-unreadable `env_file` to fail loud; the locator `SPEC_KITTY_HOME` ignored-with-warning if set inside the file. | High | Open |
| FR-005 | Single `config.yaml` env-file pointer | As an operator, I want exactly one `env_file: ${SPEC_KITTY_HOME}/.kitty.env` expansion in `config.yaml`, resolved once at bootstrap, kept outside any `extra="forbid"` block; no separate `CONFIG_HOME` var. | High | Open |
| FR-006 | Kernel env-expansion seam | As a developer, I want one kernel `expand_env_template(raw, inject_defaults)` — fail-loud for resolution fields, default-inject for provenance/config — plus `get_packs_root_default()` returning `get_built_in_pack_root().parent` (token names the parent; resolver rejoins the fixed `built-in` child); `org_pack_config` delegates, keeping its fail-loud contract. | High | Open |
| FR-007 | Provision migration for `.kitty.env` (WP2, standalone) | As an operator, I want an independently-idempotent migration that creates `.kitty.env` (seeding only already-set values; never `SPEC_KITTY_PACKS_ROOT`), registers the single pointer, and adds `.gitignore` + `.claudeignore` rules. | High | Open |
| FR-008 | Secret redaction (fail-closed allowlist) | As an operator, I want a single allowlist of printable var names consulted by doctor/`sync status`/logs, so any var NOT on the allowlist (incl. newly-added secrets) is never printed by value. | High | Open |
| FR-009 | Default-off rc release channel | As an early adopter, I want a default-off `SPEC_KITTY_PRERELEASE` preference making update-checks pre-release-aware and the upgrade command a pinned rc install; stable users unaffected. | Medium | Open |
| FR-010 | Doctor env-file + channel health facets | As an operator, I want `spec-kitty doctor` to report `.kitty.env` health (presence, tier, readability, pointer, ignore rules — names only) via a `_env_file_doctor.py` sibling (WP04) **and** the active rc channel via a `_channel_doctor.py` sibling (WP05) — two physically-isolated facet files, not `runtime/doctor.py`. | Medium | Open |
| FR-011 | Docs + ADR + SaaS architecture section | As a contributor, I want the exact ADR set and interaction diagrams in SC-006, plus updated env-var/install/opt-in docs and the SOURCE `src/doctrine/skills/spk-team-*` skills. | Medium | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Startup budget | The pre-import env-file load adds bounded overhead measured as a delta against a no-file baseline (≤ the run-to-run noise floor of the completion benchmark), and does not regress the TAB-completion benchmark defined in the completion test suite. | Performance | High | Open |
| NFR-002 | Migration idempotency | Re-running each mission migration (heal, provision) produces zero changes, verified by a re-run assertion per migration. | Reliability | High | Open |
| NFR-003 | Provenance invariance | A committed `charter.yaml`/`agent_profiles_manifest.json` is byte-identical across editable checkout and installed wheel; 0 absolute built-in paths. (Forward: extracted-pack layout — non-blocking aim.) | Portability | High | Open |
| NFR-004 | Secret non-disclosure | 0 token values appear in any CLI output, log, or committed file; `.kitty.env` matches an ignore rule in both `.gitignore` and `.claudeignore`. | Security | High | Open |
| NFR-005 | Cross-platform resolution | Loader, locator, and pointer resolve correctly on POSIX and Windows, verified by path-resolution unit tests parametrized for both (incl. `%LOCALAPPDATA%\spec-kitty`). | Compatibility | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | DR-1 single read | Exactly one `os.environ` read per governed var at the kernel floor; the env-file seeds `os.environ`, it adds no readers. `SPEC_KITTY_HOME` is the bootstrap locator and is exempt (it locates the file, per C-004). | Technical | High | Open |
| C-002 | Kernel layering | The expand primitive + `KEY=VALUE` parsing arithmetic live at the kernel floor; kernel gains no upward imports (arch-gated by `test_kernel_no_doctrine_import`/`test_layer_rules`); the `.kitty.env` file-convention + shim wiring stay in specify_cli. | Technical | High | Open |
| C-003 | No absolute paths committed | No provenance/charter-compile path may serialize an absolute pack path into a committed artifact — regression-tested including the `SPEC_KITTY_PACKS_ROOT=<abs>`-exported case. | Technical | High | Open |
| C-003a | Scaffold must not seed PACKS_ROOT | The provisioned `.kitty.env` scaffold MUST NOT seed `SPEC_KITTY_PACKS_ROOT`; PACKS_ROOT stays an explicit opt-in override so the TEMPLATE_ROOT presence gate (`kernel/paths.py:324`) is not silently disabled — regression-tested. | Technical | High | Open |
| C-004 | HOME excluded / no locator recursion / no CONFIG_HOME | `.kitty.env` must not set `SPEC_KITTY_HOME`; the locator must not be definable inside the file; the deliberate `.kittify` vs `.spec-kitty` dual-root is preserved; the locator is `SPEC_KITTY_HOME` — NO separate `CONFIG_HOME` var is introduced. | Technical | High | Open |
| C-005 | rc channel default off | The unstable channel is off by default; stable-channel users are never advised onto an rc; CI rc-cadence + publication stay in #3047 (this mission is the consumer slice only). | Business | High | Open |
| C-006 | Naming convention | New vars keep the `SPEC_KITTY_` prefix (no bare `KITTY_*`); `stdlib-only` for the pre-import loader; Terminology Canon respected. | Technical | Medium | Open |
| C-007 | Change hygiene | Any change to `__init__.py` carries a `pyproject.toml` bump + `CHANGELOG.md` entry; new/changed branches carry tests in the same PR; ruff/mypy clean; run `tests/architectural/test_no_legacy_terminology.py` before pushing prose. | Technical | Medium | Open |

### Key Entities

- **`.kitty.env` file**: two-tier (home-tier `${SPEC_KITTY_HOME}/.kitty.env`, per-repo `.kittify/.kitty.env`) KEY=VALUE file holding path (excl. HOME) / sync / beta vars and secrets; gitignored + claudeignored.
- **`config.yaml` env-file pointer**: single `${SPEC_KITTY_HOME}`-expanded `env_file` key.
- **Kernel env-expansion seam**: `expand_env_template` + default-injection registry + `get_packs_root_default` (= `.parent`).
- **Shared path→token normalizer**: the single emit-side helper both provenance carriers consume.
- **Provenance token**: `${SPEC_KITTY_PACKS_ROOT}/built-in/...` in `charter.yaml` / `agent_profiles_manifest.json`.
- **Release-channel preference**: default-off `SPEC_KITTY_PRERELEASE`.
- **Secret allowlist**: printable-var-name allowlist (fail-closed) for output redaction.

## Dependencies & Assumptions

- **Epic #3493**; children **#3494** (T1/US1, WP1), **#3495** (T2/US2/US4, WP2), **#3496** (T3/US3, WP3 — consumer slice).
- **#3047 (rc producer half)** — coordination *interface*: the consumer (FR-009) discovers rc's as PEP 440 pre-releases on the same PyPI index the CLI already probes; #3047's producer half must publish rc's there under that scheme, else consumer and producer never meet. CI rc-cadence stays in #3047.
- **#3381 (consent migration)** — shares the upgrade-migration sequence with FR-007; ordering must be coordinated and both must be auto-run + idempotent (carry #3381's lesson).
- **#3251** (PACKS_ROOT fail-closed), **#3022** (external packs — the token form survives extraction; repo-relative would not), **#2519** (charter lifecycle) — related, cross-linked.
- **Decomposition constraints for the plan:** WP1 (heal) and WP2 (provision) are two *independent* migration files; `doctor.py` checks (FR-003, FR-008, FR-010) must be isolated per-check (campsite: #1623 god-module) so WP1/WP2/WP3 don't collide; sequence WP0 → (WP1 ∥ WP2) → WP3 → WP4 (WP3 reads `.kitty.env` → depends on WP0/WP2 loader).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A `charter.yaml` generated on two different machines / install modes (editable, wheel) is byte-identical and contains 0 absolute built-in paths — including when `SPEC_KITTY_PACKS_ROOT` is exported to an absolute path.
- **SC-002**: An operator enables hosted sync by editing a single `.kitty.env` file with **0** manual shell exports, and sync commands reach the drain/delivery stage without a config error.
- **SC-003**: With the channel off, **0** rc upgrade advisories reach a stable user even when a newer rc exists; with it on, the newest rc is surfaced and a pinned-install command is offered.
- **SC-004**: Upgrading an existing project heals **100%** of absolute built-in provenance paths and provisions the env-file with **0** manual steps; a second run of each migration makes **0** changes.
- **SC-005**: **0** secret values appear in any doctor/status/log output; `.kitty.env` is ignored by both `.gitignore` and `.claudeignore`.
- **SC-006**: The architecture corpus contains a dedicated Team Kitty (SaaS) section with (at minimum) the end-to-end opt-in→sync interaction diagram; and **exactly two ADRs** exist under `docs/adr/3.x/`: (1) the config/env-resolution + provenance-form + kernel-layering decision, (2) the default-off rc-channel decision.
