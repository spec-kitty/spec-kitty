"""Issue #3998: an unlocked torn read on a fresh (cold) shared home used to
crash the actual command a user or agent ran, instead of waiting for the
concurrent installer and converging.

The pre-fix failure path: ``AssetPreparation.observe()`` sees an owner's own
inventory file in two different states within one unlocked assessment pass
(a benign concurrent peer mid-write) and raised ``ValueError("Asset changed
during preparation: <path>")``. The retired ``retry_torn_read`` re-raced the
writer three times WITHOUT waiting, ``incomplete()`` collapsed the error into
the generic ``global_assets_unavailable`` diagnostic, and ``ensure_*`` raised
a bare ``RuntimeError`` that the CLI rendered as a traceback.

This file drives EACH owner's PRE-EXISTING startup entry point
(``bootstrap.ensure_runtime``, ``agent_commands.ensure_global_agent_commands``,
``agent_skills.ensure_global_agent_skills``), injecting the torn read ONLY at
leaf I/O (``asset_preparation.node_state`` / ``asset_preparation.
machine_file_lock``) -- never by patching ``assess_*``, ``retry_torn_read``,
``build_serialized`` or any other helper. See spec.md/plan.md for the fix
design (serialization-point escalation) this test proves.

The first test below (``test_ensure_converges_when_unlocked_assessment_tears``)
was committed RED on the planning base for all three owner parameters with the
exact production failure ``Asset changed during preparation`` (C-007,
ADR 2026-07-17-1) -- see the WP Activity Log for the captured red evidence --
and is now the FUNCTIONAL proof pinning the fixed convergence: the owner
escalates to its serialization point, reassesses once under it, and the
command runs (FR-001/FR-002, SC-002). The remaining tests pin what stays
terminal: a torn read that recurs under the serialization point (FR-004/
FR-005/C-010, no traceback), a source-role torn read (C-001, refused without
waiting), and a genuine non-torn-read failure (US3.3, refused without
waiting either).
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from kernel.locks import SyncMachineFileLock
from kernel.locks import machine_file_lock as _REAL_MACHINE_FILE_LOCK

import specify_cli
import specify_cli.runtime.agent_commands as agent_commands
import specify_cli.runtime.agent_skills as agent_skills
import specify_cli.runtime.asset_preparation as asset_preparation
import specify_cli.runtime.bootstrap as bootstrap
from specify_cli.runtime.asset_preparation import StartupAssetError
from specify_cli.runtime.home import get_kittify_home
from specify_cli.skills.registry import SkillRegistry
from specify_cli.tool_surface.operations import Diagnostic, FileState

pytestmark = [pytest.mark.unit, pytest.mark.fast]

#: owner key -> the pre-existing startup entry point this WP must drive
#: through, never a lower-level helper. ``commands`` scopes to one agent and
#: ``fake_command_templates`` trims the template source so the render stays
#: fast and never touches the real ``packs/built-in`` corpus (see that
#: fixture's docstring).
_ENTRY_POINTS: dict[str, Callable[[], None]] = {
    "runtime": bootstrap.ensure_runtime,
    "commands": lambda: agent_commands.ensure_global_agent_commands(agent_keys=["claude"]),
    "skills": agent_skills.ensure_global_agent_skills,
}
_OWNER_KEYS = {"runtime": "runtime_bootstrap", "commands": "slash_commands", "skills": "global_skills"}
#: Each owner's own module logger, the OPERATOR_SIGNAL_CONTRACT sink
#: build_serialized's INFO line is emitted on (fold 7).
_OWNER_LOGGERS = {
    "runtime": bootstrap.logger.name,
    "commands": agent_commands.logger.name,
    "skills": agent_skills.logger.name,
}


@pytest.fixture()
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point ``SPEC_KITTY_HOME``/``HOME`` at a genuinely cold home.

    Mirrors ``tests/runtime/test_generic_asset_scope.py``'s identically-named
    fixture. Also clears the per-agent config-root overrides
    (``tests/conftest.py``'s WP04 per-worker isolation always sets
    ``XDG_CONFIG_HOME`` to a worker-scoped fake home, NOT this test's own
    ``tmp_path``) so ``get_global_command_dir``'s opencode/llxprt branches
    fall back to ``Path.home()``-relative paths -- otherwise the commands
    owner's anchor computation (the commonpath of every agent's command dir)
    spans two unrelated fake homes and no longer resolves under ``tmp_path``,
    breaking the fold-5 sentinel-identity assertion. Mirrors
    ``tests/specify_cli/runtime/test_agent_commands.py``'s
    ``TestFreshnessPrecheck._isolated_project``.
    """
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))
    monkeypatch.delenv("OPENCODE_CONFIG_DIR", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("LLXPRT_CONFIG_HOME", raising=False)
    return home


@pytest.fixture()
def fake_package_assets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Minimal fake package asset root for the RUNTIME family.

    Kept OUTSIDE the kittify home (a sibling of ``fake_home``'s ``home``, both
    under ``tmp_path``) so a source-role observation of a package asset never
    shares a path with a destination-probe of the runtime owner's own
    managed tree -- source-role stickiness must never accidentally reclassify
    the injected destination tear as source drift.
    """
    pkg_root = tmp_path / "package"
    missions = pkg_root / "missions"
    (missions / "software-dev").mkdir(parents=True)
    (missions / "software-dev" / "mission.yaml").write_text("test-mission")
    (missions / "software-dev" / "templates").mkdir()
    (missions / "software-dev" / "templates" / "spec.md").write_text("test-template")

    scripts = pkg_root / "scripts"
    scripts.mkdir(parents=True)
    (scripts / "validate.py").write_text("# validate")

    (pkg_root / "AGENTS.md").write_text("# Agents")

    monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(missions))
    return missions


@pytest.fixture()
def fake_command_templates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A trimmed command-templates dir (``PROMPT_DRIVEN_COMMANDS`` only).

    With the REAL templates, the commands param takes ~15s and reading
    ``packs/built-in`` trips the corpus-marker guard -- see fold note 5 on
    the WP prompt. Mirrors ``tests/specify_cli/runtime/test_agent_commands.py``'s
    ``TestFreshnessPrecheck._write_prompt_templates``.
    """
    from specify_cli.shims.registry import PROMPT_DRIVEN_COMMANDS

    templates_dir = tmp_path / "command-templates"
    for command in PROMPT_DRIVEN_COMMANDS:
        step_dir = templates_dir / command
        step_dir.mkdir(parents=True)
        (step_dir / "prompt.md").write_text(f"---\ndescription: {command}\n---\n# {command}\n", encoding="utf-8")
    monkeypatch.setattr(agent_commands, "_get_command_templates_dir", lambda: templates_dir)
    return templates_dir


@pytest.fixture()
def fake_skill_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SkillRegistry:
    """A minimal real canonical skill registry.

    Mirrors ``tests/runtime/test_generic_asset_scope.py``'s identically-named
    fixture -- lets ``agent_skills``'s assess/ensure entry points run for real
    against a tiny, deterministic catalog instead of the full package registry.
    """
    skills_root = tmp_path / "doctrine_skills"
    skill_dir = skills_root / "spec-kitty-test-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: spec-kitty-test-skill\ndescription: test\n---\n# test\n",
        encoding="utf-8",
    )
    registry = SkillRegistry(skills_root)
    monkeypatch.setattr(agent_skills, "_discover_registry", lambda: registry)
    return registry


