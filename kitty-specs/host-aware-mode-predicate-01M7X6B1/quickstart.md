# Quickstart: verify the Mission locally

```bash
make dev-setup && make sync-packs
# predicate unit matrix + emulated-Windows convergence
.venv/bin/python -m pytest tests/specify_cli/tool_surface/test_mode_equivalence.py tests/specify_cli/runtime/test_global_mode_convergence_windows.py -q
# re-pinned host-aware suites
.venv/bin/python -m pytest tests/specify_cli/tool_surface/providers/test_managed_skills_host_aware.py tests/specify_cli/skills/test_installer.py -q
# ratchet gate
.venv/bin/python -m pytest tests/architectural/test_mode_equality_authority.py -q
```
