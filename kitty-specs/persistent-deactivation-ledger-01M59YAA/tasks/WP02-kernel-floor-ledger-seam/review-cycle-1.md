---
affected_files: []
cycle_number: 1
mission_slug: persistent-deactivation-ledger-01M59YAA
reproduction_command:
reviewed_at: '2026-10-19T16:06:03Z'
reviewer_agent: claude
wp_id: WP02
---

# WP02 review, cycle 1: changes requested

Reviewer: claude (reviewer-renata). Base 3adc84da, commits 9213f548..9dff4be6.

Most of the WP is sound: the resolver rows match data-model §5 in both modes, the deny guard compares
normalised sets, the vocabulary derives from `ArtifactKind`, `ACTIVATION_YAML_KEYS` is pinned by tuple,
the kernel imports nothing upward, no boundary baseline grew, only the kernel resolver test and the
`_support` module reference the env var, and the 6 mypy errors in pack_context/pack_manager are
pre-existing on 37ed6c90. All four reported deviations are accepted (see "Deviations" below).
Four defects block approval.

## Defects

**Issue 1**: [HIGH] src/charter/activation/activation_ledger.py:436 - `_prepare_ledger_write` crashes with an
uncaught `ValueError("Cannot preserve YAML aliases or section boundaries")` from
`charter_yaml_io.render_yaml_document` whenever the write leaves the ledger empty. Reproduction:
ledger `deactivated_tactics: [t1]\n`, then
`_prepare_ledger_write(root, {"deactivated_tactics": []}, deny_change=DenyListChoice.ACTIVATE)`. The same
happens for `{"activated_tactics": None}` or `remove=("activated_tactics",)` on a single-key ledger. That is the
basic deactivate-then-reactivate round trip on a fresh project, where the ledger holds only the deny list.
`test_empty_deny_list_is_removed_on_write` misses it because its fixture also holds `activated_tactics`.
Required fix: handle a write that empties the document (for example render `{}\n` or keep the comments,
whichever is the documented choice), and add a test for a deny-only ledger whose last key is removed, with
the ledger reloading to an empty `LEDGER` afterwards.

**Issue 2**: [MEDIUM] src/charter/activation/activation_ledger.py:396-403 (`_assign`) - written values are not
checked against L2. `{"activated_tactics": "t2"}` is written verbatim (`activated_tactics: t2`), which the
next `load_activation_ledger` refuses. `{"deactivated_tactics": "t2"}` is silently turned into "remove the deny
list" (`_deny_set` maps a non-list to the empty set); with a `deny_change` this drops the existing deny entries
without complaint. Required fix: validate each written value (a list of strings, or `None`) before the guard
and before anything is written, raising instead of coercing. Add a test for each case and check the file is
byte-identical afterwards.

**Issue 3**: [MEDIUM] src/charter/activation/activation_ledger.py:264-268 (`_resolve`) together with
src/kernel/activation_ledger_store.py:118-128 - the seam's error text for a malformed `config.yaml` differs
from the golden text that WP03 must keep byte-identical. Today `pack_context._load_config` says
`Invalid YAML in .kittify/config.yaml: ...` and `.kittify/config.yaml root must be a mapping.`.
`load_activation_ledger` instead says `Invalid YAML in /abs/path/.kittify/config.yaml: ...` and
`/abs/path/.kittify/config.yaml root must be a mapping.`, because the kernel probe of `config.yaml` raises first
with its own text. A second, smaller difference: the kernel checks pointer existence with `is_file()`, where
today's code uses `exists()`, so a pointer that names a directory now gets the "does not exist" text instead of
`Invalid YAML in ...`. Required fix: make the seam produce today's texts for `config.yaml` (and keep the
`exists()` semantics, or record the change as a decision in design-decisions.md). Add a test that compares the
seam's message with `pack_context`'s for the same malformed `config.yaml`, on the same fixture.

**Issue 4**: [MEDIUM] src/charter/activation/activation_ledger.py:153 - data-model §1 says `ActivationLedger` is
frozen and hashable. `_unknown_deny_values` holds the raw YAML value (a `list`), so `hash(ledger)` raises
`TypeError: unhashable type: 'list'` whenever the ledger carries an unknown `deactivated_<x>` key. Reproduction:
ledger `deactivated_newkinds: [x]\n`. Required fix: store a hashable form (for example a tuple of strings,
validated like a known deny list, or a frozen copy) and keep `raw()` returning lists. Add a
`hash(load_activation_ledger(...))` assertion on a fixture with an unknown deny key.

## Deviations (accepted)

1. The hooks live in `tests/_support/activation_strict_mode.py`, bound into conftest by assignment. This is
   accepted: `test_home_owner_behaviour.py` freezes conftest's definition list. WP14 must own and delete the
   module (already in carry-forward.md), and the no-env-var gate must cover it.
2. `SWEPT_PREFIXES` lists WP02's two new files. This is required by the test-mode rules.
3. Underscore-private `_prepare_ledger_write`, `_legacy_save_accepts_deny` and `_legacy_activation_scope` until
   their consumers land. This is accepted; the carry-forward notes name the WPs that make them public.
4. `ledger_exists`, `report_stray=`, public `config_error`, the kernel format-error wrapping and sorted, deduplicated
   deny lists are accepted. All are consistent with §1, §5 and §6 (L3).

## Notes (non-blocking)

- The red commit is red by `ModuleNotFoundError` at collection. That is acceptable for new modules.
- `report_stray_legacy_keys` dedupes on the stray tuple, not per root. This is fine, but the docstring says
  "per root".
