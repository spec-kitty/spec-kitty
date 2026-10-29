# Quickstart — verifying Synthesis record integrity

```bash
# Targeted tests
uv run --frozen pytest tests/charter/synthesizer/test_synthesis_lock.py \
  tests/charter/synthesizer/test_synthesize_activation_append.py \
  tests/charter/synthesizer/test_synthesize_reconcile.py \
  tests/charter/synthesizer/test_styleguide_reach_only.py -q

# Lock primitive gate
uv run --frozen pytest tests/architectural/test_lock_primitive_ban.py -q
```

Manual check (#6455): corrupt `.kittify/charter/synthesized-artifacts.yaml` (e.g. `echo ':' > ...`), run `spec-kitty charter synthesize`, and read the warning: it names the file, says to restore it with `git checkout -- <path>` or repair its YAML keeping the ids, and says not to delete it.

Manual check (#6453): hold the lock from one shell (`python -c "from charter.activation.api import synthesis_lock; ..."`) and run `spec-kitty charter synthesize` in another; it exits 1 after ~10 s with `CHARTER_SYNTHESIS_LOCK_HELD`.
