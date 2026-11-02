# Discovery — acceptance activation field pin (#7038)

## Reproduction on current `main`

Base: `origin/main` at `9aed3a8012` (the issue was filed against `874613dba7`; still red).

```text
$ uv run pytest tests/acceptance/test_unmigrated_cli_still_runs.py::test_charter_yaml_with_all_ten_activation_fields_still_loads -q
FAILED ...::test_charter_yaml_with_all_ten_activation_fields_still_loads
tests/acceptance/test_unmigrated_cli_still_runs.py:136: in ...
    assert len(fields) == 10
E   AssertionError: assert 13 == 10
1 failed in 2.39s
```

Not superseded: no merged PR or ADR addresses this test (`git log -S "len(fields) == 10" --
tests/` returns only #6496, the commit that introduced it). The issue is unassigned and
carries only `from:qa` before this Mission's claim.

## Decision 1 — the model is right and the test is wrong

Evidence, in history order:

1. #6496 (`a58a8ef830`, "test(charter): cover the activation ledger, deny survival and the
   ledger migration") introduced the test. At that commit `CharterYaml` declared exactly ten
   activation fields (`git show a58a8ef830:src/charter/activation/schemas.py`), so
   `assert len(fields) == 10` was true, but even then it was tautological: it derived the
   names from `CharterYaml.model_fields` and then asserted their count.
2. #6556 (`4d948f52c9`, "fix(charter): CharterYaml accepts every activation key the writer
   writes") deliberately added three fields — `activated_glossary_packs`, `activated_skills`
   and `activated_anti_patterns` — because `charter activate` on an unmigrated project writes
   them to `charter.yaml` and `model_validate` then failed `extra_forbidden`. `activated_assets`
   was deliberately excluded (`ArtifactKind.ASSET.activatable is False`).
3. The single vocabulary authority, `charter.activation.pack_manager.ACTIVATION_YAML_KEYS`,
   holds exactly 13 keys, and
   `tests/charter/test_activation_vocabulary_setequal.py::test_charter_yaml_activation_fields_set_equal_to_authority`
   asserts the model's activation fields are set-equal to it in both directions — green today.
4. #6556 updated the unit-level field test (`tests/charter/test_charter_yaml_model.py`) to
   parametrize over the authority and added the parity gate, but did not touch this acceptance
   test. That is the whole defect: a hard-coded count left behind by an intentional model
   growth.

Conclusion: bumping `10` to `13` would be wrong twice over — it leaves a second hand-restated
copy of the vocabulary (forbidden by the charter's single-authority rule) and keeps a pin that
can only fail on a legitimate addition. The acceptance test must stop restating the vocabulary.

## Decision 2 — read the field set from the authority; keep the behavioural load

- The vocabulary is owned by `ACTIVATION_YAML_KEYS`; the model-vs-authority set equality is
  owned by the parity gate. This test's job is the behavioural proof: a `charter.yaml` that
  carries every key the writer may write validates through `CharterYaml` and loads through the
  real `charter context --action implement` CLI. So the test takes the key list from the
  authority and keeps validating the document end to end.
- Non-vacuity: `assert fields` guards against an empty authority turning the loop into a no-op.
  A missing model field still reds the test through `extra="forbid"` on the document load, and
  the parity gate names missing/stray keys for a faster diagnosis.
- Import the authority lazily (function-scoped), matching the #6556 precedent in
  `tests/charter/test_charter_yaml_model.py`: `pack_manager` imports the schemas package, so a
  module-level back-import in the test would be a needless import-order dependency.
- Rename the test: `test_charter_yaml_with_all_ten_activation_fields_still_loads` carries the
  stale count in its own name. New name states what it proves.
- No production-code change: `CharterYaml`, `ACTIVATION_YAML_KEYS` and `extra="forbid"` are
  untouched.

## Edge cases confirmed

- The fixture already sets `activated_directives` and `mission_type_activations`; the derived
  loop excludes those two so their values are not replaced by `[]` (current behaviour, kept).
- `activated_assets` is not an activatable charter key and must not appear.

## Open questions

None. The issue's "Done when" offers two routes ("measure the model's field set instead of a
hard-coded count, or state the intended count with its rationale"); this Mission takes the
first, which is also the charter's single-authority rule. No maintainer decision is needed.
