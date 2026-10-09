# Tooling Friction — serialise-next-advance

Running log of tooling/process friction encountered during the mission. Append
dated entries: `- **[YYYY-MM-DD][phase] Short symptom.** prose; #NNNN; disposition.`

## Entries

- **[2026-10-08][research] None yet.** Mission bootstrapped cleanly on
  `issue-5854-serialise-next` (topology resolved to `coord`). Recording started.
- **[2026-10-08][implement] `tests/next` conftest cold-start is ~20s.** First
  test in a fresh process pays a one-time discovery cost; warm runs are ~3s. No
  action; noting for anyone timing a single-test run.
- **[2026-10-08][implement] Pre-existing mypy debt in `engine.py` (12 call-arg
  errors on `spec_kitty_events` payloads missing `mission_id`/`mission_slug`).**
  Identical on unmodified main (different line numbers); not introduced by this
  WP, left untouched. #N/A; disposition: pre-existing, out of scope.
- **[2026-10-08][implement] Non-owned tests needed contract updates.** FR-006
  (unique temp) and the new `plan_advance(..., expected_issued_step=)` kwarg broke
  5 tests outside this WP's owned set (`test_run_state_hardening.py` tmp-name
  pins; `plan_advance` stubs in `test_bridge_decide_next.py` /
  `test_bridge_decision_log_flush.py`). Updated them to the new contract
  (WP01 is the sole code lane); disposition: necessary campsite fix, recorded.
