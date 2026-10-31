# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · claude · spec-kitty plan --json reports target_branch as the current mission branch even though meta.json stores target_branch=main; the resolver appears to prefer the checked-out branch. Harmless here (single_branch), worth watching at consolidate.

2026-10-31 · claude · The mission-level review prompt carries the SPDD/REASONS block and asserts 'This project's active charter includes the SPDD/REASONS artifacts', but .kittify has no SPDD activation (only historical metadata mentions) and 4 of ~660 kitty-specs missions carry a reasons-canvas.md, none recent. The block reads as unconditional template text; ignored here, consistent with every recent mission. Worth a step-contract fix so reviewers are not told to author an artifact the charter never selected.
