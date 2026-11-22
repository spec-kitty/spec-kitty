"""``derive_project_slug`` against real git remotes (spec-kitty#113 triage).

Deliberately not mocked: the thing under test is the interaction with git's
own URL-resolution behavior, so a mock would encode the very assumption
being verified.

spec-kitty#113 asked whether ``derive_project_slug`` needed the same
raw-config-over-transport-view fix #111 gave
``zeitgeist_client/repo_identity.py`` (both read a git remote URL on a
machine that may carry a global ``url.<base>.insteadOf`` rewrite, e.g.
every exe.dev VM). Triage conclusion: no. #111's site consumes the URL's
*host* for forge-admission; this function only ever consumes the trailing
path segment via ``url.split("/")[-1]``, and ``insteadOf`` is a pure prefix
substitution — it rewrites the host but can never touch what follows the
matched prefix. ``test_slug_unaffected_by_a_global_insteadof_transport_rewrite``
below pins that invariant so a future refactor of the URL parsing can't
silently reintroduce a host dependency.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.identity.project import derive_project_slug

pytestmark = [pytest.mark.git_repo]


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


@pytest.fixture()
def origin(tmp_path: Path) -> Path:
    bare = tmp_path / "acme-widgets.git"
    bare.mkdir()
    _git("init", "--bare", "-q", cwd=bare)
    return bare


def _clone(origin: Path, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    _git("clone", "-q", str(origin), str(dest), cwd=dest.parent)
    _git("config", "user.email", "t@example.com", cwd=dest)
    _git("config", "user.name", "t", cwd=dest)
    return dest


@pytest.fixture()
def instead_of_rewrite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """A synthetic global git config that rewrites ``https://github.com/``
    onto a proxy host, inherited by every child ``git`` through
    ``GIT_CONFIG_GLOBAL`` (the real machine config is never touched).

    Same shape as ``tests/zeitgeist_client/conftest.py``'s fixture of the
    same name (#111) — kept local here rather than shared, since this repo
    has no top-level conftest both suites can see."""
    proxy_host = "github.int.example.invalid"
    config_path = tmp_path / "global-gitconfig"
    config_path.write_text(f'[url "https://{proxy_host}/"]\n\tinsteadOf = https://github.com/\n')
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config_path))
    return proxy_host


def test_slug_derived_from_https_origin(tmp_path: Path, origin: Path) -> None:
    clone = _clone(origin, tmp_path / "work" / "some-other-dirname")
    _git("remote", "set-url", "origin", "https://github.com/acme/acme-widgets.git", cwd=clone)
    assert derive_project_slug(clone) == "acme-widgets"


def test_slug_derived_from_ssh_origin(tmp_path: Path, origin: Path) -> None:
    clone = _clone(origin, tmp_path / "work" / "some-other-dirname")
    _git("remote", "set-url", "origin", "git@github.com:acme/acme-widgets.git", cwd=clone)
    assert derive_project_slug(clone) == "acme-widgets"


def test_slug_falls_back_to_directory_name_without_a_remote(tmp_path: Path) -> None:
    local = tmp_path / "My_Project"
    local.mkdir()
    _git("init", "-q", cwd=local)
    assert derive_project_slug(local) == "my-project"


def test_slug_unaffected_by_a_global_insteadof_transport_rewrite(tmp_path: Path, origin: Path, instead_of_rewrite: str) -> None:
    """Pins the invariant ``derive_project_slug``'s docstring relies on for
    its #113 triage: a host-rewriting ``insteadOf`` changes what
    ``git remote get-url`` reports, but never the trailing path segment
    this function extracts."""
    clone = _clone(origin, tmp_path / "work" / "some-other-dirname")
    _git("remote", "set-url", "origin", "https://github.com/acme/acme-widgets.git", cwd=clone)
    assert derive_project_slug(clone) == "acme-widgets"


def test_slug_from_git_remote_is_none_without_origin(tmp_path: Path) -> None:
    """#5215: the remote-only lookup never falls back to the directory name."""
    from specify_cli.identity.project import slug_from_git_remote

    local = tmp_path / "dirname-differs"
    local.mkdir()
    _git("init", "-q", cwd=local)

    assert slug_from_git_remote(local) is None
    assert derive_project_slug(local) == "dirname-differs"


def test_remote_url_naming_no_repository_falls_back_to_directory(tmp_path: Path) -> None:
    """#5215: an empty last URL segment is "no repository", so the directory name is used."""
    from specify_cli.identity.project import slug_from_git_remote

    local = tmp_path / "dirname-differs"
    local.mkdir()
    _git("init", "-q", cwd=local)
    _git("remote", "add", "origin", "https://example.invalid/", cwd=local)

    assert slug_from_git_remote(local) is None
    assert derive_project_slug(local) == "dirname-differs"


@pytest.mark.parametrize(
    ("url", "slug"),
    [
        ("https://example.invalid/acme/acme-widgets/", "acme-widgets"),
        ("https://example.invalid/acme/acme-widgets.git/", "acme-widgets"),
        ("git@example.invalid:acme/acme-widgets.git", "acme-widgets"),
        ("https://example.invalid", None),
        ("https://user:TOKEN@example.invalid", None),
        ("https://user:TOKEN@example.invalid:8443/acme/acme-widgets.git", "acme-widgets"),
    ],
)
def test_slug_from_git_remote_url_shapes(tmp_path: Path, url: str, slug: str | None) -> None:
    """#5215 review L2: a trailing slash still names the repository; a bare host names none."""
    from specify_cli.identity.project import slug_from_git_remote

    local = tmp_path / "clone"
    local.mkdir()
    _git("init", "-q", cwd=local)
    _git("remote", "add", "origin", url, cwd=local)

    assert slug_from_git_remote(local) == slug