def _tear_owner_inventory_while_peer_active(
    inventory: Path,
    peer: dict[str, bool],
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[str, Path]]:
    """Wrap leaf I/O ONLY to model a concurrent peer mid-write to *inventory*.

    Every unlocked observation of *inventory* alternates absent/file (a
    changing digest) while ``peer["active"]`` is True -- exactly the shape an
    in-flight writer produces (each fresh ``AssetPreparation`` observes its
    inventory exactly twice per pass: once at ``__init__``, once again at
    ``finish()``'s effect computation, so the alternation naturally starts
    from ``absent`` for every fresh attempt). Wrapping
    ``machine_file_lock`` (never any higher-level assess/retry/escalation
    helper) clears the flag the instant this process is granted a REAL lock,
    modeling "the writer already finished by the time I hold its lock".

    Returns the ordered ``(kind, path)`` event log this injection records --
    ``"observe"`` for each ``node_state`` hit on *inventory*, ``"lock"`` for
    each ``machine_file_lock`` call -- so callers can assert precise
    interleaving (fold 5: the inventory must be observed exactly twice before
    the FIRST lock call, and that first lock must be the cold-install
    sentinel, never an extra unlocked retry).
    """
    real_node_state = asset_preparation.node_state
    calls = {"n": 0}
    events: list[tuple[str, Path]] = []

    def fake_node_state(path: Path, *, read_content: bool = True) -> FileState:
        if peer["active"] and path == inventory:
            calls["n"] += 1
            events.append(("observe", path))
            if calls["n"] % 2 == 1:
                return FileState("absent")
            changing_digest = asset_preparation.digest(str(calls["n"]).encode())
            return FileState("file", sha256=changing_digest, mode=0o644)
        return real_node_state(path, read_content=read_content)

    def fake_machine_file_lock(
        path: Path,
        *,
        blocking: bool = False,
        timeout_s: float | None = None,
        reentrant: bool = False,
    ) -> SyncMachineFileLock:
        events.append(("lock", path))
        peer["active"] = False
        return _REAL_MACHINE_FILE_LOCK(path, blocking=blocking, timeout_s=timeout_s, reentrant=reentrant)

    monkeypatch.setattr(asset_preparation, "node_state", fake_node_state)
    monkeypatch.setattr(asset_preparation, "machine_file_lock", fake_machine_file_lock)
    return events


