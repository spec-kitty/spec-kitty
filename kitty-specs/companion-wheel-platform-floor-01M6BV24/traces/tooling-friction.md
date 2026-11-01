# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · claude · The local pre-review gate (review.test_command = make test-fast, the whole fast tier) cannot finish inside the project's 300 s budget on this 20-agent batch host (load average >300 on 40 cores, two consecutive timeouts, then a pass in ~5 min after a temporary local budget bump that the PR does not carry). Also: lane venvs created by this flow lack pip and the build extra, so test_backend_fallback_wheel_installs_with_pip and the packaging-safety fixtures error until uv sync --frozen --all-extras and uv pip install pip; and packs/internal must be synced per worktree or the terminology gate fails vacuously.
