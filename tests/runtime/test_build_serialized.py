"""Direct unit tests for ``asset_preparation.build_serialized`` and the
``_serialize_owner`` primitive it shares with ``recheck_assets`` (FR-003,
FR-007, FR-008, C-001, C-005, C-008, NFR-002/003; contracts/startup-asset-
escalation.md P1-P6).

Each test names the requirement it pins in its docstring.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from kernel.locks import SyncMachineFileLock
from kernel.locks import machine_file_lock as _REAL_MACHINE_FILE_LOCK

import specify_cli.runtime.agent_commands as agent_commands
import specify_cli.runtime.agent_skills as agent_skills
import specify_cli.runtime.asset_preparation as asset_preparation
import specify_cli.runtime.bootstrap as bootstrap
from specify_cli.runtime.asset_preparation import (
    AssetPreparation,
    ObservationRole,
    StartupAssetError,
    TornReadError,
    _HELD_LOCKS,
    build_serialized,
    incomplete,
)
from specify_cli.runtime.home import get_kittify_home
from specify_cli.skills.registry import SkillRegistry
from specify_cli.tool_surface.operations import ApplyConsent, Diagnostic, OperationRoot, PhysicalEffect

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_ANCHOR_LABEL = "test-owner"

#: The frozen true original, imported directly from ``kernel.locks`` (never
#: read back off ``asset_preparation.machine_file_lock``, which resolves to
#: ``Any`` under mypy's ``specify_cli.*`` ``follow_imports = "skip"`` override
#: -- same precedent as the ``protection_policy`` / ``asset_preservation.
#: backup`` entries in pyproject.toml). Every spy below wraps THIS reference,
#: never whatever is currently installed, so calling a spy helper more than
#: once in the same test (e.g. once for ``recheck_assets``, once for the
#: escalation) never chains through a stale wrapper.


@pytest.fixture(autouse=True)
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Sandbox EVERY test in this module (autouse): several primitive tests
    below drive a REAL ``_serialize_owner``/``machine_file_lock`` acquisition
    (the escalation path is exercised for real, not mocked), and
    ``_cold_install_sentinel`` resolves under ``get_runtime_state_root()``,
    which honors ``SPEC_KITTY_HOME`` -- without this, those calls would touch
    the operator's actual ``~/.spec-kitty*`` state. Also clears the per-agent
    config-root overrides (``tests/conftest.py``'s WP04 per-worker isolation
    always sets ``XDG_CONFIG_HOME`` to a worker-scoped fake home, not this
    test's own ``tmp_path``) so the commands owner's anchor computation
    never spans two unrelated fake homes -- mirrors
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
def fake_skill_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> SkillRegistry:
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


@pytest.fixture()
def fake_command_templates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    from specify_cli.shims.registry import PROMPT_DRIVEN_COMMANDS

    templates_dir = tmp_path / "command-templates"
    for command in PROMPT_DRIVEN_COMMANDS:
        step_dir = templates_dir / command
        step_dir.mkdir(parents=True)
        (step_dir / "prompt.md").write_text(f"---\ndescription: {command}\n---\n# {command}\n", encoding="utf-8")
    monkeypatch.setattr(agent_commands, "_get_command_templates_dir", lambda: templates_dir)
    return templates_dir


def _torn(
    lock_paths: tuple[Path, ...] = (),
    anchor: Path | None = None,
    role: ObservationRole = "destination_probe",
) -> TornReadError:
    return TornReadError(
        path=Path("/tmp/owner-assets.json"),
        role=role,
        lock_paths=lock_paths or (Path("/tmp/owner.lock"),),
        anchor=anchor or Path("/tmp"),
    )


def _spy_lock(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Record each REAL lock-path argument ``machine_file_lock`` is called
    with, in order -- concrete evidence for C-008 identity assertions, not
    merely a call count. Always wraps the frozen true original, so calling
    this twice in one test never double-counts through a stale wrapper.
    """
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


