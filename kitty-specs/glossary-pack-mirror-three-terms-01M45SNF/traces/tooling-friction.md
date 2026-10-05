# Tooling friction

Tooling this mission touches: the `spec-kitty` CLI mission loop (single_branch
topology on `issue-5761-glossary-pack-terms`), `spec-kitty doctrine
regenerate-graph`, the docs retrieval index and contextive generators, and the
glossary parity gates.

- 2026-10-05: the cloud checkout was shallow (50 commits), so the precedent
  commits `b70a344fc8` / `8fc1a85560` were unreachable until
  `git fetch --unshallow origin main`.
- 2026-10-05: `agent mission create` commits its scaffold without the
  operator's required `Co-Authored-By` trailer; CLI-authored commits cannot be
  given a trailer at commit time.
- 2026-10-05: `setup-plan` auto-commits plan.md ("Add plan for feature ...")
  with the retired "feature" word in its message and without the operator's
  trailer; research.md / data-model.md / quickstart.md / meta.json are left
  for the agent to commit.
