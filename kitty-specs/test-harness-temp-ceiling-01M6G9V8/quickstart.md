# Quickstart: check the harness temp ceiling

Three commands, in the order they are worth running.

## 1. Is the run's tempfile root inside the ceiling?

```bash
cat > /tmp/probe_temp_root.py <<'EOF'
import os, tempfile
from pathlib import Path

def test_probe(tmp_path):
    print("tempfile root:", tempfile.gettempdir())
    print("basetemp     :", tmp_path.parent)
    print("ceilings     :", os.environ.get("GIT_CEILING_DIRECTORIES", "").split(os.pathsep))
EOF
cp /tmp/probe_temp_root.py tests/unit/test_zz_probe_temp_root.py
uv run pytest tests/unit/test_zz_probe_temp_root.py -q -s
rm tests/unit/test_zz_probe_temp_root.py
```

Expect `tempfile root` to be `<basetemp>/tmp` and both paths to appear under `ceilings`
(the basetemp is one entry, the worker's isolated home the other).

## 2. Does a hostile temp root still resolve nothing?

```bash
uv run pytest tests/unit/test_harness_temp_root.py -q
```

`test_a_tempfile_dir_under_a_hostile_temp_root_resolves_no_project` builds a repository that
*encloses* the run's basetemp, makes a directory with `tempfile` inside it, and asserts the walk
answers `None` — then removes the ceiling and asserts the same walk finds that repository, so a
green run cannot be vacuous.

## 3. Does a from-scratch child keep the boundary?

```bash
uv run pytest tests/unit/test_harness_child_env.py -q
```

Each of the six child-environment sites is driven through its own helper. A helper that forgets
`harness_env()` reds its own test by name.

## If a suite reds on a host whose `/tmp` is inside a repository

That is the failure this mission fixes. Confirm the three commands above are green, then re-run
the failing module; if it still fails, the module is reading the platform temp root directly
(`tempfile.gettempdir()` at import time or a hard-coded `/tmp`) rather than using `tempfile`, and
that is worth an issue of its own.
