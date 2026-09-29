# Quickstart — reproducing and verifying slice 10

All reproductions are real-CLI tests in temporary repositories (no mocked git):

```bash
PWHEADLESS=1 .venv/bin/python -m pytest tests/terminus/test_repro_5338.py -q      # claim-time refusal: no ref/state/event change, exit 1
PWHEADLESS=1 .venv/bin/python -m pytest tests/terminus/test_repro_5318.py -q      # gate FAIL/REFUSE restores all branches; --abort + fresh run passes
PWHEADLESS=1 .venv/bin/python -m pytest tests/terminus/test_repro_5332.py -q      # projection refusal restores
PWHEADLESS=1 .venv/bin/python -m pytest tests/terminus/test_repro_5296.py -q      # planning claim leaves target unchanged; consolidate passes
PWHEADLESS=1 .venv/bin/python -m pytest tests/consolidation/test_rollback_authority.py tests/consolidation/test_single_rollback_authority.py -q
```

Each repro records `git rev-parse` of target, mission branch and every lane branch before and after the command and asserts on those SHAs.
