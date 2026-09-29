---
affected_files: []
cycle_number: 1
mission_slug: requirement-id-grammar-01M3NRCA
reproduction_command:
reviewed_at: '2026-09-29T12:44:00Z'
reviewer_agent: claude
wp_id: WP06
---

# WP06 review feedback (cycle 1) - reviewer-renata

Verdict: changes requested. The code, tests and gates are sound. Every gate is green, T038 kills both all-or-nothing mutants, and the C6 disposal is honest. The ADR (FR-018) is the only file that must change, plus some optional polish.

## Required

**Issue 1 (MEDIUM): the ADR does not record the known low residuals.**
`kitty-specs/requirement-id-grammar-01M3NRCA/traces/design-decisions.md:24` accepts these residuals, and each one is still live at the lane tip (verified with `grammar.find_all`). The ADR mentions none of them.
- The C-001 literal AST gate cannot see a runtime-joined kind alternation. Obfuscation remains a review concern.
- A truncated slug `foo/bar#FR-001` parses as foreign with mission `bar`, which is the wrong slug. It is never parsed as local.
- `issue #FR-003` is now dropped: `find_all` returns `[]`.
- An ID declared only inside an HTML comment is no longer declared. This is a behaviour change from the trace at `design-decisions.md:23`, and it is missing from `#### Negative` consequences.

Fix: add a short `### Known residuals` subsection, or bullets under `#### Negative`/`#### Neutral`, that records each one honestly.

**Issue 2 (LOW-MEDIUM): the Decision Moments behind the decisions are not cited.**
The ADR cites only `01M3P2HXKASQY2ZKSEY3MAWA9H` and `01M3P07HV88QNVVKP3E2W28VB6`. The WP prompt's "Decision Moments to cite" table lists rulings that each back one Decision Outcome subsection. Cite each ID in its subsection:
- `01M3NSKBMEKR60XKRJSYQC41G3` backs the verdict table.
- `01M3NRCRYFBC1QNN62EFGXDVBY` backs SC tracked-not-gating.
- `01M3NSKHE8T6TBKNFPSJ6BRD2G` backs never rewrite.
- `01M3NSKEGC7QNXA1G3711AP77X` backs PLAN_SETUP_FAILED.
- `01M3NRD1N2PFH7MX82PH2D93PV` backs the qualified citation.
- `01M3NRCVW5VPE1DC9J6G5F3RBC` backs the lowercase suffix.
- `01M3NRCYSGDJ3VDW6KJ2DVBWZF` backs the setup-plan block/warn.

Also add `01M3NYFZ1P6QBD2DX4DVDA323W`: a WP whose only refs are foreign-qualified is "missing". The code cites this ruling at `mission_finalize.py:1214` and `runtime_bridge_cores.py:376`, but the ADR never states the rule.

## Recommended (non-blocking; fold them in while you are in the file)

- **Citation precision.** The ADR cites `grammar.py:136-139` for `canonical`; the actual lines are 137-140. It cites `:154-159` for `__str__`; the actual lines are 154-158. The ADR's line 131 attributes `__init__.py:165-177` to `find_bare_prose_requirement_ids`, but those lines hold the helper `_unqualified_unsuffixed_ids`. The public function is at `:270`, so name the helper.
- **"Purely additive" is inaccurate** at `envelope.py:58` and `docs/api/orchestrator-api.md:85`. `SPEC_FILE_MISSING`, `TEMPLATE_CONFIGURATION_ERROR` and `PLAN_CONTEXT_UNRESOLVED` used to leak verbatim as `error_code`. They now surface as `PLAN_SETUP_FAILED`, which is a consumer-visible change. Word it as the 1.7.0 entry does: "additive keys plus a closed-envelope remap; minor bump".
- **Dangling mentions of the deleted `read_all_wp_requirement_refs`:**
  - the docstring at `src/runtime/next/runtime_bridge.py:1059`;
  - the comment at `src/specify_cli/cli/commands/agent/tasks_map_requirements.py:392`;
  - the docstring at `tests/specify_cli/test_audit_tail_readers.py:717`.

  All three name a symbol that no longer exists. `runtime_bridge.py` is outside your sanctioned edits, so list it for closeout.
- **Lost branch coverage.** The retired `test_returns_empty_for_missing_dir` was the only test of `_read_wp_frontmatter_values`'s `if not tasks_dir.exists()` branch. Add an equivalent test for `read_all_wp_raw_requirement_refs` in `TestReadAllWpRawRequirementRefs`.
- **Glossary.** The `Requirement ID` "Do NOT use when" row in `docs/context/spec-driven.md` says "see the linked ADR below", but only the `Qualified citation` row links the ADR. Link it from `Requirement ID`'s Related terms too.
