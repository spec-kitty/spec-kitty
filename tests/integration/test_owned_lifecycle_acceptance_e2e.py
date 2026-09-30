"""End-to-end owned-checkout lifecycle walk (SC-001 / SC-003 / NFR-001 / NFR-002).

Mission ``owned-checkout-lifecycle-authority-01M3M2ZB``, closing WP18 (T098, T099).

Automates the ``quickstart.md`` script through the REAL command implementations
(``typer.testing.CliRunner`` over the per-command Typer apps the WP08-WP13
acceptance files use, in process so the walk stays on the per-PR path):

    create -> spec-commit -> setup-plan -> status -> finalize-tasks
        -> next (implement WP01, workspace == P) -> move-task claimed / in_progress
        -> commit an implementation change in P -> move-task for_review
        -> next (review prompt based on WP01's claim commit) -> context resolve

for the invoking cwd in {repository root checkout R, owned checkout P, another
linked checkout S} and with and without a stale copy of the mission in R. After
EVERY step:

* the command exits 0;
* every absolute path in the JSON payload resolves under P (the only exceptions are
  R's stale copy, named solely by ``stale_repository_root_copy.path`` and the
  top-level ``warnings`` rendering of it, and the P-keyed prompt cache
  ``SPEC_KITTY_HOME/spec-kitty-prompts/<key of P>/`` ``next`` writes);
* R is unchanged (working tree including ignored files, ``HEAD``, index, the
  shared lock root and ``SPEC_KITTY_HOME``; the two named NFR-001 tolerances are
  the per-mission status mutex and that same P-keyed prompt cache -- any other
  write under the home, or a prompt directory keyed to another checkout, fails).

NFR-002 is measured here too: exactly one ownership validation per owned command
(counted at ``checkout_ownership.resolve_ownership_claim``), and no extra git
subprocess for an owned ``agent tasks status`` read versus the non-owned path.
Both count checks ship with a committed non-vacuity twin that must FAIL when the
command validates twice or bypasses validation.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from specify_cli.cli.commands import next_cmd
from specify_cli.cli.commands.agent.context import app as context_app
from specify_cli.cli.commands.agent.mission import app as mission_app
from specify_cli.cli.commands.agent.tasks import app as tasks_app
from specify_cli.cli.commands.agent.workflow import app as action_app
from specify_cli.cli.commands.spec_commit_cmd import spec_commit_command
from tests._factories import provision_test_charter
from tests._owned_fixtures import RSnapshotter, mint_test_fact, prompt_cache_prefix
from tests.integration.conftest import OwnedCheckouts, _git, _init_repo, _write_mission, _write_single_lane_manifest
from tests.runtime._next_mission_scaffold import advance_to_step

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

runner = CliRunner()
next_app = typer.Typer()
next_app.command(name="next")(next_cmd.next_step)
spec_commit_app = typer.Typer()
spec_commit_app.command(name="spec-commit")(spec_commit_command)

_OWNED_BRANCH = "kitty/demo-owned"
_SIBLING_BRANCH = "codex/sibling"
_STALE_KEY = "stale_repository_root_copy"
_CWDS = ("R", "P", "elsewhere")


# ---------------------------------------------------------------------------
# Site: R (repository root checkout), P (owned checkout), S (another checkout)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Site:
    r: Path
    p: Path
    s: Path
    home: Path | None

    def cwd(self, where: str) -> Path:
        return {"R": self.r, "P": self.p, "elsewhere": self.s}[where]


def _commit_all(root: Path, message: str) -> None:
    _git(root, "add", "-A")
    _git(root, "commit", "-qm", message)


def _build_site(tmp_path: Path) -> _Site:
    r = tmp_path / "repository-root"
    _init_repo(r)
    p = tmp_path / "owned"
    _git(r, "worktree", "add", "-qb", _OWNED_BRANCH, str(p))
    s = tmp_path / "sibling"
    _git(r, "worktree", "add", "-qb", _SIBLING_BRANCH, str(s))
    (p / ".gitignore").write_text(".kittify/derived/\n", encoding="utf-8")  # mirror the `spec-kitty init` ignore contract
    for checkout in (r, p, s):
        provision_test_charter(checkout)
        _commit_all(checkout, "provision charter")
    home = Path(os.environ["SPEC_KITTY_HOME"]) if os.environ.get("SPEC_KITTY_HOME") else None
    return _Site(r=r, p=p, s=s, home=home)


# ---------------------------------------------------------------------------
# Command plumbing
# ---------------------------------------------------------------------------


def _payload(result: Any) -> dict[str, Any]:
    """The first JSON document in the combined output (stderr advisories may follow it)."""
    text = result.output
    data, _end = json.JSONDecoder().raw_decode(text[text.index("{") :])
    assert isinstance(data, dict), text
    return data


@dataclass
class _ClaimProbe:
    """Counts ``resolve_ownership_claim`` calls (NFR-002) per CLI command run through :func:`_run`."""

    count: int = 0
    per_command: list[tuple[str, int]] = field(default_factory=list)


_ACTIVE_PROBE: _ClaimProbe | None = None


def _run(app: typer.Typer, args: list[str]) -> dict[str, Any]:
    from specify_cli.workspace.context import clear_workspace_resolution_caches

    clear_workspace_resolution_caches()  # process-global caches would hide a re-validation behind a hit
    probe = _ACTIVE_PROBE
    started = probe.count if probe is not None else 0
    result = runner.invoke(app, args)
    assert result.exit_code == 0, f"{args}\n{result.output}"
    if probe is not None:
        probe.per_command.append((" ".join(args[:2]), probe.count - started))
    return _payload(result)


@pytest.fixture
def claim_probe(monkeypatch: pytest.MonkeyPatch) -> Iterator[_ClaimProbe]:
    """Wrap the real ``resolve_ownership_claim`` with a counter that delegates to it unchanged.

    ``owned_mission`` imports the primitive lazily inside its validator, so patching the
    module attribute is seen by every caller.
    """
    global _ACTIVE_PROBE
    from specify_cli.core import checkout_ownership

    probe = _ClaimProbe()
    real = checkout_ownership.resolve_ownership_claim

    def _counting(*args: Any, **kwargs: Any) -> Any:
        probe.count += 1
        return real(*args, **kwargs)

    monkeypatch.setattr(checkout_ownership, "resolve_ownership_claim", _counting)
    _ACTIVE_PROBE = probe
    try:
        yield probe
    finally:
        _ACTIVE_PROBE = None


def _assert_one_validation_per_command(probe: _ClaimProbe) -> None:
    """FR-003 / NFR-002: 0 or >= 2 ownership validations for an owned command fail."""
    assert probe.per_command, "no command was counted"
    offenders = [(command, delta) for command, delta in probe.per_command if delta != 1]
    assert not offenders, f"exactly one ownership validation per owned command expected; got {offenders} of {probe.per_command}"


def _absolute_paths(node: Any, *, skip_key: str | None = None) -> Iterator[str]:
    """Every absolute-path-looking string in ``node`` (skipping the value of ``skip_key``)."""
    if isinstance(node, dict):
        for key, value in node.items():
            if key == skip_key:
                continue
            yield from _absolute_paths(value, skip_key=skip_key)
    elif isinstance(node, list):
        for item in node:
            yield from _absolute_paths(item, skip_key=skip_key)
    elif isinstance(node, str):
        for token in node.replace("\n", " ").split():
            candidate = token.strip("\"'`,;()[]{}")
            if candidate.startswith("/") and len(candidate) > 1 and "/" in candidate[1:]:
                yield candidate


def _under(path: str | Path, root: Path) -> bool:
    return Path(path).resolve().is_relative_to(root.resolve())


#: ``mission create`` reports the repository root it resolved under this key by design
#: (an identity field of the create envelope, not a path the command reads or writes).
_CREATE_IDENTITY_KEYS = frozenset({"canonical_repo_root"})
#: ``next`` reports where the mission DEFINITION came from under ``origin`` (the shipped
#: package-default mission, a resource of the installed package rather than of any checkout).
_NEXT_PROVENANCE_KEYS = frozenset({"origin"})


def _assert_paths_under_p(site: _Site, payload: dict[str, Any], *, step: str, ignore_keys: frozenset[str] = frozenset()) -> None:
    """SC-001: no path in the payload resolves outside P, except two narrowly-keyed stale-copy channels.

    R's stale copy may be named ONLY by ``stale_repository_root_copy.path`` and by a string inside
    the top-level ``warnings`` list (the rendered ``STALE_COPY_WARNING``), and in ``warnings`` only
    as that exact path. Under any other key -- ``feature_dir`` included -- it is a violation. The
    only other allowed root is the P-keyed prompt cache under ``SPEC_KITTY_HOME`` (never the whole home).
    """
    stale = payload.get(_STALE_KEY)
    stale_path = Path(str(stale["path"])).resolve() if stale is not None else None
    stripped = {key: value for key, value in payload.items() if key not in {_STALE_KEY, "warnings"} and key not in ignore_keys}
    warnings = payload.get("warnings") or []
    allowed_roots = [site.p]
    if site.home is not None:
        allowed_roots.append(site.home / prompt_cache_prefix(site.p))
    for candidate in _absolute_paths(stripped):
        if not any(_under(candidate, root) for root in allowed_roots):
            raise AssertionError(f"{step}: path outside P: {candidate}\npayload={payload}")
    for candidate in _absolute_paths(warnings):
        if stale_path is not None and Path(candidate).resolve() == stale_path:
            continue
        if not any(_under(candidate, root) for root in allowed_roots):
            raise AssertionError(f"{step}: path outside P in warnings: {candidate}\npayload={payload}")
    if stale is not None:
        assert _under(stale["path"], site.r), f"{step}: stale copy path is not under R: {stale}"


def _paths_site(tmp_path: Path) -> _Site:
    for name in ("r", "p", "s"):
        (tmp_path / name).mkdir()
    return _Site(r=tmp_path / "r", p=tmp_path / "p", s=tmp_path / "s", home=None)


def test_paths_check_admits_the_stale_path_only_in_the_stale_channel(tmp_path: Path) -> None:
    """Non-vacuity twin of the SC-001 path check: R's stale path is allowed under ONE key and ONE list."""
    site = _paths_site(tmp_path)
    stale_path = str(site.r / "kitty-specs" / "demo")
    stale = {"path": stale_path, "mission_id": "01ABC"}
    warning = f"The repository root checkout holds a stale copy of mission demo at {stale_path}; the owned checkout {site.p} is authoritative."
    _assert_paths_under_p(site, {_STALE_KEY: stale, "warnings": [warning], "feature_dir": str(site.p / "kitty-specs" / "demo")}, step="channel")
    for key in ("feature_dir", "mission_dir", "workspace"):
        with pytest.raises(AssertionError, match="path outside P"):
            _assert_paths_under_p(site, {_STALE_KEY: stale, key: stale_path}, step=key)
    with pytest.raises(AssertionError, match="path outside P"):
        _assert_paths_under_p(site, {_STALE_KEY: stale, "nested": {"warnings": [warning]}}, step="nested-warnings")
    with pytest.raises(AssertionError, match="path outside P"):
        _assert_paths_under_p(site, {_STALE_KEY: stale, "warnings": [f"see {site.r / 'other'}"]}, step="other-path-in-warnings")


