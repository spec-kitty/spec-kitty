# Quickstart — verify the split

```bash
source .venv/bin/activate
# layout contract
python -m pytest tests/runtime/test_runtime_bridge_query_seam_layout.py -q
# the engine no longer reaches into the bridge
grep -n "import runtime_bridge\b" src/runtime/next/runtime_bridge_engine.py   # no output
# public names are the same objects
python -c "import runtime.next.runtime_bridge as b, runtime.next.runtime_bridge_query as q; assert b.query_current_state is q.query_current_state"
# targeted surface
python -m pytest $(cat surface.txt) -n 8 --dist loadfile -q
wc -l src/runtime/next/runtime_bridge*.py
```
