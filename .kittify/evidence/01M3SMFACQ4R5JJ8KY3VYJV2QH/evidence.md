# red-proofs-s
No planted breaks: pure dead-parameter removal (no red-first test required per task).
Proof of deadness: grep of src/ tests/ showed ensure_sync_daemon only forwarded as ensure_daemon into
fire_saas_fanout(**kwargs) -> handlers; adapters.py / zeitgeist_bridge.py never read kwargs["ensure_daemon"].
Natural guard: passing ensure_sync_daemon= now raises TypeError. No dead-symbol/retired-subsystem allowlist covers a parameter.
