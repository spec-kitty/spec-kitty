# Aggregate review — dispatch-router-docs-coverage-01M6BTTX

**Verdict: LAND.**

Scope: the combined diff of WP01 (router), WP02 (CLI rendering), WP03 (changelog + docs)
against `origin/main` at `287a226cfe`. Per-WP review passed for all three; this pass looks
for what only exists once they are combined.

## What was checked

1. **The reported defect is actually fixed at the surface a user runs.**
   On pristine `origin/main` the issue's own request
   `"mark ADR-0068 Accepted and regenerate the ADR index"` raised
   `RouterAmbiguityError(ROUTER_NO_MATCH)` with `candidates == []`. On this branch the
   same request routes to `curator-carla` with `router_confidence: domain_keyword`
   through `route()` **and** through `dispatch ... --dry-run --json`
   (`test_issue_request_routes_through_the_dispatch_command`, real shipped catalog).
   `"index the invoice table"` still refuses on both surfaces (FR-002).

2. **The router change cannot move an existing route.** The keyword ladder is
   single-token → phrase → documentation alias, and a later tier is consulted only when
   the earlier one produced no candidate. The shipped-catalog differential corpus
   (`_TODAY_ROUTES`, captured on `main`) plus the two tier-order guards
   (`release notes for the sprint` → `planner-priti`, `the guide for the spike` →
   `researcher-robbie`) are green, so the new vocabulary is strictly additive (FR-011).

3. **Router purity and single catalog read are intact.** `_nearest_profiles` runs only on
   the refusal path, over the one `list_all()` the router already performs; a decided
   route reports no alternatives and the ranking never runs (FR-009/FR-012).

4. **The machine contract is unchanged.** The CLI emitter keeps the five-key
   `routing_failed` envelope on stderr with exit 1; `--dry-run` keeps exit 0 for a routed
   request and for `ROUTER_AMBIGUOUS`. WP02 only renders what the router decided — it
   does not re-rank or re-derive a suggestion (C-004).

5. **Cross-WP integration.** WP02's CLI tests consume WP01's router output; both the
   populated-candidate refusal and the ambiguous tie are asserted from the router's own
   values, not from hard-coded prose, so a future wording change in the router does not
   silently desynchronize the two. WP03 documents exactly the behaviour WP01/WP02 ship.

6. **Hygiene.** ruff (including `C90`, max-complexity 15) and mypy pass on both changed
   source files; no `# noqa`, `# type: ignore`, xfail or skip was added; no dependency,
   no pack file, no new confidence value; every commit is authored by the operator's
   noreply identity and carries no machine-local path.

## Findings

No blocking finding. Two non-blocking observations, both disclosed in the PR:

- The local pre-review regression gate could not run in this repo (the repo-declared
  `review.test_command` is the whole `make test-fast` tier; the frontmatter escape hatch
  is rejected by `WPMetadata`). Existing issue **#6865**; the affected suites were run
  directly instead. Not caused by this diff.
- `accept` initially reported a `path_violations` convention (no `contracts/` directory).
  Resolved by adding `contracts/README.md`, which records that no external contract
  changed and points at the tests that pin the envelope.
