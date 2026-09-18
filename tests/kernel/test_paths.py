"""Tests for kernel.paths — cross-platform path resolution.

These are the canonical tests for get_kittify_home() and
get_package_asset_root(). The functions were moved from
specify_cli.runtime.home into kernel.paths; specify_cli.runtime.home
is now a thin re-export shim covered by test_home_unit.py smoke tests.

Coverage:
- T004: Cross-platform kittify home resolution
- T005: SPEC_KITTY_HOME env-var override
- T006: Package asset root discovery (env-var + importlib)
- T011: Kill render_runtime_path mutants (WP03)
- T012: Kill get_kittify_home mutants (WP03)
- T013: Kill get_package_asset_root mutants (WP03)
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

import pytest

import kernel.paths as kernel_paths
from kernel.paths import (
    get_built_in_pack_root,
    get_kittify_home,
    get_package_asset_root,
    posix_tree_path,
    render_runtime_path,
    repo_tree_path,
    to_posix,
)
from tests.kernel.test_sibling_paths import build_post_relocation_wheel_shaped_site_packages

pytestmark = pytest.mark.fast


# ---------------------------------------------------------------------------
# T004: get_kittify_home — cross-platform default resolution
# ---------------------------------------------------------------------------


class TestGetKittifyHomeUnix:
    """Unix (macOS/Linux) default path resolution."""

    def test_unix_default_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """On Unix, default is ~/.kittify/."""
        monkeypatch.delenv("SPEC_KITTY_HOME", raising=False)
        monkeypatch.setattr("kernel.paths.is_windows", lambda: False)
        result = get_kittify_home()
        assert result == Path.home() / ".kittify"

    def test_returns_path_object(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Return type is Path, not str."""
        monkeypatch.delenv("SPEC_KITTY_HOME", raising=False)
        monkeypatch.setattr("kernel.paths.is_windows", lambda: False)
        assert isinstance(get_kittify_home(), Path)

    def test_returns_absolute_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Path is always absolute."""
        monkeypatch.delenv("SPEC_KITTY_HOME", raising=False)
        monkeypatch.setattr("kernel.paths.is_windows", lambda: False)
        assert get_kittify_home().is_absolute()


class TestGetKittifyHomeWindows:
    """Windows default path resolution via platformdirs (app name: spec-kitty)."""

    def test_windows_default_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """On Windows, default uses platformdirs user_data_dir('spec-kitty').

        The app name 'spec-kitty' (not 'kittify') ensures kernel.paths resolves
        to the same root as specify_cli.paths.get_runtime_root().base (FR-005 / C-002).
        """
        import platformdirs

        monkeypatch.delenv("SPEC_KITTY_HOME", raising=False)
        monkeypatch.setattr("kernel.paths.is_windows", lambda: True)
        monkeypatch.setattr(
            platformdirs,
            "user_data_dir",
            lambda *_a, **_kw: r"C:\Users\test\AppData\Local\spec-kitty",
        )
        result = get_kittify_home()
        assert result == Path(r"C:\Users\test\AppData\Local\spec-kitty")


# ---------------------------------------------------------------------------
# T005: SPEC_KITTY_HOME env-var override
# ---------------------------------------------------------------------------


class TestSpecKittyHomeEnvOverride:
    """SPEC_KITTY_HOME environment variable overrides default path."""

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """SPEC_KITTY_HOME overrides default on all platforms."""
        custom = str(tmp_path / "custom-kittify")
        monkeypatch.setenv("SPEC_KITTY_HOME", custom)
        assert get_kittify_home() == Path(custom)

    def test_env_override_on_windows(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """SPEC_KITTY_HOME takes precedence even on Windows."""
        custom = str(tmp_path / "custom-kittify")
        monkeypatch.setenv("SPEC_KITTY_HOME", custom)
        monkeypatch.setattr("kernel.paths.is_windows", lambda: True)
        assert get_kittify_home() == Path(custom)

    def test_env_override_returns_path(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Env override returns a Path object."""
        monkeypatch.setenv("SPEC_KITTY_HOME", str(tmp_path))
        assert isinstance(get_kittify_home(), Path)

    def test_empty_env_var_uses_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Empty SPEC_KITTY_HOME falls through to platform default."""
        monkeypatch.setenv("SPEC_KITTY_HOME", "")
        monkeypatch.setattr("kernel.paths.is_windows", lambda: False)
        # Empty string is falsy -> falls through
        assert get_kittify_home() == Path.home() / ".kittify"


# ---------------------------------------------------------------------------
# T005 (mission spec-kitty-home-isolation): SPEC_KITTY_HOME precedence flows
# into specify_cli.paths.get_runtime_root().base with the SAME walrus-falsy
# idiom as kernel.paths.get_kittify_home(). The two canonical home helpers must
# agree under the env override so the runtime state root and the asset home stay
# unified (FR-005 / C-002, FR-011, FR-012).
# ---------------------------------------------------------------------------


class TestRuntimeRootSpecKittyHomeParity:
    """get_runtime_root().base honors SPEC_KITTY_HOME exactly like get_kittify_home."""

    def test_runtime_root_base_matches_env(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A non-empty SPEC_KITTY_HOME becomes get_runtime_root().base verbatim."""
        from specify_cli.paths import get_runtime_root

        custom = str(tmp_path / "custom-home")
        monkeypatch.setenv("SPEC_KITTY_HOME", custom)
        assert get_runtime_root().base == Path(custom)

    def test_runtime_root_and_kittify_home_agree_under_env(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Under SPEC_KITTY_HOME both helpers resolve to the same path."""
        from specify_cli.paths import get_runtime_root

        custom = str(tmp_path / "shared-home")
        monkeypatch.setenv("SPEC_KITTY_HOME", custom)
        assert get_runtime_root().base == get_kittify_home()

    def test_empty_env_falls_through_for_runtime_root(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Empty SPEC_KITTY_HOME is falsy ⇒ POSIX ``~/.spec-kitty`` default."""
        from specify_cli.paths import get_runtime_root, windows_paths

        monkeypatch.setenv("SPEC_KITTY_HOME", "")
        monkeypatch.setattr(windows_paths, "_current_platform", lambda: "linux")
        assert get_runtime_root().base == Path.home() / ".spec-kitty"


# ---------------------------------------------------------------------------
# T006: get_package_asset_root — package asset discovery
# ---------------------------------------------------------------------------


class TestGetPackageAssetRoot:
    """Package asset discovery via SPEC_KITTY_TEMPLATE_ROOT and importlib."""

    def test_template_root_env_override(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """SPEC_KITTY_TEMPLATE_ROOT overrides package discovery."""
        missions = tmp_path / "missions"
        templates = missions / "software-dev" / "templates"
        templates.mkdir(parents=True)
        (templates / "plan-template.md").write_text("# Plan\n", encoding="utf-8")
        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(missions))
        assert get_package_asset_root() == missions

    def test_template_root_checkout_root_normalizes_to_doctrine_missions(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A checkout root env var resolves to src/charter/offering/missions.

        The fixture carries a realistic decoy at the checkout root itself
        (``docs/templates/index.md``, mirroring this real repository's own
        ``docs/templates/index.md``) that satisfies
        ``_looks_like_missions_root``'s loose ``*/templates/*.md`` content
        sniff just as well as the real missions directory does. Without the
        decoy this test cannot distinguish a correct implementation from one
        that tries the bare checkout-root candidate before the
        ``src/*/*/missions`` glob -- which would return the checkout root
        itself instead of ``src/charter/offering/missions`` (the WP04 cycle-1
        regression this decoy pins).
        """
        checkout = tmp_path / "spec-kitty"
        missions = checkout / "src" / "charter" / "offering" / "missions"
        templates = missions / "software-dev" / "templates"
        templates.mkdir(parents=True)
        (templates / "plan-template.md").write_text("# Plan\n", encoding="utf-8")

        decoy_templates = checkout / "docs" / "templates"
        decoy_templates.mkdir(parents=True)
        (decoy_templates / "index.md").write_text("# Docs\n", encoding="utf-8")

        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(checkout))

        assert get_package_asset_root() == missions

    def test_template_root_direct_legacy_missions_remaps_to_sibling_doctrine(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A direct stale specify_cli missions root resolves to doctrine assets."""
        checkout = tmp_path / "spec-kitty"
        stale_missions = checkout / "src" / "specify_cli" / "missions"
        stale_software_dev = stale_missions / "software-dev"
        stale_software_dev.mkdir(parents=True)
        (stale_software_dev / "mission.yaml").write_text("name: software-dev\n", encoding="utf-8")

        doctrine_missions = checkout / "src" / "charter" / "offering" / "missions"
        templates = doctrine_missions / "software-dev" / "templates"
        templates.mkdir(parents=True)
        (templates / "plan-template.md").write_text("# Plan\n", encoding="utf-8")

        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(stale_missions))

        assert get_package_asset_root() == doctrine_missions

    def test_template_root_legacy_package_asset_root_with_command_templates(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A direct package asset root with command templates remains valid."""
        package_assets = tmp_path / "pkg"
        command_templates = package_assets / "software-dev" / "command-templates"
        command_templates.mkdir(parents=True)
        (command_templates / "implement.md").write_text("# Implement\n", encoding="utf-8")

        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(package_assets))

        assert get_package_asset_root() == package_assets

    def test_template_root_legacy_package_asset_root_with_mission_yaml(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A direct package asset root with only mission YAML is incomplete."""
        package_assets = tmp_path / "pkg"
        mission = package_assets / "software-dev"
        mission.mkdir(parents=True)
        (mission / "mission.yaml").write_text("name: software-dev\n", encoding="utf-8")

        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(package_assets))

        with pytest.raises(FileNotFoundError, match="does not contain mission assets"):
            get_package_asset_root()

    def test_template_root_env_nonexistent_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """SPEC_KITTY_TEMPLATE_ROOT with invalid path raises FileNotFoundError."""
        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", "/nonexistent/path")
        with pytest.raises(FileNotFoundError, match="SPEC_KITTY_TEMPLATE_ROOT"):
            get_package_asset_root()

    def test_template_root_existing_invalid_dir_raises(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """SPEC_KITTY_TEMPLATE_ROOT must contain recognizable mission assets."""
        empty_root = tmp_path / "empty"
        empty_root.mkdir()

        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(empty_root))

        with pytest.raises(FileNotFoundError, match="does not contain mission assets"):
            get_package_asset_root()

    def test_importlib_discovery(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Falls through to importlib.resources when env var not set."""
        monkeypatch.delenv("SPEC_KITTY_TEMPLATE_ROOT", raising=False)
        result = get_package_asset_root()
        assert result.is_dir()
        assert result.name == "missions"

    def test_returns_path_object(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Return type is Path."""
        monkeypatch.delenv("SPEC_KITTY_TEMPLATE_ROOT", raising=False)
        assert isinstance(get_package_asset_root(), Path)

    def test_returns_existing_directory(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Returned path must exist as a directory."""
        monkeypatch.delenv("SPEC_KITTY_TEMPLATE_ROOT", raising=False)
        assert get_package_asset_root().is_dir()

    def test_importlib_failure_raises_file_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Raises FileNotFoundError when the kernel resolution primitive fails.

        Reimplemented for FR-004 (mission
        doctrine-consumer-surface-missions-extraction-01KZ6G6H):
        get_package_asset_root() no longer calls
        importlib.resources.files("charter.offering") directly (SC-002 forbids a
        doctrine-identifying string literal anywhere in src/kernel/) -- it
        delegates to kernel.sibling_paths.resolve_installed_sibling instead.
        This test now forces that primitive to fail, in place of the retired
        importlib seam it used to mock.
        """
        from kernel.sibling_paths import SiblingPathNotFound

        monkeypatch.delenv("SPEC_KITTY_TEMPLATE_ROOT", raising=False)

        def _raise(**_kwargs: object) -> Path:
            raise SiblingPathNotFound(PurePosixPath("missions"), Path("/nonexistent"))

        monkeypatch.setattr("kernel.paths.resolve_installed_sibling", _raise)
        with pytest.raises(FileNotFoundError, match="Cannot locate package mission assets"):
            get_package_asset_root()

    def test_env_var_takes_precedence_over_importlib(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Env var is checked before the kernel resolution primitive.

        Reimplemented for FR-004 (see
        ``test_importlib_failure_raises_file_not_found`` above): the retired
        importlib seam is replaced by mocking the primitive kernel.paths now
        delegates to, proving it is never even called when the env var wins.
        """
        missions = tmp_path / "missions"
        templates = missions / "software-dev" / "templates"
        templates.mkdir(parents=True)
        (templates / "plan-template.md").write_text("# Plan\n", encoding="utf-8")
        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(missions))
        # Even if the primitive would fail, the env var wins and it is never called.
        monkeypatch.setattr(
            "kernel.paths.resolve_installed_sibling",
            lambda **_kwargs: (_ for _ in ()).throw(AssertionError("should not be called")),
        )
        assert get_package_asset_root() == missions

    def test_resolves_in_a_wheel_layout_via_the_caller_s_own_pattern(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Binds ``kernel.paths``' own ``MISSION_ASSETS_SIBLING_PATTERN``, not a
        pattern written inside the test.

        ``TestWheelShapedAnchor`` (``test_sibling_paths.py``) proves the shared
        primitive resolves correctly *given* a bare ``"*/missions"`` pattern --
        but that pattern is supplied by the test itself, not by
        ``kernel.paths``. The WP04 cycle-1 defect was exactly that this
        module's own module-level constant carried a ``"src/*/missions"``
        shape that can never match an installed wheel (no ``src/`` directory
        exists at any level there). Reusing the same synthetic site-packages
        tree here, but calling the real public entry point
        (``get_package_asset_root``) with ``kernel.paths.__file__``
        monkeypatched to the synthetic anchor, exercises the actual committed
        constant: this test reds on the cycle-1 pattern and greens on the
        current one.

        **This is also the caller-level wheel test for mission #3091's own
        thesis (WP05, FR-005/SC-001).** Mission
        ``doctrine-consumer-surface-missions-extraction-01KZ6G6H`` relocated
        the missions data from ``src/charter/offering/missions`` to
        ``packs/built-in/missions``, so the fixture below
        (:func:`build_post_relocation_wheel_shaped_site_packages`) plants BOTH
        the real relocated data AND the still-existing, now data-less
        ``doctrine/missions`` package directory side by side in one synthetic
        wheel layout. This test only passes if the resolver finds the real
        data, not the data-less decoy -- it reds if
        ``MISSION_ASSETS_SIBLING_PATTERN`` ever regresses to a bare/wildcard
        ``"*/missions"`` shape, which would match the decoy at the
        site-packages ancestor before ever considering ``packs/built-in``.
        """
        site, anchor, _repository_anchor = build_post_relocation_wheel_shaped_site_packages(tmp_path)
        monkeypatch.setattr(kernel_paths, "__file__", str(anchor))
        monkeypatch.delenv("SPEC_KITTY_TEMPLATE_ROOT", raising=False)

        result = get_package_asset_root()

        assert result == site / "packs" / "built-in" / "missions"
        assert result != site / "doctrine" / "missions", (
            "get_package_asset_root() self-matched the data-less doctrine "
            "package directory instead of the relocated real data -- the "
            "exact self-match trap this mission's WP05 exists to close."
        )


class TestGetPackageAssetRootPacksRoot:
    """SPEC_KITTY_PACKS_ROOT relocates the built-in pack root (DR-1; C-R2/C-R3/C-R4).

    The unified resolver locates the ``built-in`` pack from the env-supplied
    pack root and the door returns ``<PACKS_ROOT>/built-in/missions`` through
    the kernel built-in-pack-root primitive. PACKS_ROOT governs pack-root
    *location* and wins over ``SPEC_KITTY_TEMPLATE_ROOT`` for it (C-R3); a pack
    root with no ``built-in/missions`` tree fails closed rather than falling
    through to a legacy layout (C-R4 / FR-013).
    """

    def test_packs_root_relocates_the_door(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A PACKS_ROOT with ``built-in/missions`` present resolves under it."""
        packs_root = tmp_path / "packs-root"
        missions = packs_root / "built-in" / "missions"
        missions.mkdir(parents=True)
        monkeypatch.delenv("SPEC_KITTY_TEMPLATE_ROOT", raising=False)
        monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(packs_root))

        assert get_package_asset_root() == missions

    def test_packs_root_without_missions_tree_fails_closed(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A PACKS_ROOT whose ``built-in`` has no ``missions`` leaf raises, no fall-through."""
        packs_root = tmp_path / "packs-root"
        # ``built-in`` exists (the env override resolves) but carries no
        # ``missions`` leaf: the door must fail closed, never fall through to a
        # legacy layout or the ancestor walk's real tree.
        (packs_root / "built-in").mkdir(parents=True)
        monkeypatch.delenv("SPEC_KITTY_TEMPLATE_ROOT", raising=False)
        monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(packs_root))

        with pytest.raises(FileNotFoundError):
            get_package_asset_root()

    def test_packs_root_wins_over_template_root(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """With BOTH env vars set, PACKS_ROOT governs pack-root location (C-R3)."""
        packs_root = tmp_path / "packs-root"
        packs_missions = packs_root / "built-in" / "missions"
        packs_missions.mkdir(parents=True)

        template_root = tmp_path / "template-root"
        template_templates = template_root / "software-dev" / "templates"
        template_templates.mkdir(parents=True)
        (template_templates / "plan-template.md").write_text("# Plan\n", encoding="utf-8")

        monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(packs_root))
        monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", str(template_root))

        assert get_package_asset_root() == packs_missions


class TestGetBuiltInPackRootMisconfiguredPacksRootWarning:
    """A set-but-unresolvable ``SPEC_KITTY_PACKS_ROOT`` now warns loudly (2026-08-07).

    Supersedes DR-1's original silent-parity framing (see the ADR addendum on
    ``docs/adr/3.x/2026-08-05-1-mission-type-availability-before-kind-promotion.md``):
    resolution stays fail-open (no raise, still falls back to the installed
    sibling), but the fallback is no longer silent -- ``get_built_in_pack_root``
    emits a ``UserWarning`` naming the misconfigured path. The warning must fire
    ONLY in that set-but-unresolvable case: not when the var is unset, and not
    when the override resolves cleanly.
    """

    def test_bogus_packs_root_warns_and_falls_back(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A nonexistent PACKS_ROOT warns, then still resolves via the ancestor walk."""
        site, anchor, _repository_anchor = build_post_relocation_wheel_shaped_site_packages(
            tmp_path
        )
        monkeypatch.setattr(kernel_paths, "__file__", str(anchor))
        bogus_root = tmp_path / "does-not-exist"
        monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(bogus_root))

        with pytest.warns(UserWarning, match="SPEC_KITTY_PACKS_ROOT"):
            result = get_built_in_pack_root()

        assert result == site / "packs" / "built-in"

    def test_unset_packs_root_emits_no_warning(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, recwarn: pytest.WarningsRecorder
    ) -> None:
        """No env var at all -- the ancestor walk resolves silently, no warning."""
        site, anchor, _repository_anchor = build_post_relocation_wheel_shaped_site_packages(
            tmp_path
        )
        monkeypatch.setattr(kernel_paths, "__file__", str(anchor))
        monkeypatch.delenv("SPEC_KITTY_PACKS_ROOT", raising=False)

        result = get_built_in_pack_root()

        assert result == site / "packs" / "built-in"
        assert len(recwarn.list) == 0, [str(w.message) for w in recwarn.list]

    def test_valid_packs_root_emits_no_warning(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, recwarn: pytest.WarningsRecorder
    ) -> None:
        """A PACKS_ROOT whose ``built-in`` child exists wins silently, no warning."""
        env_root = tmp_path / "env-packs"
        env_built_in = env_root / "built-in"
        env_built_in.mkdir(parents=True)

        # Anchor is irrelevant here since the valid override wins outright, but
        # point it at a real synthetic tree for realism/consistency with the
        # sibling tests above.
        site, anchor, _repository_anchor = build_post_relocation_wheel_shaped_site_packages(
            tmp_path
        )
        monkeypatch.setattr(kernel_paths, "__file__", str(anchor))
        monkeypatch.setenv("SPEC_KITTY_PACKS_ROOT", str(env_root))

        result = get_built_in_pack_root()

        assert result == env_built_in
        assert result != site / "packs" / "built-in"
        assert len(recwarn.list) == 0, [str(w.message) for w in recwarn.list]


class TestRenderRuntimePath:
    """User-facing rendering for runtime paths lives in kernel for shared use."""

    def test_windows_always_returns_absolute_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("kernel.paths.is_windows", lambda: True)
        rendered = render_runtime_path(Path("/nonexistent/spec-kitty/auth"))
        assert rendered == str(Path("/nonexistent/spec-kitty/auth").resolve(strict=False))

    def test_posix_tilde_compression_under_home(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr("kernel.paths.is_windows", lambda: False)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        rendered = render_runtime_path(tmp_path / ".kittify" / "auth")
        assert rendered == "~/.kittify/auth"

    def test_posix_outside_home_stays_absolute(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr("kernel.paths.is_windows", lambda: False)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        rendered = render_runtime_path(Path("/var/lib/spec-kitty"))
        assert rendered == str(Path("/var/lib/spec-kitty").resolve(strict=False))

    def test_for_user_false_disables_tilde_shortening(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr("kernel.paths.is_windows", lambda: False)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        rendered = render_runtime_path(tmp_path / ".kittify" / "auth", for_user=False)
        assert rendered == str((tmp_path / ".kittify" / "auth").resolve(strict=False))


# ---------------------------------------------------------------------------
# T011: Kill render_runtime_path survivors (WP03)
# ---------------------------------------------------------------------------


class TestRenderRuntimePathMutantKills:
    """Assertion-strengthening tests that pin render_runtime_path behaviour.

    Each test encodes the observable difference between the original source and
    a specific surviving mutant, per the mutation-aware-test-design styleguide.
    """

    def test_default_for_user_compresses_to_tilde_on_posix(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Default for_user=True must tilde-compress on POSIX.

        Kills __mutmut_1 (for_user default flipped from True to False): with
        for_user=False the function returns the absolute path, not the tilde
        form — so a call that omits the keyword must produce the tilde string.
        """
        monkeypatch.setattr("kernel.paths.is_windows", lambda: False)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        rendered = render_runtime_path(tmp_path / ".kittify" / "auth")
        assert rendered == "~/.kittify/auth"
        assert rendered.startswith("~/")

    def test_home_must_exist_when_resolving(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """home.resolve() uses strict=False so missing home does not raise.

        Kills __mutmut_11 (home resolve flipped to strict=True): if the home
        directory is missing and strict=True is used, Path.resolve() raises
        FileNotFoundError. The original, strict=False, must succeed and
        tilde-compress the target.
        """
        fake_home = tmp_path / "no-such-home-directory"
        assert not fake_home.exists()
        monkeypatch.setattr("kernel.paths.is_windows", lambda: False)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
        # Target path is beneath the (nonexistent) home root — should still
        # render as tilde form without raising FileNotFoundError.
        rendered = render_runtime_path(fake_home / ".kittify" / "state")
        assert rendered == "~/.kittify/state"

    def test_tilde_output_uses_forward_slash_separator(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Output uses forward-slash separator, never backslash.

        Kills __mutmut_21 (replace("\\\\", "/") mutated to replace("XX\\\\XX", "/"))
        and __mutmut_22 (replace("\\\\", "/") mutated to replace("\\\\", "XX/XX")).
        We cannot force backslashes into a POSIX Path literal, so we assert the
        observable invariant instead: the returned string contains forward
        slashes and no "XX" literal from a mangled replacement target/source.
        """
        monkeypatch.setattr("kernel.paths.is_windows", lambda: False)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        rendered = render_runtime_path(tmp_path / "nested" / "dir" / "file.txt")
        assert rendered == "~/nested/dir/file.txt"
        assert "XX" not in rendered
        assert "\\" not in rendered

    def test_path_resolve_accepts_nonexistent_target(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Target path resolve uses strict=False so missing target is ok.

        Documents the behaviour that __mutmut_3 (resolve(strict=None)) leaves
        unchanged because CPython treats None as falsy at the C layer, making
        that mutant equivalent. This test anchors the contract even so: a
        nonexistent target under home is rendered in tilde form.
        """
        monkeypatch.setattr("kernel.paths.is_windows", lambda: False)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        missing = tmp_path / ".kittify" / "never-created"
        assert not missing.exists()
        rendered = render_runtime_path(missing)
        assert rendered == "~/.kittify/never-created"


# ---------------------------------------------------------------------------
# T012: Kill get_kittify_home Windows-branch survivors (WP03)
# ---------------------------------------------------------------------------


class TestGetKittifyHomeWindowsPlatformdirsContract:
    """Pin the exact platformdirs.user_data_dir() call contract.

    These tests spy on user_data_dir and assert the three positional/keyword
    arguments — "spec-kitty", appauthor=False, roaming=False — are all passed
    unchanged. A single spy kills the ten surviving mutants that permute,
    replace, or drop one of those arguments.
    """

    def _install_platformdirs_spy(
        self, monkeypatch: pytest.MonkeyPatch, return_value: str
    ) -> list[tuple[tuple[Any, ...], dict[str, Any]]]:
        """Install a recording spy for platformdirs.user_data_dir.

        Returns a list that will accumulate (args, kwargs) tuples for each
        call — the test body inspects this list after invoking the code
        under test.
        """
        import platformdirs

        calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

        def _spy(*args: Any, **kwargs: Any) -> str:
            calls.append((args, kwargs))
            return return_value

        monkeypatch.setattr(platformdirs, "user_data_dir", _spy)
        monkeypatch.setattr("kernel.paths.is_windows", lambda: True)
        monkeypatch.delenv("SPEC_KITTY_HOME", raising=False)
        return calls

    def test_user_data_dir_receives_spec_kitty_app_name(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """First argument to user_data_dir must be the exact string 'spec-kitty'.

        Kills __mutmut_7 (app name -> None), __mutmut_10 (positional arg removed),
        __mutmut_13 ("XXspec-kittyXX"), and __mutmut_14 ("SPEC-KITTY").
        """
        calls = self._install_platformdirs_spy(monkeypatch, r"C:\fake")
        get_kittify_home()

        assert len(calls) == 1
        args, kwargs = calls[0]
        # The app name must be in the first positional slot OR in a kwarg
        # with key 'appname'. Either way it must equal exactly 'spec-kitty'.
        app_name: Any = args[0] if args else kwargs.get("appname")
        assert app_name == "spec-kitty"
        assert app_name != "SPEC-KITTY"
        assert "XX" not in str(app_name)

    def test_user_data_dir_receives_appauthor_false_explicitly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """appauthor must be passed as exactly False (not True, not omitted).

        Kills __mutmut_8 (appauthor=None), __mutmut_11 (appauthor kwarg removed),
        and __mutmut_15 (appauthor=True).
        """
        calls = self._install_platformdirs_spy(monkeypatch, r"C:\fake")
        get_kittify_home()

        args, kwargs = calls[0]
        assert "appauthor" in kwargs, "appauthor kwarg must be passed explicitly"
        assert kwargs["appauthor"] is False
        # Bi-Directional Logic: False and True are distinct observables.
        assert kwargs["appauthor"] is not True

    def test_user_data_dir_receives_roaming_false_explicitly(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """roaming must be passed as exactly False (not True, not omitted).

        Kills __mutmut_9 (roaming=None), __mutmut_12 (roaming kwarg removed),
        and __mutmut_16 (roaming=True). The FR-005/C-002 invariant requires
        roaming=False so that kernel.paths matches
        specify_cli.paths.get_runtime_root on Windows.
        """
        calls = self._install_platformdirs_spy(monkeypatch, r"C:\fake")
        get_kittify_home()

        args, kwargs = calls[0]
        assert "roaming" in kwargs, "roaming kwarg must be passed explicitly"
        assert kwargs["roaming"] is False
        assert kwargs["roaming"] is not True


# ---------------------------------------------------------------------------
# T013: Kill get_package_asset_root survivor (WP03)
# ---------------------------------------------------------------------------


class TestGetPackageAssetRootErrorMessage:
    """Pin the exact error message emitted when assets cannot be located."""

    def test_missing_assets_error_message_is_exact(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """FileNotFoundError message must be the plain English sentence.

        Kills __mutmut_17 (error string replaced with "XXCannot locate …XX").
        We assert the message starts with the real sentence and contains no
        mutmut sentinel markers, and also verify it contains the actionable
        remediation substring.

        Reimplemented for FR-004: forces the kernel resolution primitive (not
        the retired importlib.resources.files("charter.offering") seam -- see
        ``test_importlib_failure_raises_file_not_found`` above) to fail so we
        reach the final raise/translation.
        """
        from kernel.sibling_paths import SiblingPathNotFound

        monkeypatch.delenv("SPEC_KITTY_TEMPLATE_ROOT", raising=False)

        def _raise(**_kwargs: object) -> Path:
            raise SiblingPathNotFound(PurePosixPath("missions"), Path("/nonexistent"))

        monkeypatch.setattr("kernel.paths.resolve_installed_sibling", _raise)
        with pytest.raises(FileNotFoundError) as exc_info:
            get_package_asset_root()

        message = str(exc_info.value)
        assert message.startswith("Cannot locate package mission assets"), message
        assert "XX" not in message, f"mutmut sentinel leaked into message: {message!r}"
        assert "SPEC_KITTY_TEMPLATE_ROOT" in message
        assert "spec-kitty-cli" in message


# ---------------------------------------------------------------------------
# Forward-slash normalization seams: to_posix / posix_tree_path / repo_tree_path
# (#2836 — git HEAD:<path> / ls-files require forward slashes; the single
# behaviour-agnostic separator seam lives here in kernel).
# ---------------------------------------------------------------------------


class TestToPosix:
    """``to_posix`` normalizes Path and str inputs to forward slashes."""

    def test_purepath_uses_as_posix(self) -> None:
        assert to_posix(PurePosixPath("kitty-specs", "m", "spec.md")) == "kitty-specs/m/spec.md"

    def test_path_input(self) -> None:
        assert to_posix(Path("a") / "b" / "c.md") == "a/b/c.md"

    def test_str_with_backslashes_is_normalized(self) -> None:
        assert to_posix("a\\b\\c.md") == "a/b/c.md"

    def test_str_already_posix_is_unchanged(self) -> None:
        assert to_posix("a/b/c.md") == "a/b/c.md"


class TestPosixTreePath:
    """``posix_tree_path`` joins parts as a forward-slashed git tree path."""

    def test_multi_component(self) -> None:
        assert posix_tree_path(("kitty-specs", "slug", "spec.md")) == "kitty-specs/slug/spec.md"

    def test_single_component(self) -> None:
        assert posix_tree_path(("spec.md",)) == "spec.md"

    def test_empty_parts_returns_empty_string(self) -> None:
        # exercises the ``if parts else ""`` branch
        assert posix_tree_path(()) == ""

    def test_witnesses_windows_backslash_regression(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Substituting PureWindowsPath proves a reverted ``str(Path(*parts))``
        form would reintroduce backslashes; the PurePosixPath fix is immune."""
        monkeypatch.setattr("kernel.paths.Path", PureWindowsPath)
        assert posix_tree_path(("kitty-specs", "slug", "spec.md")) == "kitty-specs/slug/spec.md"
        assert "\\" not in posix_tree_path(("a", "b", "spec.md"))


class TestRepoTreePath:
    """``repo_tree_path`` resolves (git_cwd, forward-slashed tree path)."""

    def test_primary_checkout(self, tmp_path: Path) -> None:
        spec = tmp_path / "kitty-specs" / "slug" / "spec.md"
        spec.parent.mkdir(parents=True)
        spec.write_text("x", encoding="utf-8")
        git_cwd, tree_path = repo_tree_path(spec, tmp_path)
        assert git_cwd == tmp_path.resolve()
        assert tree_path == "kitty-specs/slug/spec.md"

    def test_linked_worktree_strips_worktree_prefix(self, tmp_path: Path) -> None:
        wt = tmp_path / ".worktrees" / "my-wt"
        spec = wt / "kitty-specs" / "slug" / "spec.md"
        spec.parent.mkdir(parents=True)
        spec.write_text("x", encoding="utf-8")
        git_cwd, tree_path = repo_tree_path(spec, tmp_path)
        assert git_cwd == wt.resolve()
        assert tree_path == "kitty-specs/slug/spec.md"

    def test_file_outside_repo_raises_value_error(self, tmp_path: Path) -> None:
        outside = tmp_path.parent / "elsewhere" / "spec.md"
        with pytest.raises(ValueError):
            repo_tree_path(outside, tmp_path / "repo")
