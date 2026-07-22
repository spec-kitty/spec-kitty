"""Git-clone-backed org doctrine source.

``GitSource`` is a *persistent* clone manager: ``target_dir`` IS the working
repository — ``.git/`` is preserved across fetches.  The atomic-write pattern
in :mod:`specify_cli.doctrine.snapshot` deliberately does NOT apply here; git
provides its own consistency guarantees via ``fetch`` + ``reset --hard``.

Authentication relies on the system git config (SSH keys, credential helper).
For HTTPS URLs, a ``GIT_TOKEN`` env var is injected as an OAuth2 user so that
CI can pass a short-lived token without modifying ``~/.gitconfig``.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from .protocol import FetchResult


@dataclass
class GitSource:
    """Source that clones (or updates) a git repository in place.

    Args:
        url: Repository URL (SSH or HTTPS).
        ref: Optional branch, tag, or commit SHA to check out.  When omitted,
            the default branch is used (``origin/HEAD`` on update).
        inject_token: When True (default), embed ``GIT_TOKEN`` as HTTPS
            userinfo for CI-authenticated fetches. Set False for untrusted
            template URLs (doctrine ``org init --template``).
    """

    url: str
    ref: str | None = None
    inject_token: bool = True

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def fetch(self, target_dir: Path) -> FetchResult:
        """Clone or update the git repository at ``target_dir``."""
        target_dir = Path(target_dir)
        effective_url = self._inject_token(self.url)

        if (target_dir / ".git").exists():
            return self._update(target_dir)
        return self._first_install(target_dir, effective_url)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _first_install(self, target_dir: Path, effective_url: str) -> FetchResult:
        target_dir.parent.mkdir(parents=True, exist_ok=True)

        clone_proc = self._run_git(["git", "clone", effective_url, str(target_dir)])
        if clone_proc.returncode != 0:
            # Clean up any partial clone so a retry starts from a known state.
            if target_dir.exists():
                shutil.rmtree(target_dir, ignore_errors=True)
            return FetchResult(
                ok=False,
                artifacts_written=0,
                pack_version=None,
                errors=[
                    _redact_git_tokens(clone_proc.stderr.strip())
                    or "git clone failed"
                ],
            )

        if self.ref:
            checkout_proc = self._run_git(
                ["git", "-C", str(target_dir), "checkout", self.ref]
            )
            if checkout_proc.returncode != 0:
                shutil.rmtree(target_dir, ignore_errors=True)
                return FetchResult(
                    ok=False,
                    artifacts_written=0,
                    pack_version=None,
                    errors=[
                        _redact_git_tokens(checkout_proc.stderr.strip())
                        or "git checkout failed"
                    ],
                )

        return self._success_result(target_dir)

    def _update(self, target_dir: Path) -> FetchResult:
        fetch_proc = self._run_git(
            ["git", "-C", str(target_dir), "fetch", "--tags", "origin"]
        )
        if fetch_proc.returncode != 0:
            # Existing clone remains untouched on update failure.
            return FetchResult(
                ok=False,
                artifacts_written=0,
                pack_version=None,
                errors=[
                    _redact_git_tokens(fetch_proc.stderr.strip())
                    or "git fetch failed"
                ],
            )

        reset_target = self.ref if self.ref else "origin/HEAD"
        reset_proc = self._run_git(
            ["git", "-C", str(target_dir), "reset", "--hard", reset_target]
        )
        if reset_proc.returncode != 0:
            return FetchResult(
                ok=False,
                artifacts_written=0,
                pack_version=None,
                errors=[
                    _redact_git_tokens(reset_proc.stderr.strip())
                    or "git reset failed"
                ],
            )

        return self._success_result(target_dir)

    def _success_result(self, target_dir: Path) -> FetchResult:
        return FetchResult(
            ok=True,
            artifacts_written=_count_yaml_files(target_dir),
            pack_version=self._describe(target_dir),
            errors=[],
        )

    def _describe(self, target_dir: Path) -> str | None:
        describe = self._run_git(
            ["git", "-C", str(target_dir), "describe", "--tags", "--always"]
        )
        if describe.returncode != 0:
            return None
        version = describe.stdout.strip()
        return version or None

    def _inject_token(self, url: str) -> str:
        if not self.inject_token:
            return url
        token = os.environ.get("GIT_TOKEN")
        if not token:
            return url
        if not url.startswith("https://"):
            return url
        # Insert token as oauth2 user. URL-encode so reserved chars cannot
        # split the credential field; stderr is redacted before returning.
        return url.replace("https://", f"https://oauth2:{quote(token, safe='')}@", 1)

    @staticmethod
    def _run_git(argv: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(  # noqa: S603 - argv is constructed in-module
            argv,
            capture_output=True,
            text=True,
            check=False,
        )


def _count_yaml_files(target_dir: Path) -> int:
    """Count ``*.yaml`` files in ``target_dir`` excluding ``.git/``."""
    if not target_dir.exists():
        return 0
    count = 0
    for path in target_dir.rglob("*.yaml"):
        if ".git" in path.parts:
            continue
        count += 1
    return count


def _redact_git_tokens(text: str) -> str:
    """Remove OAuth2 credentials from git stderr before operator-facing output."""
    return re.sub(
        r"oauth2:[^\s'\"]+@(?=[^@\s/'\"]+(?::\d+)?(?:/|$))",
        "oauth2:<redacted>@",
        text,
    )