# ---------------------------------------------------------------------------
# The walk: one function per quickstart step
# ---------------------------------------------------------------------------


@dataclass
class _Walk:
    site: _Site
    slug: str = ""
    mission_id: str = ""
    step: str = ""


def _step_create(walk: _Walk) -> dict[str, Any]:
    payload = _run(
        mission_app,
        [
            "create",
            "demo",
            "--mission-type",
            "software-dev",
            "--owned-checkout",
            str(walk.site.p),
            "--target-branch",
            _OWNED_BRANCH,
            "--topology",
            "single_branch",
            "--branch-strategy",
            "already-confirmed",
            "--json",
        ],
    )
    walk.slug = str(payload["mission_slug"])
    meta = json.loads((walk.site.p / "kitty-specs" / walk.slug / "meta.json").read_text(encoding="utf-8"))
    walk.mission_id = str(meta["mission_id"])
    return payload


def _mission_dir(walk: _Walk) -> Path:
    return walk.site.p / "kitty-specs" / walk.slug


def _step_spec_commit(walk: _Walk) -> dict[str, Any]:
    mission_dir = _mission_dir(walk)
    (mission_dir / "spec.md").write_text(
        "# Demo\n\n## Functional Requirements\n\n| ID | Requirement | Status |\n|----|-------------|--------|\n| FR-001 | The demo works. | Draft |\n",
        encoding="utf-8",
    )
    return _run(
        spec_commit_app,
        [
            str(mission_dir / "spec.md"),
            str(mission_dir / "meta.json"),
            "--message",
            "docs: spec for demo",
            "--mission",
            walk.slug,
            "--owned-checkout",
            str(walk.site.p),
            "--json",
        ],
    )


