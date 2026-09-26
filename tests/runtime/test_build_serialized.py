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

import specify_cli.runtime.agent_commands as agent_commands
import specify_cli.runtime.agent_skills as agent_skills
import specify_cli.runtime.asset_preparation as asset_preparation
import specify_cli.runtime.bootstrap as bootstrap
from specify_cli.runtime.asset_preparation import (
    AssetPreparation,
    StartupAssetError,
    TornReadError,
    _HELD_LOCKS,
    build_serialized,
    incomplete,
)
from specify_cli.runtime.home import get_kittify_home
from specify_cli.skills.registry import SkillRegistry
from specify_cli.tool_surface.operations import OperationRoot

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_ANCHOR_LABEL = "test-owner"


@pytest.fixture(autouse=True)
def fake_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Sandbox EVERY test in this module (autouse): several primitive tests
    below drive a REAL ``_serialize_owner``/``machine_file_lock`` acquisition
    (the escalation path is exercised for real, not mocked), and
    ``_cold_install_sentinel`` resolves under ``get_runtime_state_root()``,
    which honors ``SPEC_KITTY_HOME`` -- without this, those calls would touch
    the operator's actual ``~/.spec-kitty*`` state.
    """
    home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SPEC_KITTY_HOME", str(home / ".kittify"))
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


def _torn(lock_paths: tuple[Path, ...] = (), anchor: Path | None = None, role: str = "destination_probe") -> TornReadError:
    return TornReadError(
        path=Path("/tmp/owner-assets.json"),
        role=role,  # type: ignore[arg-type]
        lock_paths=lock_paths or (Path("/tmp/owner.lock"),),
        anchor=anchor or Path("/tmp"),
    )


def _spy_lock(monkeypatch: pytest.MonkeyPatch) -> list[tuple[object, ...]]:
    calls: list[tuple[object, ...]] = []
    real_lock = asset_preparation.machine_file_lock

    def fake_lock(*args: object, **kwargs: object):
        calls.append(args)
        return real_lock(*args, **kwargs)

    monkeypatch.setattr(asset_preparation, "machine_file_lock", fake_lock)
    return calls


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
        """P2/FR-008/NFR-003: one destination tear escalates once and converges."""
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
        assert len(lock_calls) >= 1, "the escalation must acquire the serialization point"

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

        def torn_then_ok() -> str:
            torn_then_ok.calls += 1  # type: ignore[attr-defined]
            if torn_then_ok.calls == 1:  # type: ignore[attr-defined]
                raise _torn(lock_paths=(tmp_path / "owner.lock",), anchor=tmp_path)
            return "ok"

        torn_then_ok.calls = 0  # type: ignore[attr-defined]
        build_serialized(torn_then_ok)
        assert _HELD_LOCKS.get() == before

        def always_torn() -> str:
            raise _torn(lock_paths=(tmp_path / "owner2.lock",), anchor=tmp_path)

        with pytest.raises(TornReadError):
            build_serialized(always_torn)
        assert _HELD_LOCKS.get() == before


class TestSerializationPointIdentity:
    """C-008: the escalation and the existing locked recheck acquire the
    identical lock set for the same owner."""

    def test_recheck_and_escalation_agree_on_the_lock_set(
        self,
        fake_home: Path,
        fake_package_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        assessment = bootstrap.assess_runtime()
        assert assessment.complete and assessment.effects
        prepared = assessment.prepared
        assert isinstance(prepared, asset_preparation.PreparedAssets)

        recheck_paths: list[Path] = []
        real_lock = asset_preparation.machine_file_lock

        def spy_recheck(*args: object, **kwargs: object):
            recheck_paths.append(args[0])  # type: ignore[arg-type]
            return real_lock(*args, **kwargs)

        monkeypatch.setattr(asset_preparation, "machine_file_lock", spy_recheck)
        with asset_preparation.recheck_assets(assessment):
            pass
        assert recheck_paths, "setup guard: a cold assessment must take at least one lock"

        # Reset _HELD_LOCKS is automatic (recheck_assets' own finally already
        # ran). Now drive the SAME lock_paths/anchor through the escalation
        # seam, from a fresh cold state (delete what recheck_assets created).
        for path in prepared.lock_paths:
            path.unlink(missing_ok=True)
        sentinel = asset_preparation._cold_install_sentinel(prepared.anchor)
        sentinel.unlink(missing_ok=True)

        escalation_paths: list[Path] = []

        def spy_escalation(*args: object, **kwargs: object):
            escalation_paths.append(args[0])  # type: ignore[arg-type]
            return real_lock(*args, **kwargs)

        monkeypatch.setattr(asset_preparation, "machine_file_lock", spy_escalation)
        calls = {"n": 0}

        def build() -> str:
            calls["n"] += 1
            if calls["n"] == 1:
                raise TornReadError(path=prepared.lock_path, role="destination_probe", lock_paths=prepared.lock_paths, anchor=prepared.anchor)
            return "ok"

        assert build_serialized(build) == "ok"
        assert escalation_paths == recheck_paths, (escalation_paths, recheck_paths)


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
        escalate) AND applying ``_mandatory_lock_read_simulation`` (Windows
        mandatory-lock semantics): any content read of a path this process
        holds in ``_HELD_LOCKS`` raises. The escalation must still converge,
        proving it never reads the held lock's bytes.
        """
        from specify_cli.tool_surface.operations import FileState

        bootstrap.ensure_runtime()  # materialize a warm home with a real owner lock
        lock_path = get_kittify_home() / "cache" / ".update.lock"
        assert lock_path.is_file(), "setup guard: the persistent owner lock must exist"
        inventory = get_kittify_home() / "cache" / "runtime_bootstrap-assets.json"

        peer = {"active": True}
        counter = {"n": 0}
        real_node_state = asset_preparation.node_state
        real_lock = asset_preparation.machine_file_lock
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

        def fake_machine_file_lock(*args: object, **kwargs: object):
            peer["active"] = False
            return real_lock(*args, **kwargs)

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
        prepared = AssetPreparation(_ANCHOR_LABEL, root, cache, ".test.lock", asset_preparation.ApplyConsent())
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


