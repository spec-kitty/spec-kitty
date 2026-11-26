"""FR-010: the merge probes fail closed on effective merge attributes and drivers.

``git_probes.n_way_merge_blob`` (the clean-fold recognizer) and
``git_probes.merge_own_changed_paths`` (the own-content probe) re-run git's merge.
git honours clone-local and unreviewed merge settings while it does so, so each
route below can make arbitrary bytes look like a clean merge, or a hand resolution
look like "no own content". Both probes must raise ``GitProbeError`` instead.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import pytest

from specify_cli.consolidation import git_probes
from specify_cli.consolidation.git_probes import GitProbeError

pytestmark = pytest.mark.git_repo

#: The union of the two conflicting edits: what ``merge=union`` writes, and the hand resolution of ``M``.
UNION_BYTES = "ONE\nTWO\nb\nc\n"

#: A driver that writes the hand resolution's bytes and exits 0: a forged "clean" merge.
FORGE_DRIVER = r"printf 'ONE\nTWO\nb\nc\n' > %A; true"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


def _write(repo: Path, rel: str, body: str) -> None:
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")


def _commit(repo: Path, branch: str, rel: str, body: str) -> str:
    _git(repo, "checkout", "-q", branch)
    _write(repo, rel, body)
    _git(repo, "add", rel)
    _git(repo, "commit", "-qm", f"edit {rel} on {branch}")
    return _git(repo, "rev-parse", "HEAD")


def _init(root: Path) -> Path:
    subprocess.run(["git", "init", "-qb", "main", str(root)], check=True)
    for key, value in (("user.email", "t@t.co"), ("user.name", "T"), ("commit.gpgsign", "false")):
        _git(root, "config", key, value)
    return root


class Conflict:
    """``main`` with *path* = ``a b c``; ``one`` and ``two`` edit line 1; ``merge`` is a hand merge of them."""

    def __init__(self, root: Path, path: str) -> None:
        self.repo = _init(root)
        self.path = path
        _write(self.repo, path, "a\nb\nc\n")
        _write(self.repo, "q.py", "x\n")
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-qm", "base")
        self.base = _git(self.repo, "rev-parse", "HEAD")
        _git(self.repo, "branch", "one")
        _git(self.repo, "branch", "two")
        self.one = _commit(self.repo, "one", path, "ONE\nb\nc\n")
        self.two = _commit(self.repo, "two", path, "TWO\nb\nc\n")
        precondition = subprocess.run(["git", "-C", str(self.repo), "merge-tree", "--write-tree", self.one, self.two], capture_output=True, text=True, check=False)
        assert precondition.returncode == 1, "fixture must conflict on the probed path"
        _git(self.repo, "checkout", "-q", "one")
        subprocess.run(["git", "-C", str(self.repo), "merge", "--no-commit", "two"], capture_output=True, check=False)
        _write(self.repo, path, UNION_BYTES)
        _git(self.repo, "add", path)
        _git(self.repo, "commit", "-qm", "hand merge")
        self.merge = _git(self.repo, "rev-parse", "HEAD")
        assert git_probes.merge_own_changed_paths(self.repo, self.merge) == [path], "without attributes the hand resolution is own content"

    def info_attributes(self, line: str) -> None:
        info = Path(_git(self.repo, "rev-parse", "--git-common-dir"))
        info = info if info.is_absolute() else self.repo / info
        (info / "info").mkdir(parents=True, exist_ok=True)
        with (info / "info" / "attributes").open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


@pytest.fixture
def conflict(tmp_path: Path) -> Conflict:
    return Conflict(tmp_path / "repo", "p.py")


def _route_info_attributes(c: Conflict, tmp_path: Path) -> None:
    c.info_attributes(f"{c.path} merge=union")


def _route_worktree_gitattributes(c: Conflict, tmp_path: Path) -> None:
    _write(c.repo, ".gitattributes", f"{c.path} merge=union\n")


def _route_core_attributes_file(c: Conflict, tmp_path: Path) -> None:
    outside = tmp_path / "global-attributes"
    outside.write_text(f"{c.path} merge=union\n", encoding="utf-8")
    _git(c.repo, "config", "core.attributesFile", str(outside))


def _route_custom_driver(c: Conflict, tmp_path: Path) -> None:
    c.info_attributes(f"{c.path} merge=evil")
    _git(c.repo, "config", "merge.evil.driver", FORGE_DRIVER)


def _route_merge_default(c: Conflict, tmp_path: Path) -> None:
    _git(c.repo, "config", "merge.default", "union")


def _route_binary_redefined(c: Conflict, tmp_path: Path) -> None:
    c.info_attributes(f"{c.path} merge=binary")
    _git(c.repo, "config", "merge.binary.driver", FORGE_DRIVER)


def _route_text_redefined(c: Conflict, tmp_path: Path) -> None:
    c.info_attributes(f"{c.path} merge=text")
    _git(c.repo, "config", "merge.text.driver", FORGE_DRIVER)


def _route_registered_redefined(c: Conflict, tmp_path: Path) -> None:
    c.info_attributes(f"{c.path} merge=spec-kitty-meta")
    _git(c.repo, "config", "merge.spec-kitty-meta.driver", FORGE_DRIVER)


def _route_registered_shipped_wrong_pattern(c: Conflict, tmp_path: Path) -> None:
    c.info_attributes(f"{c.path} merge=spec-kitty-meta")
    _git(c.repo, "config", "merge.spec-kitty-meta.driver", "spec-kitty merge-driver-meta %O %A %B")


#: (route id, probed path, setup, text the refusal must name besides the path)
ATTACKS = [
    pytest.param("p.py", _route_info_attributes, "union", id="info_attributes"),
    pytest.param("p.py", _route_worktree_gitattributes, "union", id="worktree_gitattributes"),
    pytest.param("p.py", _route_core_attributes_file, "union", id="core_attributes_file"),
    pytest.param("p.py", _route_custom_driver, "evil", id="custom_driver"),
    pytest.param("p.py", _route_merge_default, "merge.default", id="merge_default"),
    pytest.param("p.py", _route_binary_redefined, "merge.binary.driver", id="builtin_binary_redefined"),
    pytest.param("p.py", _route_text_redefined, "merge.text.driver", id="builtin_text_redefined"),
    pytest.param("p.py", _route_registered_redefined, "spec-kitty-meta", id="registered_driver_redefined_wrong_pattern"),
    pytest.param("kitty-specs/m/meta.json", _route_registered_redefined, "merge.spec-kitty-meta.driver", id="registered_driver_redefined_on_its_pattern"),
    pytest.param("p.py", _route_registered_shipped_wrong_pattern, "spec-kitty-meta", id="registered_driver_shipped_command_wrong_pattern"),
]


@pytest.mark.parametrize(("path", "route", "named"), ATTACKS)
def test_n_way_merge_blob_refuses_an_unregistered_merge_route(tmp_path: Path, path: str, route: Callable[[Conflict, Path], None], named: str) -> None:
    c = Conflict(tmp_path / "repo", path)
    route(c, tmp_path)
    with pytest.raises(GitProbeError) as caught:
        git_probes.n_way_merge_blob(c.repo, [c.one, c.two], path)
    assert path in str(caught.value)
    assert named in str(caught.value)


@pytest.mark.parametrize(("path", "route", "named"), ATTACKS)
def test_merge_own_changed_paths_refuses_an_unregistered_merge_route(tmp_path: Path, path: str, route: Callable[[Conflict, Path], None], named: str) -> None:
    c = Conflict(tmp_path / "repo", path)
    route(c, tmp_path)
    with pytest.raises(GitProbeError) as caught:
        git_probes.merge_own_changed_paths(c.repo, c.merge)
    assert path in str(caught.value)
    assert named in str(caught.value)


def test_an_attribute_on_another_path_does_not_refuse(conflict: Conflict) -> None:
    """The guard is per path: ``q.py merge=union`` says nothing about ``p.py``, which the merge touched and ``q.py`` is untouched."""
    conflict.info_attributes("q.py merge=union")
    assert git_probes.n_way_merge_blob(conflict.repo, [conflict.one, conflict.two], "p.py") is None
    assert git_probes.merge_own_changed_paths(conflict.repo, conflict.merge) == ["p.py"]


def test_union_on_a_non_conflicting_path_still_refuses(tmp_path: Path) -> None:
    """Over-refusal is the accepted fail-closed direction: a clean union fold is not trusted either."""
    repo = _init(tmp_path / "repo")
    _write(repo, "p.py", "a\nb\nc\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "branch", "one")
    _git(repo, "branch", "two")
    one = _commit(repo, "one", "p.py", "ONE\nb\nc\n")
    two = _commit(repo, "two", "p.py", "a\nb\nTHREE\n")
    _write(repo, ".gitattributes", "p.py merge=union\n")
    with pytest.raises(GitProbeError, match="p.py"):
        git_probes.n_way_merge_blob(repo, [one, two], "p.py")


def test_merge_own_changed_paths_guards_paths_changed_against_either_parent(tmp_path: Path) -> None:
    """A union path changed only against the SECOND parent still refuses (a first-parent-only listing would miss it)."""
    repo = _init(tmp_path / "repo")
    _write(repo, "p.py", "a\nb\nc\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "branch", "two")
    _commit(repo, "main", "p.py", UNION_BYTES)
    _commit(repo, "two", "q.py", "x\n")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--no-edit", "two")
    merge = _git(repo, "rev-parse", "HEAD")
    assert "p.py" not in git_probes.first_parent_changed_paths(repo, merge)
    _write(repo, ".gitattributes", "p.py merge=union\n")
    with pytest.raises(GitProbeError, match="p.py"):
        git_probes.merge_own_changed_paths(repo, merge)


def test_n_way_merge_blob_single_commit_is_not_guarded(conflict: Conflict) -> None:
    conflict.info_attributes("p.py merge=union")
    assert git_probes.n_way_merge_blob(conflict.repo, [conflict.one], "p.py") == git_probes.path_state_at(conflict.repo, conflict.one, "p.py")


def test_git_version_is_read_once_per_run_scope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from kernel.git.read_cache import git_read_cache_scope
    from specify_cli.git.merge_tree_probe import check_attr_source_available, merge_tree_write_tree_available, remerge_diff_available

    repo = _init(tmp_path / "repo")
    _write(repo, "f", "x\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    real_run = subprocess.run
    version_calls: list[list[str]] = []

    def spy(argv: Sequence[str], *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[Any]:
        if list(argv) == ["git", "--version"]:
            version_calls.append(list(argv))
        return real_run(argv, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", spy)
    with git_read_cache_scope():
        for _ in range(3):
            assert remerge_diff_available(repo)
            assert merge_tree_write_tree_available(repo)
            assert check_attr_source_available(repo)
    assert len(version_calls) == 1, "NFR-001: one git --version per run scope, whichever probe asks"
    version_calls.clear()
    assert remerge_diff_available(repo)
    assert remerge_diff_available(repo)
    assert len(version_calls) == 2


# ---------------------------------------------------------------------------
# T002: the registry accessor and its drift guard
# ---------------------------------------------------------------------------


def test_registered_merge_driver_specs_agree_with_the_attribute_lines() -> None:
    from specify_cli.lanes.consolidation import merge_driver_attribute_lines, registered_merge_driver_specs

    specs = registered_merge_driver_specs()
    assert specs
    assert all(pattern.startswith("kitty-specs/") for _key, _command, pattern in specs)
    assert tuple(dict.fromkeys(f"{pattern} merge={key}" for key, _cmd, pattern in specs)) == merge_driver_attribute_lines()


# ---------------------------------------------------------------------------
# T003: the guard's pure parts
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "kitty-specs/a/status.events.jsonl",
        "kitty-specs/status.events.jsonl",
        "kitty-specs/a/b/status.events.jsonl",
        "kitty-specs/a/b/tasks/WP01/review-cycle-1.md",
        "kitty-specs/m/tasks/WP01/review-cycle-2.md",
        "kitty-specs/a/meta.json",
        "kitty-specs/a/traces/approach.md",
    ],
)
def test_registered_patterns_match_their_paths(path: str) -> None:
    from specify_cli.consolidation.merge_attribute_guard import _matches_registered_pattern
    from specify_cli.lanes.consolidation import registered_merge_driver_specs

    assert any(_matches_registered_pattern(pattern, path) for _key, _command, pattern in registered_merge_driver_specs())


@pytest.mark.parametrize(
    "path",
    [
        "src/kitty-specs/a/meta.json",
        "kitty-specs/a/meta.json.bak",
        "kitty-specs/a/traces/x/y.md",
        "kitty-specs/m/tasks/WP01/sub/review-cycle-2.md",
        "p.py",
    ],
)
def test_registered_patterns_do_not_match_other_paths(path: str) -> None:
    from specify_cli.consolidation.merge_attribute_guard import _matches_registered_pattern
    from specify_cli.lanes.consolidation import registered_merge_driver_specs

    assert not any(_matches_registered_pattern(pattern, path) for _key, _command, pattern in registered_merge_driver_specs())


@pytest.mark.parametrize(
    "pattern", ["kitty-specs/[ab]/meta.json", "kitty-specs/?/meta.json", "kitty-specs/a\\b", "kitty-specs/a/**", "src/*.py", "kitty-specs/a**b"]
)
def test_an_unsupported_pattern_shape_refuses(pattern: str) -> None:
    from specify_cli.consolidation.merge_attribute_guard import _matches_registered_pattern

    with pytest.raises(GitProbeError):
        _matches_registered_pattern(pattern, "kitty-specs/a/meta.json")


_SHIPPED_META = "spec-kitty merge-driver-meta %O %A %B"


def _config(*names: str, drivers: dict[str, str] | None = None) -> Any:
    """A :class:`MergeConfig` from configured key names (``merge.default``, ``merge.<name>.<variable>``) and driver commands."""
    from specify_cli.consolidation.merge_attribute_guard import DriverConfig, MergeConfig

    drivers = drivers or {}
    per_name: dict[str, DriverConfig] = {}
    for key in names:
        if key == "merge.default":
            continue
        _section, name, variable = key.split(".", 2)
        current = per_name.get(name, DriverConfig())
        per_name[name] = DriverConfig(
            driver=drivers.get(name, "x") if variable == "driver" else current.driver,
            recursive=current.recursive or variable == "recursive",
            any_key=True,
        )
    return MergeConfig(merge_default="merge.default" in names, names=per_name)


def _registry() -> Any:
    from specify_cli.consolidation.merge_attribute_guard import _registry as registry

    return registry()


@pytest.mark.parametrize(
    ("path", "value", "names", "drivers"),
    [
        pytest.param("p.py", "unspecified", (), {}, id="unspecified"),
        pytest.param("p.py", "set", ("merge.default",), {}, id="set"),
        pytest.param("p.py", "unset", ("merge.default",), {}, id="unset"),
        pytest.param("p.py", "text", ("merge.binary.driver",), {}, id="text_no_driver"),
        pytest.param("p.py", "binary", (), {}, id="binary_no_driver"),
        pytest.param("kitty-specs/m/meta.json", "spec-kitty-meta", (), {}, id="registered_no_config"),
        pytest.param(
            "kitty-specs/m/meta.json",
            "spec-kitty-meta",
            ("merge.spec-kitty-meta.name", "merge.spec-kitty-meta.driver"),
            {"spec-kitty-meta": _SHIPPED_META},
            id="registered_shipped",
        ),
    ],
)
def test_path_refusal_allows(path: str, value: str, names: tuple[str, ...], drivers: dict[str, str]) -> None:
    from specify_cli.consolidation.merge_attribute_guard import _path_refusal

    assert _path_refusal(path, value, _config(*names, drivers=drivers), _registry()) == ""


@pytest.mark.parametrize(
    ("path", "value", "names", "drivers", "named"),
    [
        pytest.param("p.py", "union", (), {}, "union", id="union"),
        pytest.param("p.py", "evil", (), {}, "evil", id="custom_name"),
        pytest.param("p.py", "unspecified", ("merge.default",), {}, "merge.default", id="merge_default"),
        pytest.param("p.py", "text", ("merge.text.driver",), {}, "merge.text.driver", id="text_with_driver"),
        pytest.param("p.py", "binary", ("merge.binary.driver",), {}, "merge.binary.driver", id="binary_with_driver"),
        pytest.param("p.py", "binary", ("merge.binary.recursive",), {}, "merge.binary.recursive", id="binary_with_recursive"),
        pytest.param("p.py", "text", ("merge.text.name",), {}, "merge.text.*", id="text_with_any_key"),
        pytest.param("p.py", "spec-kitty-meta", (), {}, "outside its registered pattern", id="registered_wrong_path"),
        pytest.param(
            "kitty-specs/m/meta.json",
            "spec-kitty-meta",
            ("merge.spec-kitty-meta.driver",),
            {"spec-kitty-meta": "true"},
            _SHIPPED_META,
            id="registered_wrong_command",
        ),
        pytest.param(
            "kitty-specs/m/meta.json",
            "spec-kitty-meta",
            ("merge.spec-kitty-meta.driver",),
            {"spec-kitty-meta": _SHIPPED_META + "\nprintf EVIL > %A"},
            "merge.spec-kitty-meta.driver",
            id="registered_command_with_a_second_line",
        ),
        pytest.param(
            "kitty-specs/m/meta.json", "spec-kitty-meta", ("merge.spec-kitty-meta.recursive",), {}, "merge.spec-kitty-meta.recursive", id="registered_recursive"
        ),
    ],
)
def test_path_refusal_refuses(path: str, value: str, names: tuple[str, ...], drivers: dict[str, str], named: str) -> None:
    from specify_cli.consolidation.merge_attribute_guard import _path_refusal

    reason = _path_refusal(path, value, _config(*names, drivers=drivers), _registry())
    assert path in reason
    assert f"'{value}'" in reason
    assert named in reason


# ---------------------------------------------------------------------------
# T003: the guard against real git
# ---------------------------------------------------------------------------


def _count_git(monkeypatch: pytest.MonkeyPatch, subcommand: str) -> list[list[str]]:
    real_run = subprocess.run
    calls: list[list[str]] = []

    def spy(argv: Sequence[str], *args: Any, **kwargs: Any) -> subprocess.CompletedProcess[Any]:
        if len(argv) > 1 and argv[0] == "git" and argv[1] == subcommand:
            calls.append(list(argv))
        return real_run(argv, *args, **kwargs)

    monkeypatch.setattr(subprocess, "run", spy)
    return calls


def test_three_paths_cost_one_check_attr_process(conflict: Conflict, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.consolidation.merge_attribute_guard import assert_registered_merge_behaviour

    calls = _count_git(monkeypatch, "check-attr")
    assert_registered_merge_behaviour(conflict.repo, ["p.py", "q.py", "kitty-specs/m/meta.json"])
    assert len(calls) == 1


def test_empty_paths_spawn_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.consolidation.merge_attribute_guard import assert_registered_merge_behaviour

    calls = _count_git(monkeypatch, "check-attr")
    assert_registered_merge_behaviour(tmp_path, [])
    assert calls == []


def test_a_git_failure_raises(tmp_path: Path) -> None:
    from specify_cli.consolidation.merge_attribute_guard import assert_registered_merge_behaviour

    outside = tmp_path / "not-a-repo"
    outside.mkdir()
    with pytest.raises(GitProbeError, match="check-attr"):
        assert_registered_merge_behaviour(outside, ["p.py"])


@pytest.mark.parametrize("path", ["a\nb.py", '"quoted.py', ""])
def test_a_path_check_attr_cannot_read_refuses(conflict: Conflict, path: str) -> None:
    from specify_cli.consolidation.merge_attribute_guard import assert_registered_merge_behaviour

    with pytest.raises(GitProbeError, match="cannot be passed"):
        assert_registered_merge_behaviour(conflict.repo, [path])


def test_a_line_count_mismatch_refuses(conflict: Conflict, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.consolidation import merge_attribute_guard

    real_run_git = merge_attribute_guard._run_git

    def short(repo_root: Path, argv: Sequence[str], stdin: str | None = None) -> subprocess.CompletedProcess[str]:
        if argv[0] != "check-attr":
            return real_run_git(repo_root, argv, stdin)
        return subprocess.CompletedProcess(["git", *argv], 0, stdout="p.py: merge: unspecified\n", stderr="")

    monkeypatch.setattr(merge_attribute_guard, "_run_git", short)
    with pytest.raises(GitProbeError, match="2 path"):
        merge_attribute_guard.assert_registered_merge_behaviour(conflict.repo, ["p.py", "q.py"])


def test_a_git_that_cannot_start_refuses(conflict: Conflict, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.consolidation import merge_attribute_guard

    def missing(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("git")

    monkeypatch.setattr(subprocess, "run", missing)
    with pytest.raises(GitProbeError, match="could not be started"):
        merge_attribute_guard.assert_registered_merge_behaviour(conflict.repo, ["p.py"])


def test_config_reads_are_live_inside_a_run_scope(conflict: Conflict, monkeypatch: pytest.MonkeyPatch) -> None:
    """#5604 review fold I2 (replaces the run-scoped cache pin): every guard call reads its config again.

    The read cache fingerprints only the repository's own config files, so a cached answer could go
    stale when global, system or ``include.path`` config changes; the reads are a few cheap ``git config --get``.
    """
    from kernel.git.read_cache import git_read_cache_scope
    from specify_cli.consolidation.merge_attribute_guard import assert_registered_merge_behaviour

    calls = _count_git(monkeypatch, "config")
    with git_read_cache_scope():
        assert_registered_merge_behaviour(conflict.repo, ["p.py"])
        first = len(calls)
        assert_registered_merge_behaviour(conflict.repo, ["p.py"])
    assert first >= 1
    assert len(calls) == 2 * first, "each call reads the merge config itself"


def _shared_text_repo(tmp_path: Path) -> Path:
    repo = _init(tmp_path / "repo")
    _write(repo, ".gitattributes", "shared.py merge=text\n")
    _write(repo, "shared.py", "x\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "attrs")
    return repo


def test_a_driver_added_through_an_included_config_file_mid_run_refuses(tmp_path: Path) -> None:
    """#5604 review fold I2: the guard's config reads are not cached, so an ``include.path`` driver added mid-run is seen.

    Red before the fold: the run-scoped cache fingerprinted only ``.git/config`` and served the
    pre-change answer, while the merge itself honoured the new driver.
    """
    from kernel.git.read_cache import git_read_cache_scope
    from specify_cli.consolidation.merge_attribute_guard import assert_registered_merge_behaviour

    repo = _shared_text_repo(tmp_path)
    included = tmp_path / "included.cfg"
    included.write_text("", encoding="utf-8")
    _git(repo, "config", "include.path", str(included))
    with git_read_cache_scope():
        assert_registered_merge_behaviour(repo, ["shared.py"])
        included.write_text(f'[merge "text"]\n\tdriver = {FORGE_DRIVER}\n', encoding="utf-8")
        with pytest.raises(GitProbeError, match="merge.text.driver"):
            assert_registered_merge_behaviour(repo, ["shared.py"])


def test_a_driver_added_to_the_global_config_mid_run_refuses(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#5604 review fold I2: a ``$HOME/.gitconfig`` driver added mid-run is seen too (global scope, outside ``.git``)."""
    from kernel.git.read_cache import git_read_cache_scope
    from specify_cli.consolidation.merge_attribute_guard import assert_registered_merge_behaviour

    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.delenv("GIT_CONFIG_GLOBAL", raising=False)
    monkeypatch.delenv("GIT_CONFIG_NOSYSTEM", raising=False)
    repo = _shared_text_repo(tmp_path)
    with git_read_cache_scope():
        assert_registered_merge_behaviour(repo, ["shared.py"])
        (home / ".gitconfig").write_text(f'[merge "text"]\n\tdriver = {FORGE_DRIVER}\n', encoding="utf-8")
        with pytest.raises(GitProbeError, match="merge.text.driver"):
            assert_registered_merge_behaviour(repo, ["shared.py"])


