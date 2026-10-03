# Design decisions

Taken without the operator, within the brief's latitude. Full rationale in `../research.md`.

1. **No new public flag** (C-002). Consent to replace an edited command skill is `doctor tool-surfaces --fix` (or an interactive upgrade "yes"), carried as `ApplyConsent.overwrite_paths` — the agent-profile pattern.
2. **Fix false drift at the owner.** `command_installer` treats canonical bytes as fresh and refreshes the recorded hash in the adoption pass; providers stay thin.
3. **Git object ids decide planning staging.** `hash-object --stdin-paths` versus `ls-tree`, batched, fail closed; `show_blob` unchanged.
4. **Standalone clone as mission workspace** instead of a linked worktree, to keep `lanes_with_coord` and leave the primary checkout untouched (see tooling-friction).
5. **`init` drift path left out.** Brownfield check found `init.py` ~1499-1506 exits 1 on the same false drift, because `init` never runs the adoption pass. It is not one of #5574/#5575/#5576 (C-001). Follow-up issue candidate.
6. **Out of scope held**: #702, the Codex skill-drift programme, #2527, spec-kitty-qa#766.
