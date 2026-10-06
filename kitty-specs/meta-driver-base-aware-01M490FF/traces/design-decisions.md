# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-06 · claude · Seed: Decision Moment 01M490FHTGTH51TAD3KNPVMG8H — target-authoritative keys win only on a genuine both-sides conflict (not always); acceptance_history stays a union; a corrupt base fails loud and named; deletion vs change is a conflict resolved by precedence. Grounding dry run: 2270/2270 merge-suite tests green, 13/13 real squashes byte-identical.

2026-10-06 · claude · Post-spec squad (reviewer-renata) folded: squash path opts out of base-awareness (Decision 01M493BC3KPSC4FT6XSC7ESNDN; the squash has no reliable ancestor after reopen+reconsolidate), so 3-way applies only to real merges/pulls; coupled key groups (flatten triple, merged_*, acceptance stamps) merge as one unit; MISSING sentinel distinct from null; unassigned mission_number never replaces an assigned one regardless of ancestor; merge_history stays whole-value (residual).

2026-10-06 · python-pedro · Opt-out placed once in lanes/consolidation.py::_run_squash_merge (squash_env = {**env, META_DRIVER_TWO_WAY_ENV: '1'}) instead of at the two call sites: both the real integration and the dry-run preview reach the single 'git merge --squash' subprocess there, and _make_merge_env stays untouched (ratchet-pinned). Shell wraps run_meta_driver via functools.partial(two_way=...) so _run and the registry keep their 3-positional contract.
