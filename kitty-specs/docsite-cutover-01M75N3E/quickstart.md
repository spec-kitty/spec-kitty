# Quickstart: verify the cutover locally

```bash
# The job-graph, ownership and fork-guard tests
uv run --frozen pytest tests/release/test_release_ci_ownership.py tests/ci/test_fork_guard.py tests/ci/test_docs_site_job.py tests/ci/test_nightly_tooling_cache.py --tb=line -q

# The docs subsystem (includes the probe's own tests and the llms.txt references)
uv run --frozen pytest tests/docs -n 4 --dist loadfile --tb=line -q

# Workflow lint
actionlint .github/workflows/docs-pages.yml .github/workflows/docs-site-build.yml
```

After the operator merges: the first push run on `main` shows `pages`, `build`, `deploy` and `smoketest` green, and `https://docs.spec-kitty.ai/llms.txt` serves the generated file. Rollback: revert the pull request.
