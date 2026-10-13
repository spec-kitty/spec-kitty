# Quickstart

```bash
# Per-PR scenario contract check (no JDK)
uv run --frozen pytest -q tests/architectural/test_scenario_contract.py

# Nightly passes locally (JDK 25 + pinned Gradle)
gradle -p acceptance-jvm test --no-daemon -Pacceptance.pass=gating
gradle -p acceptance-jvm test --no-daemon -Pacceptance.pass=wip
uv run --frozen python -m scripts.ci.acceptance_evidence --root acceptance-jvm/build/acceptance --os "$(uname -s)"
cat acceptance-jvm/build/acceptance/evidence.json
```