def _spy_asset_preparation_init(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    """Count ``AssetPreparation.__init__`` calls, with the primitive's REAL
    signature (never ``*args``/``**kwargs`` forwarding, which mypy correctly
    refuses once the real ``src`` types are visible alongside these tests).
    """
    init_calls = {"n": 0}
    real_init = AssetPreparation.__init__

    def counting_init(
        self: AssetPreparation,
        owner: str,
        root: OperationRoot,
        cache: Path,
        lock_name: str,
        consent: ApplyConsent,
    ) -> None:
        init_calls["n"] += 1
        real_init(self, owner, root, cache, lock_name, consent)

    monkeypatch.setattr(AssetPreparation, "__init__", counting_init)
    return init_calls


class TestBuildSerializedPrimitive:
    """P1-P6 of contracts/startup-asset-escalation.md, plus FR-007's six cases."""

    def test_clean_first_pass_takes_no_lock(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """P1/C-002: a clean build returns after exactly one call, no lock."""
        lock_calls = _spy_lock(monkeypatch)
        calls = {"n": 0}

        def build() -> str:
            calls["n"] += 1
            return "ok"

        assert build_serialized(build) == "ok"
        assert calls["n"] == 1
        assert lock_calls == []

    def test_destination_tear_then_success_serializes_once(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """P2/FR-008/NFR-003: one destination tear escalates once and
        converges. The cold-home escalation locks EXACTLY the cold-install
        sentinel -- a concrete list, not merely "at least one call".
        """
        lock_path = tmp_path / "owner.lock"
        anchor = tmp_path / "anchor"
        lock_calls = _spy_lock(monkeypatch)
        calls = {"n": 0}

        def build() -> str:
            calls["n"] += 1
            if calls["n"] == 1:
                raise _torn(lock_paths=(lock_path,), anchor=anchor)
            return "converged"

        logger = logging.getLogger("test.build_serialized.destination_tear")
        with caplog.at_level("INFO", logger=logger.name):
            result = build_serialized(build, logger=logger)

        assert result == "converged"
        assert calls["n"] == 2
        info_records = [r for r in caplog.records if r.levelname == "INFO"]
        assert len(info_records) == 1, caplog.messages
        assert "Error" not in info_records[0].message
        assert lock_calls == [asset_preparation._cold_install_sentinel(anchor)], "the escalation must acquire exactly the cold-install sentinel"

    def test_tear_on_both_attempts_propagates_after_two_builds(self, tmp_path: Path) -> None:
        """FR-004: a torn read that recurs under the serialization point is terminal."""
        lock_path = tmp_path / "owner.lock"
        anchor = tmp_path / "anchor"
        calls = {"n": 0}

        def build() -> str:
            calls["n"] += 1
            raise _torn(lock_paths=(lock_path,), anchor=anchor)

        with pytest.raises(TornReadError):
            build_serialized(build)
        assert calls["n"] == 2

    def test_reentrant_held_lock_propagates_without_blocking(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """C-005/P4: a torn read while ANY serialization point is held is
        terminal after exactly one build, with zero lock calls -- never
        blocks on itself. Pinned with an UNRELATED held path (fold 1): C-005
        is non-empty-``_HELD_LOCKS``, not merely a subset check.
        """
        lock_calls = _spy_lock(monkeypatch)
        unrelated = tmp_path / "unrelated.lock"
        token = _HELD_LOCKS.set(frozenset({unrelated}))
        calls = {"n": 0}
        try:

            def build() -> str:
                calls["n"] += 1
                raise _torn(lock_paths=(tmp_path / "owner.lock",), anchor=tmp_path)

            with pytest.raises(TornReadError):
                build_serialized(build)
        finally:
            _HELD_LOCKS.reset(token)
        assert calls["n"] == 1
        assert lock_calls == []

    def test_source_role_tear_refused_without_locking(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """C-001/P3: a source-role torn read propagates after one build, 0 locks."""
        lock_calls = _spy_lock(monkeypatch)
        calls = {"n": 0}

        def build() -> str:
            calls["n"] += 1
            raise _torn(role="source_read")

        with pytest.raises(TornReadError):
            build_serialized(build)
        assert calls["n"] == 1
        assert lock_calls == []

    @pytest.mark.parametrize("error", [ValueError("x"), OSError("y")])
    def test_non_torn_errors_propagate_immediately(self, error: Exception) -> None:
        """P5: any non-``TornReadError`` exception propagates after one build."""
        calls = {"n": 0}

        def build() -> str:
            calls["n"] += 1
            raise error

        with pytest.raises(type(error)):
            build_serialized(build)
        assert calls["n"] == 1

    def test_held_locks_restored_after_return_and_raise(self, tmp_path: Path) -> None:
        """P6: ``_HELD_LOCKS`` equals its entry value after both outcomes."""
        before = _HELD_LOCKS.get()

        def ok_build() -> str:
            return "ok"

        build_serialized(ok_build)
        assert _HELD_LOCKS.get() == before

        torn_then_ok_calls = {"n": 0}

        def torn_then_ok() -> str:
            torn_then_ok_calls["n"] += 1
            if torn_then_ok_calls["n"] == 1:
                raise _torn(lock_paths=(tmp_path / "owner.lock",), anchor=tmp_path)
            return "ok"

        build_serialized(torn_then_ok)
        assert _HELD_LOCKS.get() == before

        def always_torn() -> str:
            raise _torn(lock_paths=(tmp_path / "owner2.lock",), anchor=tmp_path)

        with pytest.raises(TornReadError):
            build_serialized(always_torn)
        assert _HELD_LOCKS.get() == before


class TestSerializationPointIdentity:
    """C-008: the escalation and the existing locked recheck acquire the
    IDENTICAL, CONCRETE lock set for the same owner -- not merely "the same
    call", which would tautologically hold since both route through
    ``_serialize_owner``.
    """

    def test_recheck_and_escalation_agree_on_the_lock_set_cold(
        self,
        fake_home: Path,
        fake_package_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        assessment = bootstrap.assess_runtime()
        assert assessment.complete and assessment.effects
        prepared = assessment.prepared
        assert isinstance(prepared, asset_preparation.PreparedAssets)
        assert not prepared.lock_path.exists(), "setup guard: must start cold"
        expected = [asset_preparation._cold_install_sentinel(prepared.anchor)]

        recheck_calls = _spy_lock(monkeypatch)
        with asset_preparation.recheck_assets(assessment):
            pass
        assert recheck_calls == expected

        # recheck_assets's own acquisition just materialized the sentinel
        # file; remove it so the escalation half observes the SAME cold
        # precondition, not an artifact of the first half having just run.
        expected[0].unlink(missing_ok=True)
        escalation_calls = _spy_lock(monkeypatch)
        calls = {"n": 0}

        def build() -> str:
            calls["n"] += 1
            if calls["n"] == 1:
                raise TornReadError(path=prepared.lock_path, role="destination_probe", lock_paths=prepared.lock_paths, anchor=prepared.anchor)
            return "ok"

        assert build_serialized(build) == "ok"
        assert escalation_calls == expected

    def test_recheck_and_escalation_agree_on_the_lock_set_warm(
        self,
        fake_home: Path,
        fake_package_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        assessment = bootstrap.assess_runtime()
        assert assessment.complete and assessment.effects
        prepared = assessment.prepared
        assert isinstance(prepared, asset_preparation.PreparedAssets)
        prepared.lock_path.parent.mkdir(parents=True, exist_ok=True)
        prepared.lock_path.touch()
        expected = [prepared.lock_path]

        recheck_calls = _spy_lock(monkeypatch)
        with asset_preparation.recheck_assets(assessment):
            pass
        assert recheck_calls == expected

        escalation_calls = _spy_lock(monkeypatch)
        calls = {"n": 0}

        def build() -> str:
            calls["n"] += 1
            if calls["n"] == 1:
                raise TornReadError(path=prepared.lock_path, role="destination_probe", lock_paths=prepared.lock_paths, anchor=prepared.anchor)
            return "ok"

        assert build_serialized(build) == "ok"
        assert escalation_calls == expected


class TestWindowsLockReadSafety:
    """C-009: the escalation path never reads a held owner lock's bytes."""

    def test_escalation_never_reads_the_held_lock_bytes(
        self,
        fake_home: Path,
        fake_package_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Drive the REAL ``ensure_runtime()`` entry point on an already-warm
        home (so the owner lock file already exists -- ``_serialize_owner``
        takes the existing-lock branch, not the cold-sentinel one) while
        BOTH injecting the T001-style torn read (forcing the unlocked pass to
        escalate) AND applying the Windows mandatory-lock semantics: any
        content read of a path this process holds in ``_HELD_LOCKS`` raises.
        The escalation must still converge, proving it never reads the held
        lock's bytes.
        """
        from specify_cli.tool_surface.operations import FileState

        bootstrap.ensure_runtime()  # materialize a warm home with a real owner lock
        lock_path = get_kittify_home() / "cache" / ".update.lock"
        assert lock_path.is_file(), "setup guard: the persistent owner lock must exist"
        inventory = get_kittify_home() / "cache" / "runtime_bootstrap-assets.json"

        peer = {"active": True}
        counter = {"n": 0}
        real_node_state = asset_preparation.node_state
        seen: list[Path] = []

        def fake_node_state(path: Path, *, read_content: bool = True) -> FileState:
            if read_content and path in asset_preparation._HELD_LOCKS.get():
                seen.append(path)
                raise PermissionError(13, "Permission denied")
            if peer["active"] and path == inventory:
                counter["n"] += 1
                if counter["n"] % 2 == 1:
                    return FileState("absent")
                return FileState("file", sha256=asset_preparation.digest(str(counter["n"]).encode()), mode=0o644)
            return real_node_state(path, read_content=read_content)

        def fake_machine_file_lock(
            path: Path,
            *,
            blocking: bool = False,
            timeout_s: float | None = None,
            reentrant: bool = False,
        ) -> SyncMachineFileLock:
            peer["active"] = False
            return _REAL_MACHINE_FILE_LOCK(path, blocking=blocking, timeout_s=timeout_s, reentrant=reentrant)

        monkeypatch.setattr(asset_preparation, "node_state", fake_node_state)
        monkeypatch.setattr(asset_preparation, "machine_file_lock", fake_machine_file_lock)

        bootstrap.ensure_runtime()  # must NOT raise; must never read the held lock's bytes

        assert not seen, f"the escalation must never content-read a held owner lock, but read: {seen!r}"


class TestAncestorDirectoryNotTornByPeerChildren:
    """spec Assumption / C-001 safety: directory identity excludes mtime."""

    def test_creating_a_child_does_not_tear_the_ancestor_observation(self, tmp_path: Path) -> None:
        ancestor = tmp_path / "ancestor"
        ancestor.mkdir()
        cache = tmp_path / "cache"
        cache.mkdir()
        root = OperationRoot(_ANCHOR_LABEL, "global", tmp_path)
        prepared = AssetPreparation(_ANCHOR_LABEL, root, cache, ".test.lock", ApplyConsent())
        prepared.observe(ancestor / "child", role="destination_probe")
        (ancestor / "new-sibling").mkdir()
        # Re-observing a descendant re-walks the ancestor; must not raise.
        prepared.observe(ancestor / "child", role="destination_probe")


class TestIncompleteDiagnosticCodes:
    """T007.12: incomplete() routes on exception type, never message text."""

    def test_destination_torn_read_gets_asset_torn_read(self) -> None:
        root = OperationRoot(_ANCHOR_LABEL, "global", Path("/tmp"))
        error = _torn(role="destination_probe")
        assessment = incomplete(_ANCHOR_LABEL, root, error)
        assert assessment.diagnostics[0].code == "asset_torn_read"

    def test_source_torn_read_gets_asset_source_drift(self) -> None:
        root = OperationRoot(_ANCHOR_LABEL, "global", Path("/tmp"))
        error = _torn(role="source_read")
        assessment = incomplete(_ANCHOR_LABEL, root, error)
        assert assessment.diagnostics[0].code == "asset_source_drift"

    def test_plain_value_error_gets_global_assets_unavailable(self) -> None:
        root = OperationRoot(_ANCHOR_LABEL, "global", Path("/tmp"))
        assessment = incomplete(_ANCHOR_LABEL, root, ValueError("boom"))
        assert assessment.diagnostics[0].code == "global_assets_unavailable"


class TestNoNestedSerializationPoint:
    """Fold 1 (C-005, stronger): ``_HELD_LOCKS`` holding an UNRELATED path
    makes any torn read terminal, with 0 lock calls -- never only a subset
    check."""

    def test_unrelated_held_path_makes_torn_read_terminal(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        lock_calls = _spy_lock(monkeypatch)
        unrelated = tmp_path / "some-other-owner.lock"
        token = _HELD_LOCKS.set(frozenset({unrelated}))
        try:

            def build() -> str:
                raise _torn(lock_paths=(tmp_path / "this-owner.lock",), anchor=tmp_path)

            with pytest.raises(TornReadError):
                build_serialized(build)
        finally:
            _HELD_LOCKS.reset(token)
        assert lock_calls == []


class TestSplitAnchorNeverNests:
    """F3 (pre-PR squad): ``_is_terminal_torn_read``'s "terminal when held"
    rule holds even when owners' anchors do NOT coincide. With
    ``XDG_CONFIG_HOME`` pointed outside ``HOME``, the commands owner's
    anchor (spanning every configured agent's command directory) differs
    from the runtime owner's anchor, and therefore keys a DIFFERENT
    ``_cold_install_sentinel`` -- yet a torn read while ANY serialization
    point is held stays terminal regardless of whether it is the SAME
    sentinel that is held.
    """

    def test_runtime_and_commands_owners_derive_different_sentinel_keys(
        self,
        fake_home: Path,
        fake_package_assets: Path,
        fake_command_templates: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        xdg = fake_home.parent / "xdg"  # a sibling of HOME, never nested under it
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))

        runtime_assessment = bootstrap.assess_runtime()
        assert runtime_assessment.complete
        assert isinstance(runtime_assessment.prepared, asset_preparation.PreparedAssets)

        commands_assessment = agent_commands.assess_global_agent_commands()
        assert commands_assessment.complete
        assert isinstance(commands_assessment.prepared, asset_preparation.PreparedAssets)

        runtime_anchor = runtime_assessment.prepared.anchor
        commands_anchor = commands_assessment.prepared.anchor
        assert runtime_anchor != commands_anchor, "setup guard: XDG_CONFIG_HOME outside HOME must split the two owners' anchors"
        assert asset_preparation._cold_install_sentinel(runtime_anchor) != asset_preparation._cold_install_sentinel(commands_anchor)

    def test_torn_read_is_still_terminal_while_holding_the_other_owners_sentinel(
        self,
        fake_home: Path,
        fake_package_assets: Path,
        fake_command_templates: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        xdg = fake_home.parent / "xdg"
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))

        runtime_assessment = bootstrap.assess_runtime()
        assert isinstance(runtime_assessment.prepared, asset_preparation.PreparedAssets)
        commands_assessment = agent_commands.assess_global_agent_commands()
        assert isinstance(commands_assessment.prepared, asset_preparation.PreparedAssets)
        assert runtime_assessment.prepared.anchor != commands_assessment.prepared.anchor, "setup guard: anchors must differ"

        # This process already holds the RUNTIME owner's serialization point
        # (a DIFFERENT sentinel key from the commands owner's); a torn read
        # on the COMMANDS owner must still be terminal -- never blocks, 0
        # lock calls -- even though it is not the SAME sentinel held.
        held = frozenset({asset_preparation._cold_install_sentinel(runtime_assessment.prepared.anchor)})
        token = _HELD_LOCKS.set(held)
        lock_calls = _spy_lock(monkeypatch)
        try:

            def build() -> str:
                raise _torn(lock_paths=commands_assessment.prepared.lock_paths, anchor=commands_assessment.prepared.anchor)

            with pytest.raises(TornReadError):
                build_serialized(build)
        finally:
            _HELD_LOCKS.reset(token)
        assert lock_calls == []


class TestStartupAssetErrorConstruction:
    """T006: MRO, JSON-safe path, code as a Python-only attribute."""

    def test_is_both_guarded_read_error_and_runtime_error(self) -> None:
        from kernel.errors import GuardedReadError

        error = asset_preparation.startup_asset_error(
            "runtime_bootstrap", (Diagnostic("asset_torn_read", "runtime_bootstrap", "error", "Asset changed during preparation: /tmp/x"),)
        )
        assert isinstance(error, RuntimeError)
        assert isinstance(error, GuardedReadError)
        assert isinstance(error, StartupAssetError)

    def test_path_is_none_and_code_is_first_diagnostic(self) -> None:
        diagnostics = (Diagnostic("asset_torn_read", "runtime_bootstrap", "error", "Asset changed during preparation: /tmp/x"),)
        error = asset_preparation.startup_asset_error("runtime_bootstrap", diagnostics)
        assert error.path is None
        assert error.code == "asset_torn_read"
        assert "runtime_bootstrap" in str(error)
        assert "Asset changed during preparation" in str(error)


class TestWarmPathBuildCounts:
    """NFR-002/SC-003: on a warm home, each owner constructs exactly one
    ``AssetPreparation`` and acquires zero locks per startup."""

    def test_runtime_warm_path_builds_once_no_lock(
        self,
        fake_home: Path,
        fake_package_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        bootstrap.ensure_runtime()  # materialize
        lock_calls = _spy_lock(monkeypatch)
        init_calls = _spy_asset_preparation_init(monkeypatch)

        bootstrap.ensure_runtime()

        assert init_calls["n"] == 1
        assert lock_calls == []

    def test_skills_warm_path_builds_once_no_lock(
        self,
        fake_home: Path,
        fake_skill_registry: SkillRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        agent_skills.ensure_global_agent_skills()  # materialize
        lock_calls = _spy_lock(monkeypatch)
        init_calls = _spy_asset_preparation_init(monkeypatch)

        agent_skills.ensure_global_agent_skills()

        assert init_calls["n"] == 1
        assert lock_calls == []

    def test_commands_warm_path_short_circuits_without_asset_preparation(
        self,
        fake_home: Path,
        fake_command_templates: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The commands owner's Ruling-6 freshness pre-check short-circuits
        the FULL-FLEET (``agent_keys=None``) call before ever constructing an
        ``AssetPreparation`` -- 0 builds, 0 locks on the warm path."""
        agent_commands.ensure_global_agent_commands()  # materialize (all agents)
        lock_calls = _spy_lock(monkeypatch)
        init_calls = _spy_asset_preparation_init(monkeypatch)

        agent_commands.ensure_global_agent_commands()

        assert init_calls["n"] == 0
        assert lock_calls == []


class TestFR002BatchIncludeCalledOnce:
    """T007.13 (FR-002/C-003): the injected torn read must converge through
    the SKILLS startup path (``assess_global_assets(runtime=False,
    commands=False)`` -- the exact call ``ensure_global_agent_skills()``
    makes), with ``_GlobalAssetPreparation.include`` called exactly once,
    AND with the escalation actually having fired (never a vacuous pass
    where the tear happened not to trigger). The direct, non-batched
    ``bootstrap.assess_runtime()`` half is kept alongside as a control and
    must independently show escalation fired too.
    """

    def test_batch_include_called_once_after_escalation(
        self,
        fake_home: Path,
        fake_package_assets: Path,
        fake_skill_registry: SkillRegistry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from specify_cli.tool_surface.operations import FileState

        state = {
            "inventory": get_kittify_home() / "cache" / "runtime_bootstrap-assets.json",
            "peer_active": True,
            "calls": 0,
        }
        real_node_state = asset_preparation.node_state

        def fake_node_state(path: Path, *, read_content: bool = True) -> FileState:
            if state["peer_active"] and path == state["inventory"]:
                state["calls"] += 1
                if state["calls"] % 2 == 1:
                    return FileState("absent")
                return FileState("file", sha256=asset_preparation.digest(str(state["calls"]).encode()), mode=0o644)
            return real_node_state(path, read_content=read_content)

        lock_calls: list[Path] = []

        def fake_machine_file_lock(
            path: Path,
            *,
            blocking: bool = False,
            timeout_s: float | None = None,
            reentrant: bool = False,
        ) -> SyncMachineFileLock:
            lock_calls.append(path)
            state["peer_active"] = False
            return _REAL_MACHINE_FILE_LOCK(path, blocking=blocking, timeout_s=timeout_s, reentrant=reentrant)

        monkeypatch.setattr(asset_preparation, "node_state", fake_node_state)
        monkeypatch.setattr(asset_preparation, "machine_file_lock", fake_machine_file_lock)

        include_calls = {"n": 0}
        real_include = asset_preparation._GlobalAssetPreparation.include

        def counting_include(
            self: asset_preparation._GlobalAssetPreparation,
            builder: AssetPreparation,
            effects: tuple[PhysicalEffect, ...],
        ) -> None:
            include_calls["n"] += 1
            real_include(self, builder, effects)

        monkeypatch.setattr(asset_preparation._GlobalAssetPreparation, "include", counting_include)

        # -- Control: the direct, non-batched runtime owner must escalate on
        # -- EXACTLY its own cold-install sentinel -- derived by reading the
        # -- anchor PRODUCTION already computed onto the real, completed
        # -- assessment's PreparedAssets, never by re-deriving the anchor
        # -- formula independently (fold F2).
        direct = bootstrap.assess_runtime()
        assert direct.complete
        assert isinstance(direct.prepared, asset_preparation.PreparedAssets)
        assert lock_calls == [asset_preparation._cold_install_sentinel(direct.prepared.anchor)], (
            "the direct runtime assessment must have escalated on exactly its cold-install sentinel"
        )

        # -- The SKILLS startup path: reset state for a fresh cold tear on --
        # -- the skills owner's OWN inventory, then assert both include() ---
        # -- ran exactly once AND the escalation fired on exactly the ------
        # -- skills batch's own cold-install sentinel. --
        state["inventory"] = get_kittify_home() / "cache" / "global_skills-assets.json"
        state["peer_active"] = True
        state["calls"] = 0
        lock_calls.clear()
        include_calls["n"] = 0

        batch_assessment = asset_preparation.assess_global_assets(runtime=False, commands=False)
        assert batch_assessment.complete
        assert include_calls["n"] == 1
        assert isinstance(batch_assessment.prepared, asset_preparation.PreparedAssets)
        assert lock_calls == [asset_preparation._cold_install_sentinel(batch_assessment.prepared.anchor)], (
            "the skills batch escalation must have fired on exactly its cold-install sentinel"
        )