def test_check_attr_is_not_cached(conflict: Conflict) -> None:
    from kernel.git.read_cache import git_read_cache_scope
    from specify_cli.consolidation.merge_attribute_guard import assert_registered_merge_behaviour

    with git_read_cache_scope():
        assert_registered_merge_behaviour(conflict.repo, ["p.py"])
        _write(conflict.repo, ".gitattributes", "p.py merge=union\n")
        with pytest.raises(GitProbeError, match="union"):
            assert_registered_merge_behaviour(conflict.repo, ["p.py"])


@pytest.mark.parametrize(
    "first",
    ["specify_cli.consolidation.merge_attribute_guard", "specify_cli.consolidation.git_probes", "specify_cli.lanes.consolidation"],
)
def test_the_guard_imports_without_a_cycle(first: str) -> None:
    import sys

    code = f"import {first}; import specify_cli.consolidation.merge_attribute_guard as g; g._registry()"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


# ---------------------------------------------------------------------------
# T005: spec-kitty's own drivers and committed attributes
# ---------------------------------------------------------------------------


def _mission_repo(root: Path, *, install_drivers: bool) -> tuple[Path, str]:
    """Two lanes edit ``src/app.py`` (conflicting) and each touches one bookkeeping file only on its own side; ``merge`` resolves ``src/app.py`` by hand."""
    from specify_cli.lanes.consolidation import install_merge_driver_config, merge_driver_attribute_lines

    repo = _init(root)
    _write(repo, "src/app.py", "a\nb\nc\n")
    _write(repo, "kitty-specs/this-mission/status.events.jsonl", '{"event_id": "1"}\n')
    _write(repo, "kitty-specs/other-mission/meta.json", '{"a": 1}\n')
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    if install_drivers:
        install_merge_driver_config(repo)
        info = repo / ".git" / "info"
        info.mkdir(parents=True, exist_ok=True)
        (info / "attributes").write_text("".join(f"{line}\n" for line in merge_driver_attribute_lines()), encoding="utf-8")
    _git(repo, "branch", "one")
    _git(repo, "branch", "two")
    _commit(repo, "one", "kitty-specs/this-mission/status.events.jsonl", '{"event_id": "1"}\n{"event_id": "2"}\n')
    _commit(repo, "one", "src/app.py", "ONE\nb\nc\n")
    _commit(repo, "two", "kitty-specs/other-mission/meta.json", '{"a": 2}\n')
    _commit(repo, "two", "src/app.py", "TWO\nb\nc\n")
    _git(repo, "checkout", "-q", "one")
    subprocess.run(["git", "-C", str(repo), "merge", "--no-commit", "two"], capture_output=True, check=False)
    _write(repo, "src/app.py", UNION_BYTES)
    _git(repo, "add", "src/app.py")
    _git(repo, "commit", "-qm", "hand merge")
    return repo, _git(repo, "rev-parse", "HEAD")


