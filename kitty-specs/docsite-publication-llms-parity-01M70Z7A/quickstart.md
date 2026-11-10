# Quickstart

- Build and check locally: `make docs-site` (contract check, install, frontmatter + strict link gates, build, built-site check, built-links check).
- Check a built tree only: `python3 -m scripts.docs.site_built_check site/dist`.
- Regenerate the projection after editing the contract: `python -m scripts.docs.site_contract`.
- Unpublish a page: working notes → `doc_status: draft`; retired page → `git mv` under `docs/archive/<section>/` + append a `site/moves.yaml` row to the section hub.
