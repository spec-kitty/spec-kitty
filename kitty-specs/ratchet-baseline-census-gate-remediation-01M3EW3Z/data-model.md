# Data Model: Ratchet, baseline & census gate remediation

Entities are test-infrastructure records. All identities are content-based; a line number may appear only as a diagnostic, never as identity.

## ContentDescriptor entry (hand-curated allowlists)

Used by: join allowlist (WP02), kernel exemptions (WP03), os-detect exemptions (WP03).

The entry type is the existing substrate `NamedTuple` `tests/architectural/_ratchet_keys.py::ContentDescriptor` (no new type):

| Field | Type | Rule |
|-------|------|------|
| `rel_path` | str, repo-relative POSIX path | must exist at test time |
| `qualname` | str | the enclosing dotted qualname, as `_ratchet_keys.enclosing_qualname` outputs it |
| `token_substring` | str | a substring of the finding's **normalised** token line (`code_tokens_by_line` output), never raw source |
| `occurrence` | int ≥ 0 or `None` | 0-based ordinal among same-qualname/same-substring candidates; `None` means the substring must be unique within the qualname |
| `rationale` | str | non-empty justification |

**Invariants**
- Resolved in two steps by `tests/architectural/_content_identity.py` (WP02): `resolve_allowlist(descriptors, source_for)` turns descriptors into a `Counter[CompositeKey]` (`CompositeKey = (rel_path, qualname, token_line)`) and reports every descriptor that resolves to 0 or > 1 sites as an error (`DescriptorResolutionError` semantics); `partition_findings(findings, allowed)` returns `(unexpected, unused)`. Each entry suppresses **at most one** live finding (multiset semantics; `neutrality/lint.py:379/380` produce identical keys).
- **Stale = fail**: an entry that suppresses no live finding fails the gate and is named (FR-007, D-OP-8).
- Exemption text files (`_exemptions/os-detect-ban-*.txt`) hold one descriptor per line in the form `<rel_path>::<qualname>::<token_substring>[::<occurrence>]`, serialised by `_content_identity.render_descriptor_line` / `parse_descriptor_line` and loaded by `_os_detection_exemptions.py`; the `path:line` form is rejected by the widened ban.

## CensusKey (census allowlists)

Used by: destructive-op (22), mutation (56) and overwrite (2), all re-keyed in WP04 (split commits: helper → destructive + overwrite → mutation). Stale detection goes through `_content_identity.partition_findings` (D-OP-9).

| Field | Type | Rule |
|-------|------|------|
| `rel` | str | repo-relative path |
| `qualname` | str | `_ratchet_keys.enclosing_qualname(source, lineno)` (the census helper's own algorithm is deleted, C-004) |
| `token_line` | str | from `composite_key` |
| `op` | str | census operation label |
| `op_ordinal` | int ≥ 0 | ordinal among live findings sharing `(rel, qualname, token_line, op)`, ordered by source line |

**Invariants**
- Allowlist literal form: `CensusKey(rel=..., qualname=..., token_line=..., op=..., op_ordinal=...): "rationale"`.
- A second identical op in an exempted function yields `op_ordinal + 1` → unexpected → **fail**.
- Changed arguments → new `token_line` → unexpected (**fail**) + old key stale (**warn**).
- **Stale = warn** (documented census contract, unchanged).
- `len(test_mutation_ownership_routing._ALLOWLIST) == 56` (`destructive_op_allowlist`) is unchanged.

**Equivalence artefact** `census-rekey-map.csv`: `gate, old_key, rel, qualname, token_line, op, op_ordinal, rationale_sha256`, 80 rows; `research/census_rekey_equivalence.py --base <sha> --head-root <lane-worktree>` proves old site set == new site set, bijection, and rationale hashes equal; `--self-test` proves the script detects a flipped `op_ordinal`, a dropped key and a swapped rationale.

## Positional-anchor exemption row (interim)

| Field | Type | Rule |
|-------|------|------|
| `module` | str | gate module or exemption file |
| `symbol` | str | allowlist symbol (or file) |
| `site` | str | the flagged literal, verbatim |
| `reason` | str | non-empty; names the migrating WP |

**Lifecycle**: `interim (WP01: 94 rows)` → `shrinking (WP02–WP04 remove their rows)` → `pinned empty (WP13: frozenset equality with frozenset())`. Counted per site (NFR-003).

## Baseline leaf (`_baselines.yaml`)

| Field | Type | Rule |
|-------|------|------|
| path | `gate.key[.subkey]` | must appear in the single comparison table in `test_ratchet_baselines.py` |
| value | int ≥ 0 | live measurement must be ≤ value |

**Invariants (FR-011)**
- The set of allowed leaves is **derived from the comparison table**, not from a name search; a leaf outside it fails the ratchet and is named.
- For every enforced leaf, setting the value to `live − 1` makes the ratchet fail (mutation test; skipped only where live == 0 and the leaf is at 0, which is asserted separately).
- Removed leaves: `unassigned_entries`, `masking_suppressions` (WP05, sequenced edit), then `category_1`, `skip_marker_blocks` (WP06, D-OP-2). `baseline_entries`: 38 → 36 (WP05; stale `styleguide-references`, `model` rows dropped).

## Parity suite verdict (FR-018)

| Field | Values |
|-------|--------|
| module | path under `tests/` |
| discriminator | behavioural/negative invariant · positive shape · mixed |
| churn | commits touching file / co-changed with `src/`, window `git log --since=2026-03-26` at HEAD `34f19c6fb` (blobless clone holding history since 2026-03-20; `research/grounding-2631_2972.md` Part 2) |
| verdict | keep · convert · retire · split |
| surviving enforcer | test node ID, or cited reason + mutation proof (NFR-006) |

Recorded by WP12 in `research/parity-verdicts.md` and the mission's design-decisions tracer, in the #2620 catalog format.
