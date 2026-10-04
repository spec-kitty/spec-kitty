"""Scheduled recapture of drifted shard-timings entries, for every registry module
(mission shared-collection-and-shard-recapture-01M42V58, WP04; originally the
charter-only recapture of mission per-pr-shard-timings-recapture-friction-01M3H7V8,
spec-kitty#5189).

``.github/ci-shard-timings.json`` records, per registry module, how many tests the
shard collects and how long each took. A module's recorded count drifts away from
live collection whenever tests are added or removed, and the per-PR gate only warns
about it. This script is the automatic remediation: a scheduled workflow invokes
:func:`main` in up to three phases (``detect`` / ``capture`` / ``publish``) and the
result is a pull request that refreshes the stale entries.

What a ``capture`` run does
---------------------------
1. **Count-only pass.** Each candidate module's test count is collected without running a
   test (``pytest --collect-only``, over the directories and marker expression the
   canonical producer uses, so "collected" means the same thing here and there). Each pass is
   capped at :data:`COUNT_PASS_TIMEOUT_SECONDS`, and none starts once the time budget is
   spent: the modules not counted are reported as ``deferred``, never as clean.
2. A module is **drifted** when that count differs from the committed ``module_test_count``
   or its provenance record is missing or not valid (:func:`is_valid_capture`,
   :func:`drifted_modules`).
3. Each drifted module is captured by the canonical producer
   (``python -m scripts.ci.capture_shard_timings --module <m> --write``) in **its own
   subprocess**, oldest provenance first, until the time budget is spent. Modules left
   over are reported as ``deferred``; the next run recomputes drift, so no state is kept.
4. A capture is **valid** when its provenance record carries the run id this script passed
   in, exit status 0 or 1, and at least one measured test. An invalid capture (a crash,
   a collection error, a timeout) restores the committed file byte for byte and the module
   is reported as ``failed``; the remaining modules are still processed.
5. The machine-readable result (``drifted`` / ``captured`` / ``failed`` / ``deferred``)
   and a job-summary table are written. Exit status is 1 when any module failed.

Shard counts are not touched here: the existing skew check reports a count that no
longer fits (``tests/architectural/test_module_shard_registry.py``).

Open proposal
-------------
The proposal branch (:data:`RECAPTURE_BRANCH`) has at most one open pull request. When
one is open, the ``capture`` phase starts from that branch's timings file for the modules
the proposal already refreshed (:func:`overlay_proposal`), so a nightly run continues the
work instead of repeating it, and the ``publish`` phase adds an ordinary follow-up commit
with a plain (never forced) push. The force push survives only on the path where no pull
request is open on the branch.

Credential split (F1 / #5271)
-----------------------------
The write-scoped ``CHARTER_SHARD_RECAPTURE_TOKEN`` is wired into the ``detect`` and
``publish`` steps only. The ``capture`` phase runs test code for a long time, refuses to
run when the token is in its environment (:func:`_refuse_if_token_present`) and starts
every subprocess from :func:`_scrubbed_env`. ``git push`` receives the credential through a
one-shot ``GIT_CONFIG_*`` ``http.extraheader`` entry (:func:`_push_env`), ``gh`` through
``GH_TOKEN`` (:func:`_gh_env`); never argv, never a persisted git config.

A rejected push (HTTP 403, ``Permission ... denied``) is reported in words the operator
can act on (:func:`push_failure_message`): the token cannot write to the repository.
Code cannot fix that; the message says which secret to fix.

Invoked as ``python -m scripts.ci.recapture_shard_timings <detect|capture|publish>
[--module NAME]... [--budget-seconds N] [--write]``. See :func:`main`.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Actions runs this trusted-checkout script before installing the package, and
# ``scripts.ci`` resolves as a namespace package only with the repo root on the
# path. Resolve from the script, never the caller's cwd.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ci import capture_shard_timings  # noqa: E402  (import after the path guard above)

#: The fixed recapture head branch. GitHub permits only one open PR per head branch into
#: a given base, so a duplicate recapture PR from this workflow is structurally impossible.
RECAPTURE_BRANCH = "ci/recapture-shard-timings"

#: The dedicated PAT/App-token secret NAME (never a value). Never ``GITHUB_TOKEN``.
SECRET_NAME = "CHARTER_SHARD_RECAPTURE_TOKEN"  # noqa: S105  # env-var name, not a secret value

#: The phases the workflow invokes this script with, as its one positional argument.
PHASE_DETECT = "detect"
PHASE_CAPTURE = "capture"
PHASE_PUBLISH = "publish"
PHASES = (PHASE_DETECT, PHASE_CAPTURE, PHASE_PUBLISH)

#: ``detect`` -> ``capture``: whether a recapture proposal is open (``true`` / ``false``).
PROPOSAL_OPEN_ENV_VAR = "RECAPTURE_PROPOSAL_OPEN"
#: ``capture`` -> ``publish``: the machine-readable :class:`RecaptureResult` as one JSON line.
RESULT_ENV_VAR = "RECAPTURE_RESULT"

#: A single producer subprocess may run this long. The longest module (``charter``) took
#: roughly 25 minutes on a runner in the runs that hit the old 30-minute job cap, so 35
#: minutes leaves 40% headroom while still bounding a hung capture.
DEFAULT_CAPTURE_TIMEOUT_SECONDS = 35 * 60

#: The count-only pass of one module may run this long. It collects without running a test
#: (seconds in practice); the bound only stops a hung collection from consuming the job
#: limit (NFR-007). A pass that exceeds it is a failed module, never a clean one.
COUNT_PASS_TIMEOUT_SECONDS = 5 * 60

#: Every ambient token variable stripped from each subprocess environment by
#: :func:`_scrubbed_env` before the one credential that subprocess needs is added back.
_TOKEN_ENV_VARS = (SECRET_NAME, "GH_TOKEN", "GITHUB_TOKEN")

#: The git config key the push credential is scoped to (matches the ``origin`` URL
#: actions/checkout writes: ``https://github.com/<owner>/<repo>``).
_PUSH_EXTRAHEADER_KEY = "http.https://github.com/.extraheader"

#: Reuse the canonical paths -- single source of truth, never a second literal.
TIMINGS_PATH = capture_shard_timings.TIMINGS_PATH
REGISTRY_PATH = capture_shard_timings.REGISTRY_PATH
_TIMINGS_GIT_PATH = ".github/ci-shard-timings.json"

#: The producer's per-module tables: durations, count, summed seconds, provenance.
_DURATIONS_KEY = "module_test_durations"
_COUNT_KEY = "module_test_count"
_SECONDS_KEY = "module_duration_seconds"
_PROVENANCE_KEY = "module_capture_provenance"
_MODULE_TABLE_KEYS = (_DURATIONS_KEY, _COUNT_KEY, _SECONDS_KEY, _PROVENANCE_KEY)

#: Pytest exit statuses that mean "the suite ran" (0 clean, 1 some tests failed).
_VALID_EXIT_CODES = (0, 1)
_NODE_ID_SEPARATOR = "::"

#: Fixed, non-human bot identity for the recapture commit -- never the PAT owner's own.
COMMIT_AUTHOR_NAME = "spec-kitty-ci-bot"
COMMIT_AUTHOR_EMAIL = "ci-bot@users.noreply.github.com"

#: Fixed commit subject / PR title.
COMMIT_MESSAGE = "chore(ci): automated shard-timings recapture"

#: PR-body template; the ``{captured}``/``{failed}``/``{deferred}`` fields are module lists.
PR_BODY_TEMPLATE = (
    "Automated recapture opened by the scheduled `ci-shard-recapture.yml` workflow "
    "(`scripts/ci/recapture_shard_timings.py`). Refreshes the drifted modules' entries in "
    "`.github/ci-shard-timings.json`.\n\n"
    "- Captured: {captured}\n"
    "- Failed (committed data left unchanged): {failed}\n"
    "- Deferred (time budget spent, retried next run): {deferred}\n\n"
    "Workflow run: `{run_url}`. See spec-kitty#5189."
)

_NONE_LABEL = "none"


# --------------------------------------------------------------------------- #
# Pure decisions -- no filesystem, no subprocess.                             #
# --------------------------------------------------------------------------- #


def is_valid_capture(provenance: Mapping[str, object] | None) -> bool:
    """The single authority for "this provenance record is a trustworthy capture".

    Valid when the capture run's ``exit_code`` is 0 (clean) or 1 (some measured tests
    failed -- the durations are still complete) AND at least one test was measured
    (``unique_tests_measured`` above zero). Any other pytest exit status (2 interrupted /
    collection error, 3 internal error, 4 usage error, 5 nothing collected) means the
    suite never ran, so the recorded entry is empty or garbage; committing it would
    silently replace a real timings table. The recapture script and the provenance
    completeness check share this predicate (research D-11).
    """
    if not isinstance(provenance, Mapping):
        return False
    exit_code = provenance.get("exit_code")
    measured = provenance.get("unique_tests_measured")
    if isinstance(exit_code, bool) or isinstance(measured, bool):
        return False
    return isinstance(exit_code, int) and isinstance(measured, int) and exit_code in _VALID_EXIT_CODES and measured > 0


def capture_is_trustworthy(pytest_exit_code: int | None, after_length: int) -> bool:
    """Gate a capture on the pytest exit code AND a non-empty captured module.

    A thin view over :func:`is_valid_capture` for callers holding the two raw values.
    """
    return is_valid_capture({"exit_code": pytest_exit_code, "unique_tests_measured": after_length})


def _provenance_of(timings: Mapping[str, Any], module: str) -> Mapping[str, object] | None:
    records = timings.get(_PROVENANCE_KEY)
    record = records.get(module) if isinstance(records, Mapping) else None
    return record if isinstance(record, Mapping) else None


def _committed_count(timings: Mapping[str, Any], module: str) -> int | None:
    counts = timings.get(_COUNT_KEY)
    count = counts.get(module) if isinstance(counts, Mapping) else None
    if isinstance(count, int) and not isinstance(count, bool):
        return count
    durations = timings.get(_DURATIONS_KEY)
    listed = durations.get(module) if isinstance(durations, Mapping) else None
    return len(listed) if isinstance(listed, list) else None


def has_valid_provenance(timings: Mapping[str, Any], module: str) -> bool:
    """True when *module*'s committed provenance record is a valid capture."""
    return is_valid_capture(_provenance_of(timings, module))


