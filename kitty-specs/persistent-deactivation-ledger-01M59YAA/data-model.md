# Data model: Persistent deactivation, one activation ledger

All kinds below are the charter-activatable `ArtifactKind` members (`kind.activatable`, 11 today:
directive, tactic, styleguide, toolguide, paradigm, procedure, agent_profile,
mission_step_contract, glossary_pack, anti_pattern, skill). No list is written by hand; every key
set derives from the enum (C-004). Revised after the post-plan squad (R1–R12, B1, M1–M5, P2–P15).

## 1. Activation ledger file — `.kittify/charter/activation.yaml`

The file is git-tracked. It is an *optional* tracked bundle member and an *optional* content-hash
member (§10). It is a flat YAML mapping, and every key is optional.

| Key | Type | Absent means | `[]` means | Writers |
|---|---|---|---|---|
| `activated_kinds` | list of plural kind names | every kind | no kind | `charter activate`, presets |
| `mission_type_activations` | list of mission-type ids | none in force (#2657) | none | `init` provisioning (B1), upgrade provisioning, `charter activate mission-type`, presets |
| `activated_<plural>` | list of ids | the kind's `effective_when_absent` default: `"all"` → every available artifact; `"required"` (skill) → the required floor | nothing (fail-closed empty) | activate/deactivate, promotion, presets, synthesis |
| `deactivated_<plural>` | non-empty sorted list of ids (stem spelling) | no exclusion | treated as absent; never written | explicit choices only (§6) |

Example:

```yaml
mission_type_activations: [software-dev, research]
activated_tactics: [reasons-canvas-fill, tdd-red-green]
deactivated_directives: [DIRECTIVE_025]
deactivated_tactics: [reasons-canvas-review]
```

Invariants:

- **L1**: an unknown **non-deny** key → `ActiveCharterConfigError` (fail closed, nothing written).
  An unknown `deactivated_<x>` key (a later CLI's new kind) is preserved verbatim, ignored by
  readers and reported as a doctor warning (P15).
- **L2**: every value is a list of strings. `null` reads as absent and is never written.
- **L3**: an empty `deactivated_<plural>` is never written. The writer removes the key, and the
  guard compares normalised sets, so absent, `[]` and `null` are equal (P13).
- **L4**: `deactivated_*` keys exist only here, never in `charter.yaml` or `config.yaml` (C-003).
- **L5**: an id can sit in both lists only after a hand edit. Deny wins over the allow list, never
  over the required floor. Doctor warns.
- **L6**: deny entries change only through an explicit choice (§6, FR-008/FR-014).

Typed read model (`charter.activation.activation_ledger.ActivationLedger`, frozen, hashable):

```python
@dataclass(frozen=True)
class ActivationLedger:
    path: Path
    source: ActivationSource                       # LEDGER | LEGACY (§5)
    exists: bool                                   # False: LEDGER with no file yet (fresh project)
    activated_kinds: tuple[str, ...] | None
    mission_type_activations: tuple[str, ...] | None
    allow: tuple[tuple[ArtifactKind, tuple[str, ...] | None], ...]
    deny: tuple[tuple[ArtifactKind, tuple[str, ...]], ...]
    unknown_deny_keys: tuple[str, ...] = ()        # P15
    stray_legacy_keys: tuple[tuple[Path, tuple[str, ...]], ...] = ()   # P10: legacy keys beside a ledger
    def allow_for(self, kind: ArtifactKind) -> tuple[str, ...] | None: ...
    def deny_for(self, kind: ArtifactKind) -> tuple[str, ...]: ...
    def raw(self) -> dict[str, Any]: ...
```

`list_cmd` reads `ActivationLedger` through `charter.activation.api`. There is no separate
`list_deactivated` (R12).

## 2. Effective-set algebra (FR-006)

For a kind *k*:

- `Avail(k)` is the set of ids available across the built-in, org-chain and project layers.
- `R(k)` is the **required floor**: the union of `required_<plural>` over every declared org pack and
  each pack's `extends:` chain, read by one iterator (§4) and normalised to stems. Precedence
  never decides membership (C-005). The read is **strict**: an unreadable or malformed declared
  pack, or an `extends:` cycle or dangling base, raises `ActiveCharterConfigError`. It never
  silently widens (R3/P8).
- `D(k)` is the ledger's `deactivated_<plural>`.
- `D*(k) = resolve_deny(D(k)) − R(k)` is the **effective deny**, held in identity space (§2.1).
- `A(k)` is the allow state: `ABSENT`, `[]`, or a list `S`.

```
base(k) = S                          if A(k) = S
        = ∅                          if A(k) = []
        = Avail(k)                   if A(k) = ABSENT and effective_when_absent(k) = "all"
        = R(k) (+ built-in defaults) if A(k) = ABSENT and effective_when_absent(k) = "required"
E(k)    = base(k) − D*(k)            (membership tested in identity space)
Sel(k)  = (selected_<k> ∪ R(k)) − D*(k)     (governance selection overlay, US1.6)
```

### 2.1 Identity-space deny (R4/R5)

```python
@dataclass(frozen=True)
class DenySet:
    stems: frozenset[str]
    declared_ids: frozenset[str]
    urns: frozenset[str]           # DRG URNs (normalize_activation_identifier)
    def admits(self, token: str) -> bool: ...   # False if token matches any spelling
```

`resolve_deny(kind, tokens, identity: IdentityIndex) -> DenySet` is the one subtraction helper.
`PackContext.from_config` calls it once, and only for kinds with a non-empty `D(k)`.

`PackContext` additions:

| Member | Meaning |
|---|---|
| `denied: tuple[tuple[str, DenySet], ...]` | per plural, sorted, hashable; `D*` |
| `denied_for(kind) -> DenySet` | empty `DenySet` when nothing is denied |
| `admits(kind, token, *, available) -> bool` | allow state (absent → default; under absent "all" the token must be in `available`) and not denied — the effective-membership accessor (M2) |
| `effective_ids(kind, available) -> frozenset[str]` | `E(k)` over *available* |
| `deactivated_urns: frozenset[str]` | union of `DenySet.urns` (cascade, DRG filter) |
| `activated_<plural>` | present lists netted by `D*`; absent stays `None` |

Gate `test_no_raw_activation_membership.py` forbids raw `.activated_<plural> is None` /
`is not None` / `in ….activated_<plural>` checks outside `pack_context.py` and
`activation_ledger.py`.

Facts the conformance table pins:

| Allow | Deny | Required | Effective |
|---|---|---|---|
| absent ("all") | {D} | ∅ | Avail − {D} |
| [A, D] | {D} | ∅ | {A} |
| [] | {D} | ∅ | ∅ |
| absent ("all") | {D} | {D} | Avail (stale deny inert) |
| absent (skill, "required") | {S} | {R1} | {R1} |
| [A] | ∅ | {R1} | {A} (unchanged; promotion adds required ids) |
| [declared-id X] | {stem of X} | ∅ | ∅ (identity space, R4) |
| absent ("all"), agent_profile | {P} | ∅ | profile registry and action bundle omit P (M2) |

Mission types and `activated_kinds` have no deny list.

## 3. Plans (pure) and the single write

`ActivationPlan` (frozen) gains `deny_key: str | None`, `new_deny_list: list[str] | None` (`[]`
removes the key) and `deny_change: DenyListChoice | None`. Reporting deltas are **computed**,
not stored (R11): `deny_delta(before, after) -> (added, cleared)`. They are used for the
`ActivationResult` text, the preset report and the cascade "reinstated" line.
`PromotionOutcome.skipped_denied: dict[str, list[str]]` stays (its data does not come from a
delta).

State transitions for one id *x* of kind *k*:

| Command | Precondition | Allow after | Deny after |
|---|---|---|---|
| `deactivate k x` | x ∈ R(k) | refused (§6) | unchanged |
| `deactivate k x` | floor unreadable | refused (`ActiveCharterConfigError`) | unchanged |
| `deactivate k x` | x ∉ Avail(k) and x ∉ S | refused (unknown id) | unchanged |
| `deactivate k x` | x ∈ D | unchanged (warning) | unchanged |
| `deactivate k x` | otherwise | S − {x} / [] / absent | D ∪ {x} |
| cascade child of `deactivate` | exclusive, not required, S present | S − {child} | unchanged |
| cascade child of `deactivate` | allow absent | absent; rendered "still active (no allow-list; only P excluded)" (P11) | unchanged |
| `activate k x` | x ∈ D, A absent, "all" | absent | D − {x} |
| `activate k x` | x ∈ D, A absent, "required" | in-force set + x | D − {x} |
| `activate k x` | x ∈ D, A = [] or S | [x] / S + x | D − {x} |
| `activate k x` | x ∉ D, A absent | (materialised in-force set − D*) + x (#4253) | unchanged |
| `activate k x --only` | any | R(k) stems + x | D − {x} |
| promotion (interview / org / synthesis / migration) | x ∈ D* | unchanged (x skipped, warned) | unchanged |
| preset without `--force` | x listed, x ∈ D* | preset list − {x} (warned) | unchanged |
| preset with `--force` | x listed, x ∈ D | preset list | D − listed |
| cascade activate, x reached | x ∈ D*, no opt-in | unchanged; the walk stops at x | unchanged |
| cascade activate `--include-deactivated` | x ∈ D | S + x / absent | D − {x} |
| `init` provisioning (B1) | fresh project | `mission_type_activations` only | none |

`commit_plan` assigns both keys and calls `save(path, data, deny_change=plan.deny_change)` once.

## 4. Required provenance (one reader, R3)

```python
@dataclass(frozen=True)
class RequiringPack:
    pack: str               # the chain member whose own org-charter.yaml lists the id
    via: str | None = None  # the declared pack whose extends: chain inherits it
```

- `_iter_org_charter_docs(repo_root, *, strict)` yields `(declared_pack, member_pack, raw)`,
  walking `extends:` once.
- `read_org_required_ids` and `_read_org_required_selections` (overlay) read the same iterator.
- `read_org_required_provenance(repo_root, kind, *, strict) -> dict[stem, tuple[RequiringPack, ...]]`.

`RequiringPack` reaches specify_cli through `pack_manager.__all__` (existing baseline row, m5).

## 5. Source resolution (FR-017 amended, one resolver in kernel, R2; one mode after the reduced flip)

`kernel.activation_ledger_store.resolve_activation_source(repo_root, *, legacy_keys)` returns a
`ResolvedActivationSource`: `source` (`LEDGER | LEGACY`), `unmigrated: bool` (with
`unmigrated_keys`), the resolved `pointer: Path | None` (with `pointer_exists: bool`) and
`stray_legacy_keys`. The kernel **never raises an activation-domain error**; callers keep their own
error texts (`pack_context.py:570` `_config_error`, `pack_manager.py:658`, the SPDD probe's
`_SpddActivationConfigError`). Only the raw read's `ActivationLedgerFormatError` is a kernel raise.

**Shipped semantics after WP14** (`mission_pivot_option_b`, 2026-10-20):

| Ledger file | Upgrade scope (canonical-root aware, M3) | Legacy keys | Read | Allow-only write | Deny write |
|---|---|---|---|---|---|
| exists | any | none | ledger | ledger | ledger |
| exists | any | present | ledger; `stray_legacy_keys` as data → FR-020 warning on the ordinary read path; doctor `LEGACY_KEYS_PRESENT` | ledger | ledger |
| absent | inside | any | `LEGACY`, byte-for-byte (shipped migrations) | legacy | never (no migration writes deny; rc8 refuses legacy deny keys) |
| absent | outside | present (**unmigrated**) | `LEGACY`, `unmigrated=True`: legacy **allow** keys only; `deactivated_*` keys there are dropped and reported (FR-020 path, doctor `LEGACY_DENY_KEY`) | legacy target, as on `main` | **refused** (`ActiveCharterConfigError` naming `spec-kitty upgrade` / `migrate activation-ledger`), nothing written |
| absent | outside | none (**fresh**) | `LEDGER`, `exists=False` | ledger (created) | ledger (created) |

Rules:
- **Deny write**: the outgoing mapping contains a `deactivated_<kind>` key, or the normalised deny
  sets differ. A non-`None` `deny_change` that clears nothing is not a deny write. So on an
  unmigrated project, `activate`, `--preset --force` and cascade `--include-deactivated` succeed.
- **No implicit ledger**: a writer may create `activation.yaml` only for a **fresh** project. An
  unmigrated project gets it only from `spec-kitty upgrade` or `spec-kitty migrate activation-ledger`.
  Creating it beside legacy keys would strand them as stray keys, widening to "absent = all".
- **Kept for the legacy reader until the epic** (epic child #6535: retire the legacy activation reader): `compiler._bootstrap_charter_yaml` keeps copying the legacy **allow** keys (never deny keys) into a newly bootstrapped `charter.yaml` **only when the activation source is LEGACY** (an unmigrated project). When a ledger exists, or the project is fresh, it copies nothing, so it never duplicates the ledger's keys or creates stray keys beside it. Removing the copy entirely is the epic's (#6535); also the `CharterYaml` activation fields.
- **Upgrade finalizer provisioning** (pass-8 M3) resolves its target outside the legacy scope, after the migrations, so a keyless pre-ledger project is fresh and gets the ledger.
- **Init seed** (pass-8 M4): the rc8 record is not seeded while legacy activation keys exist and no ledger exists.
- The legacy-key probe is cached per process, keyed on `(path, mtime, size)` (NFR-003).

**During the Mission (WP02–WP10, removed by WP14)**: `SPEC_KITTY_ACTIVATION_STRICT` selected a
tolerant mode (today's storage; the legacy save carried deny keys; blank → legacy) or a strict
mode (unmigrated → fail closed; `test` additionally raised on stray keys). Its only purpose was
in-Mission testing, and none of it ships.

Scope state: `_LEGACY_SCOPE: ContextVar[frozenset[Path]]` holds resolved and canonical roots.

It is entered by:

- `BaseMigration` for every public project-path method a subclass defines in `cls.__dict__`;
- `MigrationRegistry.get_applicable`;
- the `MigrationRunner` selection points;
- `spec-kitty migrate ledger`;
- the `spec-kitty upgrade` command body.

## 6. Refusal and error shapes

| Error | Base | Raised by | Fields | Exit / effect |
|---|---|---|---|---|
| `ActiveCharterConfigError` (existing) | `KittyInternalConsistencyError` | malformed ledger, strict floor unreadable, **deny write on an unmigrated project** (names `spec-kitty upgrade` / `spec-kitty migrate activation-ledger`; checked before any write and before the floor read, all-or-nothing for a cascade), a deny key bound for a legacy surface | `body` | CLI exit 1; nothing written. The fail-open callers (P2) now propagate it |
| `UnmigratedActivationError` | — | **dropped** (D0): the kernel returns `UNMIGRATED`; the activation seam raises `ActiveCharterConfigError` naming the files, the keys and `spec-kitty upgrade` | — | — |
| `DenyListWriteRefused` (new) | `ActiveCharterConfigError` | `prepare_ledger_write` with `deny_change=None` and a normalised deny difference | `key`, `added`, `removed` | nothing written; a programming error the FR-014 gate catches |
| `DeactivationRefused` (new, abstract) | `ValueError` | `check_deactivation_permitted` | `kind`, `artifact_id`, `reason` (`"required"`; a later `"locked"` plugs in) | CLI direct: exit 1; cascade: rendered skip |
| `RequiredArtifactDeactivationError` (new) | `DeactivationRefused` | same | `policy_key`, `requiring: tuple[RequiringPack, ...]` | `Cannot deactivate directive 'D': required by org pack 'acme' (required_directives). Nothing was recorded.` |
| `UnknownActivationIdError` (existing) | `ValueError` | `plan_activation`, now also `plan_deactivation` | `kind`, `artifact_id` | exit 1 |
| `NoActivationRestrictionsError` | — | **removed** (C-008) | — | — |

Explicit choice (R1). There is no token object, only a keyword:

```python
class DenyListChoice(StrEnum):
    ACTIVATE = "activate"                                   # charter activate <kind> <id> [--only]
    DEACTIVATE = "deactivate"                               # charter deactivate <kind> <id>
    CASCADE_INCLUDE_DEACTIVATED = "cascade-include-deactivated"
    PRESET_FORCE = "preset-force"                           # charter activate --preset X --force

def prepare_ledger_write(repo_root, values, *, remove=(), deny_change: DenyListChoice | None = None): ...
```

Every caller that passes a non-`None` `deny_change` is pinned by the static half of the FR-014
gate.

## 7. Cascade result shape (FR-010/FR-011, operator ruling `cascade_walk_through_denied`)

```python
@dataclass(frozen=True)
class ReferencedArtifact:                 # reused for every bucket entry (R10)
    kind: ArtifactKind
    artifact_id: str
    urn: str
    via_requires: bool = False            # the source or a reached node has a REQUIRES edge to it
    required_by: tuple[str, ...] = ()     # those parents' URNs, sorted

@dataclass(frozen=True)
class CascadeActivationResult:
    activated: dict[str, list[str]]                                  # unchanged
    skipped_by_scope: dict[str, list[str]]                           # unchanged
    not_cascaded_kind_filtered: dict[str, list[str]]                 # unchanged
    skipped_deactivated: dict[str, list[ReferencedArtifact]] = {}    # new
    unreached_behind_deactivated: dict[str, list[str]] = {}          # new (P12)
```

Walk rules:

- **Denied nodes block expansion.** A denied node is recorded and not expanded; its `REQUIRES`
  (and other reference) edges are not followed.
- **Other paths still count.** A node that is reachable over another path avoiding every denied
  node is reached normally.
- **Unreached bucket.** `unreached_behind_deactivated` holds nodes in the full walk that are
  reachable only through denied nodes.
- **Opt-in.** `--include-deactivated` walks the full graph. Formerly denied nodes land in
  `activated`, and the "reinstated" report comes from the deny delta.
- **Invariant.** Every node of the full walk lands in exactly one bucket. Scope is decided
  before deny, so a denied node outside the scope is reported under `skipped_by_scope`.

CLI rendering (as shipped by WP07; one line per node):

```
Skipped (out of scope): styleguide/python-style
Skipped (out of scope): tactic/x (deactivated; nothing behind it was walked)
Skipped, deactivated: tactic/reasons-canvas-review (required by directive:DIRECTIVE_038 — the parent no longer has this requirement)
Unreached (behind a deactivated artifact): procedure/canvas-review-checklist
Hint: Run with --include-deactivated to activate these and clear their exclusions.
```

The no-cascade warning adds `referenced kind/id is deactivated and was not activated.`, and
`--include-deactivated` lives in a separate "Cascade options" help panel. A mission type is a
cascade source too (FR-022).

Cascade deactivation: the engine's `DeactivationPlan` is unchanged (C-007). The CLI renders
required children as "skipped (required by <pack>)". Under an absent allow list it renders
children as "still active (no allow-list; only <P> excluded)" (P11).

## 8. Conformance case table (FR-015)

`tests/charter/conformance/activation_ledger_cases.yaml`, schema `activation-ledger-conformance/1`.
Every case records each artifact id in **both spellings**, `{stem, declared_id}`, with
`declared_id == stem` when there is no distinct declared id, so that the charter harness can map
to contract URNs (FR-024). A `divergences:` section registers the semantic differences from the
contract (FR-024).
The sections are `effective_set`, `identity`, `readers`, `cascade`, `deactivation` and
`ledger_migration`. Every case is plain data: ledger mapping, required map with packs, available
ids, identity rows (stem ↔ declared id), graph edges, legacy surfaces. Each case carries the
expected answer.

```yaml
schema: activation-ledger-conformance/1
effective_set:
  - id: absent-all-minus-deny
    kind: directive
    available: [A, B, D]
    required: {}
    ledger: {deactivated_directives: [D]}
    expect: {effective: [A, B]}
identity:
  - id: declared-id-allow-stem-deny
    kind: procedure
    identity: [{stem: canvas-review, declared_id: PROC_CANVAS_REVIEW}]
    ledger: {activated_procedures: [PROC_CANVAS_REVIEW], deactivated_procedures: [canvas-review]}
    expect: {effective: []}
cascade:
  - id: stop-at-denied
    graph: {edges: [[directive:P, tactic:C, requires], [tactic:C, procedure:G, requires]]}
    source: directive:P
    scope: all
    ledger: {deactivated_tactics: [C]}
    include_deactivated: false
    expect:
      activated: {}
      skipped_deactivated: {tactic: [{id: C, via_requires: true, required_by: [directive:P]}]}
      unreached_behind_deactivated: {procedure: [G]}
deactivation:
  - id: required-refused
    kind: directive
    artifact_id: D
    required: {D: [{pack: acme}]}
    ledger: {}
    expect: {refused: {reason: required, packs: [acme], policy_key: required_directives}, ledger_after: {}}
  - id: cascade-child-absent-allow
    kind: directive
    artifact_id: P
    graph: {edges: [[directive:P, tactic:C, suggests]]}
    ledger: {}
    expect: {ledger_after: {deactivated_directives: [P]}, children: {tactic: [{id: C, state: still-active-no-allow-list}]}}
divergences:                      # FR-024: core vs the proposed charter contract
  - id: required-on-read
    core: "a required id is not served when an explicit allow list omits it; never subtracted by deny"
    contract: "required and locked are always active on read"
    status: logged
    ruling: required_always_active_divergence
    cases: [explicit-allow-omits-required]
  # ... write-time-floor, preset-force-clears-exclusions, unknown-deny-key-preserved, stale-required-deny-inert,
  #     languages-authored-vs-derived, id-spelling, unknown-token
  # activate/deactivate are NOT divergences: charter #125 aligned select/deactivate with core (R8, 1:1)
ledger_migration:
  - id: pointer-charter-yaml-moves
    surfaces: {charter_yaml: {activated_directives: []}, config_yaml: {charter: .kittify/charter/charter.yaml}}
    expect: {ledger: {activated_directives: []}, charter_yaml_keys_removed: [activated_directives], refused: null}
  - id: stray-copy-authority-lacks-key
    surfaces: {charter_yaml: {}, config_yaml: {charter: .kittify/charter/charter.yaml, activated_tactics: [T]}}
    expect: {refused: {key: activated_tactics}}
  - id: legacy-deny-key-refused
    surfaces: {charter_yaml: {activated_tactics: [T], deactivated_tactics: [X]}, config_yaml: {charter: .kittify/charter/charter.yaml}}
    expect: {refused: {key: deactivated_tactics}}
  - id: rerun-after-crash-strips-equal
    surfaces: {ledger: {activated_tactics: [T]}, charter_yaml: {activated_tactics: [T]}}
    expect: {ledger: {activated_tactics: [T]}, charter_yaml_keys_removed: [activated_tactics], refused: null}
```

## 9. Doctor findings (FR-005, R12)

`org_drg["activation_ledger"] = {"errors": [Finding], "warnings": [Finding]}`, where
`Finding = {"code", "file", "key", "ids", "message"}`.

| Code | Severity | Condition |
|---|---|---|
| `ACTIVATION_STORE_ERROR` | error | the seam raised `ActiveCharterConfigError` (malformed ledger, unreadable required floor); `message` is its body |
| `ACTIVATION_UNMIGRATED` | warning | legacy activation keys and no ledger; reads stay legacy (`mission_pivot_option_b`); names `spec-kitty upgrade` / `migrate activation-ledger` |
| `LEGACY_DENY_KEY` | error | a `deactivated_<kind>` key on a legacy surface: never applied, and the migration refuses it; remedy: remove it by hand, then migrate |
| `REQUIRED_OMITTED_BY_ALLOW_LIST` | warning | FR-023 / R12: an org-required id that an explicit `activated_<kind>` list omits (names packs); `charter list` shows it as `required (not in force: explicit allow list omits it)` and `--json` `required_not_in_force` |
| `LEGACY_KEYS_PRESENT` | error | activation keys in `charter.yaml`/`config.yaml` beside a ledger (the ledger wins). Computed from the resolver's `stray_legacy_keys` data, never via the raising read path (M2). |
| `DENY_UNKNOWN_ID` | warning | deny entry no layer provides |
| `DENY_REQUIRED_ID` | warning | deny entry for an org-required id (names packs; required wins) |
| `DENY_SELECTED_ID` | warning | `answers.selected_<kind>` lists a denied id |
| `UNKNOWN_DENY_KEY` | warning | `deactivated_<x>` for a kind this CLI does not know (P15) |

## 10. Bundle membership (FR-018, M5/P14)

- `CharterBundleManifest.optional_tracked_files: list[Path]` holds `ACTIVATION_YAML`. It is
  disjoint from `tracked_files` and `derived_files`, and `tracked_files` is unchanged (the shipped
  rc35 bundle migration and `charter bundle validate` are unaffected).
- `BUNDLE_OPTIONAL_CONTENT_HASH_FILES = (ACTIVATION_LEDGER.name,)`, derived from `kernel.activation_ledger_store` (no new literal, M5). Its digest is appended only when
  the file exists, so a project without a ledger keeps its hash, and an out-of-band ledger edit
  changes the hash and is detected.
- Every successful ledger write is followed by `restamp_bundle_hash`.


## 11. Narrow move command (FR-021, operator ruling `dogfood_migration_path`)

`spec-kitty migrate activation-ledger [--dry-run] [--json]` runs only the ledger migration's
move. It shares the planner and apply functions with `4.0.0rc8_activation_ledger`.

**Behaviour**:
- The refusals are the same as the migration's: divergence (FR-004) and a legacy `deactivated_*` key.
- It is idempotent.
- It runs inside `legacy_activation_scope`.
- On success it writes the `success` row for `4.0.0rc8_activation_ledger` **only when `.kittify/migration-ledger.jsonl` already exists** (ledger-adopted project), through the ledger module's writer. With no migration ledger it records nothing (`ledger_record: "not_recorded"`), because creating the file would flip `metadata._ledger_adopted` and drop `metadata.yaml`'s `migrations:` history before the backfill reads it. A later `spec-kitty upgrade` then still selects rc8; its `detect()` is False, nothing moves, and the runner records `skipped` (carry-forward M2; binding: WP08 T051.2). `ledger_record` is exactly `written` or `not_recorded`.

**Exit codes**:

| Code | Meaning |
|---|---|
| 0 | moved, or nothing to do |
| 1 | refused; nothing written |
| 2 | usage error |

**JSON shape**:

```json
{"result": "moved|noop|refused|dry_run",
 "moves": [{"key": "...", "from": "...", "to": "..."}],
 "refusal": {"key": "...", "files": ["..."], "reason": "divergent|legacy_deny_key"} ,
 "ledger_record": "written|not_recorded"}
```

`refusal` is `null` when the command did not refuse.
