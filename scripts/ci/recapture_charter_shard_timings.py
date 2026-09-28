"""Scheduled recapture of ``charter``'s shard-timings entry (mission
per-pr-shard-timings-recapture-friction-01M3H7V8, WP02; spec-kitty#5189).

The per-PR gate (WP01) demotes ``test_charter_is_not_allowlisted_and_agrees`` to a
warn-by-default check, which stops blocking individual PRs on ``charter``'s recorded
shard-timing count drifting away from live collection, but does nothing to *close* that
drift. This module is the automatic remediation: a scheduled workflow (WP03) invokes
:func:`main` in one of two phases (F1 -- see below), which re-runs
``scripts/ci/capture_shard_timings.py --module charter --write`` **in-process** (never as
a subprocess -- see the design note below) and, only when the freshly-captured entry's
length actually changed, commits it to a fixed branch and opens a PR.

Two-phase credential split (F1 / #5271 landing pass)
-----------------------------------------------------
``main`` takes exactly one positional argument, ``"capture"`` or ``"publish"``
(:data:`PHASE_CAPTURE` / :data:`PHASE_PUBLISH`), and the two phases run as **separate
workflow steps with separate step ``env:`` blocks** so the write-scoped
``CHARTER_SHARD_RECAPTURE_TOKEN`` PAT is never present in the process environment during
the ~18-minute in-process pytest capture or the preceding ``uv sync``:

* :func:`run_capture_phase` (the ``capture`` step) calls **no** ``require_recapture_token``
  and touches no ``gh``/``git`` network call. It refuses to run at all if the PAT is
  present in its environment (:func:`_refuse_if_token_present` -- a mis-wired workflow
  fails loud instead of silently exposing the PAT). It runs the capture mechanism, applies the
  F2 trustworthiness gate, computes the FR-006 drift decision, and records
  ``drift``/``before``/``after`` to ``$GITHUB_OUTPUT`` (:func:`_write_github_output`) for
  the next step to consume. The checkout step it depends on uses the workflow's default
  token with ``persist-credentials: false`` -- no push credential is persisted to
  ``.git/config`` at any point in this phase.
* :func:`run_publish_phase` (the ``publish`` step, gated by the workflow's own
  ``if: steps.capture.outputs.drift == 'true'``) is the ONLY phase that calls
  :func:`require_recapture_token` -- as the very first action, before any ``gh``/``git``
  call (mirrors the single-phase script's original ordering guarantee). It re-reads the
  ``before``/``after`` lengths from :data:`BEFORE_LENGTH_ENV_VAR`/:data:`AFTER_LENGTH_ENV_VAR`
  (the workflow threads the capture step's outputs into this step's ``env:``, since the
  committed file on disk by now holds ``after_length``, not ``before_length`` -- it cannot
  be re-derived from the working tree), no-ops if they are equal (defense-in-depth behind
  the workflow's ``if:``), and performs the single open-PR check
  (:func:`find_open_recapture_pr`) immediately before the push -- this single check IS the
  "re-check right before push" guarantee. There is deliberately no pre-capture check: it
  would need a token in the capture step, and an open recapture PR only costs one wasted
  (token-free) capture before the publish phase skips. Because ``git push`` can no longer
  rely on a persisted credential, :func:`_push_and_open_pr` hands every subprocess an
  explicit environment built from :func:`_scrubbed_env` (the PAT and any ambient
  ``GH_TOKEN``/``GITHUB_TOKEN`` removed) and adds the credential back ONLY where needed:
  ``git push`` gets a one-shot ``GIT_CONFIG_COUNT``/``GIT_CONFIG_KEY_0``/
  ``GIT_CONFIG_VALUE_0`` ``http.https://github.com/.extraheader`` entry
  (:func:`_push_auth_header`) -- never argv (world-readable via ``/proc`` and echoed by a
  ``CalledProcessError`` message), never a persisted git config write -- and ``gh`` gets
  ``GH_TOKEN``. ``git add``/``git commit`` get no credential at all.

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
sniffing. A mechanism that did NOT crash can still have produced an untrustworthy result
(a pytest collection error, for instance, returns cleanly with an empty capture) --
:func:`capture_is_trustworthy` (F2) is the separate, second gate that catches that case
before it can reach ``has_drift``/commit. This script's ``MODULE = "charter"`` scope lock
(FR-009) is also a precondition
for that in-process choice being safe: exactly one ``pytest.main()`` invocation happens
per process, so pytest's own repeated-invocation state (stale ``sys.modules`` entries,
assertion-rewrite hook accumulation) is never at risk.

Invoked as ``python scripts/ci/recapture_charter_shard_timings.py <capture|publish>`` --
exactly one positional argument, no flags. See :func:`main`.
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
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

#: F1: the two phases the workflow (`ci-charter-shard-recapture.yml`) invokes this script
#: with as its sole positional argument. `PHASE_CAPTURE` never sees the recapture token --
#: see the module docstring's "Two-phase credential split" section. `PHASE_PUBLISH` is the
#: only phase `require_recapture_token()` is called from.
PHASE_CAPTURE = "capture"
PHASE_PUBLISH = "publish"

#: F1: the env vars the workflow threads the capture phase's `$GITHUB_OUTPUT` decision
#: through to the publish phase's step `env:` (never re-derived from the working tree at
#: publish time, since by then the file on disk already holds `after_length`, not
#: `before_length`).
BEFORE_LENGTH_ENV_VAR = "RECAPTURE_BEFORE_LENGTH"
AFTER_LENGTH_ENV_VAR = "RECAPTURE_AFTER_LENGTH"

#: F1: every ambient token variable stripped from each gh/git subprocess environment by
#: :func:`_scrubbed_env` before the one credential that subprocess needs is added back.
_TOKEN_ENV_VARS = (SECRET_NAME, "GH_TOKEN", "GITHUB_TOKEN")

#: F1: the git config key the push credential is scoped to (matches the ``origin`` URL
#: actions/checkout writes: ``https://github.com/<owner>/<repo>``).
_PUSH_EXTRAHEADER_KEY = "http.https://github.com/.extraheader"

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


def capture_is_trustworthy(pytest_exit_code: int | None, after_length: int) -> bool:
    """F2/FR-008 amendment: gate a *mechanism-ok* capture on the pytest exit code AND a
    non-empty captured module before it is eligible to commit.

    ``run_capture_or_die`` already tells a genuine mechanism crash (exception/SystemExit)
    from a returned exit code apart -- but a returned exit code is not, by itself,
    trustworthy: pytest's collection-error / interrupted / usage-error / no-tests-collected
    exit codes (2, 3, 4, 5, ...) mean the measured suite never actually ran, so the
    captured ``charter`` entry is empty or garbage. Treating that as ``mechanism_ok`` and
    letting it through to ``has_drift``/commit would silently replace a real timings table
    with ``[]`` and open a PR for it -- a fail-open regression, not a legitimate recapture.
    Only exit code 0 (clean) or 1 (ordinary test failures -- FR-008's *not*-abort case)
    paired with ``after_length > 0`` counts as trustworthy.
    """
    return pytest_exit_code in (0, 1) and after_length > 0


def has_drift(before_length: int, after_length: int) -> bool:
    """FR-006: length-only drift. Equal lengths => no drift, even if --write rewrote
    run_id/captured_at/duration-value noise (never compare raw file diffs)."""
    return before_length != after_length


def find_open_recapture_pr(open_prs: Sequence[Mapping[str, object]]) -> int | None:
    """FR-007: match ONLY on head branch == RECAPTURE_BRANCH. An unrelated PR that also
    touches .github/ci-shard-timings.json on a different head (e.g. #5175/#5177) is never
    matched, because its head branch differs.

    pr-contract-001: a malformed ``number`` field on the matching PR fails loudly -- never
    silently coerced to ``None``, which downstream is indistinguishable from a genuine
    "no open PR" answer before the pre-push open-PR decision.
    """
    for pr in open_prs:
        if pr.get("headRefName") == RECAPTURE_BRANCH:
            number = pr.get("number")
            if not isinstance(number, int):
                print(
                    f"::error::unexpected `gh pr list` JSON shape: PR number is not an int: {number!r}",
                    file=sys.stderr,
                )
                raise SystemExit(1)
            return number
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


def _run_subprocess_or_die(
    cmd: list[str],
    *,
    step: str,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    capture_output: bool = False,
    text: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Run *cmd*, surfacing a genuine gh/git failure via the script's own ``::error::``
    convention (pr-contract-002) instead of a raw, unhandled ``CalledProcessError``
    traceback. *step* names which command failed (e.g. ``"gh pr list"``) -- never the
    token, which is passed only via *env* and never logged.
    """
    try:
        return subprocess.run(cmd, cwd=cwd, env=env, capture_output=capture_output, text=text, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"::error::{step} failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def _list_open_recapture_prs(repository: str, token: str) -> list[dict[str, object]]:
    """``gh pr list`` edge -- authenticated with *token* (never ``GITHUB_TOKEN``; C-004).

    Returns the parsed JSON array verbatim; :func:`find_open_recapture_pr` does the actual
    head-branch matching (both ``number`` and ``headRefName`` are requested -- the latter
    is what the match reads, the former is what a caller reports).
    """
    env = dict(os.environ)
    env["GH_TOKEN"] = token
    result = _run_subprocess_or_die(
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
        step="gh pr list",
        env=env,
        capture_output=True,
        text=True,
    )
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        # F8: empty stdout, a proxy error page, or a gh warning is not "no open PR" --
        # fail loud via the ::error:: convention, never a raw JSONDecodeError traceback.
        print(f"::error::`gh pr list` returned non-JSON output: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    if not isinstance(parsed, list):
        # pr-contract-001: an unexpected shape (e.g. an object, or a schema change) fails
        # loudly -- never silently coerced to [], which downstream is indistinguishable
        # from a genuine "no open PR" answer before the pre-push open-PR decision.
        print(
            f"::error::unexpected `gh pr list` JSON shape: expected a list, got {type(parsed).__name__}",
            file=sys.stderr,
        )
        raise SystemExit(1)
    return parsed


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


def _push_auth_header(token: str) -> str:
    """F1: the ``http.extraheader`` value git needs to push over HTTPS with no persisted
    credential (the checkout step uses ``persist-credentials: false``). Handed ONLY to the
    single ``git push`` subprocess, through its own environment (:func:`_push_env`); never
    argv, never written to any git config file. Same Basic-auth shape actions/checkout
    itself persists (``x-access-token:<token>``, base64-encoded).
    """
    encoded = base64.b64encode(f"x-access-token:{token}".encode("ascii")).decode("ascii")
    return f"AUTHORIZATION: basic {encoded}"


def _scrubbed_env() -> dict[str, str]:
    """F1: a copy of ``os.environ`` with every token variable (:data:`_TOKEN_ENV_VARS`)
    removed -- the base environment for every gh/git subprocess, so none inherits the PAT
    (or an ambient token) implicitly."""
    return {key: value for key, value in os.environ.items() if key not in _TOKEN_ENV_VARS}


def _push_env(token: str) -> dict[str, str]:
    """F1: the ``git push`` subprocess environment -- :func:`_scrubbed_env` plus a one-shot,
    env-scoped git config entry carrying the push credential (git >= 2.31
    ``GIT_CONFIG_COUNT`` protocol). Appended after any ambient ``GIT_CONFIG_*`` entries
    rather than overwriting index 0, so pre-existing env-scoped config is preserved."""
    env = _scrubbed_env()
    raw_count = env.get("GIT_CONFIG_COUNT", "").strip()
    index = int(raw_count) if raw_count.isdigit() else 0
    env[f"GIT_CONFIG_KEY_{index}"] = _PUSH_EXTRAHEADER_KEY
    env[f"GIT_CONFIG_VALUE_{index}"] = _push_auth_header(token)
    env["GIT_CONFIG_COUNT"] = str(index + 1)
    return env


def _gh_env(token: str) -> dict[str, str]:
    """F1: the ``gh`` subprocess environment -- :func:`_scrubbed_env` plus ``GH_TOKEN``."""
    env = _scrubbed_env()
    env["GH_TOKEN"] = token
    return env


def _push_and_open_pr(repository: str, token: str, before: int, after: int, run_url: str) -> None:
    """Commit, force-push to the fixed branch, and open the recapture PR.

    Only reachable from the no-open-PR / drift-found path -- a plain ``git push --force``
    here is acceptable ONLY because :func:`run_publish_phase` already confirmed no PR from
    RECAPTURE_BRANCH is open immediately before calling this. NFR-003/F1: *token* is never
    printed, logged, or placed in any argv; it reaches ``git push`` only through that
    subprocess's own ``GIT_CONFIG_*`` environment (:func:`_push_env`) and ``gh`` only
    through its own ``GH_TOKEN`` (:func:`_gh_env`). ``git add``/``git commit`` run with
    :func:`_scrubbed_env` -- no credential at all.
    """
    no_credential_env = _scrubbed_env()
    _run_subprocess_or_die(["git", "add", str(TIMINGS_PATH)], step="git add", cwd=REPO_ROOT, env=no_credential_env)
    _run_subprocess_or_die(
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
        step="git commit",
        cwd=REPO_ROOT,
        env=no_credential_env,
    )
    _run_subprocess_or_die(
        ["git", "push", "--force", "origin", f"HEAD:refs/heads/{RECAPTURE_BRANCH}"],
        step="git push",
        cwd=REPO_ROOT,
        env=_push_env(token),
    )
    body = PR_BODY_TEMPLATE.format(before=before, after=after, run_url=run_url)
    _run_subprocess_or_die(
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
        step="gh pr create",
        env=_gh_env(token),
    )


def _write_github_output(**fields: object) -> None:
    """F1: record *fields* (``drift``/``before``/``after``) to ``$GITHUB_OUTPUT`` for the
    workflow's publish step to read as ``steps.capture.outputs.<name>``. Falls back to
    stdout when unset (local/test runs) -- never raises for a missing ``$GITHUB_OUTPUT``,
    since the capture phase's own success must not depend on running inside Actions.
    """
    lines = [f"{name}={value}" for name, value in fields.items()]
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with Path(output_path).open("a", encoding="utf-8") as handle:
            for line in lines:
                handle.write(line + "\n")
    for line in lines:
        print(line)


def _read_int_env(name: str) -> int:
    """Read an integer the workflow threaded in via step ``env:`` (F1). Fails loud --
    never defaults to 0, which downstream (:func:`has_drift`) is indistinguishable from a
    genuine zero-length capture."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        print(f"::error::{name} is not set (or is empty) -- the publish phase cannot run without it", file=sys.stderr)
        raise SystemExit(1)
    try:
        return int(raw)
    except ValueError:
        print(f"::error::{name}={raw!r} is not an integer", file=sys.stderr)
        raise SystemExit(1) from None


def _refuse_if_token_present() -> bool:
    """F1: True (after an ``::error::``) when the PAT is in this process's environment.
    The capture phase must never run test code with the write credential reachable; a
    workflow that wires the secret into the capture step is a defect to fail loud on, not
    to tolerate."""
    if SECRET_NAME in os.environ:
        print(
            f"::error::{SECRET_NAME} is present in the capture phase's environment -- refusing to "
            "run the capture with the write credential exposed (wire it into the publish step only)",
            file=sys.stderr,
        )
        return True
    return False


def run_capture_phase() -> int:
    """F1's ``capture`` phase: no recapture token, no ``gh``/``git`` network call.

    Runs the capture mechanism in-process, applies the F2 trustworthiness gate, computes
    the FR-006 drift decision, and records it to ``$GITHUB_OUTPUT`` for the workflow's
    publish step. See the module docstring's "Two-phase credential split" section for why
    this phase must never see ``CHARTER_SHARD_RECAPTURE_TOKEN``.
    """
    if _refuse_if_token_present():
        return 1
    before_length = _read_charter_length()  # BEFORE the capture call can overwrite it.

    outcome = run_capture_or_die(capture_shard_timings.main, ["--module", MODULE, "--write"])
    if not outcome.mechanism_ok:
        print(f"::error::recapture mechanism crashed: {outcome.error}", file=sys.stderr)
        return 1

    after_length = _read_charter_length()  # AFTER the capture call.
    if not capture_is_trustworthy(outcome.pytest_exit_code, after_length):  # F2
        print(
            "::error::recapture aborted: pytest exit code "
            f"{outcome.pytest_exit_code!r} with captured length {after_length} does not "
            "look like a real run (collection error, interrupted, or no tests collected) "
            "-- refusing to commit an untrustworthy `charter` entry",
            file=sys.stderr,
        )
        return 1

    drift = has_drift(before_length, after_length)
    _write_github_output(drift=str(drift).lower(), before=before_length, after=after_length)
    return 0


def run_publish_phase() -> int:
    """F1's ``publish`` phase: the ONLY phase that reads ``CHARTER_SHARD_RECAPTURE_TOKEN``.

    The workflow gates this step on ``steps.capture.outputs.drift == 'true'``, so by the
    time this runs, a drifted, trustworthy capture is already known to exist. This phase
    still does its own open-PR check immediately before the push -- see the module
    docstring for why a single check here is sufficient (no separate pre-capture check to
    duplicate, now that the token-free capture phase no longer needs one to decide whether
    to run).
    """
    token = require_recapture_token()  # First action, no exceptions before this.
    before_length = _read_int_env(BEFORE_LENGTH_ENV_VAR)
    after_length = _read_int_env(AFTER_LENGTH_ENV_VAR)
    if not has_drift(before_length, after_length):  # defense-in-depth behind the workflow `if:`
        return 0
    repository = os.environ.get("GITHUB_REPOSITORY", "")

    open_prs = _list_open_recapture_prs(repository, token)  # The single, pre-push check.
    pr_number = find_open_recapture_pr(open_prs)
    if pr_number is not None:
        _write_job_summary(_skip_summary_line(pr_number))
        return 0

    _push_and_open_pr(repository, token, before_length, after_length, _run_url())
    return 0


def main(argv: list[str] | None = None) -> int:
    """Dispatch to :func:`run_capture_phase` or :func:`run_publish_phase` (F1).

    Exactly one positional argument is required: ``"capture"`` or ``"publish"``
    (:data:`PHASE_CAPTURE` / :data:`PHASE_PUBLISH`). Any other argv -- missing, extra, or
    an unrecognized phase name -- fails loud with exit code 2 before either phase's own
    work (including :func:`require_recapture_token`) runs.
    """
    args = sys.argv[1:] if argv is None else argv
    if args not in ([PHASE_CAPTURE], [PHASE_PUBLISH]):
        print(
            f"::error::this script requires exactly one positional argument, {PHASE_CAPTURE!r} or {PHASE_PUBLISH!r} (got {args!r})",
            file=sys.stderr,
        )
        return 2
    if args == [PHASE_CAPTURE]:
        return run_capture_phase()
    return run_publish_phase()


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main(sys.argv[1:]))
