# Diagnosis — #702 Codex `.agents/skills` drift (Phase 0)

## Scope grounding (is it still real on `main`?)

Validated on `main` @ **4.0.0rc7** (not just the rc5 report in the issue). The §1 alignment gate — "is the issue superseded or already resolved?" — is answered **no**: the defect reproduces on current main. The operator's 2026-10-05 note ("Issue should be solved" after rc6) was a verification hand-off, not a landed fix; #5709 only softened the exit code, explicitly *not* the classification.

## Reproduction (real entry point)

```bash
spec-kitty init --ai codex,claude --yes         # generates .agents/skills/spec-kitty.*/SKILL.md + command-skills-manifest.json
# simulate a second checkout / older build: on-disk bytes now differ from the recorded hash and the render
printf '\n<!-- stale output from another checkout -->\n' >> .agents/skills/spec-kitty.accept/SKILL.md
spec-kitty upgrade --project --yes < /dev/null
```

Observed on rc7:

```
Errors:
  ✗ Not updated, your local edit was kept: .agents/skills/spec-kitty.accept/SKILL.md (Managed command content has drifted)
Upgrade finished, but 1 managed file(s) with local edits were not updated.   # exit 0
```

`spec-kitty doctor skills --json` → `ok: false`. The derived projection is left drifted; the only remedy today is to delete the file and re-run (absence *is* regenerated).

rc5 → rc7 difference: rc5 hard-failed `exit 1` ("Upgrade failed"); #5709 made the exit non-fatal and named the files. The **misclassification is unchanged** — exactly the operator's stated reason for the P1 escalation.

## Root cause

`src/specify_cli/skills/command_installer.py::_Plan.preserve()` (≈ line 740):

```python
if existing is not None and before.sha256 not in (existing.content_hash, digest):
    if rel in self.inputs.consent.overwrite_paths:
        return False  # explicit exact-path consent overwrites
    self.disposition(rel, "consent_required", "Managed command content has drifted")
    return True
```

- `existing is not None` → the path is **manifest-owned** (a `spec-kitty.<command>/SKILL.md` the installer wrote).
- `before.sha256 not in (content_hash, digest)` → on-disk bytes equal neither the recorded manifest hash nor the fresh render — i.e. stale/cross-checkout generated output.
- Verdict `consent_required` → the tool-surface provider (`tool_surface/providers/command_skills.py`, `unresolved = {preserve, consent_required}`) reports it as drift; upgrade keeps the file.

This applies *tracked-file* consent semantics to a surface the state contract declares **derived**:

`src/specify_cli/state/contract.py` — `shared_skills_projection`: `path_pattern=".agents/skills/<skill_name>/"`, `authority=AuthorityClass.DERIVED`, `git_class=GitClass.IGNORED`, owner `skills/installer`, "never commit … always regenerable".

The installer owns **only** this surface: `install_command()` hardcodes `rel = ".agents/skills/spec-kitty.{command}/SKILL.md"`, and the module contract (NFR-002) is that non-manifest paths are never touched. So the `consent_required` drift branch is *always* operating on DERIVED/IGNORED paths, where there is no committed user edit to protect.

## Why cross-checkout drift is spurious (not a user edit)

The tracked manifest records the hash of ignored output. Checkout A's upgrade rewrites that hash; checkout B's ignored bytes never travel with the commit. B's untouched generated output therefore reads as "drifted from the manifest," though nobody edited it. Treating it as a user edit is the bug.

## Fix direction

In `preserve()`, a drift on a **manifest-owned** projection regenerates (return `False` → the canonical bytes are written) rather than emitting `consent_required`. The surface's DERIVED/IGNORED class justifies it; a guard test pins that the `shared_skills_projection` surface is DERIVED/IGNORED so the premise cannot silently change. The `existing is None` branch (non-manifest / third-party) is untouched — user content stays preserved (FR-002, NFR-002). The clean version-upgrade re-render (on-disk == recorded hash, ≠ new render) already falls through this branch and is unaffected.

## Non-goals / out of scope

- The `.claude/skills/**` managed-file installer (`skills/installer.py`) and `.claude/agents/*.md` profile surface — related split, separate manifests, separate code paths.
- #5574 (byte-identical case), #5709 (exit-code explanation), #5745 (exit-code decision), #1780 (session-presence), #1670 (`spec-kitty.advise`).
- Redesigning the skills system, the manifest schema, or the `.agents/` gitignore policy.
- `remove_entry()` prune-time consent for retired commands (not the reported install-time symptom).

## Affected tests (superseded policy — update with #702 justification)

- `tests/specify_cli/skills/test_command_installer.py::test_wp04_drift_and_unknown_preserved_while_gap_repaired` (asserts a drifted owned file is *preserved* unchanged).
- The `_prepare`-based drift cases asserting `consent_required` without overwrite consent (≈ lines 1223, 1260, 1274).
- `verify()` drift-reporting tests are unaffected — `verify` still reports drift pre-reconcile; the reconcile now clears it.
