# Quickstart: verifying the per-user location convergence by hand

Everything below runs on Linux (this host). The macOS and Windows expectations are what
the faked-platform tests pin; the commands show how to reproduce them.

## 1. See the divergence on the pre-fix tree

```bash
cd <repo-root>
XDG_CACHE_HOME=/tmp/xdg XDG_STATE_HOME=/tmp/state uv run python - <<'EOF'
from charter.offering.packs.pack_fetch import default_cache_root
from specify_cli.compat.cache import _resolve_cache_dir
print("pack_fetch      :", default_cache_root())
print("compat.cache    :", _resolve_cache_dir())
EOF
```

On the pre-fix tree with no XDG variables set and a faked macOS home they disagree
(`~/.cache/spec-kitty/open-packs` vs `~/Library/Caches/spec-kitty`). The regression test
`tests/kernel/test_user_dirs_convergence.py` does exactly this comparison for all six
callers, per platform, without needing the host to be macOS.

## 2. Resolve every caller for one faked platform

```bash
uv run pytest tests/kernel/test_user_dirs.py tests/kernel/test_user_dirs_convergence.py -q
```

The pins assert the full table from `data-model.md`: cache, state and config per platform,
XDG precedence, empty-variable fallback, and `appauthor=False` on Windows.

## 3. Prove the guard is not vacuous

Each caller is listed in the convergence test with the rule it used before this Mission.
To confirm the test discriminates, temporarily put one caller back on its old rule:

```bash
# put the pre-fix composition back, run the convergence test, expect FAIL
sed -i 's|return user_cache_dir() / "open-packs"|return user_cache_dir() / "spec-kitty" / "open-packs"|' \
  src/charter/offering/packs/pack_fetch.py
uv run pytest tests/kernel/test_user_dirs_convergence.py -q   # must fail, naming pack_fetch
git checkout src/charter/offering/packs/pack_fetch.py
```

A run that stays green after that edit means the guard is exercising something else and
must be fixed before the work package is approved.

## 4. Watch the legacy discard

```bash
H=$(mktemp -d)
HOME="$H" XDG_CACHE_HOME= uv run python - <<'EOF'
from pathlib import Path
import os
legacy = Path(os.environ["HOME"]) / ".cache" / "spec-kitty"
legacy.mkdir(parents=True)
(legacy / "upgrade-check.json").write_text("{}")
from kernel.user_dirs_legacy import discard_legacy_locations
print("removed:", discard_legacy_locations())
print("still there:", legacy.exists())
EOF
```

On Linux the run removes nothing, because `~/.cache/spec-kitty` is still the live cache
directory. Under the faked macOS fixture the same call removes it. Both halves are asserted
in `tests/kernel/test_user_dirs_legacy.py` on one fixture.

## 5. Confirm a command still works

```bash
uv run spec-kitty --help >/dev/null && echo ok
uv run pytest tests/core/test_upgrade_probe_and_notifier.py tests/next/test_runtime_pkg_notice_unit.py \
  tests/charter_offering/test_pack_fetch_cache_root.py tests/kernel/test_service_artifacts.py -q
```

## 6. Docs

```bash
uv run python -m scripts.docs.check_docs_freshness --ci   # expect errors=0
uv run pytest tests/architectural/test_no_legacy_terminology.py -q
```
