"""Unit tests for the validated ownership fact (owned-checkout-lifecycle-authority WP01, T003).

Pins every invariant and behaviour of ``mission_runtime.OwnedCheckout``,
including cross-platform identity (NFR-006). All construction goes through
``OwnedCheckout._mint`` (contract §1, "or a ``tests/`` helper"); gate G3
scans ``src/`` only.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

import kernel.paths as kernel_paths
from mission_runtime.context import MissionTopology
from mission_runtime.owned_checkout import (
    OwnedCheckout,
    OwnedCheckoutPathRefused,
    OwnedRefusalCode,
    _is_within,
    _MINT_TOKEN,
    _same_path,
)
from mission_runtime.resolution import ActionContextError

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _layout(tmp_path: Path, slug: str = "owned-01M1A900") -> tuple[Path, Path, Path]:
    repo = tmp_path / "repo"
    owned = tmp_path / "owned"
    mission = owned / "kitty-specs" / slug
    mission.mkdir(parents=True)
    repo.mkdir()
    return repo, owned, mission


def _mint(
    repo: Path,
    owned: Path,
    mission: Path,
    *,
    repository_root: Path | None = None,
    owned_root: Path | None = None,
    mission_dir: Path | None = None,
    mission_slug: str | None = None,
    topology: MissionTopology | None = None,
    target_branch: str | None = None,
) -> OwnedCheckout:
    """Mint a fact from the ``_layout`` triple, with per-field overrides.

    Explicit keyword-only override parameters (rather than ``**kwargs`` over
    a plain ``dict``) so every argument stays individually typed for mypy
    ``--strict`` -- no ``# type: ignore`` needed.
    """
    return OwnedCheckout._mint(
        repository_root=repository_root if repository_root is not None else repo,
        owned_root=owned_root if owned_root is not None else owned,
        mission_dir=mission_dir if mission_dir is not None else mission,
        mission_slug=mission_slug if mission_slug is not None else mission.name,
        topology=topology if topology is not None else MissionTopology.SINGLE_BRANCH,
        write_branch=target_branch if target_branch is not None else "codex/owned",
    )


# ---------------------------------------------------------------------------
# Sole construction (contract §1)
# ---------------------------------------------------------------------------


def test_direct_construction_raises_type_error(tmp_path: Path) -> None:
    repo, owned, mission = _layout(tmp_path)

    with pytest.raises(TypeError):
        OwnedCheckout(
            repository_root=repo,
            owned_root=owned,
            mission_dir=mission,
            mission_slug=mission.name,
            topology=MissionTopology.SINGLE_BRANCH,
            target_branch="codex/owned",
        )


def test_forged_token_raises_type_error(tmp_path: Path) -> None:
    repo, owned, mission = _layout(tmp_path)

    with pytest.raises(TypeError):
        OwnedCheckout(
            repository_root=repo,
            owned_root=owned,
            mission_dir=mission,
            mission_slug=mission.name,
            topology=MissionTopology.SINGLE_BRANCH,
            target_branch="codex/owned",
            _token=object(),
        )


def test_mint_token_is_not_reproducible_by_identity() -> None:
    """A caller cannot reconstruct the sentinel; only the module's own object works."""
    assert object() is not _MINT_TOKEN


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_mint_happy_path_resolves_fields(tmp_path: Path) -> None:
    repo, owned, mission = _layout(tmp_path)

    fact = _mint(repo, owned, mission)

    assert fact.repository_root == repo.resolve()
    assert fact.owned_root == owned.resolve()
    assert fact.mission_dir == mission.resolve()
    assert fact.mission_slug == mission.name
    assert fact.topology is MissionTopology.SINGLE_BRANCH
    assert fact.write_branch == "codex/owned"


# ---------------------------------------------------------------------------
# Invariants
# ---------------------------------------------------------------------------


def test_owned_root_equal_to_repository_root_raises(tmp_path: Path) -> None:
    repo, owned, mission = _layout(tmp_path)

    with pytest.raises(ValueError, match="owned_root must not be the repository root checkout"):
        _mint(repo, owned, mission, owned_root=repo)


def test_mission_dir_outside_kitty_specs_raises(tmp_path: Path) -> None:
    repo, owned, mission = _layout(tmp_path)
    outside = owned / "elsewhere"
    outside.mkdir()

    with pytest.raises(ValueError, match="mission_dir must be inside owned_root/kitty-specs"):
        _mint(repo, owned, mission, mission_dir=outside)


def test_mission_dir_name_mismatch_raises(tmp_path: Path) -> None:
    repo, owned, mission = _layout(tmp_path)

    with pytest.raises(ValueError, match="mission_dir.name must equal mission_slug"):
        _mint(repo, owned, mission, mission_slug="not-the-slug")


def test_dataclasses_replace_reruns_invariants(tmp_path: Path) -> None:
    repo, owned, mission = _layout(tmp_path)
    fact = _mint(repo, owned, mission)

    with pytest.raises(ValueError, match="owned_root must not be the repository root checkout"):
        dataclasses.replace(fact, owned_root=fact.repository_root)


