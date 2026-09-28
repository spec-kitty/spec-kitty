---
affected_files: []
cycle_number: 1
mission_slug: squad-doctrine-single-owner-01M3KBP7
reproduction_command:
reviewed_at: '2026-09-28T13:52:47Z'
reviewer_agent: claude
wp_id: WP11
---

# WP11 review — changes requested (reviewer-renata)

Most of WP11 is correct and verified live: red-first 43 failed → 71 passed; all 64 slug→DIRECTIVE_NNN conversions are 1:1 and every slug matched its directive file; the #5078 implement-prompt section matches the operator decision; the checklist and BDD retargets are complete; 983 targeted and predecessor tests pass; and `uvx ruff@0.15.12 format --check .` (the uv.lock pin) is clean. Two blocking gaps remain.

## Blocking 1 — FR-026 is incomplete on 3 of the 8 named profiles

The WP (T059, "the 8 profiles") and FR-026 say that profiles reference DIRECTIVE_051, the tactic and the toolguide **instead of restating** the pillars. The commit body says all 8 profiles were done, but python-pedro and architect-alphonso were not edited at all. java-jenny got only the BDD retarget. Each of them still restates a partial pillar list in its `directive-references` code "051" rationale. A partial list is exactly how the lockfile check got split across copies.

- `packs/built-in/agent_profiles/python-pedro.agent.yaml` (~:166-172): "require official-registry (PyPI) resolution, package freshness visibility, and license/CVE audit". It leaves out lifecycle scripts, lockfile and IoC. License/CVE belongs to dependency-hygiene, not 051.
- `packs/built-in/agent_profiles/java-jenny.agent.yaml` (~:165-170): "official-registry (Maven Central) resolution, transitive-CVE exclusion, and version-pin discipline".
- `packs/built-in/agent_profiles/architect-alphonso.agent.yaml` (~:130-137): it frames "Node runtime baseline" / "non-LTS Node baseline" as a DIRECTIVE_051 matter. FR-026 moved Node LTS out of 051 into the JS/TS toolguide.

Fix: rewrite each 051 rationale in the same style as ivan, norris and dries. Each one must reference the threat-class controls DIRECTIVE_051 names, plus the `supply-chain-install-safety` tactic and the ecosystem toolguide (`python-supply-chain`, `java-supply-chain`; for alphonso, keep the "document elevated risk as an ADR per DIRECTIVE_003" obligation and point Node baseline at `javascript-supply-chain`). Keep each profile's operative obligation (evaluate before acceptance, never a silently skipped default).

The pin did not catch this. `_PILLAR_TERMS` in `tests/doctrine/test_served_prompts_single_owner.py` matches only the exact phrases "registry authenticity" and "package freshness", so "official-registry" and "freshness visibility" slip through. Broaden the detector (for example `official-registry`, `freshness`, `Node Active LTS` / `non-LTS`, `IoC`/`indicator`) so it goes red on the current pedro, jenny and alphonso text. Record that red, then the green.

## Blocking 2 — the rewritten renata pin no longer binds the obligation

`tests/doctrine/agent_profiles/test_supply_chain_profile_bindings.py` now asserts only that `adversarial-squad-deployment` is cited. A bare pointer that drops "every contested finding must get an explicit, recorded disposition, never dropped silently" would still pass. The current renata prose does keep the obligation, so the loss is in the pin, not in the doctrine. Add an assertion that the renata tactic-reference rationale (or the security-audit mode) still carries the obligation, for example that it contains `disposition` and `silent` next to the procedure id.

Non-blocking: `test_no_restatement_of_owned_disposition_vocabulary` rejects the bare word "changed" anywhere in renata's text, so ordinary prose can trip it. Consider matching the triple (or `deferred_with_rationale` alone) instead.

## Non-blocking notes

- The claim of "pre-existing format drift in test_shipped_contracts.py" is an artifact of the local ruff version (0.15.8). With the pinned ruff 0.15.12 the whole repo is clean, so nothing to do.
- Handoff-to-WP09 (the stale graph edge reason on renata→supply-chain-install-safety) is correct. Keep it.