@pytest.mark.parametrize("install_drivers", [True, False], ids=["drivers_installed", "drivers_absent"])
def test_spec_kittys_own_drivers_pass_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, install_drivers: bool) -> None:
    from specify_cli.consolidation import merge_attribute_guard

    repo, merge = _mission_repo(tmp_path / "repo", install_drivers=install_drivers)
    guarded = git_probes.merge_own_changed_paths(repo, merge)
    assert guarded == ["src/app.py"]
    blob = git_probes.n_way_merge_blob(repo, ["one^", "two"], "kitty-specs/other-mission/meta.json")
    assert blob == git_probes.path_state_at(repo, "two", "kitty-specs/other-mission/meta.json")
    monkeypatch.setattr(merge_attribute_guard, "assert_registered_merge_behaviour", lambda *args, **kwargs: None)
    assert git_probes.merge_own_changed_paths(repo, merge) == guarded


def test_a_committed_registered_mapping_without_driver_config_passes(tmp_path: Path) -> None:
    from specify_cli.consolidation.merge_attribute_guard import assert_registered_merge_behaviour

    repo = _init(tmp_path / "repo")
    _write(repo, ".gitattributes", "kitty-specs/**/meta.json merge=spec-kitty-meta\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "attrs")
    assert_registered_merge_behaviour(repo, ["kitty-specs/m/meta.json", "p.py"])


def test_merge_set_passes(conflict: Conflict) -> None:
    conflict.info_attributes("p.py merge")
    assert git_probes.n_way_merge_blob(conflict.repo, [conflict.one, conflict.two], "p.py") is None
    assert git_probes.merge_own_changed_paths(conflict.repo, conflict.merge) == ["p.py"]


def _committed_union(conflict: Conflict) -> str:
    """Commit ``p.py merge=union`` on ``main`` and return that commit (the pre-run target tip)."""
    _git(conflict.repo, "checkout", "-q", "main")
    _write(conflict.repo, ".gitattributes", "p.py merge=union\n")
    _git(conflict.repo, "add", ".gitattributes")
    _git(conflict.repo, "commit", "-qm", "attrs")
    return _git(conflict.repo, "rev-parse", "HEAD")


def test_committed_union_is_honoured_with_the_pre_run_tip_as_source(conflict: Conflict) -> None:
    tip = _committed_union(conflict)
    assert git_probes.n_way_merge_blob(conflict.repo, [conflict.one, conflict.two], "p.py", attributes_source=tip) is not None
    assert git_probes.merge_own_changed_paths(conflict.repo, conflict.merge, attributes_source=tip) == []


def test_committed_union_refuses_without_a_source(conflict: Conflict) -> None:
    _committed_union(conflict)
    with pytest.raises(GitProbeError, match="union"):
        git_probes.n_way_merge_blob(conflict.repo, [conflict.one, conflict.two], "p.py")
    with pytest.raises(GitProbeError, match="union"):
        git_probes.merge_own_changed_paths(conflict.repo, conflict.merge)


def test_committed_union_refuses_when_info_attributes_also_sets_it(conflict: Conflict) -> None:
    tip = _committed_union(conflict)
    conflict.info_attributes("p.py merge=union")
    with pytest.raises(GitProbeError, match="clone-local"):
        git_probes.n_way_merge_blob(conflict.repo, [conflict.one, conflict.two], "p.py", attributes_source=tip)


def test_committed_union_refuses_when_the_checkout_differs(conflict: Conflict) -> None:
    """Committed ``merge=union`` on ``q.py`` only; the checkout's uncommitted edit maps ``p.py``."""
    _git(conflict.repo, "checkout", "-q", "main")
    _write(conflict.repo, ".gitattributes", "q.py merge=union\n")
    _git(conflict.repo, "add", ".gitattributes")
    _git(conflict.repo, "commit", "-qm", "attrs")
    tip = _git(conflict.repo, "rev-parse", "HEAD")
    _write(conflict.repo, ".gitattributes", "q.py merge=union\np.py merge=union\n")
    with pytest.raises(GitProbeError, match="committed value"):
        git_probes.n_way_merge_blob(conflict.repo, [conflict.one, conflict.two], "p.py", attributes_source=tip)


def test_committed_union_refuses_with_a_union_driver_configured(conflict: Conflict) -> None:
    tip = _committed_union(conflict)
    _git(conflict.repo, "config", "merge.union.driver", FORGE_DRIVER)
    with pytest.raises(GitProbeError, match=r"merge\.union"):
        git_probes.n_way_merge_blob(conflict.repo, [conflict.one, conflict.two], "p.py", attributes_source=tip)


def test_committed_union_refuses_on_git_older_than_2_40(conflict: Conflict, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.git import merge_tree_probe

    tip = _committed_union(conflict)
    monkeypatch.setattr(merge_tree_probe, "_read_git_version", lambda repo_root: (2, 39))
    with pytest.raises(GitProbeError, match="2.40"):
        git_probes.n_way_merge_blob(conflict.repo, [conflict.one, conflict.two], "p.py", attributes_source=tip)


def test_committed_binary_refuses_with_a_binary_driver_configured(conflict: Conflict) -> None:
    _git(conflict.repo, "checkout", "-q", "main")
    _write(conflict.repo, ".gitattributes", "p.py merge=binary\n")
    _git(conflict.repo, "add", ".gitattributes")
    _git(conflict.repo, "commit", "-qm", "attrs")
    tip = _git(conflict.repo, "rev-parse", "HEAD")
    _git(conflict.repo, "config", "merge.binary.driver", FORGE_DRIVER)
    with pytest.raises(GitProbeError, match=r"merge\.binary\.driver"):
        git_probes.n_way_merge_blob(conflict.repo, [conflict.one, conflict.two], "p.py", attributes_source=tip)
    with pytest.raises(GitProbeError, match=r"merge\.binary\.driver"):
        git_probes.merge_own_changed_paths(conflict.repo, conflict.merge, attributes_source=tip)


# ---------------------------------------------------------------------------
# T001: the verifier seam (real verifier, hand-built claims)
# ---------------------------------------------------------------------------


def test_squash_recognizer_refuses_a_union_forged_resolution(conflict: Conflict) -> None:
    """The last-chance clean-fold recognizer would attribute the union blob; the gate REFUSEs instead."""
    from specify_cli.consolidation.reconciliation_claim_types import ApprovedWpCommitSet, LaneContribution
    from specify_cli.consolidation.reconciliation_verifier import MergeOutcomeVerifier, VerifyStatus

    repo = conflict.repo
    _git(repo, "checkout", "-q", "-b", "target", conflict.base)
    _write(repo, "p.py", UNION_BYTES)
    _git(repo, "add", "p.py")
    _git(repo, "commit", "-qm", "squash")
    one_blob = git_probes.path_state_at(repo, conflict.one, "p.py")
    two_blob = git_probes.path_state_at(repo, conflict.two, "p.py")
    assert one_blob is not None and two_blob is not None
    claim = ApprovedWpCommitSet(
        approved={"WP01": (conflict.one,), "WP02": (conflict.two,)},
        manifest_wp_ids=frozenset({"WP01", "WP02"}),
        excluded_window_base=conflict.base,
        enforce_closed_world=True,
        verify_reachability=False,
        authored_blobs=frozenset({("p.py", one_blob), ("p.py", two_blob)}),
        path_contributions={"p.py": (LaneContribution("lane-a", conflict.one, one_blob), LaneContribution("lane-b", conflict.two, two_blob))},
    )
    conflict.info_attributes("p.py merge=union")
    result = MergeOutcomeVerifier(repo).verify("target", claim)
    assert result.status is VerifyStatus.REFUSE
    assert "union" in (result.refusal_reason or "")


def test_merge_closed_world_refuses_a_union_forged_merge(conflict: Conflict) -> None:
    """The merge-strategy closed world REFUSEs instead of skipping ``M`` as a clean merge."""
    from specify_cli.consolidation.reconciliation_claim_types import ApprovedWpCommitSet
    from specify_cli.consolidation.reconciliation_verifier import MergeOutcomeVerifier, VerifyStatus

    claim = ApprovedWpCommitSet(
        approved={"WP01": (conflict.one,), "WP02": (conflict.two,)},
        manifest_wp_ids=frozenset({"WP01", "WP02"}),
        excluded_window_base=conflict.base,
        enforce_closed_world=True,
        authored_shas=frozenset({conflict.one, conflict.two}),
    )
    conflict.info_attributes("p.py merge=union")
    result = MergeOutcomeVerifier(conflict.repo).verify(conflict.merge, claim)
    assert result.status is VerifyStatus.REFUSE
    assert "union" in (result.refusal_reason or "")


# ---------------------------------------------------------------------------
# Review cycle 1 (HIGH): renormalize plus a clean filter launders hand content
# ---------------------------------------------------------------------------


class Laundered:
    """A clean merge ``M`` of ``one`` (line 1) and ``two`` (line 4) whose hand edit turns ``l7`` into ``EVIL``."""

    def __init__(self, root: Path) -> None:
        self.repo = _init(root)
        _write(self.repo, "f", "l1\nl2\nl3\nl4\nl5\nl6\nl7\n")
        _git(self.repo, "add", ".")
        _git(self.repo, "commit", "-qm", "base")
        _git(self.repo, "branch", "one")
        _git(self.repo, "branch", "two")
        self.one = _commit(self.repo, "one", "f", "A\nl2\nl3\nl4\nl5\nl6\nl7\n")
        self.two = _commit(self.repo, "two", "f", "l1\nl2\nl3\nB\nl5\nl6\nl7\n")
        _git(self.repo, "checkout", "-q", "one")
        _git(self.repo, "merge", "-q", "--no-commit", "two")
        _write(self.repo, "f", "A\nl2\nl3\nB\nl5\nl6\nEVIL\n")
        _git(self.repo, "add", "f")
        _git(self.repo, "commit", "-qm", "merge with a hand edit")
        self.merge = _git(self.repo, "rev-parse", "HEAD")
        assert git_probes.merge_own_changed_paths(self.repo, self.merge) == ["f"], "without the laundering setup the hand edit is own content"

    def filter_evil(self) -> None:
        info = self.repo / ".git" / "info"
        info.mkdir(parents=True, exist_ok=True)
        (info / "attributes").write_text("* filter=evil\n", encoding="utf-8")
        _git(self.repo, "config", "filter.evil.clean", "sed s/l7/EVIL/")
        _git(self.repo, "config", "filter.evil.smudge", "cat")


def _renormalize(repo: Path, how: str, monkeypatch: pytest.MonkeyPatch) -> None:
    if how == "config_file":
        _git(repo, "config", "merge.renormalize", "true")
    else:
        monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
        monkeypatch.setenv("GIT_CONFIG_KEY_0", "merge.renormalize")
        monkeypatch.setenv("GIT_CONFIG_VALUE_0", "true")


@pytest.mark.parametrize("how", ["config_file", "git_config_count"])
def test_renormalize_with_a_clean_filter_refuses_both_probes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, how: str) -> None:
    case = Laundered(tmp_path / "repo")
    case.filter_evil()
    _renormalize(case.repo, how, monkeypatch)
    with pytest.raises(GitProbeError, match="merge.renormalize"):
        git_probes.merge_own_changed_paths(case.repo, case.merge)
    with pytest.raises(GitProbeError, match="merge.renormalize"):
        git_probes.n_way_merge_blob(case.repo, [f"{case.merge}^1", f"{case.merge}^2"], "f")


@pytest.mark.parametrize("how", ["config_file", "git_config_count"])
def test_renormalize_alone_refuses_both_probes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, how: str) -> None:
    case = Laundered(tmp_path / "repo")
    _renormalize(case.repo, how, monkeypatch)
    with pytest.raises(GitProbeError, match="merge.renormalize"):
        git_probes.merge_own_changed_paths(case.repo, case.merge)
    with pytest.raises(GitProbeError, match="merge.renormalize"):
        git_probes.n_way_merge_blob(case.repo, [case.one, case.two], "f")


