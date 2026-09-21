"""WP01 harness controls; product acceptance remains a separate red suite."""

from __future__ import annotations

import json
import os
from dataclasses import replace
from pathlib import Path

import pytest

from tests.upgrade.preview_support.process import child_environment, run_process
from tests.upgrade.preview_support.fixtures import copy_case, prepare_case
from tests.upgrade.preview_support.provenance import identify_source
from tests.upgrade.preview_support.snapshot import Node, assert_unchanged, net_delta, snapshot

pytestmark = pytest.mark.integration
LANE = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("mutation", ["ignored", "mkdir", "rmdir", "unlink", "retarget", "chmod", "mtime"])
def test_observations_and_omission_controls(tmp_path: Path, mutation: str) -> None:
    """Each required observation catches its own otherwise invisible mutation."""
    root = tmp_path / "root"
    root.mkdir()
    (root / ".gitignore").write_text("ignored\n")
    regular = root / "ignored"
    regular.write_bytes(b"before")
    empty = root / "empty"
    empty.mkdir()
    link = root / "link"
    link.symlink_to("missing")
    before = snapshot({"project": root})
    if mutation == "ignored":
        regular.write_bytes(b"after")
    elif mutation == "mkdir":
        (root / "new").mkdir()
    elif mutation == "rmdir":
        empty.rmdir()
    elif mutation == "unlink":
        link.unlink()
    elif mutation == "retarget":
        link.unlink()
        link.symlink_to("other-missing")
    elif mutation == "chmod":
        regular.chmod(0o700)
    else:
        old = regular.stat().st_mtime_ns
        regular.write_bytes(b"before")
        os.utime(regular, ns=(old, old + 1_000_000_000))
    after = snapshot({"project": root})
    with pytest.raises(AssertionError, match="Filesystem changed"):
        assert_unchanged(before, after)
    key = ("project", {"mkdir": "new", "rmdir": "empty", "unlink": "link", "retarget": "link"}.get(mutation, "ignored"))
    # A blinded observer loses this witness even when incidental parent mtimes
    # are restored. This control does not modify the real raw snapshots.
    blinded = dict(after)
    for path, node in before.items():
        if path in blinded and node.kind == "directory":
            blinded[path] = replace(blinded[path], mtime_ns=node.mtime_ns)
    if key in before:
        blinded[key] = before[key]
    else:
        del blinded[key]
    assert_unchanged(before, blinded)
    if mutation != "mtime":
        expected = {"ignored": "update", "mkdir": "create", "rmdir": "delete", "unlink": "delete", "retarget": "retarget", "chmod": "chmod"}[mutation]
        assert [(effect.path, effect.action) for effect in net_delta(before, after)] == [(key[1], expected)]


def test_absent_roots_and_creation_mode_are_not_lost(tmp_path: Path) -> None:
    root = tmp_path / "absent"
    before = snapshot({"home": root})
    assert before[("home", ".")].kind == "absent"
    root.mkdir(mode=0o700)
    (root / "executable").write_bytes(b"data")
    (root / "executable").chmod(0o755)
    after = snapshot({"home": root})
    assert [(e.path, e.action) for e in net_delta(before, after)] == [(".", "create"), ("executable", "create")]
    assert after[("home", "executable")].mode == 0o755