def drifted_modules(modules: Sequence[str], timings: Mapping[str, Any], counts: Mapping[str, int]) -> list[str]:
    """The modules whose committed entry no longer matches reality.

    A module is drifted when its provenance is missing or not valid, or when its collected
    count (*counts*) differs from the committed ``module_test_count``. A module with a valid
    provenance and no entry in *counts* cannot be judged and is left out; the caller reports
    the failed count pass separately instead of treating the module as clean.
    """
    drifted: list[str] = []
    for module in modules:
        if not has_valid_provenance(timings, module):
            drifted.append(module)
            continue
        collected = counts.get(module)
        if collected is not None and collected != _committed_count(timings, module):
            drifted.append(module)
    return drifted


def order_oldest_first(modules: Sequence[str], timings: Mapping[str, Any]) -> list[str]:
    """Longest-untouched first: missing provenance first of all, then oldest ``captured_at``.

    ``captured_at`` is an ISO-8601 UTC timestamp, which sorts correctly as text. Ties break
    by module name so the order is deterministic.
    """

    def key(module: str) -> tuple[str, str]:
        record = _provenance_of(timings, module)
        captured_at = record.get("captured_at") if record else None
        return (captured_at if isinstance(captured_at, str) else "", module)

    return sorted(modules, key=key)


