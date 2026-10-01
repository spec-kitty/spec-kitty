# Data Model: test-suite-remediation-01M3SSDW

Four record shapes:

1. the dead-symbol allowlist file (FR-009), which is a committed artefact;
2. the masked-green inventory item (FR-001..FR-005);
3. the pin inventory item (FR-006..FR-008);
4. the evidence record (FR-011).

Items 2–4 are mission artefacts under `evidence/`. They are not product code.

**Who writes them:** WPs report their evidence records **in full** (per item: path::function::mutation, the old result, the new result on the break, and the result after revert) in their review notes and final report. The orchestrator materializes them under `kitty-specs/test-suite-remediation-01M3SSDW/evidence/` at closeout (tasks.md "Closeout (orchestrator)"). No code WP writes a `kitty-specs/` path.

The loader and gate behaviour for item 1 is specified in [contracts/dead-symbol-allowlist.md](contracts/dead-symbol-allowlist.md).

---

## 1. `tests/architectural/dead_symbol_allowlist.yaml`

### 1.1 Shape

```yaml
schema_version: 1

categories:                                   # mapping: category id -> category record
  category_a_slice_f_deferred:
    rationale: "Slice-F forward API held for Slice G; ..."   # required, non-empty
    requires_issue: false                     # required bool
    target: "0 by Slice G"                    # optional free text (burn-down target)
  category_b_grandfathered_legacy:
    rationale: "..."
    requires_issue: true

entries:                                      # list of allowlist entries (__all__ scope)
  - module: specify_cli.dashboard.server      # required: dotted __all__-declaring module
    name: BackgroundPortReportError           # required: bare module-level name
    category: category_a_slice_f_deferred     # required: a declared category id
    rationale: "deliberately exported typed failure contract"   # optional; see L6
    issue: "#577"                             # optional; required when the category has requires_issue

widened_grandfathered_470:                    # the folded #470 list (non-__all__ scope)
  rationale: "Pre-existing debt surfaced by the #470 widening; triaged per entry"   # required
  issue: "#633"                               # required
  entries:
    - module: charter.activation._io
      name: load_charter_bytes
      note: "..."                             # optional; carries the existing per-entry comment
```

### 1.2 Field rules

| Path | Type | Required | Rule |
|---|---|---|---|
| `schema_version` | int | yes | Must equal `1`. Any other value is rejected. |
| `categories` | mapping | yes | Non-empty. Keys match `^category_[a-z0-9_]+$`. |
| `categories.<id>.rationale` | str | yes | Stripped, non-empty. |
| `categories.<id>.requires_issue` | bool | yes | A real YAML bool; a truthy string is rejected. |
| `categories.<id>.target` | str | no | Free text. |
| `entries[]` | list | yes | May be empty only when the allowlist is fully burned down. |
| `entries[].module` | str | yes | A dotted identifier, `^[A-Za-z_][\w]*(\.[A-Za-z_][\w]*)*$` with `re.ASCII`. |
| `entries[].name` | str | yes | A Python identifier (`str.isidentifier()`), not a dotted path. |
| `entries[].category` | str | yes | Must be a key of `categories`. |
| `entries[].rationale` | str | no | Non-empty if present. |
| `entries[].issue` | str | conditional | Matches `^(#\d+\|[\w.-]+/[\w.-]+#\d+)$`. Required when the category has `requires_issue: true`. |
| `widened_grandfathered_470.rationale` / `.issue` | str | yes | Non-empty; the issue follows the same pattern. |
| `widened_grandfathered_470.entries[]` | list | yes | `module` and `name` as above; `note` is optional. |
| any other key | — | — | Rejected, at every level. |

### 1.3 Category-id derivation (migration)

The category id is the existing constant name, lower-cased, with the leading underscore dropped (ruling R2; plan RK-4). For example, `_CATEGORY_C_TERMINUS_RECONCILIATION_5001` becomes `category_c_terminus_reconciliation_5001`.

The 9 empty tombstone `frozenset()` categories are **not** migrated.

### 1.4 In-memory model (loader output)

| Type | Fields | Notes |
|---|---|---|
| `DeadSymbolKey` | `module: str`, `name: str` | A frozen dataclass. `str()` gives `"module::name"`, the same text form the gate already prints for offenders. |
| `AllowlistCategory` | `id`, `rationale`, `requires_issue`, `target` | Frozen. |
| `AllowlistEntry` | `key: DeadSymbolKey`, `category: str`, `rationale: str \| None`, `issue: str \| None` | Frozen. The **effective rationale** is `entry.rationale or categories[entry.category].rationale`. |
| `WidenedEntry` | `key: DeadSymbolKey`, `note: str \| None` | Frozen. |
| `DeadSymbolAllowlist` | `categories`, `entries`, `widened_entries`, `widened_rationale`, `widened_issue` | Frozen, with the derived properties `keys: frozenset[DeadSymbolKey]` and `widened_qualified: frozenset[str]`. The second holds `"module::name"` strings, keeping parity with `_WIDENED_SCOPE_GRANDFATHERED_470`. |