def _step_setup_plan(walk: _Walk) -> dict[str, Any]:
    return _run(mission_app, ["setup-plan", "--owned-checkout", str(walk.site.p), "--mission", walk.slug, "--json"])


def _step_status(walk: _Walk) -> dict[str, Any]:
    return _run(tasks_app, ["status", "--owned-checkout", str(walk.site.p), "--mission", walk.slug, "--json"])


def _write_tasks(walk: _Walk) -> None:
    mission_dir = _mission_dir(walk)
    tasks_dir = mission_dir / "tasks"
    tasks_dir.mkdir(exist_ok=True)
    (mission_dir / "tasks.md").write_text(
        "# Tasks\n\n## Work Package WP01\n\n**Dependencies**: None\n\nImplement the demo.\n",
        encoding="utf-8",
    )
    (tasks_dir / "WP01-demo.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Demo work package\ndependencies: []\nrequirement_refs: [FR-001]\n"
        "subtasks: []\nowned_files: [demo.py]\nauthoritative_surface: demo.py\nexecution_mode: code_change\n"
        "create_intent:\n  - demo.py\n---\n\n# WP01\n\nImplement the demo.\n",
        encoding="utf-8",
    )
    (walk.site.p / "demo.py").write_text("# demo\n", encoding="utf-8")
    _commit_all(walk.site.p, "tasks: demo work package")