def _assert_hand_edit_is_seen(case: Laundered) -> None:
    """Both probes still see the hand edit: it is own content of ``M``, and the fold of its parents is not the hand blob."""
    hand_blob = git_probes.path_state_at(case.repo, case.merge, "f")
    assert git_probes.merge_own_changed_paths(case.repo, case.merge) == ["f"]
    folded = git_probes.n_way_merge_blob(case.repo, [f"{case.merge}^1", f"{case.merge}^2"], "f")
    assert folded is not None
    assert folded != hand_blob


def test_a_hostile_clean_filter_is_inert_without_renormalize(tmp_path: Path) -> None:
    """git runs a clean filter during a merge only when renormalizing, so the filter alone does not launder."""
    case = Laundered(tmp_path / "repo")
    case.filter_evil()
    _assert_hand_edit_is_seen(case)


@pytest.mark.parametrize("how", ["config_file", "git_config_count"])
def test_the_renormalize_pin_keeps_a_hostile_clean_filter_inert(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, how: str) -> None:
    """Even past the guard's read (renormalize turned on after it), the probe's own git runs with renormalize pinned off."""
    from specify_cli.consolidation import merge_attribute_guard

    case = Laundered(tmp_path / "repo")
    case.filter_evil()
    _renormalize(case.repo, how, monkeypatch)
    monkeypatch.setattr(merge_attribute_guard, "_renormalize_refusal", lambda repo_root, paths: "")
    _assert_hand_edit_is_seen(case)


