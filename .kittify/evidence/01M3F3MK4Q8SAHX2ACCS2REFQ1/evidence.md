schema: review-verify/v1
phase: op-01M3F3MK4Q8SAHX2ACCS2REFQ1-fixround3
verifier_profile: reviewer-renata
directives_applied:
  - "024 Locality of Change: confirmed via `git diff-tree --no-commit-id --name-only -r 21609b04e` that the commit touches only docs/migrations/cross-repo-e2e-gate.md and the generated docs/development/3-2-docs-retrieval-index.yaml -- no scope creep."
  - "032 Conceptual Alignment: checked every fixture name, env var (SPEC_KITTY_REPO, SK_E2E_REARCH_ROOT, SK_E2E_SPEC_KITTY_BIN, SK_E2E_SPEC_KITTY_REPO), decorator text, and skip/fail reason string in the new Case A/A2 prose against the actual upstream identifiers, and confirmed the Case A2 label is internally consistent with the file's non-exhaustive Case A/B/C convention."
  - "030 Test and Typecheck Quality Gate: ran `.venv/bin/python -m scripts.docs.docs_index --strict` myself (exit 0, drift=False) as the quality gate for a docs-index-bearing change, plus the dangling-anchor grep."
  - "reverse-speccing tactic: re-fetched conftest.py and all three surviving scenario files fresh from spec-kitty/EXPERIMENTAL-spec-kitty-end-to-end-testing myself (not reusing the fixer's scratchpad table) and reconstructed fixture/skip behavior from source alone before reading the doc's claims."
  - "code-review-incremental tactic: read the commit's stated intent first, then verified sentence-by-sentence against source, then separately assessed the new Case A2 policy sentence against this repo's own Gate 3 doctrine (SKILL.md + ADR) rather than accepting it as another factual claim."
