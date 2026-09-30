"""``ProtectionPolicy.resolve_for_owned`` -- the ONE owned mission-scoped protection fold.

Architecture review (merge ff666bbbe) item 2: the minter, the commit router,
finalize, the bookkeeping policy and ``safe_commit`` each carried their own
copy of "fold the owned mission's ``commit_to_target``", differing in which
roots' protection configs they read. They now share this one authority, whose
semantics are pinned here (the minter's):

* the protected set is the UNION of the repository root's and the owned
  checkout's configured ``protected_branches``;
* ``commit_to_target`` is read from the fact's own mission in the owned
  checkout (never the repository root's copy), fail-closed;
* only the fact's own mission is scoped -- another mission's slug gets none.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime import OwnedCheckout
from specify_cli.core.owned_mission import resolve_owned_create_root, resolve_owned_mission
from specify_cli.git.protection_policy import ProtectionPolicy

pytestmark = [pytest.mark.git_repo]

SLUG = "owned-scope-01M3A900"
TARGET = "codex/owned"


@pytest.fixture(autouse=True)
def _hatch_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", raising=False)


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


def _protect(root: Path, *branches: str) -> None:
    (root / ".kittify").mkdir(exist_ok=True)
    (root / ".kittify" / "config.yaml").write_text(f"protection:\n  protected_branches: [{', '.join(branches)}]\n", encoding="utf-8")


def _meta(mission_dir: Path, **fields: object) -> None:
    mission_dir.mkdir(parents=True, exist_ok=True)
    body = {"mission_id": "01M3A900000000000000000001", "mission_slug": SLUG, "slug": SLUG, "mission_type": "software-dev"}
    body |= {"topology": "single_branch", "target_branch": TARGET, "flattened": False, **fields}
    (mission_dir / "meta.json").write_text(json.dumps(body), encoding="utf-8")


def _pair(tmp_path: Path, *, r_protects: tuple[str, ...], opt_out: bool = True) -> tuple[Path, Path]:
    """R (``main``) protecting ``r_protects``, and P on ``TARGET`` holding the mission."""
    r_root = tmp_path / "primary"
    r_root.mkdir()
    _git(r_root, "init", "-q", "-b", "main")
    _git(r_root, "config", "user.email", "t@example.invalid")
    _git(r_root, "config", "user.name", "T")
    _git(r_root, "config", "commit.gpgsign", "false")
    _protect(r_root, *r_protects)
    _git(r_root, "add", ".")
    _git(r_root, "commit", "-qm", "seed")
    p_root = tmp_path / "owned"
    _git(r_root, "worktree", "add", "-qb", TARGET, str(p_root))
    _meta(p_root / "kitty-specs" / SLUG, **({"commit_to_target": True} if opt_out else {}))
    _git(p_root, "add", ".")
    _git(p_root, "commit", "-qm", "mission")
    return r_root, p_root


def _fact(r_root: Path, p_root: Path) -> OwnedCheckout:
    return resolve_owned_mission(r_root, p_root, SLUG)


def test_folds_the_facts_own_mission_opt_out(tmp_path: Path) -> None:
    r_root, p_root = _pair(tmp_path, r_protects=(TARGET, "main"))

    policy = ProtectionPolicy.resolve_for_owned(_fact(r_root, p_root))

    assert policy.is_protected(TARGET) is False
    assert policy.is_protected("main") is True


def test_the_repository_roots_copy_of_the_mission_is_never_read(tmp_path: Path) -> None:
    """R carries a flagged copy of the mission; P's (unflagged) copy is the one the fold reads."""
    r_root, p_root = _pair(tmp_path, r_protects=(TARGET,), opt_out=False)
    _meta(r_root / "kitty-specs" / SLUG, commit_to_target=True)
    # P is refused at mint (no opt-out in P), so exercise the create-root arm on the same pair.
    create_root = resolve_owned_create_root(r_root, p_root)

    assert ProtectionPolicy.resolve_for_owned(create_root.bind_mission(p_root / "kitty-specs" / SLUG)).is_protected(TARGET) is True


def test_protected_set_is_the_union_of_both_roots_configs(tmp_path: Path) -> None:
    r_root, p_root = _pair(tmp_path, r_protects=(TARGET, "release"))
    fact = _fact(r_root, p_root)
    _protect(p_root, TARGET, "p-only")  # P's own config drops "release" and adds "p-only"

    policy = ProtectionPolicy.resolve_for_owned(fact)

    assert policy.is_protected("release") is True
    assert policy.is_protected("p-only") is True
    assert policy.is_protected(TARGET) is False


def test_another_missions_slug_gets_no_scope(tmp_path: Path) -> None:
    r_root, p_root = _pair(tmp_path, r_protects=(TARGET,))

    assert ProtectionPolicy.resolve_for_owned(_fact(r_root, p_root), "some-other-mission").is_protected(TARGET) is True


def test_unreadable_owned_meta_fails_closed(tmp_path: Path) -> None:
    r_root, p_root = _pair(tmp_path, r_protects=(TARGET,))
    fact = _fact(r_root, p_root)
    (fact.mission_dir / "meta.json").write_text("{not json", encoding="utf-8")

    assert ProtectionPolicy.resolve_for_owned(fact).is_protected(TARGET) is True


def test_create_mission_fact_folds_its_bound_mission_only(tmp_path: Path) -> None:
    r_root, p_root = _pair(tmp_path, r_protects=(TARGET,))
    bound = resolve_owned_create_root(r_root, p_root).bind_mission(p_root / "kitty-specs" / SLUG)

    assert ProtectionPolicy.resolve_for_owned(bound).is_protected(TARGET) is False
    assert ProtectionPolicy.resolve_for_owned(bound, "some-other-mission").is_protected(TARGET) is True


def test_create_root_refuses_to_bind_a_directory_outside_its_checkout(tmp_path: Path) -> None:
    r_root, p_root = _pair(tmp_path, r_protects=(TARGET,))
    create_root = resolve_owned_create_root(r_root, p_root)

    with pytest.raises(ValueError, match="OwnedCreateMission invariant"):
        create_root.bind_mission(r_root / "kitty-specs" / SLUG)


def test_operator_hatch_still_unprotects_everything(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    r_root, p_root = _pair(tmp_path, r_protects=(TARGET, "main"))
    fact = _fact(r_root, p_root)
    monkeypatch.setenv("SPEC_KITTY_ALLOW_PROTECTED_BRANCH_COMMITS", "1")

    assert ProtectionPolicy.resolve_for_owned(fact).is_protected("main") is False


def test_minter_refuses_exactly_what_the_owned_fold_protects(tmp_path: Path) -> None:
    """The minter decides through the same fold: a mission without the opt-out on a protected target is refused."""
    from mission_runtime import ActionContextError

    r_root, p_root = _pair(tmp_path, r_protects=(TARGET,), opt_out=False)

    with pytest.raises(ActionContextError) as excinfo:
        _fact(r_root, p_root)
    assert excinfo.value.code == "OWNED_BRANCH_REFUSED"


def test_no_second_owned_fold_survives_in_src() -> None:
    """Item 2 pin: ``scoped_to_mission`` is applied only inside ``protection_policy``; no bare-dir entry point remains."""
    src = Path(__file__).resolve().parents[2] / "src"
    offenders: list[str] = []
    for path in sorted(src.rglob("*.py")):
        if path.name == "protection_policy.py":
            continue
        text = path.read_text(encoding="utf-8")
        for needle in (".scoped_to_mission(", "for_mission_dir", "mission_meta_dir"):
            if needle in text:
                offenders.append(f"{path.relative_to(src)}: {needle}")
    assert offenders == []
