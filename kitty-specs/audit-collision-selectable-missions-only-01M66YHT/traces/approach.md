# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · claude-p10 · Grounded #6757 on main@512567ee: the engine's run_audit() feeds the default (non-residue-aware) audit_repo population into both collision reports, so a committed spec.md-only folder fakes DUPLICATE_PREFIX/AMBIGUOUS_SELECTOR on a healthy Mission. Fix is two populations: default walk for IDENTITY_MISSING, residue-aware walk for the two collision codes.
