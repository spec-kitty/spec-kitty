---
work_package_id: WP08
title: Closeout verification
dependencies:
- WP07
requirement_refs:
- FR-010
- FR-012
- NFR-004
- NFR-005
planning_base_branch: feat/drupal-dries-profile
merge_target_branch: feat/drupal-dries-profile
branch_strategy: Planning artifacts for this mission were generated on feat/drupal-dries-profile. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/drupal-dries-profile unless the human explicitly redirects the landing branch.
created_at: '2026-09-11T19:28:35+00:00'
subtasks:
- T039
- T040
- T041
- T042
- T043
history:
- at: '2026-09-11T19:28:35Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: reviewer-renata
authoritative_surface: kitty-specs/drupal-dries-profile-01M28X69/verification-report.md
create_intent:
- kitty-specs/drupal-dries-profile-01M28X69/verification-report.md
execution_mode: planning_artifact
owned_files:
- kitty-specs/drupal-dries-profile-01M28X69/verification-report.md
role: reviewer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP08 – Closeout verification

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `reviewer-renata`
- **Role**: `reviewer`

## Objective

Prove the cross-cutting claims that **no single content package was positioned to prove**, and write
the verification report the pull request will cite.

Every other WP could honestly report success while a mission-level claim failed. WP03 and WP04 each
carry part of the 14 anti-patterns and neither can confirm the total. Provenance is asserted in five
separate files by four different packages. "Activation stays opt-in" is a property of the whole pack.
That is this package's territory.

## Context

- **Spec**: FR-010, FR-012, NFR-004, NFR-005, SC-003, SC-006, SC-007
- **Contracts**: C-P7, C-P8, C-S2, C-S6, C-S8
- **Quickstart**: [quickstart.md](../quickstart.md) — the definition-of-done list and the trap table

You are verifying, not authoring. If something is wrong, report it and reject rather than quietly
fixing it in the wrong package — the exception being a typo-scale correction you record explicitly.

## Branch Strategy

- **Planning branch**: `feat/drupal-dries-profile`
- **Final merge target**: `feat/drupal-dries-profile`
- Worktrees come from `lanes.json` via `spec-kitty implement WP08`.

---

### Subtask T039: Provenance audit

**Purpose**: FR-010, C-P8, C-003. The mission distils someone else's work; attribution is not optional.

**Steps**:

1. Check each of the five new artifacts credits amazee.io's `drupal-agents-md` (Vanilla variant):
   ```bash
   for f in packs/built-in/agent_profiles/drupal-dries.agent.yaml \
            packs/built-in/styleguides/drupal-conventions.styleguide.yaml \
            packs/built-in/styleguides/drupal-security-performance.styleguide.yaml \
            packs/built-in/toolguides/DRUPAL_REVIEW_CHECKS.md \
            packs/built-in/toolguides/drupal-review-checks.toolguide.yaml; do
     printf '%s: ' "$f"; grep -ci "drupal-agents-md\|amazee" "$f" || echo 0
   done
   ```
   Every file must report at least 1.
2. Verify C-003 — distillation, not reproduction. Sample three substantial passages and confirm none
   is a verbatim block from the source. Structure and facts may carry over; prose should not.

**Validation**:
- [ ] All five artifacts credit the source
- [ ] Three sampled passages are distilled, not copied

---

### Subtask T040: Activation opt-in and context-unchanged proof

**Purpose**: FR-012, NFR-005, SC-006. A team doing no Drupal work must see no change.

**Steps**:

1. Confirm no charter or config activates the profile by default:
   ```bash
   grep -rn "drupal-dries" .kittify/ 2>/dev/null || echo "not activated — correct"
   ```
2. Prove the inactive context is unchanged. Capture a rendered context for an action before and after
   the mission's commits and compare:
   ```bash
   uv run spec-kitty charter context --action implement --json > /tmp/ctx-after.json
   ```
   Compare against the same command at the mission's base commit. Byte-identical is the requirement
   (NFR-005). If it differs, identify precisely which artifact leaked into an unactivated context —
   that is a real defect, not an accounting detail.
3. Confirm the activation path works:
   ```bash
   uv run spec-kitty charter activate agent-profile drupal-dries --help
   ```
   (Inspect availability; do not leave the profile activated in the repository.)

**Validation**:
- [ ] Not activated by default
- [ ] Inactive context byte-identical to pre-mission
- [ ] Activation path available, and the repository left unactivated

---

### Subtask T041: Full targeted test surface

**Purpose**: NFR-004 and the PR's evidence.

**Steps**:

```bash
make test-fast
uv run pytest tests/doctrine/ -q
uv run pytest tests/charter/ -q
uv run pytest tests/architectural/test_no_legacy_terminology.py -q
uv run ruff check .
uv run ruff format --check .
```

Notes that matter:

- `tests/charter/` **and** `tests/doctrine/` are both required — the mission touched
  `src/charter/offering/`, and the doctrine test tree still covers that code.
- The terminology guard (~0.1s) is required because this mission adds user-facing prose. It gates
  exactly two retired terms; it does **not** check Mission-versus-feature, which stays review-enforced.
- **`ruff format --check` is a separate gate from `ruff check`.** Lint passing says nothing about
  formatting, and CI runs the format check repo-wide.

Classify every failure against CLAUDE.md's four baseline-red categories before recording it. Do not
green-wash a known-P0 red, and do not attribute a stale-venv import error to this mission.

