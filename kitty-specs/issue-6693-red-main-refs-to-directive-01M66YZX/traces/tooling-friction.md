# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · maintainer-agent-p15 · The globally installed spec-kitty 4.0.0rc8 resolves packs/<pack>.source.yaml relative to the installed package dir, so 'charter pack vendor' fails with FileNotFoundError outside a uv-run checkout. Use 'uv run --frozen spec-kitty ...' in this repo.

2026-10-30 · maintainer-agent-p15 · Single-branch review independence: the implement claim recorded a bare 'claude', so the approval gate refused every reviewer identity because a segment recorded on one side only never proves independence. Recovery: move back to doing, re-claim with a full tool:model:profile triple, re-submit.
