"""Per-PR guard: a pull request does not modify the legacy ``kitty-ops/lifecycle.jsonl``.

Since #7006 ``main`` never writes the legacy Op lifecycle log: records go to one file per
record (``kitty-ops/lifecycle/<ulid>.json``) and the reader still reads the legacy file.
Branches cut before #7006 may still append to it; at landing their added lines are moved
into per-record files so the pull request's net diff leaves the legacy file untouched.
That only stays conflict-free while the legacy file on ``main`` never changes again (GitHub
ignores ``.gitattributes`` ``merge=union``), so one unconverted merge would make every other
old branch conflict. This guard refuses a pull request whose net diff modifies it.

Any event other than ``pull_request`` is skipped: the guard judges a PR's diff, and a push
or merge has none to judge. Runs in the always-on ``docs-lint`` job of ``ci-router.yml``,
which checks out the PR merge commit with ``fetch-depth: 2``: ``HEAD^1`` is the base, so
``HEAD^1..HEAD`` is exactly the pull request's change. Standard library only.

Invoked as ``python -m scripts.ci.check_legacy_lifecycle_log_untouched`` or bare as
``python3 scripts/ci/check_legacy_lifecycle_log_untouched.py`` from the repository root.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

LEGACY_LOG = "kitty-ops/lifecycle.jsonl"

REMEDY = (
    f"`{LEGACY_LOG}` is frozen: main no longer writes it. Move the lines your branch added into "
    "per-record files (`kitty-ops/lifecycle/<ulid>.json`, written via "
    "`specify_cli.invocation.lifecycle.append_lifecycle_record`) and reset the legacy file to "
    f"main's bytes (git checkout origin/main -- {LEGACY_LOG})."
)


def violations(changed_paths: Iterable[str]) -> list[str]:
    """Human-readable violations; empty when the pull request leaves the legacy log alone."""
    return [f"{LEGACY_LOG}: frozen legacy lifecycle log modified"] if LEGACY_LOG in set(changed_paths) else []


def skip_reason(environ: Mapping[str, str]) -> str | None:
    """Why the guard does not apply to this run, or ``None`` when it does."""
    event_name = environ.get("GITHUB_EVENT_NAME", "")
    if event_name != "pull_request":
        return f"event {event_name or '(none)'} is not a pull request"
    return None


def _git(*args: str) -> str:
    try:
        return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout
    except subprocess.CalledProcessError as exc:
        print(f"::error::git {' '.join(args)} failed (is the checkout fetch-depth >= 2?): {exc.stderr}", file=sys.stderr)
        raise SystemExit(1) from exc


def main() -> int:
    """Exit 0 when the guard is skipped or clean, 1 with ``::error::`` lines otherwise."""
    reason = skip_reason(dict(os.environ))
    if reason is not None:
        print(f"check_legacy_lifecycle_log_untouched: skipped ({reason})")
        return 0
    found = violations(_git("diff", "--name-only", "HEAD^1", "HEAD").splitlines())
    for violation in found:
        print(f"::error::{violation}", file=sys.stderr)
    if found:
        print(f"::error::{REMEDY}", file=sys.stderr)
        return 1
    print("check_legacy_lifecycle_log_untouched: clean")
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main())