@pytest.mark.parametrize("owner", ["runtime", "commands", "skills"])
def test_ensure_converges_when_unlocked_assessment_tears(
    owner: str,
    tmp_path: Path,
    fake_home: Path,
    fake_package_assets: Path,
    fake_command_templates: Path,
    fake_skill_registry: SkillRegistry,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """FR-001/FR-002/FR-006, C-007, SC-002.

    Given a cold home and a peer mid-write to this owner's inventory, when the
    owner's pre-existing startup entry point runs and its unlocked assessment
    tears, the command must converge (acquire the serialization point,
    reassess once under it, and run) rather than crash.
    """
    inventory = get_kittify_home() / "cache" / f"{_OWNER_KEYS[owner]}-assets.json"
    peer = {"active": True}
    events = _tear_owner_inventory_while_peer_active(inventory, peer, monkeypatch)

    with caplog.at_level("INFO", logger=_OWNER_LOGGERS[owner]):
        _ENTRY_POINTS[owner]()  # must NOT raise "Asset changed during preparation"

    assert inventory.is_file(), f"{owner} owner inventory must materialize once the assessment converges"

    # Fold 7: the FR-008 operator signal fired on the owner's own logger, and
    # never contains "Error" (the #3998 reproducer greps for it).
    info_messages = [record.message for record in caplog.records if record.levelname == "INFO"]
    assert info_messages, f"expected the FR-008 operator-signal INFO line on {_OWNER_LOGGERS[owner]}, got: {caplog.records!r}"
    assert all("Error" not in message for message in info_messages)

    # Fold 5 (strengthened): the unlocked pass observes the inventory EXACTLY
    # twice (init + finish's effect computation -- NFR-003, one unlocked
    # build) before the first lock call, and that first lock is the owner's
    # cold-install sentinel (this cold home has no owner lock file yet).
    # Catches a mutation that adds an extra unlocked retry before escalating
    # (verified: temporarily adding a second unretried build() attempt inside
    # build_serialized turns this red).
    first_lock_index = next(i for i, (kind, _path) in enumerate(events) if kind == "lock")
    observes_before_first_lock = [event for event in events[:first_lock_index] if event[0] == "observe"]
    assert len(observes_before_first_lock) == 2, events
    expected_sentinel = asset_preparation._cold_install_sentinel(tmp_path)
    assert events[first_lock_index] == ("lock", expected_sentinel), events


def _tear_owner_inventory_forever(inventory: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Like ``_tear_owner_inventory_while_peer_active``, but the peer NEVER
    finishes (nothing ever clears the flag) -- every unlocked AND serialized
    attempt tears, so the torn read recurs under the serialization point and
    stays terminal (FR-004).
    """
    real_node_state = asset_preparation.node_state
    calls = {"n": 0}

    def fake_node_state(path: Path, *, read_content: bool = True) -> FileState:
        if path == inventory:
            calls["n"] += 1
            if calls["n"] % 2 == 1:
                return FileState("absent")
            changing_digest = asset_preparation.digest(str(calls["n"]).encode())
            return FileState("file", sha256=changing_digest, mode=0o644)
        return real_node_state(path, read_content=read_content)

    monkeypatch.setattr(asset_preparation, "node_state", fake_node_state)


def _tear_source_file(path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Alternate two DIFFERENT ``file`` digests for *path* (never ``absent``,
    or the owner would just skip an optional source) -- a source-role tear
    (C-001), never tolerated regardless of any peer waiting.
    """
    real_node_state = asset_preparation.node_state
    calls = {"n": 0}

    def fake_node_state(p: Path, *, read_content: bool = True) -> FileState:
        if p == path:
            calls["n"] += 1
            changing_digest = asset_preparation.digest(f"variant-{calls['n']}".encode())
            return FileState("file", sha256=changing_digest, mode=0o644)
        return real_node_state(p, read_content=read_content)

    monkeypatch.setattr(asset_preparation, "node_state", fake_node_state)


def _spy_lock(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Record each REAL lock-path argument ``machine_file_lock`` is called
    with, in order -- concrete evidence, not merely a call count."""
    calls: list[Path] = []

    def fake_lock(
        path: Path,
        *,
        blocking: bool = False,
        timeout_s: float | None = None,
        reentrant: bool = False,
    ) -> SyncMachineFileLock:
        calls.append(path)
        return _REAL_MACHINE_FILE_LOCK(path, blocking=blocking, timeout_s=timeout_s, reentrant=reentrant)

    monkeypatch.setattr(asset_preparation, "machine_file_lock", fake_lock)
    return calls


class TestTornReadUnderSerializationIsTerminal:
    """FR-004/FR-005/C-010: a torn read that recurs under the serialization
    point is terminal, and surfaces cleanly (no traceback) through the real
    CLI error-presentation hook, in both text and ``--json`` mode.
    """

    def test_ensure_runtime_raises_startup_asset_error_with_torn_read_code(
        self,
        fake_home: Path,
        fake_package_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        inventory = get_kittify_home() / "cache" / "runtime_bootstrap-assets.json"
        _tear_owner_inventory_forever(inventory, monkeypatch)

        with pytest.raises(StartupAssetError) as exc_info:
            bootstrap.ensure_runtime()
        error = exc_info.value
        assert error.code == "asset_torn_read"
        assert isinstance(error, RuntimeError)

    def test_cli_text_mode_renders_one_error_line_no_traceback(
        self,
        fake_home: Path,
        fake_package_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Fold note 4: through the real hook, never ``CliRunner`` (which
        bypasses ``_run_app_with_error_hook``) and never ``main()`` (whose
        logging bootstrap mutates global handlers).
        """
        inventory = get_kittify_home() / "cache" / "runtime_bootstrap-assets.json"
        _tear_owner_inventory_forever(inventory, monkeypatch)
        monkeypatch.setattr(sys, "argv", ["spec-kitty", "events", "--help"])
        # specify_cli._get_app() memoizes a process-global _APP the FIRST time
        # it is called; register_commands()'s single-leaf-command fast path
        # narrows that build to whatever sys.argv resolves to. Isolate our
        # narrowed sys.argv from every OTHER test in this process (which may
        # need the full command set) by forcing our own fresh build here --
        # monkeypatch restores whatever _APP held before this test on teardown.
        monkeypatch.setattr(specify_cli, "_APP", None)

        with pytest.raises(SystemExit) as exc_info:
            specify_cli._run_app_with_error_hook(specify_cli._get_app(), json_mode=False)
        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        stderr_lines = captured.err.rstrip("\n").splitlines()
        assert len(stderr_lines) == 1, captured.err
        assert stderr_lines[0].startswith("Error:")
        assert "runtime_bootstrap" in stderr_lines[0]
        assert str(inventory) in stderr_lines[0]
        assert "Traceback" not in captured.out
        assert "Traceback" not in captured.err

    def test_cli_json_mode_emits_one_json_object_on_stdout(
        self,
        fake_home: Path,
        fake_package_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        inventory = get_kittify_home() / "cache" / "runtime_bootstrap-assets.json"
        _tear_owner_inventory_forever(inventory, monkeypatch)
        monkeypatch.setattr(sys, "argv", ["spec-kitty", "events", "--help", "--json"])
        # See the text-mode test above: isolate our narrowed sys.argv from
        # polluting the process-global _get_app() cache for other tests.
        monkeypatch.setattr(specify_cli, "_APP", None)

        with pytest.raises(SystemExit) as exc_info:
            specify_cli._run_app_with_error_hook(specify_cli._get_app(), json_mode=True)
        assert exc_info.value.code == 1

        captured = capsys.readouterr()
        payload = json.loads(captured.out)  # whole-stdout parse pins FR-008's stdout silence
        assert payload["kind"] == "StartupAssetError"
        assert "Traceback" not in captured.err
        assert captured.err == "", "INV-1: JSON mode emits ONLY the JSON object, nothing on stderr"


class TestSourceDriftTornReadRefusedWithoutWaiting:
    """C-001: a source-role torn read is refused immediately -- no lock, no
    waiting, unlike a destination-role tear.
    """

    def test_source_drift_refused_with_zero_lock_calls(
        self,
        fake_home: Path,
        fake_package_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        agents_md = fake_package_assets.parent / "AGENTS.md"
        _tear_source_file(agents_md, monkeypatch)
        lock_calls = _spy_lock(monkeypatch)

        with pytest.raises(StartupAssetError) as exc_info:
            bootstrap.ensure_runtime()
        assert exc_info.value.code == "asset_source_drift"
        assert lock_calls == []


class TestGenuineFailureRefusedWithoutWaiting:
    """US3.3 / fold 6 T008.4: a genuine non-torn-read failure (a malformed
    inventory) is refused immediately with the existing generic diagnostic
    code, and never waits -- P5, C-010."""

    def test_malformed_inventory_gives_global_assets_unavailable_with_zero_lock_calls(
        self,
        fake_home: Path,
        fake_package_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        inventory = get_kittify_home() / "cache" / "runtime_bootstrap-assets.json"
        inventory.parent.mkdir(parents=True, exist_ok=True)
        inventory.write_text("{}", encoding="utf-8")  # missing schema_version/entries
        lock_calls = _spy_lock(monkeypatch)

        with pytest.raises(StartupAssetError) as exc_info:
            bootstrap.ensure_runtime()
        assert exc_info.value.code == "global_assets_unavailable"
        assert lock_calls == []


class TestStartupAssetErrorNextStepHint:
    """FR-005/US3.1-3.3 (fold 8, revised per the pre-PR squad's F1): the
    next-step hint depends on the diagnostic code, and is NEVER destructive
    -- it must never suggest removing/deleting the Spec Kitty home, which
    (on Windows) also holds a user's saved auth credentials
    (auth/secure_storage/file_fallback.py)."""

    def test_torn_read_hint_names_a_possibly_different_version_peer(self) -> None:
        diagnostics = (Diagnostic("asset_torn_read", "runtime_bootstrap", "error", "Asset changed during preparation: /srv/x"),)
        error = asset_preparation.startup_asset_error("runtime_bootstrap", diagnostics)
        assert "possibly a different version" in str(error)
        assert "writing the same Spec Kitty home" in str(error)

    def test_source_drift_hint_mentions_the_installed_package_changing(self) -> None:
        diagnostics = (Diagnostic("asset_source_drift", "runtime_bootstrap", "error", "Asset changed during preparation: /srv/x"),)
        error = asset_preparation.startup_asset_error("runtime_bootstrap", diagnostics)
        assert "installed package's assets changed" in str(error)
        assert "writing the same Spec Kitty home" not in str(error)

    def test_generic_failure_hint_points_at_doctor(self) -> None:
        diagnostics = (Diagnostic("global_assets_unavailable", "runtime_bootstrap", "error", "Required package assets unavailable: /srv/x"),)
        error = asset_preparation.startup_asset_error("runtime_bootstrap", diagnostics)
        assert "spec-kitty doctor" in str(error)
        assert "writing the same Spec Kitty home" not in str(error)
        assert "installed package's assets changed" not in str(error)

    @pytest.mark.parametrize("code", ["asset_torn_read", "asset_source_drift", "global_assets_unavailable", "some_unforeseen_future_code"])
    def test_no_hint_ever_suggests_deleting_anything(self, code: str) -> None:
        diagnostics = (Diagnostic(code, "runtime_bootstrap", "error", "x"),)
        error = asset_preparation.startup_asset_error("runtime_bootstrap", diagnostics)
        lowered = str(error).lower()
        assert "remove" not in lowered
        assert "delete" not in lowered