def overlay_proposal(baseline: Mapping[str, Any], proposal: Mapping[str, Any]) -> dict[str, Any]:
    """*baseline* with the modules the open proposal already refreshed taken from *proposal*.

    A module counts as refreshed by the proposal when its provenance record differs from the
    baseline's. Only those modules' four tables move; every other key (including modules the
    primary branch changed after the proposal was cut) stays as the baseline has it, so the
    follow-up commit never reverts unrelated changes.
    """
    merged: dict[str, Any] = dict(baseline)
    proposal_records = proposal.get(_PROVENANCE_KEY)
    if not isinstance(proposal_records, Mapping):
        return merged
    for module, record in proposal_records.items():
        if _provenance_of(baseline, module) == record:
            continue
        for key in _MODULE_TABLE_KEYS:
            source = proposal.get(key)
            if isinstance(source, Mapping) and module in source:
                merged[key] = {**(merged.get(key) or {}), module: source[module]}
    return merged


def _format_modules(modules: Sequence[str]) -> str:
    return ", ".join(f"`{module}`" for module in modules) if modules else _NONE_LABEL


@dataclass(frozen=True)
class RecaptureResult:
    """The outcome of one ``capture`` run, threaded to ``publish`` as one JSON line."""

    drifted: tuple[str, ...] = ()
    captured: tuple[str, ...] = ()
    failed: tuple[str, ...] = ()
    deferred: tuple[str, ...] = ()
    reasons: Mapping[str, str] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(
            {
                "drifted": list(self.drifted),
                "captured": list(self.captured),
                "failed": list(self.failed),
                "deferred": list(self.deferred),
                "reasons": dict(self.reasons),
            },
            sort_keys=True,
        )

    @classmethod
    def from_json(cls, raw: str) -> RecaptureResult:
        payload = json.loads(raw)
        return cls(
            drifted=tuple(payload["drifted"]),
            captured=tuple(payload["captured"]),
            failed=tuple(payload["failed"]),
            deferred=tuple(payload["deferred"]),
            reasons=dict(payload.get("reasons", {})),
        )

    @property
    def publishable(self) -> bool:
        """True when at least one module holds a fresh, valid capture to publish."""
        return bool(self.captured)

    def summary_table(self) -> str:
        """A markdown job-summary table: one row per drifted module, then the failures' reasons."""
        lines = ["| module | outcome |", "| --- | --- |"]
        lines += [f"| `{module}` | captured |" for module in self.captured]
        lines += [f"| `{module}` | failed: {self.reasons.get(module, 'invalid capture')} |" for module in self.failed]
        lines += [f"| `{module}` | deferred (time budget spent) |" for module in self.deferred]
        if len(lines) == 2:
            lines.append("| _none_ | nothing drifted |")
        return "\n".join(lines)

    def proposal_body(self, run_url: str) -> str:
        return PR_BODY_TEMPLATE.format(
            captured=_format_modules(self.captured),
            failed=_format_modules(self.failed),
            deferred=_format_modules(self.deferred),
            run_url=run_url,
        )

    def commit_message(self) -> str:
        return f"{COMMIT_MESSAGE}\n\nCaptured: {_format_modules(self.captured)}\nFailed: {_format_modules(self.failed)}\nDeferred: {_format_modules(self.deferred)}"


