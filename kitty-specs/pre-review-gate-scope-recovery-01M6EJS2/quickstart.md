# Quickstart — running the pre-review gate in a repository with a whole-suite review command

Audience: a maintainer or agent who just hit
`Pre-review regression gate timed_out; transition not applied` on
`move-task --to for_review`.

## 1. Find out what the gate actually ran

Every refusal names the scope shape it chose. The two shapes are:

- **whole declared command** — the repository's scope source contributes no
  per-file narrowing, so `review.test_command` runs in full (this repository:
  `make test-fast`);
- **bounded target list** — an explicit scope ran instead (a pinned
  `pre_review_test_scope`, or a source that narrows per file).

```bash
spec-kitty agent action move-task WP01 --to for_review --json | jq '.pre_review_gate'
```

The `reason` field carries the shape, the command, the resolved budget and the
policy metadata that classifies scopes (`review/gate_budget.py`, `_RULES`).

## 2. Give the whole-suite run a budget that fits it

A whole declared command is bounded by the whole-command default (1 200 s). To
declare your own bound instead:

```yaml
# .kittify/config.yaml
review:
  test_command: 'PYTEST_ADDOPTS="--junitxml={output_file}" make test-fast'
  test_timeout_seconds: 1800
```

The declared value always wins; changing it invalidates the recorded baseline
receipt, which is recaptured on the next transition.

## 3. Or pin a bounded scope for one work package

```yaml
# kitty-specs/<mission>/tasks/WP01-....md frontmatter
pre_review_test_scope: "tests/review tests/status"
```

The gate runs exactly those pytest targets at head. The pinned scope governs
**what** runs, not the bound: the same resolved budget applies. An empty value is
treated as absent.

## 4. Only then skip explicitly

`--skip-pre-review-gate` (or `SPEC_KITTY_SKIP_PRE_REVIEW_GATE=1`) remains the
explicit, recorded opt-out. It is never the way to work around a budget that did
not match the scope — declare a budget or pin a scope instead.

## Local verification of this change

```bash
uv run --frozen pytest tests/review/test_review_budget_scope_shape.py \
  tests/review/test_pre_review_gate_scope_diagnostics.py \
  tests/review/test_pre_review_gate_engine.py \
  tests/specify_cli/status/test_wp_metadata.py -q
uv run --frozen python -m scripts.docs.check_docs_freshness --ci
```
