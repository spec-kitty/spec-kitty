# Quickstart — measure and verify the render scope

## Measure what a command parses (before/after)

```bash
# Ad-hoc census: count every shipped document a command actually parses.
cd <repo-root>
uv run --no-sync python - <<'PY' charter context --action plan
import collections, sys, time
from ruamel.yaml.main import YAML
from pathlib import PurePosixPath

counts = collections.Counter()
_orig = YAML.load

def load(self, stream, *a, **k):
    name = getattr(stream, "name", None) or "<text>"
    suffix = PurePosixPath(str(name)).suffix
    counts[suffix or "<none>"] += 1
    return _orig(self, stream, *a, **k)

YAML.load = load
from specify_cli import main
sys.argv = ["spec-kitty"] + sys.argv[1:]
t0 = time.perf_counter()
try:
    main()
except SystemExit:
    pass
print(f"{time.perf_counter() - t0:.2f}s", dict(counts), file=sys.stderr)
PY
```

Or use the mission's census harness, which counts through the production
`parse_shipped_yaml` seam and separates graph/profile/catalog documents:

```bash
uv run --frozen pytest tests/charter/test_charter_render_scope_6462.py -q -s
```

## Verify parity

```bash
# Render every action with and without the scope; the text must be byte-identical.
for a in specify plan tasks implement review merge; do
  uv run --no-sync spec-kitty charter context --action "$a" > "/tmp/render-$a.txt"
done
git stash && for a in specify plan tasks implement review merge; do
  uv run --no-sync spec-kitty charter context --action "$a" > "/tmp/before-$a.txt"
done; git stash pop
diff -r /tmp/before-plan.txt /tmp/render-plan.txt
```

## Verify the guards fail without the fix

```bash
git stash push -- src/charter/activation/catalog.py src/charter/activation/resolver.py \
  src/charter/activation/interview.py src/charter/offering/agent_profiles/repository.py
uv run --frozen pytest tests/charter/test_charter_render_scope_6462.py -q   # must fail, naming 265 / 13
git stash pop
```

## Run the focused suites

```bash
uv run --frozen pytest tests/charter/test_charter_render_scope_6462.py \
  tests/charter/activation/test_offering_catalog_scope_6462.py -q
uv run --frozen pytest tests/charter -q -n 4 --dist loadfile -m "not performance and not stress"
uv run --frozen ruff check src/charter tests/charter
uv run --frozen mypy src/charter/activation/catalog.py src/charter/activation/resolver.py \
  src/charter/offering/agent_profiles/repository.py
```
