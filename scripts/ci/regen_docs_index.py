"""Post-merge regeneration of the generated docs surfaces (``docs-index-regen.yml``).

Three docs surfaces are generated from the ``docs/`` tree:

* the docs retrieval index, ``docs/development/docs-retrieval-index.yaml``
  (``scripts/docs/docs_index.py``);
* the page inventory, ``docs/development/page-inventory.yaml``
  (``scripts/docs/inventory_lockfile.py``);
* the ADR era tables, the ``| Date | Title |`` rows of ``docs/adr/<era>/index.md``
  (``scripts/docs/freshen_adr_inventory.py --all``).

Every docs pull request used to regenerate them, so every merge conflicted every other
docs pull request in flight. They are now regenerated on ``main`` after a merge and
proposed as ONE pull request on the fixed branch :data:`REGEN_BRANCH`; a pull request
must not edit them (``scripts/ci/check_generated_docs_untouched.py``). The per-PR check
of their CONTENT is ``tests/docs/test_docs_index_regenerates_cleanly.py``.

Two phases, so the write credential never meets repository code:

* ``regenerate`` (no credential; refuses to run when :data:`SECRET_NAME` is present):
  runs the three generators in process, then reports through ``$GITHUB_OUTPUT`` whether a
  generated surface changed (``changed=true|false``). A change to any other path fails
  the step: the generators must touch nothing else.
* ``publish`` (the PAT): when a generated surface changed, commits it as the bot,
  force-pushes :data:`REGEN_BRANCH` and opens a pull request when none is open. The force
  push is safe here: the branch is always ``main`` plus one regeneration commit, a pure
  function of ``main``, so a newer run simply replaces the older proposal.

Invoked as ``python -m scripts.ci.regen_docs_index <regenerate|publish>``.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

# Resolve the repository root from the script, never the caller's cwd, so ``scripts.*``
# imports resolve however the workflow invokes it.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ci import bot_pr_publish  # noqa: E402  (import after the path guard above)

#: The fixed head branch of the regeneration proposal. GitHub permits one open PR per head
#: branch into a base, so a duplicate proposal is structurally impossible.
REGEN_BRANCH = "ci/regen-docs-index"

#: The PAT secret NAME (never a value). Shared, for now, with ``ci-shard-recapture.yml``;
#: a dedicated secret is tracked in spec-kitty/spec-kitty#6986. Never ``GITHUB_TOKEN``.
SECRET_NAME = "CHARTER_SHARD_RECAPTURE_TOKEN"  # noqa: S105  # env-var name, not a secret value

PHASE_REGENERATE = "regenerate"
PHASE_PUBLISH = "publish"
PHASES = (PHASE_REGENERATE, PHASE_PUBLISH)

#: The generated files, repo-relative. Pinned against the generators' own constants by
#: ``tests/ci/test_regen_docs_index.py`` (kept literal so the per-PR guard imports nothing
#: beyond the standard library).
DOCS_INDEX_PATH = "docs/development/docs-retrieval-index.yaml"
PAGE_INVENTORY_PATH = "docs/development/page-inventory.yaml"
GENERATED_FILES = (DOCS_INDEX_PATH, PAGE_INVENTORY_PATH)

#: An ADR era landing page whose index table the regeneration maintains.
ERA_INDEX_RE = re.compile(r"^docs/adr/\d+\.x/(?:index|README)\.md$")

#: Every token variable stripped from a subprocess environment before the one it needs.
_TOKEN_ENV_VARS = (SECRET_NAME, "GH_TOKEN", "GITHUB_TOKEN")

COMMIT_MESSAGE = "chore(docs): regenerate the docs retrieval index, page inventory and ADR era tables"

PR_BODY_TEMPLATE = (
    "Automated regeneration opened by `docs-index-regen.yml` (`scripts/ci/regen_docs_index.py`) "
    "after docs changes landed on `main`.\n\n"
    "Pull requests no longer regenerate these files; this bot does it after merge, so docs pull "
    "requests stop conflicting with each other on them.\n\n"
    "Changed:\n{paths}\n\n"
    "Workflow run: `{run_url}`. Merge it as is; a newer run replaces this branch."
)


def is_generated_surface(path: str) -> bool:
    """True iff *path* (repo-relative, POSIX) is a surface this bot regenerates."""
    return path in GENERATED_FILES or bool(ERA_INDEX_RE.match(path))


@dataclass(frozen=True)
class ChangedPaths:
    """The working-tree changes after a regeneration, split by ownership."""

    generated: tuple[str, ...]
    unexpected: tuple[str, ...]


def classify_changes(paths: Iterable[str]) -> ChangedPaths:
    """Split changed *paths* into generated surfaces and anything else (sorted, unique)."""
    unique = sorted(set(paths))
    return ChangedPaths(
        generated=tuple(p for p in unique if is_generated_surface(p)),
        unexpected=tuple(p for p in unique if not is_generated_surface(p)),
    )


def parse_porcelain(output: str) -> list[str]:
    """Paths from ``git status --porcelain=v1 -z`` output (rename sources are skipped)."""
    paths: list[str] = []
    records = output.split("\0")
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if len(record) < 4:
            continue
        status, path = record[:2], record[3:]
        paths.append(path)
        if "R" in status or "C" in status:
            index += 1  # the next record is the rename/copy source
    return paths


def pr_body(paths: Sequence[str], run_url: str) -> str:
    """The proposal PR body."""
    listed = "\n".join(f"- `{path}`" for path in paths) or "- none"
    return PR_BODY_TEMPLATE.format(paths=listed, run_url=run_url)


# --------------------------------------------------------------------------- #
# Edge -- generators, git and gh.                                             #
# --------------------------------------------------------------------------- #


def regenerate(repo_root: Path) -> None:
    """Run the three generators against *repo_root*, ADR era rows first (they are pages
    the index and inventory walk), then the inventory, then the retrieval index."""
    from scripts.docs import docs_index, freshen_adr_inventory

    docs_root = repo_root / "docs"
    targets = freshen_adr_inventory.detect_missing_adrs(docs_root)
    freshen_adr_inventory.freshen(targets, docs_root=docs_root, repo_root=repo_root, check=False)
    docs_index.run_generate_and_compare(
        docs_root=docs_root,
        index_path=repo_root / DOCS_INDEX_PATH,
        write=True,
        strict=False,
    )


def _changed_paths(env: dict[str, str]) -> ChangedPaths:
    status = bot_pr_publish.run_or_die(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        step="git status",
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    return classify_changes(parse_porcelain(status.stdout))


def _refuse_if_token_present() -> bool:
    if SECRET_NAME in os.environ:
        print(
            f"::error::{SECRET_NAME} is present in the regenerate phase's environment -- refusing to "
            "run the generators with the write credential exposed (wire it into the publish step only)",
            file=sys.stderr,
        )
        return True
    return False


def run_regenerate_phase() -> int:
    """Regenerate, then record ``changed`` for the publish step. No credential."""
    if _refuse_if_token_present():
        return 1
    regenerate(REPO_ROOT)
    changes = _changed_paths(bot_pr_publish.scrubbed_env(_TOKEN_ENV_VARS))
    if changes.unexpected:
        print(
            "::error::the regeneration changed paths it does not own: " + ", ".join(changes.unexpected),
            file=sys.stderr,
        )
        return 1
    for path in changes.generated:
        bot_pr_publish.write_job_summary(f"Regenerated `{path}`.")
    if not changes.generated:
        bot_pr_publish.write_job_summary("The generated docs surfaces are already fresh; nothing to propose.")
    bot_pr_publish.write_github_output(changed=str(bool(changes.generated)).lower())
    return 0


def _push(token: str) -> None:
    cmd = ["git", "push", "--force", "origin", f"HEAD:refs/heads/{REGEN_BRANCH}"]
    try:
        subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            env=bot_pr_publish.push_env(token, _TOKEN_ENV_VARS),
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = bot_pr_publish.redact(str(exc.stderr or ""), token).strip()
        print(
            f"::error::git push to {REGEN_BRANCH} failed. If this is a permission error, the token in the "
            f"repository secret {SECRET_NAME} lacks `contents: write`. git said: {stderr}",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc


def run_publish_phase() -> int:
    """Commit the regenerated surfaces, force-push the fixed branch, open a PR if none is."""
    token = bot_pr_publish.require_token(SECRET_NAME)  # First action, before any gh/git call.
    no_credential_env = bot_pr_publish.scrubbed_env(_TOKEN_ENV_VARS)
    changes = _changed_paths(no_credential_env)
    if changes.unexpected:
        print("::error::refusing to publish paths outside the generated surfaces: " + ", ".join(changes.unexpected), file=sys.stderr)
        return 1
    if not changes.generated:
        return 0  # Defense in depth behind the workflow's `if:`.
    bot_pr_publish.run_or_die(["git", "add", "--", *changes.generated], step="git add", cwd=REPO_ROOT, env=no_credential_env)
    bot_pr_publish.run_or_die(bot_pr_publish.git_commit_cmd(COMMIT_MESSAGE), step="git commit", cwd=REPO_ROOT, env=no_credential_env)
    _push(token)
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    open_prs = bot_pr_publish.list_open_prs(repository, REGEN_BRANCH, token, _TOKEN_ENV_VARS)
    pr_number = bot_pr_publish.find_open_pr(open_prs, REGEN_BRANCH)
    if pr_number is not None:
        bot_pr_publish.write_job_summary(f"Refreshed the open regeneration proposal #{pr_number}.")
        return 0
    bot_pr_publish.run_or_die(
        [
            "gh",
            "pr",
            "create",
            "--repo",
            repository,
            "--head",
            REGEN_BRANCH,
            "--base",
            "main",
            "--title",
            COMMIT_MESSAGE,
            "--body",
            pr_body(changes.generated, bot_pr_publish.run_url()),
        ],
        step="gh pr create",
        env=bot_pr_publish.gh_env(token, _TOKEN_ENV_VARS),
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Dispatch to :func:`run_regenerate_phase` or :func:`run_publish_phase`."""
    parser = argparse.ArgumentParser(prog="regen_docs_index", description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("phase", choices=PHASES)
    args = parser.parse_args(sys.argv[1:] if argv is None else list(argv))
    if args.phase == PHASE_REGENERATE:
        return run_regenerate_phase()
    return run_publish_phase()


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