@pytest.mark.parametrize(
    "line",
    [
        pytest.param("f filter=lfs diff=lfs merge=lfs -text", id="lfs_with_merge_lfs"),
        pytest.param("f filter=lfs", id="lfs"),
        pytest.param("f ident", id="ident"),
        pytest.param("f working-tree-encoding=UTF-16", id="working_tree_encoding"),
    ],
)
def test_a_content_conversion_attribute_alone_is_not_refused(tmp_path: Path, line: str) -> None:
    from specify_cli.consolidation.merge_attribute_guard import assert_registered_merge_behaviour

    case = Laundered(tmp_path / "repo")
    info = case.repo / ".git" / "info"
    info.mkdir(parents=True, exist_ok=True)
    (info / "attributes").write_text(line + "\n", encoding="utf-8")
    if "merge=lfs" in line:
        with pytest.raises(GitProbeError, match="'lfs'"):
            assert_registered_merge_behaviour(case.repo, ["f"])
        return
    assert_registered_merge_behaviour(case.repo, ["f"])


def test_filter_lfs_on_a_probed_path_is_not_refused(tmp_path: Path) -> None:
    """An LFS repository (``filter=lfs``) with no renormalize: both probes run and see the hand edit."""
    case = Laundered(tmp_path / "repo")
    info = case.repo / ".git" / "info"
    info.mkdir(parents=True, exist_ok=True)
    (info / "attributes").write_text("f filter=lfs\n", encoding="utf-8")
    _assert_hand_edit_is_seen(case)