def test_dataclasses_replace_with_valid_change_succeeds(tmp_path: Path) -> None:
    repo, owned, mission = _layout(tmp_path)
    fact = _mint(repo, owned, mission)

    replaced = dataclasses.replace(fact, write_branch="codex/other")

    assert replaced.write_branch == "codex/other"
    assert replaced.owned_root == fact.owned_root


# ---------------------------------------------------------------------------
# files()
# ---------------------------------------------------------------------------


def test_files_accepts_relative_path_inside(tmp_path: Path) -> None:
    repo, owned, mission = _layout(tmp_path)
    (mission / "spec.md").write_text("x", encoding="utf-8")
    fact = _mint(repo, owned, mission)

    resolved = fact.files([Path("kitty-specs") / mission.name / "spec.md"])

    assert resolved == [mission.resolve() / "spec.md"]


def test_files_refuses_dotdot_traversal(tmp_path: Path) -> None:
    repo, owned, mission = _layout(tmp_path)
    fact = _mint(repo, owned, mission)

    with pytest.raises(OwnedCheckoutPathRefused) as excinfo:
        fact.files([Path("..") / "escape.md"])

    assert excinfo.value.code == OwnedRefusalCode.OWNED_MISSION_PATH_REFUSED
    assert isinstance(excinfo.value, ActionContextError)


def test_files_refuses_absolute_path_outside(tmp_path: Path) -> None:
    repo, owned, mission = _layout(tmp_path)
    fact = _mint(repo, owned, mission)
    outside = tmp_path / "outside.md"
    outside.write_text("x", encoding="utf-8")

    with pytest.raises(OwnedCheckoutPathRefused):
        fact.files([outside])


def test_files_refuses_symlink_escape(tmp_path: Path) -> None:
    repo, owned, mission = _layout(tmp_path)
    fact = _mint(repo, owned, mission)
    outside_target = tmp_path / "outside_target.md"
    outside_target.write_text("x", encoding="utf-8")
    link = mission / "escape.md"
    try:
        link.symlink_to(outside_target)
    except OSError as exc:
        pytest.skip(f"platform cannot create symlinks: {exc}")

    with pytest.raises(OwnedCheckoutPathRefused):
        fact.files([Path("kitty-specs") / mission.name / "escape.md"])


def test_files_refuses_symlink_loop(tmp_path: Path) -> None:
    repo, owned, mission = _layout(tmp_path)
    fact = _mint(repo, owned, mission)
    a = mission / "a"
    b = mission / "b"
    try:
        a.symlink_to(b)
        b.symlink_to(a)
    except OSError as exc:
        pytest.skip(f"platform cannot create symlinks: {exc}")

    with pytest.raises(OwnedCheckoutPathRefused) as excinfo:
        fact.files([Path("kitty-specs") / mission.name / "a"])

    assert excinfo.value.code == OwnedRefusalCode.OWNED_MISSION_PATH_REFUSED
    assert isinstance(excinfo.value, ActionContextError)


# ---------------------------------------------------------------------------
# Equality / hashing / identity (NFR-006)
# ---------------------------------------------------------------------------


def test_two_mints_of_same_inputs_are_equal_and_hash_equal(tmp_path: Path) -> None:
    repo, owned, mission = _layout(tmp_path)

    first = _mint(repo, owned, mission)
    second = _mint(repo, owned, mission)

    assert first == second
    assert hash(first) == hash(second)


def test_symlink_alias_and_target_mint_to_equal_facts(tmp_path: Path) -> None:
    repo, owned, mission = _layout(tmp_path)
    link = tmp_path / "owned_link"
    try:
        link.symlink_to(owned)
    except OSError as exc:
        pytest.skip(f"platform cannot create symlinks: {exc}")

    via_link = _mint(repo, link, link / "kitty-specs" / mission.name)
    via_real = _mint(repo, owned, mission)

    assert via_link == via_real
    assert via_link.owned_root == owned.resolve()