def _step_finalize(walk: _Walk) -> dict[str, Any]:
    _write_tasks(walk)
    return _run(mission_app, ["finalize-tasks", "--owned-checkout", str(walk.site.p), "--mission", walk.slug, "--json"])


def _step_next_implement(walk: _Walk) -> dict[str, Any]:
    """``next --result success`` at the ``tasks`` step issues ``implement WP01`` with workspace == P.

    The run is driven to the composed ``tasks`` step first through the REAL engine
    (``advance_to_step``, never stubbed) -- the same priming the WP11/WP19 acceptance
    files use -- because walking every upstream step through the CLI adds ~90 s per
    parametrisation without exercising anything the per-step files do not.
    """
    advance_to_step(walk.site.p, walk.slug, "software-dev", "tasks")
    payload = _run(
        next_app,
        ["--agent", "claude", "--owned-checkout", str(walk.site.p), "--mission", walk.slug, "--result", "success", "--json"],
    )
    assert payload.get("kind") == "step", payload
    assert payload.get("action") == "implement" and payload.get("wp_id") == "WP01", payload
    assert _under(str(payload["workspace_path"]), walk.site.p), payload
    return payload


def _step_move(walk: _Walk, lane: str) -> dict[str, Any]:
    return _run(
        tasks_app,
        ["move-task", "WP01", "--to", lane, "--owned-checkout", str(walk.site.p), "--mission", walk.slug, "--agent", "claude", "--json"],
    )


def _step_implement_commit(walk: _Walk) -> None:
    (walk.site.p / "demo.py").write_text("# demo\nVALUE = 1\n", encoding="utf-8")
    _commit_all(walk.site.p, "feat: implement demo")


def _step_next_review(walk: _Walk) -> dict[str, Any]:
    """``next --result success`` after ``for_review`` issues the review prompt for WP01."""
    payload = _run(
        next_app,
        ["--agent", "claude", "--owned-checkout", str(walk.site.p), "--mission", walk.slug, "--result", "success", "--json"],
    )
    assert payload.get("kind") == "step", payload
    assert payload.get("action") == "review" and payload.get("wp_id") == "WP01", payload
    return payload


def _step_context_resolve(walk: _Walk) -> dict[str, Any]:
    payload = _run(
        context_app,
        ["--action", "implement", "--owned-checkout", str(walk.site.p), "--mission", walk.slug, "--wp-id", "WP01", "--json"],
    )
    assert payload["resolution_kind"] == "owned_checkout"
    assert payload["lane_id"] is None
    assert _under(payload["wp_file"], walk.site.p)
    assert _under(payload["workspace_path"], walk.site.p)
    return payload


