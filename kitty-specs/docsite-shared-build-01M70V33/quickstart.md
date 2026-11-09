# Quickstart: Docsite shared build definition

- The gate: `.github/workflows/ci-router.yml` job `docs-site` calls `./.github/workflows/docs-site-build.yml`. Its result shows in the run as `docs site (doc-kitty build) / build`.
- The deploy (#6938) will call it as:

  ```yaml
  build:
    uses: ./.github/workflows/docs-site-build.yml
    with:
      pages-artifact: true
  ```

  then `actions/deploy-pages` in a `deploy` job that `needs: build`.
- Locally nothing changes: `make docs-site` still runs the same contract check, frozen install and build.
- Pins: `uv run --frozen pytest tests/ci/test_docs_site_job.py`.
