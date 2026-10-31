# Contract: the upgrade fixed point after the charter fold (#6549)

Pinned by `tests/upgrade/test_promote_answers_post_fold_convergence_6549.py`.

## Parties

- The **shipped promotion** `unify_charter_activation_promote_answers` (3.2.6rc1).
- The **charter fold** `consolidate_charter_bundle_fold` (3.2.6rc1, ordered after it).
- The **activation authority**: `.kittify/charter/activation.yaml` once
  `4.0.0rc8_activation_ledger` has run; otherwise the `charter.yaml` the `config.yaml`
  `charter:` pointer names.

## Clauses

1. **The shipped step never writes after the fold.** On a post-fold project the
   registered class for `unify_charter_activation_promote_answers` is a
   `SupersededMigration`; its `detect()` is False and its `apply()` changes no bytes.
   The shipped class imported directly keeps its original `detect()` (DIRECTIVE_044):
   the registry entry, not the class, is the guard.
2. **A second upgrade re-applies no activation migration.** For a project stamped
   below `3.2.6rc1` that carries `activated_directives` in `config.yaml` and mirrors
   that selection in `answers.yaml`, the second `upgrade` records no
   activation-migration row and commits no change to `config.yaml` or
   `.kittify/charter/`.
3. **No activation copy lives in `config.yaml` after the first upgrade**, and the
   interview selection is present in the activation authority instead.
4. **The guard is load-bearing.** Removing the id from
   `specify_cli.upgrade.supersession.SUPERSEDED_MIGRATIONS` and re-discovering the
   registry through `auto_discover_migrations()` makes the second upgrade write the
   whole built-in directive set back into `config.yaml`.

## Out of contract

A project already damaged by the pre-#6629 second pass keeps its divergent
`config.yaml` copy. It is ignored by every reader, reported by
`spec-kitty doctor charter-packs` as `LEGACY_KEYS_PRESENT`, and removing it is a
maintainer decision (issue #6549's suggested fix, `#6496` refusal semantics).
