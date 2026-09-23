# Tracer: Approach
## Spine
Close the non-vacuous-guard defect class (DIRECTIVE_043) across six deferred squad findings: each guard must be demonstrated to FAIL on a planted broken input before it is trusted. Test-infra only.
## Grounding (epic #4883 research+grounding+slicing squad, opus)
- 2 grounding lenses read all 48 children, liveness-verified on upstream/main; slicing lens recommended this 6-finding non-vacuity slice as lowest-risk / highest safety-net leverage.
- Zero-work batches cleared first: 9 close-only + 2 declined (epic 48→37).
## WP shape (disjoint files → parallelizable)
- 4036 → tests/_support/repo_root_status_guard.py | 4105 → test_no_dead_src_path_literals.py+_dead_path_scan.py | 4210 → test_performance_marker_guard.py(+marker_job_completeness)+pytest.ini+ci-nightly.yml | 4388 → test_module_shard_registry.py | 4408 → _gate_coverage.py | 4536 → tests/performance/test_cli_startup_budget_4409.py