**Validation**:
- [ ] All six commands run, with pass/fail counts captured
- [ ] Every failure classified with its category and evidence
- [ ] Lint and format both clean

---

### Subtask T042: Anti-pattern completeness and Drupal claim sampling

**Purpose**: SC-003 and SC-007. The audit only this package can perform.

**Steps**:

1. **14 of 14.** Collect WP03's and WP04's number-to-pattern maps from their WP notes and check all
   fourteen source anti-patterns are represented across the two styleguides:

   | # | Anti-pattern | Expected owner |
   |---|---|---|
   | 1 | `\Drupal::` static calls in services/controllers/plugins | WP03 |
   | 2 | Direct DB queries where Entity Query suffices | WP03 |
   | 3 | `\|raw` in Twig | WP04 |
   | 4 | Monolithic `hook_form_alter()` | WP03 |
   | 5 | Config stored in state | WP03 |
   | 6 | `#markup` with unsanitized input | WP04 |
   | 7 | Entity queries without `accessCheck(TRUE)` | WP04 |
   | 8 | Hardcoded entity IDs, user IDs, paths | WP03 |
   | 9 | `hook_views_data()` without table aliases | WP03 |
   | 10 | Ignored cacheability metadata | WP04 |
   | 11 | `settings.php` with credentials | WP04 |
   | 12 | Deprecated procedural functions | WP03 |
   | 13 | Global `$_GET` / `$_POST` / `$_SERVER` | WP03 |
   | 14 | Business logic in `.module` files | WP03 |

   A gap here is the predictable failure: WP03 and WP04 each assumed the other took it. Any genuine
   omission must be recorded with a reason (SC-003 permits omission *with* a stated reason; it does
   not permit silence).

2. **Disjointness (C-S3)** — run WP04's T025 overlap script yourself. The set must be empty.

3. **No invented thresholds (C-S6)** — across all five artifacts:
   ```bash
   grep -rniE "level [0-9]|[0-9]{2}% coverage|mutation score" \
     packs/built-in/agent_profiles/drupal-dries.agent.yaml \
     packs/built-in/styleguides/drupal-*.yaml \
     packs/built-in/toolguides/DRUPAL_REVIEW_CHECKS.md
   ```
   Any hit is an NFR-006 failure and must be corrected, not waived.

4. **Claim sampling (SC-007, C-S8)** — sample ten Drupal claims at random across the artifacts and
   trace each to the source guide or official Drupal documentation. Give the `accessCheck(TRUE)`
   version claim particular attention: implicit checking deprecated in **9.2.0**, error from **10.0.0** — already mandatory on the 10.x/11.x baseline. All ten must
   trace.

**Validation**:
- [ ] 14 of 14 accounted for, with any omission reasoned
- [ ] Overlap set empty
- [ ] Threshold grep returns nothing
- [ ] Ten sampled claims all traceable, with sources recorded

---

### Subtask T043: Write the verification report

**Purpose**: Turn the evidence into something the pull request can cite.

**Steps**: Create `kitty-specs/drupal-dries-profile-01M28X69/verification-report.md` containing:

1. **Tests run** — every command with its pass/fail counts, in the shape the PR section expects.
2. **Requirement coverage** — each of the 13 FRs, 7 NFRs, and 8 Cs, with the evidence that satisfies
   it or an explicit note that it does not.
3. **Success criteria** — SC-001 through SC-007, each with its result. SC-004's ten-task table comes
   from WP06's notes; SC-007's ten sampled claims from T042.
4. **Anti-pattern audit** — the 14-row table with its resolved owner.
5. **Failures and classifications** — every red encountered, its category, and the evidence for that
   classification.
6. **Outstanding work** — anything genuinely unfinished. An empty section is fine; a dishonest one is
   not.

**Validation**:
- [ ] Report exists and is complete
- [ ] Tests-run section is paste-ready for the PR
- [ ] Every FR/NFR/C has a verdict
- [ ] No claim in the report lacks evidence behind it

---

## Definition of Done

- [ ] Provenance confirmed in all five artifacts
- [ ] Activation confirmed opt-in; inactive context byte-identical
- [ ] Six verification commands run and recorded
- [ ] 14 of 14 anti-patterns accounted for
- [ ] Zero pattern-name overlap between the styleguides
- [ ] Zero invented thresholds
- [ ] Ten Drupal claims sampled and traced
- [ ] `verification-report.md` written, evidence-backed
- [ ] Any defect found is reported, not silently patched in the wrong package

## Risks

| Risk | Mitigation |
|------|-----------|
| An anti-pattern lost between WP03 and WP04 | The 14-row table with expected owners is the whole point of T042 |
| Recording a pass without running the command | Counts go in the report; a missing count is a missing run |
| Misclassifying a stale-venv error as pre-existing | CLAUDE.md category 4 — re-sync and retry before recording |
| Fixing defects here instead of reporting them | You are the reviewer; a fix in the wrong package destroys the ownership guarantee |

## Reviewer Guidance

This package's output *is* the review evidence, so check it the way you would check a claim, not a
document. Pick three commands from the tests-run section and re-run them; the counts must match. Pick
two rows from the anti-pattern table and locate them in the styleguides yourself. Run the threshold
grep. If the report states a pass that you cannot reproduce, that is a rejection regardless of how
complete the document looks.