def _claim_commit(walk: _Walk) -> str:
    """The unique commit whose diff to ``status.events.jsonl`` introduced WP01's last ``claimed`` event."""
    events = _mission_dir(walk) / "status.events.jsonl"
    claimed = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines() if line.strip()]
    claimed = [event for event in claimed if event.get("wp_id") == "WP01" and event.get("to_lane") == "claimed"]
    event_id = claimed[-1]["event_id"]
    log = _git(walk.site.p, "log", "--format=%H", f"-S{event_id}", "HEAD", "--", f"kitty-specs/{walk.slug}/status.events.jsonl")
    commits = log.split()
    assert len(commits) == 1, log
    return commits[0]


def _stale_copy_into_r(walk: _Walk) -> None:
    """R keeps an old copy of the mission (same ``mission_id``, a larger foreign WP set)."""
    import shutil

    target = walk.site.r / "kitty-specs" / walk.slug
    shutil.copytree(_mission_dir(walk), target)
    for extra in ("WP02", "WP03"):
        (target / "tasks" / f"{extra}-stale.md").write_text(f"---\nwork_package_id: {extra}\ntitle: stale\ndependencies: []\n---\n# {extra}\n", encoding="utf-8")
    _commit_all(walk.site.r, "stale copy of the mission")


_REPRO_STEPS: tuple[str, ...] = ("create", "spec", "plan", "status", "finalize", "implement", "claimed", "in_progress", "for_review", "review", "context")


def _drive(site: _Site, *, stale: bool, where: str, monkeypatch: pytest.MonkeyPatch, seam_hook: Callable[[_Walk], None] | None = None) -> _Walk:
    """Walk the quickstart from ``where``; assert exit 0, paths under P and R unchanged after every step."""
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    monkeypatch.chdir(site.cwd(where))
    walk = _Walk(site=site)
    snapshotter = RSnapshotter(site.r, site.p, site.home)
    before = snapshotter.take()

    def check(name: str, payload: dict[str, Any] | None, *, ignore_keys: frozenset[str] = frozenset()) -> None:
        nonlocal before
        walk.step = name
        if payload is not None:
            _assert_paths_under_p(site, payload, step=name, ignore_keys=ignore_keys)
            if stale and name in {"status", "plan", "context", "finalize", "implement"}:
                assert payload.get(_STALE_KEY) is not None, f"{name}: stale copy not reported: {payload}"
            if not stale and _STALE_KEY in payload:
                assert payload[_STALE_KEY] is None, f"{name}: unexpected stale copy: {payload}"
        after = snapshotter.take()
        snapshotter.assert_unchanged(before, after, tolerate_status_mutex_for=walk.slug or None)
        before = after

    check("create", _step_create(walk), ignore_keys=_CREATE_IDENTITY_KEYS)
    if stale:
        _stale_copy_into_r(walk)
        before = snapshotter.take()
    check("spec", _step_spec_commit(walk))
    check("plan", _step_setup_plan(walk))
    check("status", _step_status(walk))
    check("finalize", _step_finalize(walk))
    check("implement", _step_next_implement(walk), ignore_keys=_NEXT_PROVENANCE_KEYS)
    if seam_hook is not None:
        seam_hook(walk)
    check("claimed", _step_move(walk, "claimed"))
    check("in_progress", _step_move(walk, "in_progress"))
    _step_implement_commit(walk)
    check("for_review", _step_move(walk, "for_review"))
    review = _step_next_review(walk)
    claim = _claim_commit(walk)
    prompt = Path(review["prompt_file"]).read_text(encoding="utf-8")
    assert f"git diff {claim}..HEAD --stat -- demo.py" in prompt, f"the review prompt is not based on WP01's claim commit {claim}"
    check("review", review, ignore_keys=_NEXT_PROVENANCE_KEYS)
    check("context", _step_context_resolve(walk))
    return walk


@pytest.fixture
def site(tmp_path: Path, canonical_home: None) -> _Site:
    return _build_site(tmp_path)


_SLOW = pytest.mark.slow  # ~70-100 s per walk; informational only: module-tests.yml runs ``-m 'not performance and not stress'``, so ALL six cells run per PR


def _matrix() -> list[Any]:
    cells = []
    for where in _CWDS:
        for stale in (False, True):
            per_pr = where == "P" and stale
            cells.append(pytest.param(where, stale, id=f"{where}-{'stale-copy' if stale else 'no-stale-copy'}", marks=[] if per_pr else [_SLOW]))
    return cells