def find_open_recapture_pr(open_prs: Sequence[Mapping[str, object]]) -> int | None:
    """Match ONLY on head branch == RECAPTURE_BRANCH. An unrelated PR that also touches
    .github/ci-shard-timings.json on a different head (e.g. #5175/#5177) is never matched.

    A malformed ``number`` field on the matching PR fails loudly -- never silently coerced to
    ``None``, which is indistinguishable from a genuine "no open PR" answer.
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
    """Truthy check ONLY. Never falls back to GH_TOKEN/GITHUB_TOKEN -- that fallback would
    silently reintroduce the anti-recursion / CI-gate-bypass risk. Fails loud
    (::error:: + non-zero exit) BEFORE any gh/git call."""
    value = os.environ.get(SECRET_NAME)
    if not value:  # catches both "unset" and "" (GitHub's injected-empty-string case)
        print(f"::error::{SECRET_NAME} is not set (or is empty) -- refusing to run", file=sys.stderr)
        raise SystemExit(1)
    return value


_PERMISSION_DENIED = re.compile(r"\b403\b|Permission to .+ denied|Permission denied", re.IGNORECASE)
_NOT_FAST_FORWARD = re.compile(r"non-fast-forward|fetch first|\[rejected\]", re.IGNORECASE)


def push_failure_message(stderr: str, *, forced: bool) -> str:
    """The operator-facing text for a rejected ``git push``, from git's own stderr.

    HTTP 403 / ``Permission ... denied`` means the token in :data:`SECRET_NAME` cannot write
    to the repository (#5536); a refused fast-forward means the proposal branch moved while
    this run was working (a follow-up is never forced). Anything else keeps git's stderr.
    """
    if _PERMISSION_DENIED.search(stderr):
        return (
            f"git push was rejected with a permission error: the token in the repository secret {SECRET_NAME} "
            "lacks write access to repository contents. The capture succeeded; nothing was published. "
            f"Fix the secret (a token with `contents: write` on this repository), then re-run this workflow. git said: {stderr.strip()}"
        )
    if not forced and _NOT_FAST_FORWARD.search(stderr):
        return (
            f"git push was refused because {RECAPTURE_BRANCH} moved while this run was working; the follow-up commit "
            f"was NOT forced. The next scheduled run starts from the new base. git said: {stderr.strip()}"
        )
    return f"git push failed: {stderr.strip()}"


# --------------------------------------------------------------------------- #
# Edge -- gh/git/pytest/filesystem at the boundary. Tests replace these by    #
# monkeypatching ``subprocess.run`` and the module's own path constants.      #
# --------------------------------------------------------------------------- #


def _now_seconds() -> float:
    """Seconds since the epoch through the repository's one clock door (``kernel.clock``)."""
    from kernel.clock import now_epoch  # path set by the producer import above

    return now_epoch()


def _scrubbed_env() -> dict[str, str]:
    """A copy of ``os.environ`` with every token variable (:data:`_TOKEN_ENV_VARS`) removed --
    the base environment for every subprocess, so none inherits the PAT implicitly."""
    return {key: value for key, value in os.environ.items() if key not in _TOKEN_ENV_VARS}


def _push_auth_header(token: str) -> str:
    """The ``http.extraheader`` value git needs to talk to the remote with no persisted
    credential (the checkout step uses ``persist-credentials: false``). Handed ONLY to the
    git subprocesses that talk to the remote, through their own environment
    (:func:`_push_env`); never argv, never a git config file."""
    encoded = base64.b64encode(f"x-access-token:{token}".encode("ascii")).decode("ascii")
    return f"AUTHORIZATION: basic {encoded}"


def _push_env(token: str) -> dict[str, str]:
    """The environment for a git subprocess that talks to the remote: :func:`_scrubbed_env`
    plus a one-shot, env-scoped git config entry carrying the credential (git >= 2.31
    ``GIT_CONFIG_COUNT`` protocol), appended after any ambient entries."""
    env = _scrubbed_env()
    raw_count = env.get("GIT_CONFIG_COUNT", "").strip()
    index = int(raw_count) if raw_count.isdigit() else 0
    env[f"GIT_CONFIG_KEY_{index}"] = _PUSH_EXTRAHEADER_KEY
    env[f"GIT_CONFIG_VALUE_{index}"] = _push_auth_header(token)
    env["GIT_CONFIG_COUNT"] = str(index + 1)
    return env


def _gh_env(token: str) -> dict[str, str]:
    """The ``gh`` subprocess environment -- :func:`_scrubbed_env` plus ``GH_TOKEN``."""
    env = _scrubbed_env()
    env["GH_TOKEN"] = token
    return env


def _redact(text: str, token: str) -> str:
    """*text* with the token (raw and header-encoded) masked, for anything printed to the log."""
    header = _push_auth_header(token)
    encoded = header.removeprefix("AUTHORIZATION: basic ")
    return text.replace(token, "***").replace(encoded, "***")


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
    convention instead of a raw ``CalledProcessError`` traceback. *step* names which command
    failed (e.g. ``"gh pr list"``) -- never the token, which is passed only via *env*."""
    try:
        return subprocess.run(cmd, cwd=cwd, env=env, capture_output=capture_output, text=text, check=True)
    except subprocess.CalledProcessError as exc:
        print(f"::error::{step} failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


def _list_open_recapture_prs(repository: str, token: str) -> list[dict[str, object]]:
    """``gh pr list`` edge -- authenticated with *token* (never ``GITHUB_TOKEN``).

    Returns the parsed JSON array verbatim; :func:`find_open_recapture_pr` does the actual
    head-branch matching.
    """
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
        env=_gh_env(token),
        capture_output=True,
        text=True,
    )
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        # Empty stdout, a proxy error page, or a gh warning is not "no open PR".
        print(f"::error::`gh pr list` returned non-JSON output: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    if not isinstance(parsed, list):
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
    """Compose the workflow run URL from GitHub Actions' own default env vars."""
    server = os.environ.get("GITHUB_SERVER_URL", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    return f"{server}/{repository}/actions/runs/{run_id}"


def _write_github_output(**fields: object) -> None:
    """Record *fields* to ``$GITHUB_OUTPUT`` for the workflow's later steps to read as
    ``steps.<id>.outputs.<name>``. Falls back to stdout when unset (local/test runs)."""
    lines = [f"{name}={value}" for name, value in fields.items()]
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with Path(output_path).open("a", encoding="utf-8") as handle:
            for line in lines:
                handle.write(line + "\n")
    for line in lines:
        print(line)


def _refuse_if_token_present() -> bool:
    """True (after an ``::error::``) when the PAT is in this process's environment.
    The capture phase must never run test code with the write credential reachable; a
    workflow that wires the secret into the capture step is a defect to fail loud on."""
    if SECRET_NAME in os.environ:
        print(
            f"::error::{SECRET_NAME} is present in the capture phase's environment -- refusing to "
            "run the capture with the write credential exposed (wire it into the detect and publish steps only)",
            file=sys.stderr,
        )
        return True
    return False


def _read_timings(path: Path | None = None) -> dict[str, Any]:
    payload = json.loads((path or TIMINGS_PATH).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        print(f"::error::{(path or TIMINGS_PATH).name} did not parse to a mapping", file=sys.stderr)
        raise SystemExit(1)
    return payload


def _write_timings(payload: Mapping[str, Any], path: Path | None = None) -> None:
    """Write *payload* exactly the way the producer does (indent 2, trailing newline)."""
    (path or TIMINGS_PATH).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _load_registry() -> dict[str, Any]:
    import yaml  # local import: the pure decisions need no YAML

    payload = yaml.safe_load(REGISTRY_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        print(f"::error::{REGISTRY_PATH.name} did not parse to a mapping", file=sys.stderr)
        raise SystemExit(1)
    return payload


def _registry_modules(registry: Mapping[str, Any]) -> list[str]:
    return [str(row["module"]) for row in registry.get("modules", []) if row.get("module")]


def _collect_count(module: str, registry: dict[str, Any]) -> int:
    """The number of tests *module*'s shard collects, without running any of them.

    Same test directories (the producer's resolver), marker expression and ``"::"`` node-id
    filter the shard and the producer use. Raises ``RuntimeError`` (naming why) when the
    pass fails, times out (:data:`COUNT_PASS_TIMEOUT_SECONDS`) or collects nothing -- the caller reports the module as failed rather than
    treating an unknown count as clean.
    """
    try:
        test_dirs = capture_shard_timings.resolve_test_dirs(registry, module)
    except (KeyError, FileNotFoundError) as exc:
        raise RuntimeError(f"cannot resolve test directories: {exc}") from exc
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", *test_dirs, "-m", capture_shard_timings.SELECTION_MARKER_EXPR, "--collect-only", "-q"],
            cwd=REPO_ROOT,
            env=_scrubbed_env(),
            capture_output=True,
            text=True,
            check=False,
            timeout=COUNT_PASS_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"count-only collection timed out after {COUNT_PASS_TIMEOUT_SECONDS}s") from exc
    node_ids = [line for line in proc.stdout.splitlines() if _NODE_ID_SEPARATOR in line]
    if proc.returncode not in _VALID_EXIT_CODES or not node_ids:
        raise RuntimeError(f"count-only collection failed (exit {proc.returncode}, {len(node_ids)} node ids)")
    return len(node_ids)


def _collect_counts(
    modules: Sequence[str],
    registry: dict[str, Any],
    timings: Mapping[str, Any],
    *,
    budget_left: Callable[[], bool] = lambda: True,
) -> tuple[dict[str, int], dict[str, str], list[str]]:
    """Count every module that still has a valid provenance; return ``(counts, failures, uncounted)``.

    A module without a valid provenance is drifted whatever its count is, so it is not
    counted (that saves a collection pass for exactly the modules that need a capture).
    *budget_left* is asked before each count pass; a module whose pass would start after the
    budget is spent is returned in *uncounted* (reported as deferred, never as clean).
    """
    counts: dict[str, int] = {}
    failures: dict[str, str] = {}
    uncounted: list[str] = []
    for module in modules:
        if not has_valid_provenance(timings, module):
            continue
        if not budget_left():
            uncounted.append(module)
            continue
        try:
            counts[module] = _collect_count(module, registry)
        except RuntimeError as exc:
            failures[module] = str(exc)
    return counts, failures, uncounted


def _read_timings_after_capture() -> tuple[dict[str, Any] | None, str | None]:
    """The timings file as the producer left it, or ``(None, why)`` when it cannot be read.

    Never raises: a producer that exits cleanly but leaves a damaged file is one failed
    module (its data restored by the caller, the other modules still processed), not a
    crash of the whole run.
    """
    try:
        payload = json.loads(TIMINGS_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:  # ValueError covers JSON and UTF-8 decoding errors
        return None, f"timings file unreadable after capture ({type(exc).__name__})"
    if not isinstance(payload, dict):
        return None, f"timings file unreadable after capture (parsed to {type(payload).__name__}, not a mapping)"
    return payload, None


def _capture_failure(module: str, run_id: str, timeout_seconds: float) -> str | None:
    """Run the producer for *module*; ``None`` when it left a valid, fresh capture behind,
    otherwise why not. The caller restores the file on a reason."""
    cmd = [sys.executable, "-m", "scripts.ci.capture_shard_timings", "--module", module, "--run-id", run_id, "--write"]
    try:
        proc = subprocess.run(cmd, cwd=REPO_ROOT, env=_scrubbed_env(), check=False, timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        return f"timed out after {int(timeout_seconds)}s"
    if proc.returncode not in _VALID_EXIT_CODES:
        return f"producer exited {proc.returncode}"
    payload, unreadable = _read_timings_after_capture()
    if payload is None:
        return unreadable
    record = _provenance_of(payload, module)
    if record is None or record.get("run_id") != run_id:
        return "producer wrote no provenance for this run (it crashed before writing)"
    if not is_valid_capture(record):
        return f"invalid capture (exit_code={record.get('exit_code')!r}, unique_tests_measured={record.get('unique_tests_measured')!r})"
    return None


def _capture_one(module: str, timeout_seconds: float) -> str | None:
    """Capture *module* in its own subprocess; on any failure put the committed file back
    byte for byte and return the reason. ``None`` means the capture is valid and kept.

    An ``OSError`` from the subprocess call (it could not start, a pipe broke) is a failure of
    this module, not of the run; any other exception propagates, after the file is put back.
    """
    before = TIMINGS_PATH.read_bytes()
    run_id = capture_shard_timings.generate_run_id(f"recapture-{module}")
    kept = False
    try:
        try:
            reason = _capture_failure(module, run_id, timeout_seconds)
        except OSError as exc:
            reason = f"capture could not run ({type(exc).__name__}: {exc})"
        kept = reason is None
    finally:
        if not kept:
            TIMINGS_PATH.write_bytes(before)
    return reason


def _fetch_proposal_timings() -> dict[str, Any]:
    """The timings file as it stands on the open proposal branch (no credential needed)."""
    no_credential_env = _scrubbed_env()
    _run_subprocess_or_die(["git", "fetch", "origin", RECAPTURE_BRANCH], step="git fetch", cwd=REPO_ROOT, env=no_credential_env)
    shown = _run_subprocess_or_die(
        ["git", "show", f"FETCH_HEAD:{_TIMINGS_GIT_PATH}"],
        step="git show",
        cwd=REPO_ROOT,
        env=no_credential_env,
        capture_output=True,
        text=True,
    )
    payload = json.loads(shown.stdout)
    if not isinstance(payload, dict):
        print(f"::error::{_TIMINGS_GIT_PATH} on {RECAPTURE_BRANCH} did not parse to a mapping", file=sys.stderr)
        raise SystemExit(1)
    return payload


# --------------------------------------------------------------------------- #
# Options and phases.                                                         #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Options:
    phase: str
    modules: tuple[str, ...] = ()
    budget_seconds: float | None = None
    write: bool = False
    capture_timeout_seconds: float = DEFAULT_CAPTURE_TIMEOUT_SECONDS


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="recapture_shard_timings", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("phase", choices=PHASES, help="detect: is a proposal open; capture: refresh drifted modules; publish: propose the refresh")
    parser.add_argument("--module", action="append", dest="modules", default=[], help="restrict to this registry module (repeatable); default every module")
    parser.add_argument("--budget-seconds", type=float, default=None, help="stop starting captures once this many seconds have elapsed")
    parser.add_argument("--write", action="store_true", help="capture and write refreshed data (without it, report drift only)")
    parser.add_argument(
        "--capture-timeout-seconds",
        type=float,
        default=DEFAULT_CAPTURE_TIMEOUT_SECONDS,
        help="kill a single module capture after this many seconds",
    )
    return parser


def _parse_options(argv: Sequence[str]) -> Options | int:
    """The parsed :class:`Options`, or the exit status argparse chose (2 for a usage error,
    0 for ``--help``) when it stopped the run."""
    try:
        args = _build_parser().parse_args(list(argv))
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    return Options(
        phase=args.phase,
        modules=tuple(args.modules),
        budget_seconds=args.budget_seconds,
        write=args.write,
        capture_timeout_seconds=args.capture_timeout_seconds,
    )


def _select_modules(registry: Mapping[str, Any], requested: Sequence[str]) -> list[str]:
    """Every registry module, or only *requested* (an unknown name exits 2)."""
    known = _registry_modules(registry)
    unknown = [module for module in requested if module not in known]
    if unknown:
        print(f"::error::not registry modules: {unknown} (known: {known})", file=sys.stderr)
        raise SystemExit(2)
    return [module for module in known if not requested or module in requested]


def _baseline_timings() -> dict[str, Any]:
    """The committed timings, with an open proposal's refreshed modules laid over them
    (and written to the working tree, where the producer reads its starting data from)."""
    timings = _read_timings()
    if os.environ.get(PROPOSAL_OPEN_ENV_VAR, "").strip().lower() != "true":
        return timings
    return overlay_proposal(timings, _fetch_proposal_timings())


def _capture_drifted(drifted: Sequence[str], timings: Mapping[str, Any], options: Options, started: float) -> RecaptureResult:
    """Capture *drifted* modules, oldest first, until the budget is spent."""
    captured: list[str] = []
    failed: list[str] = []
    deferred: list[str] = []
    reasons: dict[str, str] = {}
    for module in order_oldest_first(drifted, timings):
        if options.budget_seconds is not None and _now_seconds() - started >= options.budget_seconds:
            deferred.append(module)
            continue
        reason = _capture_one(module, options.capture_timeout_seconds)
        if reason is None:
            captured.append(module)
        else:
            failed.append(module)
            reasons[module] = reason
    return RecaptureResult(tuple(drifted), tuple(captured), tuple(failed), tuple(deferred), reasons)


def _emit_result(result: RecaptureResult) -> None:
    _write_github_output(drift=str(result.publishable).lower(), result=result.to_json())
    _write_job_summary(result.summary_table())


def run_capture_phase(options: Options) -> int:
    """The ``capture`` phase: no recapture token, no push, no ``gh`` call.

    The time budget starts here, so the count-only pass is inside it: no count pass starts once
    the budget is spent, and a module left uncounted is reported as ``deferred``. Returns 1 when
    any module failed (a failed count pass or an invalid capture); modules it could not judge
    are reported, never treated as clean.
    """
    if _refuse_if_token_present():
        return 1
    started = _now_seconds()
    registry = _load_registry()
    modules = _select_modules(registry, options.modules)
    timings = _baseline_timings()
    if options.write and timings != _read_timings():
        _write_timings(timings)

    def budget_left() -> bool:
        return options.budget_seconds is None or _now_seconds() - started < options.budget_seconds

    counts, count_failures, uncounted = _collect_counts(modules, registry, timings, budget_left=budget_left)
    drifted = drifted_modules([m for m in modules if m not in count_failures], timings, counts)
    result = _capture_drifted(drifted, timings, options, started) if options.write else RecaptureResult(drifted=tuple(drifted))
    if count_failures or uncounted:
        result = RecaptureResult(
            drifted=result.drifted,
            captured=result.captured,
            failed=(*count_failures, *result.failed),
            deferred=(*uncounted, *result.deferred),
            reasons={**count_failures, **result.reasons},
        )
    _emit_result(result)
    return 1 if result.failed else 0


def run_detect_phase() -> int:
    """The ``detect`` phase: is a recapture proposal open? Needs the token (``gh pr list``)
    but runs no test code, so the capture step that follows never sees the credential."""
    token = require_recapture_token()
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    pr_number = find_open_recapture_pr(_list_open_recapture_prs(repository, token))
    _write_github_output(proposal_open=str(pr_number is not None).lower())
    return 0


def _read_result_env() -> RecaptureResult:
    """The capture phase's result, as the workflow threaded it in. Fails loud -- an absent
    result must never read as "nothing to publish"."""
    raw = os.environ.get(RESULT_ENV_VAR, "").strip()
    if not raw:
        print(f"::error::{RESULT_ENV_VAR} is not set (or is empty) -- the publish phase cannot run without it", file=sys.stderr)
        raise SystemExit(1)
    try:
        return RecaptureResult.from_json(raw)
    except (ValueError, KeyError, TypeError) as exc:
        print(f"::error::{RESULT_ENV_VAR} is not a recapture result: {exc!r}", file=sys.stderr)
        raise SystemExit(1) from exc


def _git_commit_cmd(message: str) -> list[str]:
    return ["git", "-c", f"user.name={COMMIT_AUTHOR_NAME}", "-c", f"user.email={COMMIT_AUTHOR_EMAIL}", "commit", "-m", message]


def _push(token: str, *, force: bool) -> None:
    """Push HEAD to the recapture branch; a refusal is reported through
    :func:`push_failure_message`. *force* is only ever True on the no-open-PR path."""
    cmd = ["git", "push", *(["--force"] if force else []), "origin", f"HEAD:refs/heads/{RECAPTURE_BRANCH}"]
    try:
        subprocess.run(cmd, cwd=REPO_ROOT, env=_push_env(token), capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as exc:
        stderr = _redact(str(exc.stderr or ""), token)
        print(f"::error::git push failed: {push_failure_message(stderr, forced=force)}", file=sys.stderr)
        raise SystemExit(1) from exc


def _open_new_proposal(repository: str, token: str, result: RecaptureResult, run_url: str) -> None:
    """Commit, force-push to the fixed branch, and open the recapture PR.

    Only reachable from the no-open-PR path -- a plain ``git push --force`` is acceptable
    ONLY because :func:`run_publish_phase` already confirmed no PR from RECAPTURE_BRANCH is
    open immediately before calling this. The token never reaches argv, a log, or any
    subprocess that does not need it.
    """
    no_credential_env = _scrubbed_env()
    _run_subprocess_or_die(["git", "add", str(TIMINGS_PATH)], step="git add", cwd=REPO_ROOT, env=no_credential_env)
    _run_subprocess_or_die(_git_commit_cmd(result.commit_message()), step="git commit", cwd=REPO_ROOT, env=no_credential_env)
    _push(token, force=True)
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
            result.proposal_body(run_url),
        ],
        step="gh pr create",
        env=_gh_env(token),
    )


def _refresh_open_proposal(token: str, result: RecaptureResult) -> None:
    """Add an ordinary follow-up commit on top of the open proposal branch; never forced.

    The refreshed timings file is held in memory while the working tree moves to the
    proposal tip, then written back, so the commit carries exactly the merged data.
    """
    refreshed = TIMINGS_PATH.read_bytes()
    no_credential_env = _scrubbed_env()
    _run_subprocess_or_die(["git", "fetch", "origin", RECAPTURE_BRANCH], step="git fetch", cwd=REPO_ROOT, env=_push_env(token))
    _run_subprocess_or_die(["git", "checkout", "--force", "--detach", "FETCH_HEAD"], step="git checkout", cwd=REPO_ROOT, env=no_credential_env)
    TIMINGS_PATH.write_bytes(refreshed)
    _run_subprocess_or_die(["git", "add", str(TIMINGS_PATH)], step="git add", cwd=REPO_ROOT, env=no_credential_env)
    _run_subprocess_or_die(_git_commit_cmd(result.commit_message()), step="git commit", cwd=REPO_ROOT, env=no_credential_env)
    _push(token, force=False)


def run_publish_phase() -> int:
    """The ``publish`` phase: the ONLY phase (with ``detect``) that reads the recapture token.

    Does its own open-PR check immediately before publishing, which decides between a new
    proposal (force push allowed, no PR is open on the branch) and a follow-up commit
    (plain push). A result with nothing captured is a no-op (defense in depth behind the
    workflow's ``if:``).
    """
    token = require_recapture_token()  # First action, no exceptions before this.
    result = _read_result_env()
    if not result.publishable:
        return 0
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    pr_number = find_open_recapture_pr(_list_open_recapture_prs(repository, token))  # The single, pre-push check.
    if pr_number is None:
        _open_new_proposal(repository, token, result, _run_url())
    else:
        _refresh_open_proposal(token, result)
        _write_job_summary(f"Refreshed the open recapture proposal #{pr_number} with a follow-up commit.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """Dispatch to :func:`run_detect_phase`, :func:`run_capture_phase` or :func:`run_publish_phase`.

    A usage error (missing or unknown phase, bad option) exits 2 before any phase's own
    work -- including :func:`require_recapture_token` -- runs.
    """
    args = sys.argv[1:] if argv is None else list(argv)
    options = _parse_options(args)
    if isinstance(options, int):
        return options
    if options.phase == PHASE_DETECT:
        return run_detect_phase()
    if options.phase == PHASE_CAPTURE:
        return run_capture_phase(options)
    return run_publish_phase()


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main(sys.argv[1:]))
