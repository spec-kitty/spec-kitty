# Tooling friction

## 2026-10-25 — seed
- The cloud container shipped JDK 21; JDK 25 (Temurin 25.0.5) was installed through the HTTPS proxy into /opt/jdk25 and linked on PATH.
- The grounding subagent found the clone shallow (50 commits), so `git log -S` could not reach the culprit commits. It used the GitHub API instead.
- No `researcher-ryan` profile exists. The grounding pass used `researcher-robbie`.

## 2026-10-25 — implement
- `record-analysis` and `implement` both refuse a dirty write checkout. Code drafted before the claim had to be stashed around each call.
- Single-file `mypy <migration>` reports `Class cannot subclass "BaseMigration" (has type "Any")`, also for the shipped `m_4_0_0rc8_activation_ledger.py`. Passing `base.py` with it is clean. This is a mypy path-resolution artifact, not a code defect.
- Every test that runs the full migration registry pays about 80-90s of session fixture setup.