@pytest.mark.parametrize(("where", "stale"), _matrix())
def test_quickstart_walk_from_every_cwd(site: _Site, where: str, stale: bool, monkeypatch: pytest.MonkeyPatch) -> None:
    """SC-001: create -> ... -> review prompt -> context resolve, 0 errors, 0 R differences, all paths under P."""
    walk = _drive(site, stale=stale, where=where, monkeypatch=monkeypatch)

    assert walk.slug
    assert stale or not (site.r / "kitty-specs" / walk.slug).exists(), "the mission must never be materialised in R"


def test_walk_detects_seam_ignoring_owned(site: _Site, monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-vacuity: a placement seam whose owned arm answers with R's path makes the walk fail.

    The failure surfaces either as a path outside P in a payload or as a non-zero exit of the
    command that consumed the wrong directory; both are ``AssertionError`` from the walk's own checks.
    """
    from mission_runtime import resolution

    real_read_dir = resolution.PlacementSeam.read_dir

    def _ignore_owned(self: Any, kind: Any) -> Path:
        if self.owned is not None:
            repository_root_dir: Path = Path(self.owned.repository_root) / "kitty-specs" / str(self.mission_slug)
            return repository_root_dir
        original: Path = real_read_dir(self, kind)
        return original

    monkeypatch.setattr(resolution.PlacementSeam, "read_dir", _ignore_owned)

    with pytest.raises(AssertionError):
        _drive(site, stale=False, where="P", monkeypatch=monkeypatch)


def test_action_commands_refuse_owned_checkout_without_touching_r(site: _Site, monkeypatch: pytest.MonkeyPatch) -> None:
    """Tail of the quickstart: ``agent action implement|review --owned-checkout`` is a typed refusal."""
    walk = _drive(site, stale=False, where="R", monkeypatch=monkeypatch)
    snapshotter = RSnapshotter(site.r, site.p, site.home)
    before = snapshotter.take()
    for command in ("implement", "review"):
        result = runner.invoke(action_app, [command, "WP01", "--owned-checkout", str(site.p), "--mission", walk.slug])
        assert result.exit_code != 0, result.output
        assert "OWNED_ACTION_UNSUPPORTED" in result.output, result.output
    snapshotter.assert_unchanged(before, snapshotter.take(), tolerate_status_mutex_for=walk.slug)


# ---------------------------------------------------------------------------
# T099 -- NFR-002 (per PR): exactly one ownership validation per owned command
# ---------------------------------------------------------------------------


def test_walk_validates_ownership_exactly_once_per_command(site: _Site, claim_probe: _ClaimProbe, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every owned command of the quickstart walk validates ownership exactly once (FR-003)."""
    _drive(site, stale=False, where="P", monkeypatch=monkeypatch)

    _assert_one_validation_per_command(claim_probe)


def _created_walk(site: _Site, monkeypatch: pytest.MonkeyPatch) -> _Walk:
    """A walk that has only created the mission and committed its spec (enough for ``status``)."""
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)
    monkeypatch.chdir(site.r)
    walk = _Walk(site=site)
    _step_create(walk)
    _step_spec_commit(walk)
    return walk


