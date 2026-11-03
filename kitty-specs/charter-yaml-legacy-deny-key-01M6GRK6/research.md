# Research: the legacy `deactivated_<kind>` key on `charter.yaml` (#6855)

## Question

`CharterYaml` (`extra="forbid"`) declares the *allow* vocabulary and no `deactivated_<kind>`
field. A legacy `charter.yaml` carrying a hand-written deny key therefore fails
`model_validate`. #6855 defers the contract to this mission: does the model accept (and
report) the key, or keep refusing (and the docs stop implying it is legitimate)?

## R1 — Reproduction on current `main`

Base: `main` at `f1e860a17f` (branch `issue-6855-charter-yaml-legacy-deny-key`).

```
$ uv run --frozen python - <<'PY'
from charter.activation.schemas import CharterYaml
sound = {
    "schema_version": "2.0.0",
    "governance": {},
    "directives": {"directives": []},
    "catalog": {"mission": "software-dev", "template_set": "software-dev-default",
                "languages": [], "references": []},
    "metadata": {"generated_at": "2026-01-01T00:00:00Z", "bundle_schema_version": 2},
}
print("sound validates:", bool(CharterYaml.model_validate(sound)))
CharterYaml.model_validate({**sound, "deactivated_tactics": ["x"]})
PY
sound validates: True
ValidationError: 1 validation error for CharterYaml
deactivated_tactics
  Extra inputs are not permitted [type=extra_forbidden, input_value=['x'], input_type=list]
```

Still open: not fixed on `main`, no PR references #6855, the last commit touching
`schemas.py` is #6556's `4d948f52c9`, and no `unreleased` fragment mentions the deny side.

## R2 — What the deny key *is*, today

- **The writer never produces it.** Since #6496 the deny-list lives in
  `.kittify/charter/activation.yaml`; `deactivated_<kind>` is not in `ACTIVATION_YAML_KEYS`;
  `prepare_activation_write` refuses a deny change on a legacy surface
  (`_refuse_legacy_deny`, `refuse_unmigrated_deny_write`).
- **The read path tolerates it, and reports it.** `_stored_deny` reads the ledger seam only;
  a legacy surface's hand-written deny key is "reported, never applied". Every command warns
  once (`report_legacy_deny_keys`).
- **Doctor treats it as an error.** `activation_ledger._legacy_key_finding` classifies a
  `deactivated_` key on a project without a ledger as the `LEGACY_DENY_KEY` **error**:
  "it was never applied, and the move to the ledger refuses it. Remove it by hand…".
- **The migration refuses it.** `plan_ledger_migration` → `_deny_refusal` returns
  `LedgerMigrationRefusal(..., "legacy_deny_key")` and nothing is written.

So the only way such a key exists on `charter.yaml` is a hand edit, and every surface that
encounters it calls it a defect to be removed — not a shape to be preserved.

## R3 — The recorded decisions

1. **ADR 2026-10-19-1, Decision 1 (constraint C-003):** "`deactivated_*` keys never appear in
   `charter.yaml` or `config.yaml`." The ledger is the single home.
2. **Same ADR, Amendment 2026-10-20 (`mission_pivot_option_b`):** on an unmigrated project "a
   `deactivated_<kind>` key found there is never applied: each command warns once, doctor
   reports `LEGACY_DENY_KEY` (an error), and the migration refuses it". Also: the `CharterYaml`
   activation fields are kept only "so unmigrated `charter.yaml` files keep validating" and
   are themselves slated for removal by the alignment epic (#6535) — the model is being
   narrowed, not widened.
3. **#6556's mission spec** (`kitty-specs/charter-yaml-activation-key-parity-01M67HRX/spec.md`,
   Edge Cases): "Legacy `deactivated_<kind>` keys … so the model keeps rejecting them. They
   are ledger content, not `charter.yaml` content." That is the decision the same reviewers
   reached when #6556 was landed; #6855 was split out to record it deliberately.

## R4 — Why acceptance would be a regression, not just a semantic choice

`charter.activation.compiler` constructs the emitted `charter.yaml` as a `CharterYaml`
instance (`compiler.py` line ~915), and `emit_yaml` dumps `model_dump(mode="json")` with the
`_OPTIONAL_EMPTY_OMIT_KEYS` prune list. A declared `deactivated_*: list[str] | None = None`
field would serialize as `deactivated_<kind>: null` (or `[]`) onto every generated charter
unless all names were also added to the omit list — and adding them there would be a second,
contradictory statement of policy. NFR-005 of
`consolidate-charter-bundle-01KXSYB9` (byte-stable emitted YAML) would break for every
project that regenerates its charter.

## R5 — Decision

**Keep the refusal.** The evidence is one-sided: an operator-authored ADR constraint (C-003),
doctor's own error classification, the migration's refusal, and the preceding mission's
recorded edge case all say the key is not `charter.yaml` content. The only text pointing the
other way is `_stored_deny`'s "reported, never applied", which describes the read path and
reads, misleadingly, like acceptance — so the fix is to make that sentence precise and to make
the model's refusal say what it means.

Shape of the fix (plan.md D1–D3):

- refuse with a message naming the ledger, "never applied" and the remedy (still refuses);
- no `deactivated_*` field, so no emitted-byte change and no C-003 contradiction;
- pin refusal + disjointness + absence of fields in
  `tests/charter/test_activation_vocabulary_setequal.py`, derived from
  `activation_ledger.DENY_KEYS` so it cannot drift.

## Rejected alternatives

| Alternative | Why rejected |
|---|---|
| Declare `deactivated_<kind>` fields on the model | Contradicts ADR C-003; a declared field is emitted by `compiler`/`emit_yaml`, breaking byte stability (R4); it advertises an illegal shape as legal. |
| `model_validator(mode="before")` that *strips* the keys and reports | Silently accepts a document the ledger/doctor/migration call an error; the reported "never applied" would become "validated after silent drop", which is worse than a refusal. |
| Leave the bare `extra_forbidden`, docs-only change | The message is the reported defect ("reads like a model bug"); the contract would stay unstated at the point of failure. |
| Widen `extra` to `allow` | Deletes the structural guard (paula BLOCKER-1) that the model exists for. |