def test_case_variant_owned_root_is_same_checkout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Runs on every platform: forces ``is_windows`` True via the module attribute ``owned_checkout`` actually reads.

    ``owned_checkout.py`` does ``import kernel.paths as kernel_paths`` and
    calls ``kernel_paths.is_windows()`` at call time, so patching the
    ``kernel.paths`` module attribute (the same object as this test's
    ``kernel_paths`` import) is observed. ``owned_root`` is built as a
    case-variant of ``repository_root`` with the mission dir placed under
    that SAME variant, so the same-checkout invariant is the only one that
    can fire (it is also checked first in ``__post_init__``, before the
    mission_dir invariant) -- pinning the exact case-folding bug the review
    caught: a swapcased ``owned_root`` unrelated to ``mission_dir`` let the
    *wrong* (mission_dir) invariant raise instead.
    """
    monkeypatch.setattr(kernel_paths, "is_windows", lambda: True)
    repo = tmp_path / "Repo"
    repo.mkdir()
    swapped_owned = Path(str(repo).swapcase())
    mission_dir = swapped_owned / "kitty-specs" / "owned-01M1A900"

    with pytest.raises(ValueError, match="must not be the repository root checkout"):
        OwnedCheckout._mint(
            repository_root=repo,
            owned_root=swapped_owned,
            mission_dir=mission_dir,
            mission_slug="owned-01M1A900",
            topology=MissionTopology.SINGLE_BRANCH,
            write_branch="codex/owned",
        )


@pytest.mark.windows_ci
@pytest.mark.unit
def test_case_variant_owned_root_is_same_checkout_native_windows(tmp_path: Path) -> None:
    """The same scenario as above, run natively on ``windows-latest`` with no monkeypatch."""
    repo = tmp_path / "Repo"
    repo.mkdir()
    swapped_owned = Path(str(repo).swapcase())
    mission_dir = swapped_owned / "kitty-specs" / "owned-01M1A900"

    with pytest.raises(ValueError, match="must not be the repository root checkout"):
        OwnedCheckout._mint(
            repository_root=repo,
            owned_root=swapped_owned,
            mission_dir=mission_dir,
            mission_slug="owned-01M1A900",
            topology=MissionTopology.SINGLE_BRANCH,
            write_branch="codex/owned",
        )


def test_same_path_case_folds_only_when_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Direct unit coverage of ``_same_path``'s two branches (not only through ``_mint``)."""
    a = Path("/Owned/Repo")
    b = Path("/owned/repo")

    monkeypatch.setattr(kernel_paths, "is_windows", lambda: False)
    assert not _same_path(a, b)

    monkeypatch.setattr(kernel_paths, "is_windows", lambda: True)
    assert _same_path(a, b)


def test_is_within_case_folds_only_when_windows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Direct unit coverage of ``_is_within``'s Windows normcase branch, including nested ancestors."""
    ancestor = Path("/Owned/KITTY-SPECS")
    case_variant_child = Path("/owned/kitty-specs/slug")
    unrelated = Path("/elsewhere/slug")

    monkeypatch.setattr(kernel_paths, "is_windows", lambda: False)
    assert not _is_within(case_variant_child, ancestor)
    assert not _is_within(unrelated, ancestor)

    monkeypatch.setattr(kernel_paths, "is_windows", lambda: True)
    assert _is_within(case_variant_child, ancestor)
    assert _is_within(ancestor, ancestor)
    assert not _is_within(unrelated, ancestor)


def test_windows_case_folding_is_not_full_unicode_casefold(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression (review-cycle-2): ``str.casefold()`` folds ``"ß"`` to ``"ss"``; Windows/NTFS/``PureWindowsPath``/
    ``ntpath.normcase`` do not -- that full-Unicode fold made ``_is_within`` fail open, treating a file in the
    *sibling* directory ``strasse/`` as inside the mission dir ``straße/``. ``ntpath.normcase`` is the correct,
    OS-independent stand-in for real Windows semantics (and exactly equals ``os.path.normcase`` when actually
    running on Windows), so a forced ``is_windows()`` on Linux CI still exercises the true behaviour.
    """
    monkeypatch.setattr(kernel_paths, "is_windows", lambda: True)

    # ASCII case-variant controls stay green (unchanged behaviour).
    assert _same_path(Path("/Owned/Repo"), Path("/owned/repo"))
    assert _is_within(Path("/owned/kitty-specs/slug"), Path("/Owned/KITTY-SPECS"))

    # The Unicode-folding regression itself.
    assert not _same_path(Path("/r/Straße"), Path("/r/STRASSE"))
    assert not _is_within(Path("/o/kitty-specs/strasse/x.md"), Path("/o/kitty-specs/straße"))


# ---------------------------------------------------------------------------
# Layer isolation (C-003)
# ---------------------------------------------------------------------------


def test_owned_checkout_module_declares_no_specify_cli_import() -> None:
    """Statically pins C-003: the module's own source imports nothing from ``specify_cli``.

    A *runtime* ``"specify_cli" not in sys.modules`` assertion after ``import
    mission_runtime.owned_checkout`` cannot be used here: importing a
    submodule always imports its parent package first, and
    ``mission_runtime/__init__.py`` already transitively imports
    ``specify_cli`` (pre-existing, unrelated to this module) via sibling
    submodules. The static source check plus ``test_layer_rules.py``'s
    ``mission_runtime -> specify_cli`` outbound ledger (which this module
    does not grow) are the two checks the T001 checklist names as
    alternatives.
    """
    import ast

    module_path = Path(__file__).resolve().parents[2] / "src" / "mission_runtime" / "owned_checkout.py"
    source = module_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(module_path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert not alias.name.startswith("specify_cli"), alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            assert not node.module.startswith("specify_cli"), node.module