Module-level exports of `_dead_symbol_allowlist.py`:
- `ALLOWLIST_PATH`;
- `load_allowlist(path)`;
- `AllowlistSchemaError`;
- `StaleVerdict`;
- `SYMBOL_ALLOWLIST: frozenset[DeadSymbolKey]`, loaded at import, which the size ratchet reads;
- `WIDENED_SCOPE_GRANDFATHERED_470: frozenset[str]`, loaded at import.

The gate keeps `_SYMBOL_ALLOWLIST` and `_WIDENED_SCOPE_GRANDFATHERED_470` as aliases of these.

### 1.5 Stale semantics (the `__all__`-scope entries)

Each entry is classified by exactly **one** verdict. The first matching rule wins, in this order. The inputs are:
- `all_literal_decls` (the static `__all__` per module);
- `corpus`;
- `star_targets`;
- the caller index;
- the auto-exempt predicate.

| Order | Verdict | Condition | Meaning / message hint |
|---|---|---|---|
| 1 | **INVALID** | `name ∈ all_literal_decls[module]` and `resolve_symbol_key(...) is None` | The name binds nothing keyable (e.g. `__all__ = ['Ghost']`). The entry cannot exempt it, so the symbol **also** stays an offender. |
| 2 | **GONE** | `name ∉ all_literal_decls.get(module, ∅)` | Deleted, renamed, moved, or dropped from `__all__`. Hint: if an offender `X::name` exists for another module `X`, append "probably moved to `X`; update `module:`". |
| 3 | **REVIVED** | declared and `_symbol_has_caller(...)` | The symbol is used again; delete the entry. |
| 4 | **SUPERSEDED** | declared and `_is_auto_exempt(...)` | A structural auto-exemption now covers it. This replaces today's separate disjointness test. |
| 5 | **MOOT** | `module ∈ star_targets` | The offender pass skips the module, so the entry exempts nothing. This is stricter than today; 0 star targets on this tree. |
| — | *(live)* | none of the above | The entry is earning its place. |

Any verdict other than *live* fails the gate and names `module::name`, the verdict and the hint.

The widened section keeps today's `_compute_widened_stale` semantics unchanged: "no longer a widened offender" / "already rescued: used within its own module".

### 1.6 Invariants

- `(module, name)` is unique across `entries` **and** `widened_grandfathered_470.entries` together.
- `len(SYMBOL_ALLOWLIST) <= _baselines.yaml[test_no_dead_symbols][allowlist_entries]`: the shrink-only cap (IC-12).
- No `line:`, `body_hash:` or `source_module:` field exists. Identity is location by name, never by content or line.

### 1.7 Parity snapshot (`evidence/dead-symbol-parity/{before,after}.json`)

```json
{
  "base_sha": "<commit the snapshot was taken on>",
  "allowlist": [["charter.drg", "merge_three_layers", "category_..."], ["...", "...", "..."]],
  "widened_470": [["charter.activation._io", "load_charter_bytes"]],
  "offenders": [],
  "stale": [],
  "counts": {"allowlist": 293, "widened_470": 91}
}
```

- Rows are sorted lexicographically, and the JSON is written with `sort_keys=True` and a fixed indent.
- Parity holds when `allowlist`, `widened_470`, `offenders` and `stale` are equal byte-for-byte between `before` and `after`. `base_sha` may differ only if the mission rebased, and then `before` is re-taken on the new base.

---

## 2. Masked-green inventory item

One record per row of `research/masked-greens.md`. The owning WP reports it, and the orchestrator writes it into the owning concern's evidence file at closeout.

| Field | Type | Example |
|---|---|---|
| `id` | `MG-NN` | `MG-02` |
| `requirement` | FR ids | `[FR-001, FR-005]` |
| `node_ids` | list[str] | `tests/specify_cli/doctrine/test_pack_validator.py::TestIntentAwareCollision::test_enhances_suppresses_collision_advisory` |
| `mask_kind` | enum | `probe-skip \| skipif \| xfail-strict \| quarantine \| importorskip \| error-to-skip \| dead-guard \| none` |
| `stated_reason` | str | `"shipped doctrine not on disk in this environment"` |
| `cited_issue` | str \| null | `EXPERIMENTAL#171` |
| `issue_state_at_plan` | enum | `open \| closed \| n/a` |
| `observed_before` | str | `SKIP ×2` |
| `disposition` | enum | `RUN \| RUN+FIX \| RE-POINT \| RETIRE \| CONVERT \| DELETE \| KEEP \| NO-OP` |
| `new_issue` | str \| null | "new issue (filed during implementation)", replaced by its number once filed |
| `covering_guard` | str \| null | required for `RETIRE` |
| `planted_break_ref` | evidence id | `EV-IC01-03` |
| `observed_after` | str | `PASS ×2` |
| `concern` | `IC-NN` | `IC-01` |