def test_the_pin_table_turns_renormalize_off() -> None:
    from specify_cli.consolidation.merge_attribute_guard import MERGE_PROBE_CONFIG_PINS

    assert ("merge.renormalize", "false") in MERGE_PROBE_CONFIG_PINS


def test_renormalize_false_passes(tmp_path: Path) -> None:
    case = Laundered(tmp_path / "repo")
    _git(case.repo, "config", "merge.renormalize", "false")
    assert git_probes.merge_own_changed_paths(case.repo, case.merge) == ["f"]


# ---------------------------------------------------------------------------
# Review cycle 1 (MED): probe-relevant merge config is pinned on both probes
# ---------------------------------------------------------------------------


def test_directory_renames_config_is_pinned_to_conflict(tmp_path: Path) -> None:
    """``merge.directoryRenames=true`` would turn a file-location conflict into a clean merge."""
    repo = _init(tmp_path / "repo")
    _write(repo, "a/x.txt", "x\n")
    _write(repo, "a/y.txt", "y\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "branch", "one")
    _git(repo, "branch", "two")
    _git(repo, "checkout", "-q", "one")
    _git(repo, "mv", "a", "b")
    _git(repo, "commit", "-qm", "rename dir")
    one = _git(repo, "rev-parse", "HEAD")
    two = _commit(repo, "two", "a/new.txt", "new\n")
    _git(repo, "config", "merge.directoryRenames", "true")
    assert git_probes.n_way_merge_blob(repo, [one, two], "b/new.txt") is None


def test_renames_config_is_pinned_to_true(tmp_path: Path) -> None:
    """``merge.renames=false`` would read a rename plus an edit as a delete, so the edit never reaches the new path."""
    repo = _init(tmp_path / "repo")
    _write(repo, "x.txt", "".join(f"line {n}\n" for n in range(20)))
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "base")
    _git(repo, "branch", "one")
    _git(repo, "branch", "two")
    _git(repo, "checkout", "-q", "one")
    _git(repo, "mv", "x.txt", "y.txt")
    _git(repo, "commit", "-qm", "rename")
    one = _git(repo, "rev-parse", "HEAD")
    edited = "".join(f"line {n}\n" for n in range(19)) + "EDITED\n"
    two = _commit(repo, "two", "x.txt", edited)
    _git(repo, "config", "merge.renames", "false")
    expected = subprocess.run(["git", "-C", str(repo), "hash-object", "--stdin"], input=edited, capture_output=True, text=True, check=True).stdout.strip()
    assert git_probes.n_way_merge_blob(repo, [one, two], "y.txt") == expected