class TestStartupAssetErrorConstruction:
    """T006: MRO, JSON-safe path, code as a Python-only attribute."""

    def test_is_both_guarded_read_error_and_runtime_error(self) -> None:
        from kernel.errors import GuardedReadError

        error = asset_preparation.startup_asset_error(
            "runtime_bootstrap", (asset_preparation.Diagnostic("asset_torn_read", "runtime_bootstrap", "error", "Asset changed during preparation: /tmp/x"),)
        )
        assert isinstance(error, RuntimeError)
        assert isinstance(error, GuardedReadError)
        assert isinstance(error, StartupAssetError)

    def test_path_is_none_and_code_is_first_diagnostic(self) -> None:
        diagnostics = (asset_preparation.Diagnostic("asset_torn_read", "runtime_bootstrap", "error", "Asset changed during preparation: /tmp/x"),)
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
        init_calls = {"n": 0}
        real_init = AssetPreparation.__init__

        def counting_init(self: AssetPreparation, *args: object, **kwargs: object) -> None:
            init_calls["n"] += 1
            real_init(self, *args, **kwargs)

        lock_calls = _spy_lock(monkeypatch)
        monkeypatch.setattr(AssetPreparation, "__init__", counting_init)

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
        init_calls = {"n": 0}
        real_init = AssetPreparation.__init__

        def counting_init(self: AssetPreparation, *args: object, **kwargs: object) -> None:
            init_calls["n"] += 1
            real_init(self, *args, **kwargs)

        lock_calls = _spy_lock(monkeypatch)
        monkeypatch.setattr(AssetPreparation, "__init__", counting_init)

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
        init_calls = {"n": 0}
        real_init = AssetPreparation.__init__

        def counting_init(self: AssetPreparation, *args: object, **kwargs: object) -> None:
            init_calls["n"] += 1
            real_init(self, *args, **kwargs)

        lock_calls = _spy_lock(monkeypatch)
        monkeypatch.setattr(AssetPreparation, "__init__", counting_init)

        agent_commands.ensure_global_agent_commands()

        assert init_calls["n"] == 0
        assert lock_calls == []


class TestFR002BatchIncludeCalledOnce:
    """T007.13 (FR-002/C-003): the injected torn read must converge through
    ``assess_runtime()``/``assess_global_assets()`` directly, with
    ``_GlobalAssetPreparation.include`` called exactly once."""

    def test_batch_include_called_once_after_escalation(
        self,
        fake_home: Path,
        fake_package_assets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        inventory = get_kittify_home() / "cache" / "runtime_bootstrap-assets.json"
        peer = {"active": True}
        real_node_state = asset_preparation.node_state
        real_lock = asset_preparation.machine_file_lock
        counter = {"n": 0}

        def fake_node_state(path: Path, *, read_content: bool = True):
            if peer["active"] and path == inventory:
                counter["n"] += 1
                if counter["n"] % 2 == 1:
                    from specify_cli.tool_surface.operations import FileState

                    return FileState("absent")
                from specify_cli.tool_surface.operations import FileState

                return FileState("file", sha256=asset_preparation.digest(str(counter["n"]).encode()), mode=0o644)
            return real_node_state(path, read_content=read_content)

        def fake_lock(*args: object, **kwargs: object):
            peer["active"] = False
            return real_lock(*args, **kwargs)

        monkeypatch.setattr(asset_preparation, "node_state", fake_node_state)
        monkeypatch.setattr(asset_preparation, "machine_file_lock", fake_lock)

        include_calls = {"n": 0}
        real_include = asset_preparation._GlobalAssetPreparation.include

        def counting_include(self: object, *args: object, **kwargs: object) -> None:
            include_calls["n"] += 1
            return real_include(self, *args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(asset_preparation._GlobalAssetPreparation, "include", counting_include)

        direct = bootstrap.assess_runtime()
        assert direct.complete

        peer["active"] = True
        counter["n"] = 0
        include_calls["n"] = 0
        batch_assessment = asset_preparation.assess_global_assets(runtime=True, commands=False, skills=False)
        assert batch_assessment.complete
        assert include_calls["n"] == 1
