"""Git-clone-backed org doctrine source.

``GitSource`` is a *persistent* clone manager: ``target_dir`` IS the working
repository — ``.git/`` is preserved across fetches.

Hand-authored packs are preserved on both fetch paths (#4960, #4989):

* ``_first_install`` clones into a ``.tmp-<uuid>`` sibling and promotes it onto
  ``target_dir`` via the move-aside pattern borrowed from
  :mod:`specify_cli.doctrine.snapshot` (``.old-<uuid>`` → promote → restore on
  failure). A failed clone/checkout removes ONLY the temp — never
  ``target_dir`` — and a pre-existing non-empty ``target_dir`` is refused up
  front instead of being clobbered.
* ``_update`` resolves the ``reset --hard`` target by ref type (``origin/<ref>``
  only for a real remote branch, else the bare ``<ref>`` for a tag/SHA) and
  refuses — leaving the working tree and its history untouched — when the pack
  has uncommitted local changes or local commits ahead of the reset target,
  rather than silently discarding them.

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
from uuid import uuid4

from specify_cli.git import ref_advance

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
        # A valid clone (``.git`` present) is routed to ``_update`` by ``fetch``;
        # ``_first_install`` only sees a missing/empty/foreign dir. A pre-existing
        # non-empty ``target_dir`` is a hand-authored pack (or foreign content) we
        # must never clobber (#4960) — refuse before touching anything. An empty
        # dir is permitted: ``template_render/resolve.py::_resolve_git`` passes an
        # empty ``mkdtemp`` here.
        if target_dir.exists() and self._is_non_empty(target_dir):
            return _error_result(
                f"Refusing to clone into non-empty directory {target_dir}: it holds existing content that a clone would overwrite. Move or remove it first."
            )

        target_dir.parent.mkdir(parents=True, exist_ok=True)
        tmp_dir = target_dir.parent / f".tmp-{uuid4().hex}"

        clone_proc = self._run_git(["git", "clone", effective_url, str(tmp_dir)])
        if clone_proc.returncode != 0:
            # Remove ONLY the temp — target_dir is left exactly as found (#4960).
            shutil.rmtree(tmp_dir, ignore_errors=True)
            return _error_result(_redact_git_tokens(clone_proc.stderr.strip()) or "git clone failed")

        if self.ref:
            checkout_proc = self._run_git(["git", "-C", str(tmp_dir), "checkout", self.ref])
            if checkout_proc.returncode != 0:
                shutil.rmtree(tmp_dir, ignore_errors=True)
                return _error_result(_redact_git_tokens(checkout_proc.stderr.strip()) or "git checkout failed")

        promote_error = self._promote(tmp_dir, target_dir)
        if promote_error is not None:
            return _error_result(promote_error)

        return self._success_result(target_dir)

    @staticmethod
    def _is_non_empty(path: Path) -> bool:
        """True when ``path`` is a non-directory or a directory with any entry."""
        if not path.is_dir():
            return True
        return any(path.iterdir())

    @staticmethod
    def _promote(tmp_dir: Path, target_dir: Path) -> str | None:
        """Move ``tmp_dir`` onto ``target_dir`` via move-aside; return error or None.

        Mirrors :mod:`specify_cli.doctrine.snapshot` (:196-228): move any existing
        ``target_dir`` aside to ``.old-<uuid>`` first (a bare ``Path.replace`` onto
        a non-empty dir raises ``ENOTEMPTY``, and on Windows even onto an existing
        empty dir), promote the temp, restore on failure, delete the backup only
        after a successful promote.
        """
        old_dir: Path | None = None
        promoted = False
        try:
            if target_dir.exists():
                old_dir = target_dir.parent / f".old-{target_dir.name}-{uuid4().hex}"
                target_dir.replace(old_dir)
            tmp_dir.replace(target_dir)
            promoted = True
        except OSError as exc:
            shutil.rmtree(tmp_dir, ignore_errors=True)
            message = f"Failed to install cloned pack at {target_dir}: {exc}"
            if old_dir is not None and old_dir.exists() and not target_dir.exists():
                try:
                    old_dir.replace(target_dir)
                except OSError as restore_exc:
                    message += f"; automatic restore failed — the previous content is preserved at {old_dir}: {restore_exc}"
            return message
        finally:
            if promoted and old_dir is not None and old_dir.exists():
                shutil.rmtree(old_dir, ignore_errors=True)
        return None

    def _update(self, target_dir: Path) -> FetchResult:
        fetch_proc = self._run_git(["git", "-C", str(target_dir), "fetch", "--tags", "origin"])
        if fetch_proc.returncode != 0:
            # Existing clone remains untouched on update failure.
            return _error_result(_redact_git_tokens(fetch_proc.stderr.strip()) or "git fetch failed")

        reset_target = self._resolve_reset_target(target_dir)

        # Never let ``reset --hard`` silently discard local work (#4989). Refusing
        # leaves the working tree and its history exactly as found (like the
        # fetch-failure early return), so the local content stays recoverable.
        refusal = self._local_changes_refusal(target_dir, reset_target)
        if refusal is not None:
            return _error_result(
                f"Refusing to update pack at {target_dir}: {refusal}. The local content "
                f"is preserved in place (no reset performed) — resolve or relocate it, then re-fetch."
            )

        reset_proc = self._run_git(["git", "-C", str(target_dir), "reset", "--hard", reset_target])
        if reset_proc.returncode != 0:
            return _error_result(_redact_git_tokens(reset_proc.stderr.strip()) or "git reset failed")

        return self._success_result(target_dir)

    def _resolve_reset_target(self, target_dir: Path) -> str:
        """Resolve the ``reset --hard`` target by ref type (#4989 sub-bug B / F6).

        A real remote branch resets to ``origin/<ref>`` so the pack actually
        advances after ``fetch`` moved the remote-tracking ref. A tag or SHA has
        no ``origin/<ref>`` remote-tracking ref, so it resets to the bare
        ``<ref>`` — a blanket ``origin/<ref>`` would regress tag/SHA-pinned packs.
        """
        if not self.ref:
            return "origin/HEAD"
        remote_branch = self._run_git(["git", "-C", str(target_dir), "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{self.ref}"])
        if remote_branch.returncode == 0:
            return f"origin/{self.ref}"
        return self.ref

    def _local_changes_refusal(self, target_dir: Path, reset_target: str) -> str | None:
        """Return a refusal reason when ``reset --hard`` would destroy local work.

        Reuses :func:`ref_advance._dirty_entries` (arch gate forbids a parallel
        ``git status`` predicate) for uncommitted/obstructing changes, and adds an
        explicit ahead check for committed-ahead history — which a status-only
        dirty check cannot see and a worktree-bytes archive cannot preserve (F7).
        Fail-closed: any inability to determine the state refuses.
        """
        try:
            target_paths = ref_advance._target_tree_paths(target_dir, reset_target, None)
        except ref_advance.RefAdvanceError as exc:
            return f"could not inspect the target tree {reset_target!r} ({exc})"

        try:
            dirty = ref_advance._dirty_entries(target_dir, None, new_sha=reset_target, target_paths=target_paths)
        except ref_advance.RefAdvanceError as exc:
            return f"could not inspect the working tree ({exc})"
        if dirty:
            joined = "\n".join(f"    {entry}" for entry in dirty)
            return "the working tree holds uncommitted local changes\n" + joined

        ahead = self._run_git(["git", "-C", str(target_dir), "rev-list", "--count", f"{reset_target}..HEAD"])
        if ahead.returncode != 0:
            return f"could not determine whether local commits are ahead of {reset_target!r} ({ahead.stderr.strip()})"
        count_text = ahead.stdout.strip()
        if not count_text.isdigit():
            return f"could not parse the ahead-count for {reset_target!r} (got {count_text!r})"
        if int(count_text) > 0:
            return f"{count_text} local commit(s) are ahead of {reset_target!r} that a reset would orphan"
        return None

    def _success_result(self, target_dir: Path) -> FetchResult:
        return FetchResult(
            ok=True,
            artifacts_written=_count_yaml_files(target_dir),
            pack_version=self._describe(target_dir),
            errors=[],
        )

    def _describe(self, target_dir: Path) -> str | None:
        describe = self._run_git(["git", "-C", str(target_dir), "describe", "--tags", "--always"])
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
        # Non-interactive by default: an automated fetch must fail closed on a
        # missing credential rather than hang on a terminal prompt.
        env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
        return subprocess.run(  # noqa: S603 - argv is constructed in-module
            argv,
            capture_output=True,
            text=True,
            check=False,
            env=env,
        )


def _error_result(message: str) -> FetchResult:
    """Build a failed :class:`FetchResult` carrying a single error message."""
    return FetchResult(ok=False, artifacts_written=0, pack_version=None, errors=[message])


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