@pytest.mark.parametrize(
    ("key", "hostile", "pinned"),
    [
        pytest.param("merge.directoryRenames", "true", "conflict", id="directory_renames"),
        pytest.param("merge.renames", "false", "true", id="renames"),
        pytest.param("diff.algorithm", "histogram", "myers", id="diff_algorithm"),
        pytest.param("merge.conflictStyle", "zdiff3", "merge", id="conflict_style"),
    ],
)
def test_both_probes_run_git_with_the_pinned_config(conflict: Conflict, monkeypatch: pytest.MonkeyPatch, key: str, hostile: str, pinned: str) -> None:
    from kernel.git import listing

    _git(conflict.repo, "config", key, hostile)
    real_run_git = listing.run_git
    seen: list[tuple[str, Any]] = []

    def spy(cwd: Path, *args: str, **kwargs: Any) -> Any:
        subcommand = next((arg for arg in args if arg in ("merge-tree", "show")), "")
        if subcommand:
            seen.append((subcommand, kwargs.get("env")))
        return real_run_git(cwd, *args, **kwargs)

    monkeypatch.setattr(listing, "run_git", spy)
    git_probes.n_way_merge_blob(conflict.repo, [conflict.one, conflict.two], "p.py")
    git_probes.merge_own_changed_paths(conflict.repo, conflict.merge)
    assert {subcommand for subcommand, _env in seen} == {"merge-tree", "show"}
    for _subcommand, env in seen:
        assert env is not None
        effective = subprocess.run(["git", "-C", str(conflict.repo), "config", "--get", key], env=env, capture_output=True, text=True, check=True).stdout.strip()
        assert effective == pinned