def test_symlinks_are_not_followed_and_type_changes_are_replacements(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    target = tmp_path / "target"
    target.mkdir()
    (target / "sentinel").write_bytes(b"untouched")
    link = root / "link"
    link.symlink_to(target)
    before = snapshot({"project": root})
    assert ("project", "link/sentinel") not in before
    link.unlink()
    link.write_bytes(b"copy")
    assert [(e.path, e.action) for e in net_delta(before, snapshot({"project": root}))] == [("link", "replace")]
    assert (target / "sentinel").read_bytes() == b"untouched"


def test_child_environment_seals_fixture_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GH_TOKEN", "not-a-real-token")
    monkeypatch.setenv("PYTHONPATH", "/wrong/source")
    monkeypatch.setenv("SPEC_KITTY_TEMPLATE_ROOT", "/wrong/templates")
    env = child_environment(tmp_path, {"SPEC_KITTY_ENABLE_SAAS_SYNC": "1", "HOME": "/wrong/home"})
    assert env["SPEC_KITTY_ENABLE_SAAS_SYNC"] == "0"
    assert "GH_TOKEN" not in env and "PYTHONPATH" not in env
    assert "SPEC_KITTY_TEMPLATE_ROOT" not in env
    roots = [
        "HOME",
        "USERPROFILE",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
        "XDG_DATA_HOME",
        "XDG_STATE_HOME",
        "APPDATA",
        "LOCALAPPDATA",
        "SPEC_KITTY_HOME",
        "TMPDIR",
        "TMP",
        "TEMP",
    ]
    assert all(Path(env[key]).is_relative_to(tmp_path) for key in roots)
    assert not (tmp_path / "home").exists()
    argv = [str(LANE / ".venv/bin/python"), "-c", "import json, os; print(json.dumps(dict(os.environ)))"]
    result = run_process(argv, tmp_path, env)
    assert result.json()["HOME"] == env["HOME"]


def test_provenance_rejects_other_checkout(tmp_path: Path) -> None:
    env = child_environment(tmp_path)
    identity = identify_source(LANE / ".venv/bin/spec-kitty", LANE, env)
    assert Path(identity.module).is_relative_to(LANE.resolve() / "src")
    assert identity.version and identity.commit and identity.interpreter
    other = tmp_path / "other-checkout"
    other.mkdir()
    with pytest.raises(AssertionError, match="Source mismatch"):
        identify_source(LANE / ".venv/bin/spec-kitty", other, env)


@pytest.mark.parametrize("output", ["", "banner\n{}", "{}\n{}"])
def test_machine_output_must_be_one_complete_value(tmp_path: Path, output: str) -> None:
    result = run_process([str(LANE / ".venv/bin/python"), "-c", f"print({output!r})"], tmp_path, child_environment(tmp_path))
    with pytest.raises((AssertionError, json.JSONDecodeError)):
        result.json()


def test_startup_failure_cannot_pass_purity(tmp_path: Path) -> None:
    result = run_process([str(LANE / ".venv/bin/python"), "-c", "raise RuntimeError('startup control')"], tmp_path, child_environment(tmp_path))
    with pytest.raises(AssertionError, match="Command failed"):
        result.require_success()


@pytest.mark.parametrize("policy", ["record", "deny"])
def test_transient_write_observer(tmp_path: Path, policy: str) -> None:
    root = tmp_path / "measured"
    root.mkdir()
    before = snapshot({"project": root})
    log = tmp_path / "observer.jsonl"
    wrapper = Path(__file__).parent / "preview_support/write_observer.py"
    env = child_environment(tmp_path / "environment")
    result = run_process([str(LANE / ".venv/bin/python"), str(wrapper), str(log), policy, "probe", str(root / "transient")], root, env)
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    assert rows[0] == {"installed_before_cli": True}
    assert rows[1]["event"] == "open"
    assert rows[1]["denied"] == (policy == "deny")
    if policy == "record":
        result.require_success()
        assert rows[2]["event"] == "os.remove"
        # Restore incidental parent mtime so equality cannot reveal the write.
        old = before[("project", ".")].mtime_ns
        assert old is not None
        os.utime(root, ns=(old, old))
        assert_unchanged(before, snapshot({"project": root}))
    else:
        assert result.returncode != 0
        assert "Observed write attempt: open" in result.stderr
        assert_unchanged(before, snapshot({"project": root}))


def test_observer_allows_real_read_only_version(tmp_path: Path) -> None:
    log = tmp_path / "observer.jsonl"
    wrapper = Path(__file__).parent / "preview_support/write_observer.py"
    env = child_environment(tmp_path / "environment")
    before = snapshot({"home": Path(env["HOME"])})
    result = run_process([str(LANE / ".venv/bin/python"), str(wrapper), str(log), "deny", "cli", "--version"], tmp_path, env)
    result.require_success()
    assert "version" in result.stdout
    assert [json.loads(line) for line in log.read_text().splitlines()] == [{"installed_before_cli": True}]
    assert_unchanged(before, snapshot({"home": Path(env["HOME"])}))


@pytest.mark.parametrize("event", ["os.mkdir", "os.remove", "os.rmdir", "os.rename", "os.chmod", "os.utime", "os.link", "os.symlink", "os.truncate"])
def test_observer_rejects_each_covered_operation(tmp_path: Path, event: str) -> None:
    root = tmp_path / "measured"
    root.mkdir()
    (root / "file").write_bytes(b"sentinel")
    (root / "empty").mkdir()
    before = snapshot({"project": root})
    log = tmp_path / "observer.jsonl"
    wrapper = Path(__file__).parent / "preview_support/write_observer.py"
    env = child_environment(tmp_path / "environment")
    argv = [str(LANE / ".venv/bin/python"), str(wrapper), str(log), "deny", "probe-event", event, str(root)]
    result = run_process(argv, root, env)
    assert result.returncode != 0 and f"Observed write attempt: {event}" in result.stderr
    rows = [json.loads(line) for line in log.read_text().splitlines()]
    assert rows[1]["event"] == event and rows[1]["denied"] is True
    assert_unchanged(before, snapshot({"project": root}))


def test_non_ci_environment_and_sibling_isolation(tmp_path: Path) -> None:
    first = child_environment(tmp_path / "first", {"CI": "", "TERM": "xterm"})
    second = child_environment(tmp_path / "second")
    assert "CI" not in first and second["CI"] == "true"
    before = snapshot({"home": Path(second["HOME"])})
    Path(first["HOME"]).mkdir()
    (Path(first["HOME"]) / "sentinel").write_bytes(b"first only")
    assert_unchanged(before, snapshot({"home": Path(second["HOME"])}))


def test_canonical_setup_leaves_cold_home_untouched(tmp_path: Path) -> None:
    case = prepare_case(tmp_path / "original", LANE, global_state="G0")
    assert not Path(case.env["HOME"]).exists()
    assert (case.project / ".kittify/metadata.yaml").is_file()
    manifest = json.loads((case.project / ".kittify/command-skills-manifest.json").read_text())
    assert manifest["entries"], "Canonical setup must establish real ownership"
    cloned = copy_case(case, tmp_path / "copy")
    before = cloned.observe()
    (case.project / "only-original").write_bytes(b"sentinel")
    assert_unchanged(before, cloned.observe())
    assert not Path(cloned.env["HOME"]).exists()
    (case.project / "link").symlink_to("only-original")
    with pytest.raises(AssertionError, match="explicit symlink mapping"):
        copy_case(case, tmp_path / "refused")


def test_sentinel_parent_materialization_tolerated_but_narrow() -> None:
    """A cold-anchor recheck whose sentinel mkdir also creates the observed home
    root (absent -> bare directory) is coordination side effect, not drift, so
    the purity assertion tolerates it -- but any REAL content that materializes
    alongside it is still caught.

    Regression for the local-write-safety landing: the WP02 fold tolerated the
    sentinel's parent mtime only when the parent pre-existed; a cold-home
    fixture where the parent itself springs into existence (e.g.
    test_upgrade_assessment's cold-home) went uncovered and red-mained the
    upgrade shard with ``Filesystem changed: [('home', '.')]``.
    """
    directory = Node("directory", mode=0o775, mtime_ns=222)
    empty_lock = Node("file", sha256="0" * 64, mode=0o600, mtime_ns=222)
    before = {("home", "."): Node("absent")}
    after = {
        ("home", "."): directory,  # materialized purely to hold the sentinel
        ("home", ".spec-kitty-cold-install"): directory,
        ("home", ".spec-kitty-cold-install/anchor.lock"): empty_lock,
    }
    # Purity assertion: tolerated -- nothing but the sentinel and its
    # self-materialized parent changed.
    assert_unchanged(before, after)

    # Narrow: a real owner-effect landing beside the sentinel is still caught
    # by the purity assertion, even though its parent's materialization is
    # tolerated.
    real_file = Node("file", sha256="a" * 64, mode=0o644, mtime_ns=333)
    after_with_content = {**after, ("home", ".spec-kitty/credentials.toml"): real_file}
    with pytest.raises(AssertionError, match="Filesystem changed"):
        assert_unchanged(before, after_with_content)

    # Deliberate asymmetry: net_delta still reports the parent's create (a real
    # `apply` into a cold home is a genuine planned owner-effect the caller's
    # expected set accounts for) -- only the sentinel dir + its .lock are
    # excluded there. The real file is reported alongside it.
    delta = {(e.root, e.path, e.action) for e in net_delta(before, after_with_content)}
    assert delta == {("home", ".", "create"), ("home", ".spec-kitty/credentials.toml", "create")}


def test_non_ci_real_tty_remains_available(tmp_path: Path) -> None:
    env = child_environment(tmp_path, {"CI": "", "TERM": "xterm"})
    argv = [str(LANE / ".venv/bin/python"), "-c", "import os,sys; print(sys.stdout.isatty(), 'CI' in os.environ)"]
    result = run_process(argv, tmp_path, env, tty_output=True)
    result.require_success()
    assert result.stdout.strip() == "True False"
