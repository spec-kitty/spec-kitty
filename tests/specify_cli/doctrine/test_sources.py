"""Contract tests for the OrgDoctrineSource protocol and the three concrete
implementations: GitSource, HttpsBundleSource, ApiSource.

These tests intentionally exercise the **public contract** (the protocol
shape, FetchResult fields, side effects on ``target_dir``) rather than
implementation internals.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
import requests

from specify_cli.doctrine.sources import (
    ApiSource,
    FetchResult,
    GitSource,
    HttpsBundleSource,
    OrgDoctrineSource,
)


# ---------------------------------------------------------------------------
# Protocol contract
# ---------------------------------------------------------------------------

pytestmark = [pytest.mark.unit, pytest.mark.fast]


class TestOrgDoctrineSourceProtocol:
    """The runtime_checkable protocol must accept all three concrete sources."""

    def test_git_source_satisfies_protocol(self) -> None:
        source = GitSource(url="git@example.com:org/charter.offering.git")
        assert isinstance(source, OrgDoctrineSource)

    def test_https_source_satisfies_protocol(self) -> None:
        source = HttpsBundleSource(url="https://example.com/pack.tar.gz")
        assert isinstance(source, OrgDoctrineSource)

    def test_api_source_satisfies_protocol(self) -> None:
        source = ApiSource(url="https://example.com/api")
        assert isinstance(source, OrgDoctrineSource)

    def test_fetch_result_defaults(self) -> None:
        result = FetchResult(ok=True, artifacts_written=0, pack_version=None)
        assert result.errors == []


# ---------------------------------------------------------------------------
# GitSource
# ---------------------------------------------------------------------------
@dataclass
class _FakeCompletedProcess:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class _GitRunRecorder:
    """Replaces ``subprocess.run`` so we can drive GitSource via scripted exits.

    Each entry in ``script`` is a tuple ``(returncode, stdout, stderr)`` and
    is consumed in order.  An optional ``side_effect`` callable receives the
    invoked argv before the scripted result is returned (used to materialise
    a fake ``.git/`` directory during ``git clone``).
    """

    def __init__(
        self,
        script: list[tuple[int, str, str]],
        side_effects: dict[str, Any] | None = None,
    ) -> None:
        self.script = list(script)
        self.calls: list[list[str]] = []
        self.envs: list[dict[str, str] | None] = []
        self.side_effects = side_effects or {}

    def __call__(
        self,
        argv: list[str],
        capture_output: bool = True,
        text: bool = True,
        check: bool = False,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        **_extra: Any,
    ) -> subprocess.CompletedProcess[str]:
        # ``cwd``/``**_extra`` accept the ``ref_advance`` call shape (it passes
        # ``cwd=`` and is delegated to by ``_update``'s dirty/ahead checks).
        self.calls.append(argv)
        self.envs.append(env)
        for keyword, effect in self.side_effects.items():
            if any(keyword == part for part in argv):
                effect(argv)
        if not self.script:
            return _FakeCompletedProcess(returncode=0)  # type: ignore[return-value]
        returncode, stdout, stderr = self.script.pop(0)
        return _FakeCompletedProcess(  # type: ignore[return-value]
            returncode=returncode,
            stdout=stdout,
            stderr=stderr,
        )


def _make_fake_clone(directives_count: int = 2):
    """Return a side-effect that materialises a fake clone under target_dir."""

    def _effect(argv: list[str]) -> None:
        target_dir = Path(argv[-1])
        (target_dir / ".git").mkdir(parents=True, exist_ok=True)
        directives = target_dir / "directives"
        directives.mkdir(parents=True, exist_ok=True)
        for i in range(directives_count):
            (directives / f"DIR-{i}.directive.yaml").write_text("id: x\n")

    return _effect


_GIT_AVAILABLE = shutil.which("git") is not None
_requires_git = pytest.mark.skipif(not _GIT_AVAILABLE, reason="git executable not available")


def _git_env() -> dict[str, str]:
    """Deterministic, non-interactive git identity for scratch repos."""
    return {
        **os.environ,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    }


def _run_real_git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
        env=_git_env(),
    )
    if check and proc.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed in {cwd}: {proc.stderr or proc.stdout}")
    return proc


def _seed_bare_remote(tmp_path: Path, *, tag: str | None = None) -> tuple[Path, str]:
    """Create a bare remote with one seed commit; return (remote_path, seed_sha)."""
    seed = tmp_path / "seed"
    seed.mkdir()
    _run_real_git(seed, "init", "-b", "main")
    _run_real_git(seed, "config", "commit.gpgsign", "false")
    (seed / "directives").mkdir()
    (seed / "directives" / "SEED.directive.yaml").write_text("id: seed\n")
    _run_real_git(seed, "add", "-A")
    _run_real_git(seed, "commit", "-m", "seed")
    seed_sha = _run_real_git(seed, "rev-parse", "HEAD").stdout.strip()
    if tag is not None:
        _run_real_git(seed, "tag", tag)
    remote = tmp_path / "remote.git"
    _run_real_git(tmp_path, "clone", "--bare", str(seed), str(remote))
    return remote, seed_sha


class TestGitSource:
    def test_first_install_success(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "doctrine"
        runner = _GitRunRecorder(
            script=[
                (0, "", ""),  # clone
                (0, "v1.2.0\n", ""),  # describe
            ],
            side_effects={"clone": _make_fake_clone(directives_count=2)},
        )
        monkeypatch.setattr("specify_cli.doctrine.sources.git_source.subprocess.run", runner)

        result = GitSource(url="git@example.com:org/d.git").fetch(target)

        assert result.ok is True
        assert result.artifacts_written == 2
        assert result.pack_version == "v1.2.0"
        # The .git directory exists in the materialised target.
        assert (target / ".git").exists()
        # No reset/fetch on first install — just clone + describe.
        assert any(call[1] == "clone" for call in runner.calls)
        assert not any(call[1:3] == ["-C", str(target)] and "fetch" in call for call in runner.calls)

    def test_fetch_is_non_interactive(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Every git invocation disables interactive credential prompts."""
        target = tmp_path / "doctrine"
        runner = _GitRunRecorder(
            script=[
                (0, "", ""),  # clone
                (0, "v1.2.0\n", ""),  # describe
            ],
            side_effects={"clone": _make_fake_clone(directives_count=1)},
        )
        monkeypatch.setattr("specify_cli.doctrine.sources.git_source.subprocess.run", runner)

        result = GitSource(url="git@example.com:org/d.git").fetch(target)

        assert result.ok is True
        assert runner.envs, "expected at least one subprocess.run invocation"
        for env in runner.envs:
            assert env is not None
            assert env.get("GIT_TERMINAL_PROMPT") == "0"

    def test_update_path_used_when_dot_git_exists(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "doctrine"
        (target / ".git").mkdir(parents=True)
        (target / "directives").mkdir()
        (target / "directives" / "A.yaml").write_text("id: a\n")

        # Re-pinned for WP02 (#4989 / F9): between `fetch` and `reset`, `_update`
        # now delegates a dirty check (`ls-tree` + `status`, via `ref_advance`) and
        # an ahead check (`rev-list --count`). The scripted sequence models a
        # clean, not-ahead pack so the reset still proceeds. `ref_advance` has its
        # own `subprocess.run`, so both modules are patched to the one recorder.
        runner = _GitRunRecorder(
            script=[
                (0, "", ""),  # fetch --tags origin
                (0, "", ""),  # ls-tree (target tree paths) -> empty
                (0, "", ""),  # status --porcelain --ignored -> clean
                (0, "0\n", ""),  # rev-list --count origin/HEAD..HEAD -> not ahead
                (0, "", ""),  # reset --hard origin/HEAD
                (0, "v1.3.0\n", ""),  # describe
            ],
        )
        monkeypatch.setattr("specify_cli.doctrine.sources.git_source.subprocess.run", runner)
        monkeypatch.setattr("specify_cli.git.ref_advance.subprocess.run", runner)

        result = GitSource(url="git@example.com:org/d.git").fetch(target)

        assert result.ok is True
        assert result.pack_version == "v1.3.0"
        # `git fetch` first; a `git reset` follows (after the interposed dirty/ahead
        # checks) and targets the remote-tracking ref; never a clone on the update path.
        assert "fetch" in runner.calls[0]
        reset_index = next(i for i, call in enumerate(runner.calls) if "reset" in call)
        assert reset_index > 0
        assert runner.calls[reset_index][-1] == "origin/HEAD"
        assert not any(part == "clone" for call in runner.calls for part in call)

    def test_first_install_failure_cleans_up(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "doctrine"

        def _partial_clone(argv: list[str]) -> None:
            # git clone wrote some files but then failed.
            target_dir = Path(argv[-1])
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / "junk").write_text("partial\n")

        runner = _GitRunRecorder(
            script=[(128, "", "fatal: repo not found")],
            side_effects={"clone": _partial_clone},
        )
        monkeypatch.setattr("specify_cli.doctrine.sources.git_source.subprocess.run", runner)

        result = GitSource(url="git@example.com:org/d.git").fetch(target)

        assert result.ok is False
        assert "fatal: repo not found" in result.errors[0]
        assert not target.exists()

    def test_update_failure_leaves_existing_clone_untouched(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "doctrine"
        (target / ".git").mkdir(parents=True)
        (target / "directives").mkdir()
        (target / "directives" / "A.yaml").write_text("id: a\n")

        runner = _GitRunRecorder(script=[(1, "", "network unreachable")])
        monkeypatch.setattr("specify_cli.doctrine.sources.git_source.subprocess.run", runner)

        result = GitSource(url="git@example.com:org/d.git").fetch(target)

        assert result.ok is False
        assert "network unreachable" in result.errors[0]
        # Existing clone preserved.
        assert (target / ".git").exists()
        assert (target / "directives" / "A.yaml").read_text() == "id: a\n"

    def test_https_url_gets_token_injected(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "doctrine"
        monkeypatch.setenv("GIT_TOKEN", "secret-abc")

        runner = _GitRunRecorder(
            script=[(0, "", ""), (0, "v1\n", "")],
            side_effects={"clone": _make_fake_clone(directives_count=1)},
        )
        monkeypatch.setattr("specify_cli.doctrine.sources.git_source.subprocess.run", runner)

        result = GitSource(url="https://example.com/org/d.git").fetch(target)

        assert result.ok is True
        clone_argv = runner.calls[0]
        # Token must appear in the URL passed to git, not in any other arg.
        assert any("oauth2:secret-abc@example.com" in part for part in clone_argv)

    def test_ssh_url_unaffected_by_git_token(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "doctrine"
        monkeypatch.setenv("GIT_TOKEN", "secret-abc")

        runner = _GitRunRecorder(
            script=[(0, "", ""), (0, "v1\n", "")],
            side_effects={"clone": _make_fake_clone(directives_count=1)},
        )
        monkeypatch.setattr("specify_cli.doctrine.sources.git_source.subprocess.run", runner)

        GitSource(url="git@example.com:org/d.git").fetch(target)
        clone_argv = runner.calls[0]
        assert "secret-abc" not in " ".join(clone_argv)

    def test_ref_checkout_after_first_clone(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "doctrine"
        runner = _GitRunRecorder(
            script=[
                (0, "", ""),  # clone
                (0, "", ""),  # checkout
                (0, "v1.0.0\n", ""),  # describe
            ],
            side_effects={"clone": _make_fake_clone()},
        )
        monkeypatch.setattr("specify_cli.doctrine.sources.git_source.subprocess.run", runner)

        result = GitSource(url="git@example.com:org/d.git", ref="v1.0.0").fetch(target)

        assert result.ok is True
        # 2nd call must be checkout to ``ref``.
        assert runner.calls[1][-1] == "v1.0.0"

    # -- WP02 regressions (#4960, #4989): preservation of hand-authored packs --

    @pytest.mark.regression
    @_requires_git
    def test_first_install_refuses_and_preserves_nonempty_dir(self, tmp_path: Path) -> None:
        """#4960: a pre-existing non-empty local_path survives a failing clone.

        The old ``_first_install`` did ``git clone <url> <target>`` (which fails
        precisely because the dir is non-empty) then ``rmtree(target)`` — deleting
        the hand-authored pack. The fix refuses up front; only a temp is ever
        removed.
        """
        target = tmp_path / "pack"
        (target / "directives").mkdir(parents=True)
        mine = target / "directives" / "MINE.directive.yaml"
        mine.write_text("id: mine\n")
        bad_url = str(tmp_path / "does-not-exist.git")

        result = GitSource(url=bad_url, inject_token=False).fetch(target)

        assert result.ok is False
        assert mine.read_text() == "id: mine\n"  # hand-authored pack preserved
        assert not any(child.name.startswith(".tmp-") for child in tmp_path.iterdir())

    @pytest.mark.regression
    @_requires_git
    def test_first_install_refuses_successful_clone_into_nonempty_dir(self, tmp_path: Path) -> None:
        """#4960: a VALID clone into a non-empty (non-.git) target is refused, not clobbered.

        The other preservation tests drive ``_first_install`` through a FAILING
        clone (bad_url / no-such-ref), where the temp-sibling design protects
        ``target_dir`` regardless of the up-front refusal guard — so none of them
        actually exercises the guard. This pins the PRIMARY #4960 protection
        directly: a clone that WOULD succeed must still be refused up front,
        because ``target_dir`` holds hand-authored content a successful promote
        would overwrite. Disabling the ``if target_dir.exists() and
        self._is_non_empty(...)`` refusal makes this clone return ok=True and
        silently replace ``MINE.yaml`` — exactly the #4960 clobber.
        """
        remote, _ = _seed_bare_remote(tmp_path)
        target = tmp_path / "pack"
        target.mkdir()  # non-empty, non-.git dir: a hand-authored pack
        mine = target / "MINE.yaml"
        original = b"id: mine\ncustom: hand-authored\n"
        mine.write_bytes(original)

        # A bare, valid remote: the clone WOULD succeed if not refused up front.
        result = GitSource(url=str(remote), inject_token=False).fetch(target)

        assert result.ok is False  # refused by the #4960 up-front guard
        assert mine.read_bytes() == original  # hand-authored file NOT clobbered
        # The cloned pack content never landed on the target.
        assert not (target / ".git").exists()
        assert not (target / "directives" / "SEED.directive.yaml").exists()
        assert not any(child.name.startswith(".tmp-") for child in tmp_path.iterdir())

    @pytest.mark.regression
    @_requires_git
    def test_first_install_checkout_failure_removes_only_temp(self, tmp_path: Path) -> None:
        """#4960: a checkout failure removes only the temp; the caller's dir survives."""
        remote, _ = _seed_bare_remote(tmp_path)
        target = tmp_path / "pack"
        target.mkdir()  # pre-existing EMPTY dir (the _resolve_git caller pattern)

        result = GitSource(url=str(remote), ref="no-such-ref", inject_token=False).fetch(target)

        assert result.ok is False
        assert target.exists()  # NOT rmtree'd by the checkout-failure path
        assert list(target.iterdir()) == []
        assert not any(child.name.startswith(".tmp-") for child in tmp_path.iterdir())

    @pytest.mark.regression
    @_requires_git
    def test_first_install_permits_empty_dir(self, tmp_path: Path) -> None:
        """F8: a pre-existing EMPTY local_path is permitted (the _resolve_git caller passes one)."""
        remote, _ = _seed_bare_remote(tmp_path)
        target = tmp_path / "pack"
        target.mkdir()

        result = GitSource(url=str(remote), inject_token=False).fetch(target)

        assert result.ok is True
        assert (target / ".git").exists()
        assert (target / "directives" / "SEED.directive.yaml").read_text() == "id: seed\n"

    @pytest.mark.regression
    @_requires_git
    def test_update_preserves_uncommitted_local_edits(self, tmp_path: Path) -> None:
        """#4989: _update must not ``reset --hard`` away uncommitted local pack edits."""
        remote, _ = _seed_bare_remote(tmp_path)
        target = tmp_path / "pack"
        _run_real_git(tmp_path, "clone", str(remote), str(target))
        edited = target / "directives" / "SEED.directive.yaml"
        edited.write_text("id: seed\nlocal: edit\n")  # uncommitted dirt

        result = GitSource(url=str(remote), ref="main", inject_token=False).fetch(target)

        assert result.ok is False
        assert edited.read_text() == "id: seed\nlocal: edit\n"  # preserved in place

    @pytest.mark.regression
    @_requires_git
    def test_update_preserves_committed_ahead_history(self, tmp_path: Path) -> None:
        """#4989/F7: a clean worktree with a local commit ahead of origin is not orphaned.

        Guards against the naive fix (blanket ``reset --hard origin/<ref>`` without
        an ahead check), which would orphan the local commit. The correct fix
        refuses, leaving HEAD — and therefore the commit — reachable.
        """
        remote, _ = _seed_bare_remote(tmp_path)
        target = tmp_path / "pack"
        _run_real_git(tmp_path, "clone", str(remote), str(target))
        (target / "directives" / "LOCAL.directive.yaml").write_text("id: local\n")
        _run_real_git(target, "add", "-A")
        _run_real_git(target, "commit", "-m", "local ahead commit")
        local_sha = _run_real_git(target, "rev-parse", "HEAD").stdout.strip()

        result = GitSource(url=str(remote), ref="main", inject_token=False).fetch(target)

        assert result.ok is False
        contains = _run_real_git(target, "branch", "--contains", local_sha, check=False)
        assert contains.returncode == 0 and contains.stdout.strip() != ""  # NOT orphaned
        assert (target / "directives" / "LOCAL.directive.yaml").exists()

    @pytest.mark.regression
    @_requires_git
    def test_update_branch_ref_advances_to_origin(self, tmp_path: Path) -> None:
        """#4989 sub-bug B: ref=<branch> resets to origin/<branch> so the pack advances."""
        remote, _ = _seed_bare_remote(tmp_path)
        target = tmp_path / "pack"
        _run_real_git(tmp_path, "clone", str(remote), str(target))

        # Advance the remote's main via an independent clone.
        work2 = tmp_path / "work2"
        _run_real_git(tmp_path, "clone", str(remote), str(work2))
        (work2 / "directives" / "NEW.directive.yaml").write_text("id: new\n")
        _run_real_git(work2, "add", "-A")
        _run_real_git(work2, "commit", "-m", "advance")
        _run_real_git(work2, "push", "origin", "main")

        result = GitSource(url=str(remote), ref="main", inject_token=False).fetch(target)

        assert result.ok is True
        assert (target / "directives" / "NEW.directive.yaml").read_text() == "id: new\n"

    @pytest.mark.regression
    @_requires_git
    def test_update_tag_and_sha_pinned_refs_resolve(self, tmp_path: Path) -> None:
        """F6: tag- and SHA-pinned refs reset to the bare ref (no ``origin/<ref>`` regression)."""
        # Tag-pinned pack.
        tag_root = tmp_path / "tag"
        tag_root.mkdir()
        tag_remote, _ = _seed_bare_remote(tag_root, tag="v1.0.0")
        tag_target = tag_root / "pack"
        _run_real_git(tag_root, "clone", str(tag_remote), str(tag_target))
        tag_result = GitSource(url=str(tag_remote), ref="v1.0.0", inject_token=False).fetch(tag_target)
        assert tag_result.ok is True
        assert (tag_target / "directives" / "SEED.directive.yaml").read_text() == "id: seed\n"

        # SHA-pinned pack.
        sha_root = tmp_path / "sha"
        sha_root.mkdir()
        sha_remote, seed_sha = _seed_bare_remote(sha_root)
        sha_target = sha_root / "pack"
        _run_real_git(sha_root, "clone", str(sha_remote), str(sha_target))
        sha_result = GitSource(url=str(sha_remote), ref=seed_sha, inject_token=False).fetch(sha_target)
        assert sha_result.ok is True
        assert (sha_target / "directives" / "SEED.directive.yaml").read_text() == "id: seed\n"


# ---------------------------------------------------------------------------
# HttpsBundleSource
# ---------------------------------------------------------------------------
class _FakeResponse:
    def __init__(
        self,
        status_code: int = 200,
        body: bytes = b"",
        headers: dict[str, str] | None = None,
        url: str = "",
        reason: str = "OK",
    ) -> None:
        self.status_code = status_code
        self._body = body
        self.headers = headers or {}
        self.url = url
        self.reason = reason
        self.closed = False

    def iter_content(self, chunk_size: int = 65536):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i : i + chunk_size]

    def json(self) -> Any:
        return json.loads(self._body.decode("utf-8"))

    def close(self) -> None:
        self.closed = True


def _make_tar_gz_bundle(top_dir: str | None = None) -> bytes:
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tf:
        prefix = f"{top_dir}/" if top_dir else ""
        for name, content in [
            ("directives/sec.directive.yaml", "id: sec\n"),
            ("agent_profiles/eng.agent.yaml", "id: eng\n"),
        ]:
            data = content.encode("utf-8")
            info = tarfile.TarInfo(name=f"{prefix}{name}")
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _make_zip_bundle() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("directives/sec.directive.yaml", "id: sec\n")
        zf.writestr("agent_profiles/eng.agent.yaml", "id: eng\n")
    return buf.getvalue()


def _aql_payload(
    bundle: bytes,
    *,
    repo: str = "repo",
    path: str = ".",
    name: str = "pack-latest.tar.gz",
    version: str | None = "3.2.7",
    sha256: str | None = None,
    virtual_repos: list[str] | None = None,
) -> dict[str, object]:
    result: dict[str, object] = {
        "repo": repo,
        "path": path,
        "name": name,
        "properties": ([{"key": "version", "value": version}] if version is not None else []),
    }
    if sha256 is not None:
        result["sha256"] = sha256
    else:
        result["sha256"] = hashlib.sha256(bundle).hexdigest()  # noqa: TID251
    if virtual_repos is not None:
        result["virtual_repos"] = virtual_repos
    return {"results": [result]}


class TestHttpsBundleSource:
    @pytest.mark.parametrize(
        "invalid_url",
        [
            "https://[bad/artifactory/repo/pack.tar.gz",
            "https://example.com:not-a-port/artifactory/repo/pack.tar.gz",
            "http://example.com/artifactory/repo/pack.tar.gz",
            "https:///artifactory/repo/pack.tar.gz",
            "https://exa mple.com/artifactory/repo/pack.tar.gz",
            "https://%ZZ/artifactory/repo/pack.tar.gz",
            "https://./artifactory/repo/pack.tar.gz",
            "https://💩.example/artifactory/repo/pack.tar.gz",
            "https://a\u200db.example/artifactory/repo/pack.tar.gz",
            "https://\u0301bad.example/artifactory/repo/pack.tar.gz",
            f"https://{'.'.join(['é' * 20] * 10)}/artifactory/repo/pack.tar.gz",
            "https://[v1.fe]/artifactory/repo/pack.tar.gz",
            "https://download.example\\@metadata.example/artifactory/repo/pack.tar.gz",
            "https://download.example\t@metadata.example/artifactory/repo/pack.tar.gz",
            "https://download.example\n@metadata.example/artifactory/repo/pack.tar.gz",
        ],
    )
    def test_invalid_authority_fails_without_request(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        invalid_url: str,
    ) -> None:
        calls: list[str] = []

        def _unexpected_get(url: str, **kwargs: Any) -> _FakeResponse:
            calls.append(url)
            return _FakeResponse(status_code=500, url=url)

        monkeypatch.setattr(
            "specify_cli.doctrine.sources.https_source.requests.get",
            _unexpected_get,
        )
        monkeypatch.setattr(
            "specify_cli.doctrine.sources.https_source.requests.post",
            _unexpected_get,
        )

        result = HttpsBundleSource(url=invalid_url).fetch(tmp_path / "snapshot")

        assert result.ok is False
        assert any("URL is invalid" in error for error in result.errors)
        assert calls == []

    @pytest.mark.parametrize(
        "valid_url",
        [
            "https://bücher.example/pack.tar.gz",
            "https://xn--bcher-kva.example/pack.tar.gz",
            "https://127.0.0.1/pack.tar.gz",
            "https://[2001:db8::1]/pack.tar.gz",
            "https://[fe80::1%25eth0]/pack.tar.gz",
            "https://artifactory/pack.tar.gz",
        ],
    )
    def test_valid_authority_reaches_request(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        valid_url: str,
    ) -> None:
        calls: list[str] = []

        def _fake_get(url: str, **kwargs: Any) -> _FakeResponse:
            calls.append(url)
            return _FakeResponse(status_code=500, url=url)

        monkeypatch.setattr(
            "specify_cli.doctrine.sources.https_source.requests.get",
            _fake_get,
        )

        result = HttpsBundleSource(url=valid_url).fetch(tmp_path / "snapshot")

        assert result.ok is False
        assert calls
        prepared_url = requests.Request(method="GET", url=valid_url).prepare().url
        assert prepared_url is not None
        assert set(calls) == {prepared_url}

    def test_canonical_url_is_the_wire_url_after_repeated_preparation(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        raw_url = "https://example.com/a/%2e%2e/pack.tar.gz"
        canonical_url = "https://example.com/pack.tar.gz"
        sent_urls: list[str] = []

        def _fake_send(
            session: requests.Session,
            request: requests.PreparedRequest,
            **kwargs: Any,
        ) -> _FakeResponse:
            del session, kwargs
            assert request.url is not None
            sent_urls.append(request.url)
            return _FakeResponse(status_code=500, url=request.url)

        monkeypatch.setattr(requests.Session, "send", _fake_send)

        result = HttpsBundleSource(url=raw_url).fetch(tmp_path / "snapshot")

        assert result.ok is False
        assert sent_urls
        assert set(sent_urls) == {canonical_url}

    def test_fetch_captures_one_canonical_identity_for_request_and_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        trusted_url = "https://trusted.example/pack.zip"
        attacker_url = "https://attacker.example/other.zip"
        calls: list[str] = []

        class _AlternatingSource(HttpsBundleSource):
            canonical_reads = 0

            @property
            def canonical_url(self) -> str | None:
                self.canonical_reads += 1
                return trusted_url if self.canonical_reads == 1 else attacker_url

        def _fake_get(url: str, **kwargs: Any) -> _FakeResponse:
            calls.append(url)
            return _FakeResponse(status_code=404, url=url)

        monkeypatch.setattr("specify_cli.doctrine.sources.https_source.requests.get", _fake_get)
        source = _AlternatingSource(url=trusted_url)

        result = source.fetch(tmp_path / "snapshot")

        assert result.ok is False
        assert source.canonical_reads == 1
        assert calls == [trusted_url]
        assert any(trusted_url in error for error in result.errors)
        assert all(attacker_url not in error for error in result.errors)

    def test_tar_gz_extraction(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "snapshot"
        bundle = _make_tar_gz_bundle(top_dir="my-pack-v1.0.0")

        response = _FakeResponse(
            status_code=200,
            body=bundle,
            headers={"Content-Type": "application/gzip", "ETag": "abc123"},
            url="https://example.com/pack.tar.gz",
        )

        def _fake_get(url: str, **kwargs: Any) -> _FakeResponse:
            return response

        monkeypatch.setattr("specify_cli.doctrine.sources.https_source.requests.get", _fake_get)
        monkeypatch.setattr(
            "specify_cli.doctrine.sources.https_source.requests.post",
            lambda *_args, **_kwargs: pytest.fail("non-Artifactory source used AQL"),
        )

        result = HttpsBundleSource(url="https://example.com/pack.tar.gz").fetch(target)

        assert result.ok is True
        # Non-Artifactory HTTPS: etag is for conditional fetch only; no version.
        assert result.pack_version is None
        assert result.etag == "abc123"
        # Top-level dir was flattened away.
        assert (target / "directives" / "sec.directive.yaml").is_file()
        assert (target / "agent_profiles" / "eng.agent.yaml").is_file()
        assert result.artifacts_written == 2
        assert response.closed is True

    def test_non_artifactory_does_not_query_version_properties(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "snapshot"
        bundle = _make_tar_gz_bundle()
        urls: list[str] = []

        def _fake_get(url: str, **kwargs: Any) -> _FakeResponse:
            urls.append(url)
            return _FakeResponse(
                status_code=200,
                body=bundle,
                headers={"Content-Type": "application/gzip", "ETag": "abc"},
                url=url,
            )

        monkeypatch.setattr("specify_cli.doctrine.sources.https_source.requests.get", _fake_get)

        result = HttpsBundleSource(url="https://cdn.example.com/pack.tar.gz").fetch(target)

        assert result.ok is True
        assert result.pack_version is None
        assert urls == ["https://cdn.example.com/pack.tar.gz"]

    @pytest.mark.parametrize("source_type", ["https", "artifactory"])
    @pytest.mark.parametrize(
        ("auth_env", "auth_value", "expected_authorization"),
        [
            ("SPEC_KITTY_ORG_TOKEN", "token-123", "Bearer token-123"),
            ("SPEC_KITTY_ORG_AUTH_HEADER", "Basic dXNlcjpwYXNz", "Basic dXNlcjpwYXNz"),
        ],
    )
    def test_artifactory_version_property_becomes_pack_version(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        source_type: str,
        auth_env: str,
        auth_value: str,
        expected_authorization: str,
    ) -> None:
        target = tmp_path / "snapshot"
        bundle = _make_tar_gz_bundle()
        aql_calls: list[tuple[str, dict[str, Any]]] = []
        streamed: list[bool] = []
        download_headers: list[dict[str, str]] = []
        metadata_responses: list[_FakeResponse] = []
        artifact_url = "https://artifactory.example.com/artifactory/raf-generic-local/doctrines/doctrine-rnd-latest.tar.gz"

        class _TrackingDownload(_FakeResponse):
            def iter_content(self, chunk_size: int = 65536):
                yield from super().iter_content(chunk_size)
                streamed.append(True)

        def _fake_get(url: str, **kwargs: Any) -> _FakeResponse:
            download_headers.append(dict(kwargs.get("headers") or {}))
            return _TrackingDownload(
                status_code=200,
                body=bundle,
                headers={"Content-Type": "application/gzip", "ETag": '"etag-7"'},
                url=url,
            )

        def _fake_post(url: str, **kwargs: Any) -> _FakeResponse:
            assert streamed == [True], "metadata queried before body completed"
            aql_calls.append((url, kwargs))
            metadata_response = _FakeResponse(
                status_code=200,
                body=json.dumps(
                    _aql_payload(
                        bundle,
                        repo="raf-generic-local",
                        path="doctrines",
                        name="doctrine-rnd-latest.tar.gz",
                    )
                ).encode(),
                headers={"Content-Type": "application/json"},
                url=url,
            )
            metadata_responses.append(metadata_response)
            return metadata_response

        monkeypatch.delenv("SPEC_KITTY_ORG_AUTH_HEADER", raising=False)
        monkeypatch.delenv("SPEC_KITTY_ORG_TOKEN", raising=False)
        monkeypatch.setenv(auth_env, auth_value)
        monkeypatch.setattr("specify_cli.doctrine.sources.https_source.requests.get", _fake_get)
        monkeypatch.setattr("specify_cli.doctrine.sources.https_source.requests.post", _fake_post)

        result = HttpsBundleSource(url=artifact_url, source_type=source_type).fetch(target)

        assert result.ok is True
        assert result.pack_version == "3.2.7"
        assert result.etag == '"etag-7"'
        assert len(aql_calls) == 1
        assert aql_calls[0][0] == ("https://artifactory.example.com/artifactory/api/search/aql")
        query = aql_calls[0][1]["data"]
        assert '"repo":"raf-generic-local"' in query
        assert '"path":"doctrines"' in query
        assert '"name":"doctrine-rnd-latest.tar.gz"' in query
        assert '"sha256"' in query
        assert '"virtual_repos"' in query
        assert '"@version"' in query
        assert "If-None-Match" not in aql_calls[0][1]["headers"]
        assert download_headers == [{"Authorization": expected_authorization}]
        assert aql_calls[0][1]["headers"]["Authorization"] == expected_authorization
        assert all(response.closed for response in metadata_responses)

    def test_artifactory_virtual_repo_and_encoded_item_are_validated(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        bundle = _make_tar_gz_bundle()
        artifact_url = "https://artifactory.example.com/artifactory/my-virtual/folder/My%20Pack-%E2%9C%93.tar.gz"
        captured_criteria: dict[str, object] = {}

        def _fake_get(url: str, **kwargs: Any) -> _FakeResponse:
            return _FakeResponse(
                status_code=200,
                body=bundle,
                headers={"Content-Type": "application/gzip"},
                url=url,
            )

        def _fake_post(url: str, **kwargs: Any) -> _FakeResponse:
            query = kwargs["data"]
            criteria_json = query.removeprefix("items.find(").split(").include", 1)[0]
            captured_criteria.update(json.loads(criteria_json))
            payload = _aql_payload(
                bundle,
                repo="backing-local",
                path="folder",
                name="My Pack-✓.tar.gz",
                virtual_repos=["my-virtual"],
            )
            return _FakeResponse(
                status_code=200,
                body=json.dumps(payload).encode(),
                url=url,
            )

        monkeypatch.setattr("specify_cli.doctrine.sources.https_source.requests.get", _fake_get)
        monkeypatch.setattr("specify_cli.doctrine.sources.https_source.requests.post", _fake_post)

        result = HttpsBundleSource(url=artifact_url).fetch(tmp_path / "snapshot")

        assert result.ok is True
        assert result.pack_version == "3.2.7"
        assert captured_criteria == {
            "repo": "my-virtual",
            "path": "folder",
            "name": "My Pack-✓.tar.gz",
            "type": "file",
        }

    @pytest.mark.parametrize(
        "case",
        [
            "wrong-repo",
            "wrong-path",
            "wrong-name",
            "no-results",
            "duplicate-results",
            "no-version",
            "duplicate-version",
        ],
    )
    def test_artifactory_rejects_non_exact_aql_result(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case: str) -> None:
        bundle = _make_tar_gz_bundle()
        artifact_url = "https://artifactory.example.com/artifactory/repo/folder/pack-latest.tar.gz"

        def _fake_get(url: str, **kwargs: Any) -> _FakeResponse:
            return _FakeResponse(
                status_code=200,
                body=bundle,
                headers={"Content-Type": "application/gzip"},
                url=url,
            )

        def _fake_post(url: str, **kwargs: Any) -> _FakeResponse:
            payload = _aql_payload(bundle, path="folder")
            results = payload["results"]
            assert isinstance(results, list) and isinstance(results[0], dict)
            result = results[0]
            if case == "wrong-repo":
                result["repo"] = "another-repo"
            elif case == "wrong-path":
                result["path"] = "another-folder"
            elif case == "wrong-name":
                result["name"] = "another-pack.tar.gz"
            elif case == "no-results":
                results.clear()
            elif case == "duplicate-results":
                results.append(dict(result))
            elif case == "no-version":
                result["properties"] = []
            elif case == "duplicate-version":
                properties = result["properties"]
                assert isinstance(properties, list)
                properties.append({"key": "version", "value": "3.2.8"})
            return _FakeResponse(
                status_code=200,
                body=json.dumps(payload).encode(),
                url=url,
            )

        monkeypatch.setattr("specify_cli.doctrine.sources.https_source.requests.get", _fake_get)
        monkeypatch.setattr("specify_cli.doctrine.sources.https_source.requests.post", _fake_post)

        result = HttpsBundleSource(url=artifact_url).fetch(tmp_path / "snapshot")

        assert result.ok is False
        assert any("exact artifact" in error for error in result.errors)
        assert not (tmp_path / "snapshot" / "directives").exists()

    def test_artifactory_aql_retry_closes_responses_and_strips_validator(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        bundle = _make_tar_gz_bundle()
        artifact_url = "https://artifactory.example.com/artifactory/repo/pack-latest.tar.gz"
        download_response = _FakeResponse(
            status_code=200,
            body=bundle,
            headers={"Content-Type": "application/gzip"},
            url=artifact_url,
        )
        first_aql = _FakeResponse(status_code=503, url=artifact_url)
        final_aql = _FakeResponse(
            status_code=200,
            body=json.dumps(_aql_payload(bundle)).encode(),
            url=artifact_url,
        )
        responses = iter([first_aql, final_aql])
        aql_headers: list[dict[str, str]] = []

        monkeypatch.setenv("SPEC_KITTY_ORG_TOKEN", "retry-token")
        monkeypatch.setattr(
            "specify_cli.doctrine.sources.https_source.requests.get",
            lambda _url, **_kwargs: download_response,
        )

        def _fake_post(url: str, **kwargs: Any) -> _FakeResponse:
            aql_headers.append(dict(kwargs.get("headers") or {}))
            return next(responses)

        monkeypatch.setattr("specify_cli.doctrine.sources.https_source.requests.post", _fake_post)
        monkeypatch.setattr("specify_cli.doctrine.sources.https_source.time.sleep", lambda _s: None)

        result = HttpsBundleSource(
            url=artifact_url,
            if_none_match='"old-etag"',
        ).fetch(tmp_path / "snapshot")

        assert result.ok is True
        assert len(aql_headers) == 2
        assert all(headers.get("Authorization") == "Bearer retry-token" for headers in aql_headers)
        assert all("If-None-Match" not in headers for headers in aql_headers)
        assert download_response.closed is True
        assert first_aql.closed is True
        assert final_aql.closed is True

    @pytest.mark.parametrize(
        ("item_url", "source_type", "expected_error"),
        [
            (
                "https://artifactory.example.com/repo/pack.tar.gz",
                "artifactory",
                "valid Artifactory item URL",
            ),
            (
                "https://artifactory.example.com/artifactory/repo/folder%2Fpack.tar.gz",
                "https",
                "valid Artifactory item URL",
            ),
            (
                "https://artifactory.example.com/artifactory/repo/%ZZpack.tar.gz",
                "https",
                "URL is invalid",
            ),
            (
                "https://artifactory.example.com/artifactory/repo//pack.tar.gz",
                "https",
                "valid Artifactory item URL",
            ),
            (
                "https://artifactory.example.com/artifactory/repo/../pack.tar.gz",
                "https",
                "valid Artifactory item URL",
            ),
        ],
    )
    def test_artifactory_source_rejects_non_derivable_item_url(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        item_url: str,
        source_type: str,
        expected_error: str,
    ) -> None:
        calls: list[str] = []

        def _fake_get(url: str, **kwargs: Any) -> _FakeResponse:
            calls.append(url)
            return _FakeResponse(status_code=500, url=url)

        monkeypatch.setattr("specify_cli.doctrine.sources.https_source.requests.get", _fake_get)

        result = HttpsBundleSource(
            url=item_url,
            source_type=source_type,
        ).fetch(tmp_path / "snapshot")

        assert result.ok is False
        assert any(expected_error in error for error in result.errors)
        assert calls == []

    def test_artifactory_version_is_bound_to_downloaded_sha256(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        bundle = _make_tar_gz_bundle()
        artifact_url = "https://artifactory.example.com/artifactory/repo/pack-latest.tar.gz"

        def _fake_get(url: str, **kwargs: Any) -> _FakeResponse:
            return _FakeResponse(
                status_code=200,
                body=bundle,
                headers={"Content-Type": "application/gzip"},
                url=url,
            )

        def _fake_post(url: str, **kwargs: Any) -> _FakeResponse:
            return _FakeResponse(
                status_code=200,
                body=json.dumps(
                    _aql_payload(
                        bundle,
                        version="version-for-other-bytes",
                        sha256="0" * 64,
                    )
                ).encode(),
                url=url,
            )

        monkeypatch.setattr("specify_cli.doctrine.sources.https_source.requests.get", _fake_get)
        monkeypatch.setattr("specify_cli.doctrine.sources.https_source.requests.post", _fake_post)

        result = HttpsBundleSource(url=artifact_url, source_type="artifactory").fetch(tmp_path / "snapshot")

        assert result.ok is False
        assert any("checksum" in error.lower() for error in result.errors)
        assert not (tmp_path / "snapshot" / "directives").exists()

    def test_artifactory_download_fails_when_version_property_is_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        bundle = _make_tar_gz_bundle()
        artifact_url = "https://artifactory.example.com/artifactory/raf-generic-local/doctrines/doctrine-rnd-latest.tar.gz"

        def _fake_get(url: str, **kwargs: Any) -> _FakeResponse:
            return _FakeResponse(
                status_code=200,
                body=bundle,
                headers={"Content-Type": "application/gzip"},
                url=url,
            )

        def _fake_post(url: str, **kwargs: Any) -> _FakeResponse:
            return _FakeResponse(
                status_code=200,
                body=json.dumps(
                    _aql_payload(
                        bundle,
                        repo="raf-generic-local",
                        path="doctrines",
                        name="doctrine-rnd-latest.tar.gz",
                        version=None,
                    )
                ).encode(),
                url=url,
            )

        monkeypatch.setattr("specify_cli.doctrine.sources.https_source.requests.get", _fake_get)
        monkeypatch.setattr("specify_cli.doctrine.sources.https_source.requests.post", _fake_post)

        result = HttpsBundleSource(url=artifact_url, source_type="artifactory").fetch(tmp_path / "snapshot")

        assert result.ok is False
        assert any("version property" in error for error in result.errors)

    def test_artifactory_download_fails_when_file_checksum_is_missing(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        bundle = _make_tar_gz_bundle()
        artifact_url = "https://artifactory.example.com/artifactory/repo/pack-latest.tar.gz"

        def _fake_get(url: str, **kwargs: Any) -> _FakeResponse:
            return _FakeResponse(
                status_code=200,
                body=bundle,
                headers={"Content-Type": "application/gzip"},
                url=url,
            )

        def _fake_post(url: str, **kwargs: Any) -> _FakeResponse:
            payload = _aql_payload(bundle)
            result = payload["results"]
            assert isinstance(result, list) and isinstance(result[0], dict)
            result[0].pop("sha256")
            return _FakeResponse(
                status_code=200,
                body=json.dumps(payload).encode(),
                url=url,
            )

        monkeypatch.setattr("specify_cli.doctrine.sources.https_source.requests.get", _fake_get)
        monkeypatch.setattr("specify_cli.doctrine.sources.https_source.requests.post", _fake_post)

        result = HttpsBundleSource(url=artifact_url, source_type="artifactory").fetch(tmp_path / "snapshot")

        assert result.ok is False
        assert any("SHA-256 checksum" in error for error in result.errors)

    def test_304_unchanged_skips_download(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "snapshot"
        captured: dict[str, Any] = {}

        def _fake_get(url: str, **kwargs: Any) -> _FakeResponse:
            captured["headers"] = kwargs.get("headers") or {}
            return _FakeResponse(status_code=304, body=b"", reason="Not Modified")

        monkeypatch.setattr("specify_cli.doctrine.sources.https_source.requests.get", _fake_get)

        result = HttpsBundleSource(
            url="https://example.com/pack.tar.gz",
            if_none_match='"abc123"',
        ).fetch(target)

        assert result.ok is True
        assert result.unchanged is True
        assert result.etag == '"abc123"'
        assert result.pack_version is None
        assert result.artifacts_written == 0
        assert captured["headers"].get("If-None-Match") == '"abc123"'
        assert list(target.iterdir()) == []  # nothing extracted

    def test_unsolicited_304_without_validator_fails(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        response = _FakeResponse(status_code=304, reason="Not Modified")
        monkeypatch.setattr(
            "specify_cli.doctrine.sources.https_source.requests.get",
            lambda _url, **_kwargs: response,
        )

        result = HttpsBundleSource(url="https://example.com/pack.tar.gz").fetch(tmp_path / "snapshot")

        assert result.ok is False
        assert any("without an If-None-Match" in error for error in result.errors)
        assert response.closed is True

    def test_zip_extraction(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "snapshot"
        bundle = _make_zip_bundle()

        def _fake_get(url: str, **kwargs: Any) -> _FakeResponse:
            return _FakeResponse(
                status_code=200,
                body=bundle,
                headers={"Content-Type": "application/zip"},
                url=url,
            )

        monkeypatch.setattr("specify_cli.doctrine.sources.https_source.requests.get", _fake_get)

        result = HttpsBundleSource(
            url="https://example.com/pack.zip",
            ref="v2.0.0",
        ).fetch(target)

        assert result.ok is True
        assert result.pack_version == "v2.0.0"  # ref wins over (absent) ETag
        assert (target / "directives" / "sec.directive.yaml").is_file()

    def test_401_returns_auth_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        def _fake_get(url: str, **kwargs: Any) -> _FakeResponse:
            return _FakeResponse(status_code=401, body=b"", reason="Unauthorized")

        monkeypatch.setattr("specify_cli.doctrine.sources.https_source.requests.get", _fake_get)

        result = HttpsBundleSource(url="https://example.com/pack.tar.gz").fetch(tmp_path / "snapshot")

        assert result.ok is False
        assert any("SPEC_KITTY_ORG_TOKEN" in err for err in result.errors)

    def test_5xx_retried_once(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        bundle = _make_tar_gz_bundle()
        first = _FakeResponse(status_code=503, body=b"", reason="Service Unavailable")
        responses = iter(
            [
                first,
                _FakeResponse(
                    status_code=200,
                    body=bundle,
                    headers={"Content-Type": "application/gzip"},
                    url="https://example.com/pack.tar.gz",
                ),
            ]
        )

        def _fake_get(url: str, **kwargs: Any) -> _FakeResponse:
            return next(responses)

        monkeypatch.setattr("specify_cli.doctrine.sources.https_source.requests.get", _fake_get)
        monkeypatch.setattr("specify_cli.doctrine.sources.https_source.time.sleep", lambda _s: None)

        result = HttpsBundleSource(url="https://example.com/pack.tar.gz").fetch(tmp_path / "snapshot")

        assert result.ok is True
        assert first.closed is True

    def test_network_error_does_not_echo_signed_url(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        secret_url = "https://oauth2:password@example.com/pack.tar.gz?token=signed-secret"

        def _fail(_url: str, **_kwargs: Any) -> _FakeResponse:
            raise requests.ConnectionError(f"failed for {secret_url}")

        monkeypatch.setattr("specify_cli.doctrine.sources.https_source.requests.get", _fail)

        result = HttpsBundleSource(url=secret_url).fetch(tmp_path / "snapshot")

        rendered = " ".join(result.errors)
        assert result.ok is False
        assert "password" not in rendered
        assert "signed-secret" not in rendered
        assert "https://example.com/pack.tar.gz" in rendered

    def test_auth_header_is_used(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        bundle = _make_tar_gz_bundle()
        seen_headers: dict[str, str] = {}

        def _fake_get(url: str, **kwargs: Any) -> _FakeResponse:
            seen_headers.update(kwargs.get("headers") or {})
            return _FakeResponse(
                status_code=200,
                body=bundle,
                headers={"Content-Type": "application/gzip"},
                url=url,
            )

        monkeypatch.setenv("SPEC_KITTY_ORG_TOKEN", "tok123")
        monkeypatch.setattr("specify_cli.doctrine.sources.https_source.requests.get", _fake_get)

        HttpsBundleSource(url="https://example.com/pack.tar.gz").fetch(tmp_path / "snapshot")

        assert seen_headers.get("Authorization") == "Bearer tok123"


# ---------------------------------------------------------------------------
# ApiSource
# ---------------------------------------------------------------------------
class _FakeApiServer:
    """Tiny dispatcher used to mock ``requests.request`` for ApiSource tests."""

    def __init__(self, routes: dict[str, _FakeResponse]) -> None:
        self.routes = routes
        self.headers_seen: list[dict[str, str]] = []
        self.calls: list[str] = []

    def __call__(self, method: str, url: str, **kwargs: Any) -> _FakeResponse:
        self.calls.append(url)
        self.headers_seen.append(dict(kwargs.get("headers") or {}))
        for suffix, response in self.routes.items():
            if url.endswith(suffix):
                return response
        return _FakeResponse(status_code=404, body=b"", reason="Not Found")


def _json_response(payload: Any, status_code: int = 200) -> _FakeResponse:
    return _FakeResponse(
        status_code=status_code,
        body=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )


class TestApiSource:
    def test_full_flow(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "snapshot"
        server = _FakeApiServer(
            routes={
                "/artifact-types": _json_response({"types": ["directives", "agent_profiles"]}),
                "/artifacts/directives": _json_response(
                    {
                        "artifacts": [
                            {
                                "id": "sec-001",
                                "filename": "sec-001.directive.yaml",
                                "content": "id: sec-001\n",
                            }
                        ]
                    }
                ),
                "/artifacts/agent_profiles": _json_response(
                    {
                        "artifacts": [
                            {
                                "id": "eng",
                                "filename": "eng.agent.yaml",
                                "content": "id: eng\n",
                            }
                        ]
                    }
                ),
                "/drg-extensions": _json_response(
                    {
                        "fragments": [
                            {
                                "filename": "010-security.graph.yaml",
                                "content": "edges: []\n",
                            }
                        ]
                    }
                ),
                "/version": _json_response({"version": "v1.4.2"}),
            }
        )
        monkeypatch.setattr("specify_cli.doctrine.sources.api_source.requests.request", server)

        result = ApiSource(url="https://example.com/api").fetch(target)

        assert result.ok is True
        assert result.pack_version == "v1.4.2"
        assert (target / "directives" / "sec-001.directive.yaml").is_file()
        assert (target / "agent_profiles" / "eng.agent.yaml").is_file()
        assert (target / "drg" / "010-security.graph.yaml").is_file()
        # 1 directive + 1 agent + 1 drg fragment.
        assert result.artifacts_written == 3

    def test_no_drg_endpoint(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "snapshot"
        server = _FakeApiServer(
            routes={
                "/artifact-types": _json_response({"types": ["directives"]}),
                "/artifacts/directives": _json_response(
                    {
                        "artifacts": [
                            {
                                "id": "x",
                                "filename": "x.directive.yaml",
                                "content": "id: x\n",
                            }
                        ]
                    }
                ),
                # /drg-extensions and /version both fall through to 404.
            }
        )
        monkeypatch.setattr("specify_cli.doctrine.sources.api_source.requests.request", server)

        result = ApiSource(url="https://example.com/api", ref="v0.9").fetch(target)

        assert result.ok is True
        assert not (target / "drg").exists()
        # Falls back to ref when /version returns 404 without Date.
        assert result.pack_version == "v0.9"

    def test_default_types_when_artifact_types_404(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "snapshot"
        # All endpoints 404 -> default type list, all empty.
        server = _FakeApiServer(routes={})
        monkeypatch.setattr("specify_cli.doctrine.sources.api_source.requests.request", server)

        result = ApiSource(url="https://example.com/api").fetch(target)

        assert result.ok is True
        assert result.artifacts_written == 0
        # Should have called /artifact-types AND each default type's endpoint.
        called_suffixes = {url.split("/api", 1)[1] for url in server.calls}
        assert "/artifact-types" in called_suffixes
        assert "/artifacts/directives" in called_suffixes
        assert "/artifacts/agent_profiles" in called_suffixes

    def test_auth_header_override(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "snapshot"
        server = _FakeApiServer(routes={"/artifact-types": _json_response({"types": []})})
        monkeypatch.setattr("specify_cli.doctrine.sources.api_source.requests.request", server)
        monkeypatch.setenv("SPEC_KITTY_ORG_AUTH_HEADER", "Basic dXNlcjpwYXNz")

        ApiSource(url="https://example.com/api").fetch(target)

        # The custom header must appear verbatim on the first request.
        assert server.headers_seen[0].get("Authorization") == "Basic dXNlcjpwYXNz"

    def test_credential_error_propagates(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        server = _FakeApiServer(routes={"/artifact-types": _FakeResponse(status_code=401, body=b"", reason="Unauthorized")})
        monkeypatch.setattr("specify_cli.doctrine.sources.api_source.requests.request", server)

        result = ApiSource(url="https://example.com/api").fetch(tmp_path / "snapshot")

        assert result.ok is False
        assert any("SPEC_KITTY_ORG_TOKEN" in err for err in result.errors)