def test_count_detects_double_validation(site: _Site, claim_probe: _ClaimProbe, monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-vacuity: a CLI helper that validates twice makes the exactly-once check fail."""
    from specify_cli.cli.commands import _owned_checkout

    walk = _created_walk(site, monkeypatch)
    real = _owned_checkout.resolve_owned_or_adopt

    def _twice(*args: Any, **kwargs: Any) -> Any:
        real(*args, **kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(_owned_checkout, "resolve_owned_or_adopt", _twice)
    claim_probe.per_command.clear()

    _step_status(walk)

    with pytest.raises(AssertionError, match="exactly one ownership validation"):
        _assert_one_validation_per_command(claim_probe)
    assert claim_probe.per_command[-1][1] == 2


def test_count_detects_bypass(site: _Site, claim_probe: _ClaimProbe, monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-vacuity: a CLI helper that skips validation altogether makes the exactly-once check fail."""
    from specify_cli.cli.commands import _owned_checkout

    walk = _created_walk(site, monkeypatch)

    def _skip(*_args: Any, **_kwargs: Any) -> Any:
        return mint_test_fact(
            repository_root=site.r,
            owned_root=site.p,
            mission_dir=_mission_dir(walk),
            mission_slug=walk.slug,
            write_branch=_OWNED_BRANCH,
        )

    monkeypatch.setattr(_owned_checkout, "resolve_owned_or_adopt", _skip)
    claim_probe.per_command.clear()

    _step_status(walk)

    with pytest.raises(AssertionError, match="exactly one ownership validation"):
        _assert_one_validation_per_command(claim_probe)
    assert claim_probe.per_command[-1][1] == 0


# ---------------------------------------------------------------------------
# T099 -- NFR-002 (per PR): no extra git subprocess per owned status read
# ---------------------------------------------------------------------------


def _install_git_call_counter(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Count every ``git`` child process (``subprocess.run`` and friends all construct a ``Popen``)."""
    calls: list[str] = []
    real_popen = subprocess.Popen

    def _counting_popen(args: Any, *popen_args: Any, **popen_kwargs: Any) -> Any:
        argv = list(args) if isinstance(args, (list, tuple)) else [args]
        if argv and os.path.basename(str(argv[0])) in {"git", "git.exe"}:
            calls.append(" ".join(str(part) for part in argv[:4]))
        return real_popen(args, *popen_args, **popen_kwargs)

    monkeypatch.setattr(subprocess, "Popen", _counting_popen)
    return calls


def _cold() -> None:
    """Drop the process-global caches so every measured section pays its git probes from scratch."""
    from kernel import git_topology
    from specify_cli.workspace.context import clear_workspace_resolution_caches

    clear_workspace_resolution_caches()
    git_topology.clear_caches()


def _plain_repository(tmp_path: Path, slug: str, mission_id: str) -> Path:
    """An equivalent mission in a plain repository root checkout (no owned checkout at all)."""
    plain = tmp_path / "plain"
    _init_repo(plain)
    provision_test_charter(plain)
    mission_dir = plain / "kitty-specs" / slug
    _write_mission(mission_dir, mission_id=mission_id, slug=slug, topology="single_branch", target_branch="main", wp_ids=("WP01", "WP02"))
    _write_single_lane_manifest(mission_dir, mission_slug=slug, mission_id=mission_id, target_branch="main", wp_ids=("WP01", "WP02"))
    _commit_all(plain, "plain mission")
    return plain


def test_owned_status_read_adds_no_git_subprocess_beyond_the_validation(owned_checkouts: OwnedCheckouts, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-002: an owned ``agent tasks status`` read spawns no git process the non-owned read does not, beyond the validator's own probes."""
    from specify_cli.cli.commands._owned_checkout import resolve_owned_or_adopt
    from specify_cli.core.owned_mission import LIFECYCLE_OWNED_TOPOLOGIES

    plain = _plain_repository(tmp_path, "plain-mission-01M2D902", "01M2D902000000000000000001")
    calls = _install_git_call_counter(monkeypatch)
    monkeypatch.delenv("SPECIFY_REPO_ROOT", raising=False)

    monkeypatch.chdir(owned_checkouts.repository_root)
    calls.clear()
    _cold()
    _run(tasks_app, ["status", "--owned-checkout", str(owned_checkouts.owned_root), "--mission", owned_checkouts.mission_slug, "--json"])
    owned_calls = len(calls)
    owned_list = list(calls)

    monkeypatch.chdir(plain)
    calls.clear()
    _cold()
    _run(tasks_app, ["status", "--mission", "plain-mission-01M2D902", "--json"])
    non_owned_calls = len(calls)
    non_owned_list = list(calls)

    calls.clear()
    _cold()
    # The validation itself, through the ONE door every owned command uses (repository-root fold + claim + registry probes).
    resolve_owned_or_adopt(
        owned_checkouts.repository_root,
        owned_checkouts.owned_root,
        owned_checkouts.mission_slug,
        cwd=owned_checkouts.repository_root,
        allowed_topologies=LIFECYCLE_OWNED_TOPOLOGIES,
    )
    validator_probes = len(calls)
    validator_list = list(calls)

    assert owned_calls - validator_probes - non_owned_calls <= 0, (
        f"owned status spawned {owned_calls} git processes; the validator's own probes are {validator_probes} and the non-owned read spawns {non_owned_calls}\n"
        f"owned={owned_list}\nvalidator={validator_list}\nnon-owned={non_owned_list}"
    )
    assert validator_probes > 0, "the validator's own probe count must be measurable (a zero would make the bound vacuous)"
    assert non_owned_calls > 0, "the non-owned read must spawn git for the bound to mean anything"
