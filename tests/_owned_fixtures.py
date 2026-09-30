"""Shared owned-checkout snapshot helper (WP02 T011).

Plain helper module, not a conftest and not a test module: the plan's Test
Layout says fixtures are never imported from test modules, so
:class:`RSnapshotter` lives here and ``tests/integration/conftest.py``
re-exposes it only through fixtures (``r_snapshot`` / ``make_r_snapshot``).
Self-tests import :class:`RSnapshotter` from here directly when they need a
snapshotter over a non-default :class:`OwnedCheckouts` (for example an
``under_worktrees`` placement), never from the conftest module.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from mission_runtime import MissionTopology, OwnedCheckout
from runtime.next._tmp_namespace import SPEC_KITTY_PROMPT_NAMESPACE, _repo_identity
from tests._owned_tree_hash import hash_tree


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


def mint_test_fact(
    *,
    repository_root: Path,
    owned_root: Path,
    mission_dir: Path,
    mission_slug: str,
    write_branch: str,
    topology: MissionTopology = MissionTopology.SINGLE_BRANCH,
) -> OwnedCheckout:
    """Mint an :class:`OwnedCheckout` for a unit test without running the ownership claim.

    The unowned unit tests that need a fact but not the full
    ``resolve_owned_mission`` validation (no linked worktree, no registry)
    build it here. ``OwnedCheckout._mint`` is the fact's one construction door;
    G3 scans ``src/`` only, so tests may call it (WP18 T097 step 3: replaces the
    retired ``OwnedMission(...)`` factory).
    """
    return OwnedCheckout._mint(
        repository_root=repository_root,
        owned_root=owned_root,
        mission_dir=mission_dir,
        mission_slug=mission_slug,
        topology=topology,
        write_branch=write_branch,
    )


def prompt_cache_prefix(owned_root: Path) -> str:
    """The ONE named NFR-001 tolerance inside ``SPEC_KITTY_HOME``, as a home-relative prefix.

    Owned ``next`` writes its prompt file under the P-keyed prompt cache
    ``SPEC_KITTY_HOME/spec-kitty-prompts/<key derived from P>/`` (the key is the
    production ``_repo_identity`` of the owned checkout, so it is never re-derived
    here). Nothing else under the home, and no prompt directory keyed to another
    checkout, is tolerated. Defined once, next to the status-mutex tolerance in
    :meth:`RSnapshotter.assert_unchanged`.
    """
    return f"{SPEC_KITTY_PROMPT_NAMESPACE}/{_repo_identity(owned_root)}/"


class RSnapshot:
    """One point-in-time snapshot of R's observable state (NFR-001)."""

    def __init__(
        self,
        *,
        files: dict[str, str],
        head: str,
        index_stage: str,
        index_diff: str,
        lock_files: dict[str, str],
        home_files: dict[str, str],
    ) -> None:
        self.files = files
        self.head = head
        self.index_stage = index_stage
        self.index_diff = index_diff
        self.lock_files = lock_files
        self.home_files = home_files


class RSnapshotter:
    """Snapshots R's working tree, HEAD, index, lock root and SPEC_KITTY_HOME.

    Excludes exactly the owned root's resolved subtree from the file walk
    when it lives under R (any placement -- sibling or under
    ``R/.worktrees/`` -- works, since the exclusion test is
    ``owned_root.is_relative_to(repository_root)``, not a placement-specific
    branch). Requests the canonical home fixture; never sets
    ``SPEC_KITTY_HOME`` itself (see ``canonical_home``'s docstring).
    """

    def __init__(self, repository_root: Path, owned_root: Path, home: Path | None) -> None:
        self._repository_root = repository_root
        self._owned_root = owned_root
        self._home = home

    def take(self) -> RSnapshot:
        r = self._repository_root
        exclude = self._owned_root if self._owned_root.is_relative_to(r) else None
        files = hash_tree(r, exclude=exclude)
        head = _git(r, "rev-parse", "HEAD")
        index_stage = _git(r, "ls-files", "--stage")
        index_diff = _git(r, "diff", "--cached")
        from kernel.git_topology import git_common_dir
        from specify_cli.core.checkout_file_lock import LOCK_DIRECTORY

        lock_dir = git_common_dir(r) / LOCK_DIRECTORY
        lock_files = hash_tree(lock_dir) if lock_dir.exists() else {}
        home_files = hash_tree(self._home) if self._home is not None and self._home.exists() else {}
        return RSnapshot(
            files=files,
            head=head,
            index_stage=index_stage,
            index_diff=index_diff,
            lock_files=lock_files,
            home_files=home_files,
        )

    def assert_unchanged(
        self,
        before: RSnapshot,
        after: RSnapshot,
        *,
        tolerate_status_mutex_for: str | None = None,
    ) -> None:
        """Raise (with the added/removed/changed keys per component printed first).

        ``tolerate_status_mutex_for``, when given a lock key (the mission
        directory name a caller/``BookkeepingTransaction`` composes -- see
        ``status.locking.feature_status_lock_path``), tolerates EXACTLY ONE
        narrowly-shaped ``lock_files`` delta: the pre-existing per-mission
        status mutex appearing as a single newly-ADDED, EMPTY lock file
        (NFR-001). The git common directory is shared by construction
        between R and any owned checkout beneath it, and every owned
        transactional write already acquires this mutex there -- that
        behaviour predates this fixture and is out of scope to convert here.
        Every OTHER shape in ``lock_files`` still fails: a second key, a
        removed key, a changed key, a non-empty lock, or a holder sidecar.
        The second and last named tolerance is ``home_files`` under
        :func:`prompt_cache_prefix` (the P-keyed prompt cache owned ``next``
        writes); every other home path, including a prompt directory keyed to a
        different checkout, still fails. ``files``, ``head``, ``index_stage`` and
        ``index_diff`` are always compared unconditionally.
        """
        from hashlib import sha256  # noqa: TID251 — file-integrity checksum for the R snapshot (standard SHA-256), not charter freshness hashing

        from specify_cli.status.locking import feature_status_lock_path

        empty_lock_hash = sha256(b"").hexdigest()
        tolerated_key = feature_status_lock_path(self._repository_root, tolerate_status_mutex_for).name if tolerate_status_mutex_for is not None else None
        prompt_prefix = prompt_cache_prefix(self._owned_root)
        diffs: list[str] = []
        for attr, label in (
            ("files", "files"),
            ("head", "head"),
            ("index_stage", "index_stage"),
            ("index_diff", "index_diff"),
            ("lock_files", "lock_files"),
            ("home_files", "home_files"),
        ):
            b = getattr(before, attr)
            a = getattr(after, attr)
            if isinstance(b, dict):
                if attr == "home_files":
                    b = {k: v for k, v in b.items() if not k.startswith(prompt_prefix)}
                    a = {k: v for k, v in a.items() if not k.startswith(prompt_prefix)}
                added = sorted(set(a) - set(b))
                removed = sorted(set(b) - set(a))
                changed = sorted(k for k in set(a) & set(b) if a[k] != b[k])
                if (
                    attr == "lock_files"
                    and tolerated_key is not None
                    and added == [tolerated_key]
                    and not removed
                    and not changed
                    and a[tolerated_key] == empty_lock_hash
                ):
                    continue
                if added or removed or changed:
                    diffs.append(f"{label}: added={added} removed={removed} changed={changed}")
            elif a != b:
                diffs.append(f"{label}: {b!r} -> {a!r}")
        if diffs:
            report = "R snapshot changed:\n" + "\n".join(diffs)
            print(report)  # deliberate per-component report, spec §Test Layout
            raise AssertionError(report)
