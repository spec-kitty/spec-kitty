"""Per-PR guard: a pull request does not edit the generated docs surfaces.

The docs retrieval index, the page inventory and the ADR era table rows are regenerated
on ``main`` after a merge (``docs-index-regen.yml``, ``scripts/ci/regen_docs_index.py``)
and proposed on the fixed branch ``ci/regen-docs-index``. A pull request that edits them
reintroduces the merge conflicts that move removed, so this guard refuses:

* any change to ``docs/development/docs-retrieval-index.yaml`` or
  ``docs/development/page-inventory.yaml``;
* a NEW row in an ADR era table (``docs/adr/<era>/index.md``): a ``| date | [title](x.md) |``
  line whose linked file no removed line links. Editing an existing row (a title fix)
  and editing the page's prose stay allowed.

The bot's own pull request (head branch ``ci/regen-docs-index`` in this repository) is
exempt. Any event other than ``pull_request`` is skipped: the guard judges a PR's diff,
and a push or merge has none to judge.

Runs in the always-on ``docs-lint`` job of ``ci-router.yml``, which checks out the PR
merge commit with ``fetch-depth: 2``: ``HEAD^1`` is the base, so ``HEAD^1..HEAD`` is
exactly the pull request's change. Standard library only.

Invoked as ``python -m scripts.ci.check_generated_docs_untouched``.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ci.regen_docs_index import ERA_INDEX_RE, GENERATED_FILES, REGEN_BRANCH  # noqa: E402

#: An ADR era table data row, capturing the linked file name.
_ADR_ROW_RE = re.compile(r"^\s*\|\s*\d{4}-\d{2}-\d{2}\s*\|.*\]\(([^)\s]+\.md)\)")
_DIFF_FILE_RE = re.compile(r"^\+\+\+ b/(.+)$")

REMEDY = (
    "Do not regenerate the docs index, the page inventory or the ADR era tables in a pull request: "
    f"after merge, the `{REGEN_BRANCH}` bot pull request regenerates them. Revert those edits "
    "(git checkout origin/main -- <path>) and push again."
)


def protected_file_changes(changed_paths: Iterable[str]) -> list[str]:
    """The generated files among *changed_paths*, sorted."""
    return sorted({path for path in changed_paths if path in GENERATED_FILES})


def new_era_rows(era_diff: str) -> dict[str, list[str]]:
    """Per era index, the ADR files that an added table row links and no removed row does.

    *era_diff* is ``git diff --unified=0`` output; only files matching the era index
    pattern are read.
    """
    added: dict[str, set[str]] = {}
    removed: dict[str, set[str]] = {}
    current: str | None = None
    for line in era_diff.splitlines():
        header = _DIFF_FILE_RE.match(line)
        if header:
            current = header.group(1) if ERA_INDEX_RE.match(header.group(1)) else None
            continue
        if current is None or line.startswith(("+++", "---")):
            continue
        if line and line[0] in "+-":
            match = _ADR_ROW_RE.match(line[1:])
            if match:
                bucket = added if line[0] == "+" else removed
                bucket.setdefault(current, set()).add(match.group(1))
    result: dict[str, list[str]] = {}
    for path, linked in added.items():
        fresh = sorted(linked - removed.get(path, set()))
        if fresh:
            result[path] = fresh
    return dict(sorted(result.items()))


def violations(changed_paths: Iterable[str], era_diff: str) -> list[str]:
    """Human-readable violations; empty when the pull request leaves the surfaces alone."""
    found = [f"{path}: generated file edited" for path in protected_file_changes(changed_paths)]
    for path, files in new_era_rows(era_diff).items():
        found.append(f"{path}: new ADR era table row(s) for {', '.join(files)}")
    return found


def is_bot_pull_request(head_ref: str, head_repository: str, repository: str) -> bool:
    """True iff the pull request is the regeneration bot's own (same repository, fixed branch)."""
    return head_ref == REGEN_BRANCH and bool(repository) and head_repository == repository


def skip_reason(environ: Mapping[str, str], event: Mapping[str, object]) -> str | None:
    """Why the guard does not apply to this run, or ``None`` when it does."""
    event_name = environ.get("GITHUB_EVENT_NAME", "")
    if event_name != "pull_request":
        return f"event {event_name or '(none)'} is not a pull request"
    pull_request = event.get("pull_request")
    head_repository = ""
    if isinstance(pull_request, Mapping):
        head = pull_request.get("head")
        repo = head.get("repo") if isinstance(head, Mapping) else None
        full_name = repo.get("full_name") if isinstance(repo, Mapping) else None
        head_repository = full_name if isinstance(full_name, str) else ""
    if is_bot_pull_request(environ.get("GITHUB_HEAD_REF", ""), head_repository, environ.get("GITHUB_REPOSITORY", "")):
        return f"the {REGEN_BRANCH} bot pull request may update the generated surfaces"
    return None


# --------------------------------------------------------------------------- #
# Edge -- the event payload and git.                                          #
# --------------------------------------------------------------------------- #


def _read_event(environ: Mapping[str, str]) -> dict[str, object]:
    path = environ.get("GITHUB_EVENT_PATH", "")
    if not path or not Path(path).is_file():
        return {}
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout
    except subprocess.CalledProcessError as exc:
        print(f"::error::git {' '.join(args)} failed (is the checkout fetch-depth >= 2?): {exc.stderr}", file=sys.stderr)
        raise SystemExit(1) from exc


def main() -> int:
    """Exit 0 when the guard is skipped or clean, 1 with ``::error::`` lines otherwise."""
    environ = dict(os.environ)
    reason = skip_reason(environ, _read_event(environ))
    if reason is not None:
        print(f"check_generated_docs_untouched: skipped ({reason})")
        return 0
    changed = _git("diff", "--name-only", "HEAD^1", "HEAD").splitlines()
    era_diff = _git("diff", "--unified=0", "HEAD^1", "HEAD", "--", "docs/adr")
    found = violations(changed, era_diff)
    for violation in found:
        print(f"::error::{violation}", file=sys.stderr)
    if found:
        print(f"::error::{REMEDY}", file=sys.stderr)
        return 1
    print("check_generated_docs_untouched: clean")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
