# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · pi · Two pytest runs in one clone corrupted the per-clone test-venv bootstrap lease (shared .pytest_cache/spec-kitty-test-venv.state.json) with 'Directory not empty: site-packages'; one run at a time per clone. Also: host load average rose 21 -> 91 during the afternoon (20 concurrent missions), making absolute wall-clock comparisons worthless - hence the interleaved A/B protocol.