**Lifecycle**: `inventoried → dispositioned → proven (evidence recorded) → closed`. An item closes only with `observed_after` recorded and its evidence ids resolvable.

**Validation**:
- `RETIRE` requires `covering_guard`.
- `RE-POINT` requires `new_issue`, and that issue must be open at mission close (NFR-004).
- `NO-OP` requires a reason.
- `KEEP` on a platform or tool guard must name its exemption-list class.

---

## 3. Pin inventory item

One record per row of the pin dispositions table in [research.md](research.md#pin-dispositions-sc-004). The owning WP reports it in full in its review notes and final report; the orchestrator writes it into the concern's evidence file at closeout.

| Field | Type | Example |
|---|---|---|
| `id` | `#5346-N \| F-N \| K-N` (kept) \| `R-N` (resolved) | `F-11` |
| `site` | `path:line[,line]` | `tests/architectural/test_remediation_effectiveness.py:325,335,341,403` |
| `counts` | str | "remediation-emitting states in the live charter status computer" |
| `class` | enum | `live-structure-pin \| copy-pin \| name-mismatch \| ratchet \| contract \| local-test-value` |
| `repins_since_2026_08_01` | int | `1` |
| `disposition` | enum | `convert \| delete-with-guard \| keep-ratchet \| keep-contract \| not-a-pin \| resolved` |
| `invariant_form` | str \| null | "partition: emitting == set(_CASES) ..." |
| `covering_guard` | str \| null | required for `delete-with-guard` |
| `neutral_plant` | str \| null | required for `convert` and `delete-with-guard` (NFR-003) |
| `violation_plant` | str \| null | required for `convert` and `delete-with-guard` |
| `keep_reason` | str \| null | required for `keep-*` and `not-a-pin` |
| `resolution_commit` | sha \| null | required for `resolved` |
| `concern` | `IC-NN \| none` | `IC-07` |

**Validation**:
- A `convert` needs the neutral plant green with 0 test or baseline edits (NFR-003), and the violation plant red.
- A `keep-ratchet` must show that every historical move coincided with a debt change (FR-008).
- A `delete-with-guard` must satisfy C-002, via the evidence record.

---

## 4. Evidence record (FR-011)

**Location**: `kitty-specs/test-suite-remediation-01M3SSDW/evidence/IC-NN-<slug>.md`, one file per concern. WPs report the records **in full** in their review notes and final report; the orchestrator materializes them here at closeout. Split concerns merge their WPs' records into one file:
- IC-06 ← WP06 + WP07;
- IC-10 ← WP11 + WP12;
- IC-11 ← WP12 (refresh-helper retirement) + WP13;
- IC-12 ← WP14 + WP15.

**Format**: Markdown with one fenced `yaml` block per record, so a reviewer can parse it.

```yaml
id: EV-IC07-02
item: F-11                         # an MG-NN / #5346-N / F-N id
kind: FIX                          # FIX | RETIRE | RE-POINT | KEEP | RESOLVED | NO-OP
planted_break:
  target: "<the charter status-computer module the test AST-scans>"   # a file path (product or test fixture)
  description: "set remediation=None on state X without adding it to _EXEMPT_STATES"
  reverted: true                   # must be true (C-007)
command: "uv run --frozen pytest tests/architectural/test_remediation_effectiveness.py -n0 -q"
results:
  old_form_under_break: pass       # FIX: the old test stayed green on the break (it guarded nothing), or n/a
  new_form_under_break: fail       # FIX: the new form goes red
  neutral_plant: pass              # convert: a legitimate addition stays green with 0 edits
  clean_tree: pass
covering_guard:                    # required for RETIRE
  node_id: null
  under_break: null                # must be "fail" for RETIRE
counts:                            # NFR-001, for masked-green files
  executed_before: 12
  executed_after: 12
reviewer_rerun: false              # the independent review sets true for ≥6 FIX and ≥2 RETIRE (SC-005)
notes: ""
```

**Validation rules** (checked item by item at review):

| Kind | Must hold |
|---|---|
| FIX | `new_form_under_break == fail`, `clean_tree == pass`, and `planted_break.reverted == true`. |
| RETIRE | `covering_guard.node_id` is set and `covering_guard.under_break == fail` for the **same** planted break (C-002). |
| RE-POINT | The cited issue is open, and the strict xfail still fails for its reason (`--runxfail` shows fail). |
| KEEP | A reason, plus the exemption class or ratchet history. |
| RESOLVED | A resolution commit sha. |
| NO-OP | A reason, e.g. the row-8 false positive. |
| all | No commit in the mission branch contains the planted break (C-007). The reviewer checks that the product-source diff equals the intended fixes only. |

The evidence ids are cited from the inventory items (`planted_break_ref`) and from the PR's *Tests run* section.
