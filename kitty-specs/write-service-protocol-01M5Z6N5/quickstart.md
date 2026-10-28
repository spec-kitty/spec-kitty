# Quickstart: validate the mission-write contract

```bash
# Python checks over the whole contracts tree (each prints a counts: line; exit 0 is a pass)
for t in layout_check structure_check citation_check provisional_check example_check leak_scan; do
  .venv/bin/python contracts/tools/$t.py --root contracts || break
done

# Bundle only (no JDK, no Gradle)
.venv/bin/python contracts/tools/bundle.py --root contracts --out "$HOME/.cache/contract-out" --bundle-only

# Full JVM validation (JDK 21 on PATH)
.venv/bin/python contracts/tools/install_tools.py --pins contracts/tools/pins.json --dest "$HOME/.cache/contract-tools" --only gradle
PATH="$HOME/.cache/contract-tools/gradle-8.14.5/bin:$PATH" \
  .venv/bin/python contracts/tools/bundle.py --root contracts --out "$HOME/.cache/contract-out"

# Contract acceptance, parity and client-shape tests
PWHEADLESS=1 .venv/bin/python -m pytest -q tests/contract/test_mission_write_contract.py \
  tests/contract/test_layout_check.py tests/specify_cli/status/test_write_service_protocol.py
```