def test_the_pins_win_over_inherited_command_line_config(monkeypatch: pytest.MonkeyPatch, conflict: Conflict) -> None:
    from specify_cli.consolidation.merge_attribute_guard import merge_probe_env

    monkeypatch.setenv("GIT_CONFIG_PARAMETERS", "'merge.renames'='false'")
    env = merge_probe_env()
    effective = subprocess.run(
        ["git", "-C", str(conflict.repo), "config", "--get", "merge.renames"], env=env, capture_output=True, text=True, check=True
    ).stdout.strip()
    assert effective == "true"


def test_an_unreadable_renormalize_value_refuses(conflict: Conflict) -> None:
    from specify_cli.consolidation.merge_attribute_guard import assert_registered_merge_behaviour

    _git(conflict.repo, "config", "merge.renormalize", "not-a-bool")
    with pytest.raises(GitProbeError, match="merge.renormalize"):
        assert_registered_merge_behaviour(conflict.repo, ["p.py"])


def test_merge_probe_env_pins_on_a_given_base() -> None:
    from specify_cli.consolidation.merge_attribute_guard import MERGE_PROBE_CONFIG_PINS, merge_probe_env

    env = merge_probe_env({"PATH": "/bin"})
    assert env["PATH"] == "/bin"
    assert env["GIT_CONFIG_PARAMETERS"] == " ".join(f"'{key}'='{value}'" for key, value in MERGE_PROBE_CONFIG_PINS)


def test_both_probes_run_git_with_the_one_pinned_merge_env(conflict: Conflict, monkeypatch: pytest.MonkeyPatch) -> None:
    """#5604 review fold A1: the probes run with the lane-consolidation pipeline's env (``make_merge_env``) under the pins,
    as the auto-rebase and ``--incorporate`` merges do, so a registered driver resolves to the running spec-kitty."""
    import sys

    import kernel.git
    from specify_cli.consolidation.drivers import META_DRIVER_TWO_WAY_ENV

    monkeypatch.setenv(META_DRIVER_TWO_WAY_ENV, "1")
    seen: list[Any] = []
    real_merge_tree, real_remerge_paths = kernel.git.merge_tree, kernel.git.remerge_paths

    def merge_tree_spy(cwd: Path, *args: str, env: Any = None, **kwargs: Any) -> Any:
        seen.append(env)
        return real_merge_tree(cwd, *args, env=env, **kwargs)

    def remerge_spy(cwd: Path, commit: str, *, env: Any = None, **kwargs: Any) -> Any:
        seen.append(env)
        return real_remerge_paths(cwd, commit, env=env, **kwargs)

    monkeypatch.setattr(git_probes, "merge_tree", merge_tree_spy)
    monkeypatch.setattr(kernel.git, "remerge_paths", remerge_spy)
    git_probes.n_way_merge_blob(conflict.repo, [conflict.one, conflict.two], "p.py")
    git_probes.merge_own_changed_paths(conflict.repo, conflict.merge)
    assert len(seen) == 2
    venv_bin = str(Path(sys.executable).parent)
    for env in seen:
        assert env is not None
        assert env["PATH"].split(":")[0] == venv_bin, "the running spec-kitty's drivers come first"
        assert META_DRIVER_TWO_WAY_ENV not in env, "only a mission->target merge may carry the two-way opt-out"


def test_pinned_merge_env_is_the_pipeline_env_under_the_pins() -> None:
    from specify_cli.consolidation.merge_attribute_guard import merge_probe_env, pinned_merge_env
    from specify_cli.lanes.consolidation import make_merge_env

    assert pinned_merge_env() == merge_probe_env(make_merge_env())


def test_committed_attributes_source_reads_the_target_tip(conflict: Conflict) -> None:
    from specify_cli.consolidation.merge_attribute_guard import committed_attributes_source

    assert committed_attributes_source(conflict.repo, "two") == conflict.two
    assert committed_attributes_source(conflict.repo, "one") == _git(conflict.repo, "rev-parse", "one")
    assert committed_attributes_source(conflict.repo, "no-such-branch") is None
    assert committed_attributes_source(conflict.repo, None) is None
    assert committed_attributes_source(conflict.repo, "") is None