complete: true
verdicts:
  - finding_id: op-verify-001
    verdict: resolved
    evidence: >-
      Independently refetched scenarios/conftest.py (69 lines) and all three
      surviving scenario files from spec-kitty/EXPERIMENTAL-spec-kitty-end-to-end-testing
      via `gh api .../contents/scenarios/<file> --jq .content | base64 -d`
      (not reused from the fixer's scratchpad table) and re-derived every
      claim from scratch. The two specific fabrications op-verify-001 named
      are both gone and the replacement text is accurate:
      (1) "Every scenario shares the spec_kitty_repo fixture" is replaced
      with "Of the three surviving floor scenarios, only
      contract_drift_caught.py's test_contract_drift_caught takes the
      spec_kitty_repo fixture ... as a parameter" -- confirmed true:
      contract_drift_caught.py:258 is
      `def test_contract_drift_caught(tmp_path: Path, spec_kitty_repo: Path) -> None:`,
      and a full-file grep for `spec_kitty_repo` returns zero hits in both
      dependent_wp_planning_lane.py (605 lines; its
      test_dependent_wp_planning_lane_lifecycle_smoke takes only tmp_path
      and builds its own throwaway repo under tmp_path) and
      uninitialized_repo_fail_loud.py (116 lines).
      (2) The blanket "fails, never skips" generalization is now scoped to
      only "the scenario" (contract_drift_caught.py) in Case A, and a new
      Case A2 accurately and separately describes
      uninitialized_repo_fail_loud.py's own, different, skip-based gate
      (`@pytest.mark.skipif(not spec_kitty_cli_available(), ...)` at
      uninitialized_repo_fail_loud.py:55-63, decorating
      test_uninitialized_repo_fails_loud at line 65) instead of being
      silently folded into the false universal claim. Every remaining
      factual sentence in both new sections checks out against source (see
      sentence_check). docs_index --strict shows zero drift and the diff
      touches only the runbook + its generated index (see repo-state
      checks below), matching the commit message's stated scope.
sentence_check:
  - sentence: "Case A heading: '...checkout (`contract_drift_caught.py`)'"
    status: supported
    evidence: "contract_drift_caught.py:258 `def test_contract_drift_caught(tmp_path: Path, spec_kitty_repo: Path) -> None:` -- correct file/test pairing."
  - sentence: "Of the three surviving floor scenarios, only contract_drift_caught.py's test_contract_drift_caught takes the spec_kitty_repo fixture (scenarios/conftest.py) as a parameter."
    status: supported
    evidence: >-
      contract_drift_caught.py:258 has the parameter; grep -n "spec_kitty_repo"
      over dependent_wp_planning_lane.py (605 lines) and
      uninitialized_repo_fail_loud.py (116 lines) both return zero matches
      (verified independently, not reused from prior evidence table).
  - sentence: "The fixture requires a resolvable sibling spec-kitty checkout -- via an explicit SPEC_KITTY_REPO override or the SK_E2E_REARCH_ROOT-aware resolver."
    status: supported
    evidence: >-
      conftest.py:4-13 docstring: "An explicit ``SPEC_KITTY_REPO`` override
      wins; otherwise the canonical workspace resolver applies
      (:func:`spec_kitty_e2e.config.sibling_repo` via ``rearch_root()``),
      which honours the runner-exported ``SK_E2E_REARCH_ROOT``".
  - sentence: "This is a required prerequisite, not an optional one: an unresolvable checkout fails the fixture (pytest.fail(...)) rather than skipping the scenario."
    status: supported
    evidence: >-
      conftest.py:15-17 docstring: "an unresolvable one fails the lane
      instead of skipping it, so a required leg can never silently degrade
      into skipped (green) coverage (#416)." conftest.py:52-63
      `_require_spec_kitty_repo` calls `pytest.fail(...)` (not
      `pytest.skip`) when `_resolve_spec_kitty_repo()` returns None. Note
      this sentence is now correctly scoped to "the scenario" (singular),
      not generalized to the whole floor -- the exact narrowing
      op-verify-001 asked for.
  - sentence: "If the reviewer's machine genuinely lacks a resolvable sibling checkout, the operator files mission-exception.md naming contract_drift_caught.py and the exact pytest.fail text, and follows the schema above."
    status: supported
    evidence: >-
      Procedural instruction restating the doc's own pre-existing exception
      schema (lines 91-131 of the same file, unchanged by this commit); the
      scenario name it tells the operator to cite is now the correct one.
  - sentence: "Case A2 heading: 'uninitialized_repo_fail_loud.py skips when the spec-kitty CLI is unavailable'"
    status: supported
    evidence: "uninitialized_repo_fail_loud.py:55-56 `@pytest.mark.skipif(not spec_kitty_cli_available(), ...)`."
  - sentence: "uninitialized_repo_fail_loud.py does not use the spec_kitty_repo fixture."
    status: supported
    evidence: "grep -n spec_kitty_repo uninitialized_repo_fail_loud.py -> zero matches (independently re-run)."
  - sentence: "Its test_uninitialized_repo_fails_loud is decorated with @pytest.mark.skipif(not spec_kitty_cli_available(), ...):"
    status: supported
    evidence: >-
      uninitialized_repo_fail_loud.py:55-68: the skipif decorator (55-63)
      sits directly above `@pytest.mark.parametrize("subcommand", ...)`
      (64) and `def test_uninitialized_repo_fails_loud(tmp_path, subcommand)`
      (65-68) -- same decorated function.
  - sentence: "when no spec-kitty binary resolves, the test is SKIPPED (not failed), with a reason that directs the operator to set SK_E2E_SPEC_KITTY_BIN or SK_E2E_SPEC_KITTY_REPO, or to file mission-exception.md per this doc."
    status: supported
    evidence: >-
      uninitialized_repo_fail_loud.py:57-62 reason string, verbatim: "no
      resolvable spec-kitty binary -- set SK_E2E_SPEC_KITTY_BIN or
      SK_E2E_SPEC_KITTY_REPO (checkout with .venv). Environmental block --
      file mission-exception.md per
      spec-kitty/docs/migrations/cross-repo-e2e-gate.md." `pytest.mark.skipif`
      is pytest's SKIP mechanism, distinct from the FAIL that
      `pytest.fail()` produces in conftest.py.
  - sentence: "No exception artifact is required for this skip -- it is already a non-blocking, self-documenting environmental gap; file one only if the skip itself needs to be tracked as a follow-up."
    status: policy
    evidence: >-
      Not an upstream-source fact; checked against this repo's own Gate 3
      doctrine instead, per the task's instruction. Mechanically the
      narrow claim is defensible: SKILL.md:570 keys the HARD FAIL purely
      off "Non-zero exit ⇒ HARD FAIL unless [exception]" (Gate 3, Step 8.5),
      and a pytest.mark.skipif SKIP does not, by itself, produce a
      non-zero pytest exit code -- so today's Gate 3 mechanism literally
      does not trip on this skip, and the "Operator exception path (Gate 3
      only)" section (SKILL.md:624-654) exists to remedy a HARD FAIL that
      never actually fires here. BUT the sentence goes further and asserts
      a settled normative conclusion ("it is already a non-blocking ...
      gap") that Gate 3's written rule does not itself make, and that
      cuts against the gate's own governing intent: the ADR
      (docs/adr/3.x/2026-04-26-3-e2e-hard-gate.md) grounds Gate 3 in C-010,
      "the mission MUST NOT be marked complete without either executed e2e
      evidence or an explicit operator-approved exception" (ADR:184-185),
      and explicitly rejected Alternative 4 (a blanket
      SPEC_KITTY_E2E_OPTIONAL=1 waiver) because it "would re-introduce the
      silent-skip mode the gate exists to prevent" (ADR:186-187). A skip of
      test_uninitialized_repo_fails_loud is neither "executed e2e evidence"
      (FR-032/FR-039's assertions never ran for any of the three
      parametrized subcommands) nor an "explicit operator-approved
      exception" (the schema at SKILL.md:633-641 requires an
      Operator/Date/Failing-scenario/narrative/repro/follow-up artifact;
      a decorator string baked into upstream test code is none of those).
      SKILL.md itself never states a skip-vs-fail carve-out anywhere (grep
      -i skip src/charter/offering/skills/spec-kitty-mission-review/SKILL.md
      returns only two unrelated hits, lines 315 and 827) -- this doc
      commit is the first place in the repo asserting one. The claim is
      therefore invented policy, not a fact the gate as written settles
      either way; it should be left as an operator/reviewer judgment call
      (or explicitly flagged as an open gap in Gate 3's exit-code-only
      mechanism) rather than declared as an already-resolved
      non-requirement in the operator-facing runbook. See new_findings
      op-verify2-001.
  - sentence: "Case A2 fits the file's Case A/B/C structure and nothing else in the file contradicts the new text."
    status: supported
    evidence: >-
      Read the full file (docs/migrations/cross-repo-e2e-gate.md, all 195
      lines). "Common exception cases (non-exhaustive)" (line 133)
      explicitly disclaims exhaustiveness, so inserting a labeled A2
      sub-case between A and B is consistent with the section's own framing
      even though A/B/C elsewhere are single letters. The floor-scenario
      table (lines 48-62), the exception-artifact template (91-131), Case B
      (161-166), Case C (168-175), "What is NOT allowed" (177-186), and
      Cross-references (188-195) are all unchanged by this commit and none
      of them assert a competing claim about which scenario uses which
      fixture/gate mechanism -- no contradiction found elsewhere in the
      file.
repo_state_checks:
  - check: ".venv/bin/python -m scripts.docs.docs_index --strict"
    result: "exit=0 generated=826 committed=826 drift=False (added=0 removed=0 changed=0)"
  - check: 'grep -rn "cross-repo-e2e-gate.md#" --exclude-dir=kitty-ops .'
    result: "zero matches (grep exit 1) -- nothing else in the repo links to the old or new Case A anchor by fragment."
  - check: "git diff-tree --no-commit-id --name-only -r 21609b04e"
    result: "docs/development/3-2-docs-retrieval-index.yaml, docs/migrations/cross-repo-e2e-gate.md -- only the runbook and its generated index, matching the commit message's claimed scope."
  - check: "git status --short (this checkout)"
    result: "only the pre-existing untracked kitty-ops/*.jsonl and *.yaml review artifacts from earlier rounds; no other modification made by this verification."
new_findings:
  - id: op-verify2-001
    severity: 3
    title: "Case A2's 'no exception artifact is required for this skip' is invented policy, not settled by Gate 3 as written, and cuts against the ADR's C-010 / anti-silent-skip rationale"
    location: "docs/migrations/cross-repo-e2e-gate.md:157-159 (Case A2, added by 21609b04e)"
    evidence: >-
      See sentence_check entry above for the full citation chain. In
      summary: Gate 3 (SKILL.md Step 8.5, lines 563-654) enforces
      pass/fail purely via pytest's own exit code ("Non-zero exit ⇒ HARD
      FAIL unless [mission-exception.md]"); a pytest.mark.skipif SKIP does
      not produce a non-zero exit by itself, so the exception mechanism is
      mechanically moot for this specific skip today. But the doc does not
      stop at that narrow, mechanically-true observation -- it declares the
      skip "already a non-blocking, self-documenting environmental gap"
      that needs no artifact, which is a normative policy conclusion the
      gate's own text never states and which sits against the ADR's
      explicit rationale for Gate 3: C-010 requires "either executed e2e
      evidence or an explicit operator-approved exception"
      (docs/adr/3.x/2026-04-26-3-e2e-hard-gate.md:184-185), and Alternative
      4 (a blanket optional-e2e waiver) was rejected specifically to avoid
      "re-introduc[ing] the silent-skip mode the gate exists to prevent"
      (ADR:186-187). When uninitialized_repo_fail_loud.py's CLI-availability
      skipif fires, none of the FR-032/FR-039 assertions for any of the
      three parametrized subcommands (specify/plan/tasks) actually execute,
      and under this doc's new instruction no operator artifact records
      that gap either -- i.e. neither "executed e2e evidence" nor an
      "explicit operator-approved exception" exists, which is exactly the
      state C-010 was written to forbid. This is a governance/operational
      risk baked into an operator-facing runbook, not a fabricated fact
      about upstream code (hence severity 3, not 4/5) -- but it will steer
      real operators and future mission-review runs toward treating an
      unexecuted floor scenario as a non-issue on the strength of this
      doc's own say-so.
    recommendation: >-
      Soften the claim to stop short of declaring the gap resolved. E.g.:
      "Gate 3's exit-code check does not itself flag this skip as a
      failure, because pytest.mark.skipif does not produce a non-zero exit.
      That means this specific skip mechanically passes Gate 3 without an
      exception artifact today. Whether an unexecuted floor scenario (no
      FR-032/FR-039 evidence ran) still needs its own follow-up tracking is
      a reviewer/operator judgment call under C-010, not something this
      doc resolves for you -- when in doubt, file mission-exception.md or
      a follow-up issue anyway." Alternatively, raise this as a real gap in
      Gate 3's mechanism (an issue against SKILL.md/the ADR) rather than
      documenting it as an accepted non-requirement in the migration guide.
findings_summary:
  by_severity:
    "1": 0
    "2": 0
    "3": 1
    "4": 0
    "5": 0
  total: 1
