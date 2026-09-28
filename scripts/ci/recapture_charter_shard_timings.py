"""Scheduled recapture of ``charter``'s shard-timings entry (mission
per-pr-shard-timings-recapture-friction-01M3H7V8, WP02; spec-kitty#5189).

The per-PR gate (WP01) demotes ``test_charter_is_not_allowlisted_and_agrees`` to a
warn-by-default check, which stops blocking individual PRs on ``charter``'s recorded
shard-timing count drifting away from live collection, but does nothing to *close* that
drift. This module is the automatic remediation: a scheduled workflow (WP03) invokes
:func:`main`, which re-runs ``scripts/ci/capture_shard_timings.py --module charter
--write`` **in-process** (never as a subprocess -- see the design note below) and, only
when the freshly-captured entry's length actually changed, commits it to a fixed branch
and opens a PR.

Every decision is a pure, injectable function, unit-tested red-first with no real
``gh``/``git``/network call: :func:`has_drift` (FR-006, length-only -- a raw file diff
would false-positive on ``--write``'s routine ``run_id``/``captured_at``/duration-value
rewrite noise), :func:`find_open_recapture_pr` (FR-007, matches ONLY on head branch --
an unrelated PR that also touches ``.github/ci-shard-timings.json`` on a different head,
the #5175/#5177 shape, is never matched), and :func:`require_recapture_token`
(FR-005/CL-002/C-004, a truthy check with **no** ``GITHUB_TOKEN`` fallback). The
``gh``/``git`` subprocess calls and the file reads live only in the small ``_``-prefixed
edge functions :func:`main` composes them from, mirroring ``stale_running_sweep.py``'s
pure-decision-plus-thin-edge shape (DIRECTIVE_044 -- no in-repo precedent for
``gh pr create``/``gh pr list`` wiring exists, so this is written fresh, not copied).

Why the mechanism is called in-process, never as a subprocess
---------------------------------------------------------------
A subprocess's exit code alone cannot distinguish "the measured suite had failing tests"
(FR-008's *not*-abort case -- ``capture_shard_timings.py``'s ``DurationRecorder`` records
every reported test regardless of outcome, so the captured data stays complete and
trustworthy even when ``pytest.main()`` itself returns non-zero) from "the capture
mechanism itself crashed" (FR-008's abort case -- an uncaught exception exits the
interpreter with the same code 1 as a clean non-zero return). :func:`run_capture_or_die`
calls ``capture_shard_timings.main`` directly and catches any exception/``SystemExit`` at
the call site, so the two cases are told apart by construction rather than by exit-code
sniffing. This script's ``MODULE = "charter"`` scope lock (FR-009) is also a precondition
for that in-process choice being safe: exactly one ``pytest.main()`` invocation happens
per process, so pytest's own repeated-invocation state (stale ``sys.modules`` entries,
assertion-rewrite hook accumulation) is never at risk.

Never invoked as a bare ``python`` script with CLI flags -- it takes none. See
:func:`main`.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

# Actions runs this trusted-checkout script before installing the package, and
# ``scripts.ci`` resolves as a namespace package only with the repo root on the
# path. Resolve from the script, never the caller's cwd.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ci import capture_shard_timings  # noqa: E402  (import after the path guard above)

MODULE = "charter"  # FR-009: hardcoded, no --module flag exposed by this script at all

#: FR-007's fixed recapture head branch. GitHub permits only one open PR per head branch
#: into a given base, so a duplicate recapture PR from this workflow is structurally
#: impossible.
RECAPTURE_BRANCH = "ci/recapture-charter-shard-timings"

#: FR-005/CL-002/C-004: the dedicated PAT/App-token secret NAME (never a value). Never
#: ``GITHUB_TOKEN``.
SECRET_NAME = "CHARTER_SHARD_RECAPTURE_TOKEN"  # noqa: S105  # env-var name, not a secret value

#: Reuse the canonical path -- single source of truth (DIRECTIVE_044), never a second
#: literal that could drift from the producer's own.
TIMINGS_PATH = capture_shard_timings.TIMINGS_PATH

#: FR-010: fixed, non-human bot identity for the recapture commit -- never the PAT
#: owner's own git identity.
COMMIT_AUTHOR_NAME = "spec-kitty-ci-bot"
COMMIT_AUTHOR_EMAIL = "ci-bot@users.noreply.github.com"

#: FR-010: fixed, falsifiable-by-inspection commit message / PR title (verbatim).
COMMIT_MESSAGE = "chore(ci): automated charter shard-timings recapture"

#: FR-010: fixed PR-body template (verbatim except for the three filled values).
PR_BODY_TEMPLATE = (
    "Automated recapture opened by the scheduled `ci-charter-shard-recapture.yml` workflow "
    "(`scripts/ci/recapture_charter_shard_timings.py`). Updates `.github/ci-shard-timings.json`'s "
    "`charter` entry: committed length `{before}` -> `{after}`. Workflow run: `{run_url}`. "
    "See spec-kitty#5189."
)


@dataclass(frozen=True)
class CaptureOutcome:
    mechanism_ok: bool
    pytest_exit_code: int | None
    error: str | None


def run_capture_or_die(capture_main: Callable[[list[str]], int], argv: list[str]) -> CaptureOutcome:
    """Call *capture_main* in-process and tell a mechanism crash from an ordinary failure.

    Never trust a raw subprocess exit code (ambiguous -- an uncaught exception exits the
    interpreter with code 1, same as a clean ``return 1``). Any exception or ``SystemExit``
    raised by *capture_main* is a mechanism crash (FR-008's abort case); a returned exit
    code, however non-zero, means the mechanism ran to completion and its data is trustworthy
    (FR-008's ordinary-failure-continues case).
    """
    try:
        exit_code = capture_main(argv)
    except KeyboardInterrupt:
        raise
    except (Exception, SystemExit) as exc:
        # Deliberately broad: ANY uncaught exception from the mechanism is a crash -- AND so is a
        # SystemExit, which Exception alone would miss (argparse's parser.error() raises SystemExit,
        # a BaseException subclass, not an Exception subclass). KeyboardInterrupt is re-raised,
        # never swallowed as a mechanism crash.
        return CaptureOutcome(mechanism_ok=False, pytest_exit_code=None, error=str(exc))
    return CaptureOutcome(mechanism_ok=True, pytest_exit_code=exit_code, error=None)


def has_drift(before_length: int, after_length: int) -> bool:
    """FR-006: length-only drift. Equal lengths => no drift, even if --write rewrote
    run_id/captured_at/duration-value noise (never compare raw file diffs)."""
    return before_length != after_length


def find_open_recapture_pr(open_prs: list[dict[str, object]]) -> int | None:
    """FR-007: match ONLY on head branch == RECAPTURE_BRANCH. An unrelated PR that also
    touches .github/ci-shard-timings.json on a different head (e.g. #5175/#5177) is never
    matched, because its head branch differs."""
    for pr in open_prs:
        if pr.get("headRefName") == RECAPTURE_BRANCH:
            number = pr.get("number")
            return number if isinstance(number, int) else None
    return None


def require_recapture_token() -> str:
    """FR-005/CL-002/C-004: truthy check ONLY. Never falls back to GH_TOKEN/GITHUB_TOKEN --
    that fallback would silently reintroduce the anti-recursion / CI-gate-bypass risk CL-002
    forbids. Fails loud (::error:: + non-zero exit) BEFORE any recapture, commit, push, or
    open-PR check."""
    value = os.environ.get(SECRET_NAME)
    if not value:  # catches both "unset" and "" (GitHub's injected-empty-string case)
        print(f"::error::{SECRET_NAME} is not set (or is empty) -- refusing to run", file=sys.stderr)
        raise SystemExit(1)
    return value


# --------------------------------------------------------------------------- #
# Edge -- gh/git/filesystem at the boundary only. Never covered by the pure   #
# unit tests; T014/T015 monkeypatch these functions directly.                #
# --------------------------------------------------------------------------- #


def _skip_summary_line(pr_number: int) -> str:
    return f"Recapture PR #{pr_number} is already open; skipping."


def _read_charter_length(path: Path = TIMINGS_PATH) -> int:
    """Read ``.github/ci-shard-timings.json``'s ``module_test_durations[MODULE]`` length.

    Called twice by :func:`main` -- once BEFORE the capture call and once AFTER it. The
    capture call overwrites *path* in place as a side effect, so calling this at the wrong
    point would make ``before_length == after_length`` unconditionally on every run.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    return len(payload["module_test_durations"][MODULE])


def _list_open_recapture_prs(repository: str, token: str) -> list[dict[str, object]]:
    """``gh pr list`` edge -- authenticated with *token* (never ``GITHUB_TOKEN``; C-004).

    Returns the parsed JSON array verbatim; :func:`find_open_recapture_pr` does the actual
    head-branch matching (both ``number`` and ``headRefName`` are requested -- the latter
    is what the match reads, the former is what a caller reports).
    """
    env = dict(os.environ)
    env["GH_TOKEN"] = token
    result = subprocess.run(
        [
            "gh",
            "pr",
            "list",
            "--repo",
            repository,
            "--head",
            RECAPTURE_BRANCH,
            "--base",
            "main",
            "--state",
            "open",
            "--json",
            "number,headRefName",
        ],
        capture_output=True,
        text=True,
        env=env,
        check=True,
    )
    parsed = json.loads(result.stdout)
    return parsed if isinstance(parsed, list) else []


def _write_job_summary(line: str) -> None:
    """Print *line* and append it to ``$GITHUB_STEP_SUMMARY`` when set."""
    print(line)
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with Path(summary_path).open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def _run_url() -> str:
    """Compose the workflow run URL from GitHub Actions' own default env vars (FR-010)."""
    server = os.environ.get("GITHUB_SERVER_URL", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    return f"{server}/{repository}/actions/runs/{run_id}"


def _push_and_open_pr(repository: str, token: str, before: int, after: int, run_url: str) -> None:
    """Commit, force-push to the fixed branch, and open the recapture PR.

    Only reachable from the no-open-PR / drift-found path (ruling 2) -- a plain
    ``git push --force`` here is acceptable ONLY because both open-PR checks (initial +
    TOCTOU) already confirmed no PR from RECAPTURE_BRANCH is open. NFR-003: *token* is
    only ever passed through the ``gh``/git-credential process environment, never printed,
    logged, or interpolated into a string.
    """
    env = dict(os.environ)
    env["GH_TOKEN"] = token
    subprocess.run(["git", "add", str(TIMINGS_PATH)], cwd=REPO_ROOT, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            f"user.name={COMMIT_AUTHOR_NAME}",
            "-c",
            f"user.email={COMMIT_AUTHOR_EMAIL}",
            "commit",
            "-m",
            COMMIT_MESSAGE,
        ],
        cwd=REPO_ROOT,
        check=True,
    )
    subprocess.run(
        ["git", "push", "--force", "origin", f"HEAD:refs/heads/{RECAPTURE_BRANCH}"],
        cwd=REPO_ROOT,
        env=env,
        check=True,
    )
    body = PR_BODY_TEMPLATE.format(before=before, after=after, run_url=run_url)
    subprocess.run(
        [
            "gh",
            "pr",
            "create",
            "--repo",
            repository,
            "--head",
            RECAPTURE_BRANCH,
            "--base",
            "main",
            "--title",
            COMMIT_MESSAGE,
            "--body",
            body,
        ],
        env=env,
        check=True,
    )


def main(argv: list[str] | None = None) -> int:
    """Recapture ``charter``'s shard timings when drifted (spec.md FR-005..FR-010).

    Sequence (order is load-bearing -- see the module docstring and plan.md's design):
    1. Fail loudly if ``CHARTER_SHARD_RECAPTURE_TOKEN`` is missing/empty -- before ANY
       other subprocess call.
    2. Read the committed ``charter`` length BEFORE the capture call can overwrite it.
    3. Skip entirely (no push/commit/PR-open) if a recapture PR is already open.
    4. Run the capture mechanism in-process; abort (no commit/push/PR-open) on a genuine
       mechanism crash -- never merely because the measured suite has failing tests.
    5. Read the freshly-captured ``charter`` length.
    6. Skip if there is no length drift (FR-006) -- no commit/push/PR-open.
    7. Re-check for an open PR immediately before the push (TOCTOU re-check, C-006) --
       skip if one has appeared during the capture window.
    8. Commit, force-push to the fixed branch, and open the recapture PR.

    This script takes no CLI arguments (FR-009 -- no ``--module`` flag, and no other flag
    either: every scope decision is a hardcoded module-level constant).
    """
    token = require_recapture_token()  # Step 1: first action, no exceptions before this.
    if argv:
        print(f"::error::this script accepts no CLI arguments (got {argv!r})", file=sys.stderr)
        return 2
    repository = os.environ.get("GITHUB_REPOSITORY", "")

    before_length = _read_charter_length()  # Step 2: BEFORE the capture call.

    open_prs = _list_open_recapture_prs(repository, token)  # Step 3: initial open-PR check.
    pr_number = find_open_recapture_pr(open_prs)
    if pr_number is not None:
        _write_job_summary(_skip_summary_line(pr_number))
        return 0

    outcome = run_capture_or_die(capture_shard_timings.main, ["--module", MODULE, "--write"])  # Step 4
    if not outcome.mechanism_ok:
        print(f"::error::recapture mechanism crashed: {outcome.error}", file=sys.stderr)
        return 1

    after_length = _read_charter_length()  # Step 5: AFTER the capture call.
    if not has_drift(before_length, after_length):  # Step 6
        return 0

    recheck_prs = _list_open_recapture_prs(repository, token)  # Step 7: TOCTOU re-check.
    recheck_pr_number = find_open_recapture_pr(recheck_prs)
    if recheck_pr_number is not None:
        _write_job_summary(_skip_summary_line(recheck_pr_number))
        return 0

    _push_and_open_pr(repository, token, before_length, after_length, _run_url())  # Step 8
    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main(sys.argv[1:]))
