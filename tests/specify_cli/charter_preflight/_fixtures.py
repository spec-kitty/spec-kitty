"""Shared helpers for charter_preflight tests.

These helpers materialise a fake repo with charter / bundle / synthesis
state so each test can describe the *deviation* from a fresh repo rather
than rebuilding the whole layout.

Kept private to ``tests.specify_cli.charter_preflight`` — not part of
the production surface.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from textwrap import dedent
from typing import cast


def init_git_repo(repo: Path) -> None:
    """Initialise a git repo with a single commit so ``git status`` works.

    The preflight runner shells out to ``git status --porcelain`` to detect
    uncommitted artifacts.  Without an actual git repo the call would
    succeed (porcelain output is empty when run outside a repo *and*
    return code 128) — we need a real repo so we can model both clean and
    dirty states.
    """
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True)
    # Need at least one commit so HEAD exists.
    (repo / ".gitignore").write_text("# placeholder\n", encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore"], cwd=repo, check=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "init"],
        cwd=repo,
        check=True,
        env={"GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "t@x", "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "t@x", "PATH": "/usr/bin:/bin"},
    )


def seed_charter(repo: Path, body: str = "# Charter\n\nHello") -> tuple[Path, Path]:
    """Create ``.kittify/charter/charter.md`` and return ``(charter, metadata)``."""
    charter_dir = repo / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    charter_path = charter_dir / "charter.md"
    metadata_path = charter_dir / "metadata.yaml"
    charter_path.write_text(body, encoding="utf-8")
    return charter_path, metadata_path


def write_metadata(metadata_path: Path, charter_path: Path, *, mismatched: bool = False) -> None:
    """Write ``metadata.yaml`` with a charter_hash matching (or not) the charter file."""
    from charter.hasher import hash_content  # noqa: PLC0415
    charter_hash = hash_content(charter_path.read_text(encoding="utf-8"))  # "sha256:<hex>"
    digest = charter_hash.split(":", 1)[1]
    if mismatched:
        digest = "0" * 64
    metadata_path.write_text(
        dedent(
            f"""\
            charter_hash: sha256:{digest}
            timestamp_utc: 2026-01-01T00:00:00+00:00
            """
        ),
        encoding="utf-8",
    )


def seed_bundle_files(repo: Path) -> None:
    """Create the three sibling bundle YAMLs the LEGACY (pre-consolidate-
    charter-bundle) ``synced_bundle`` model expected.

    consolidate-charter-bundle WP06 (Landmine 1/2, contracts/manifest-v2.md
    M1) narrowed the freshness computer's ``_BUNDLE_FILES`` /
    ``charter.bundle.BUNDLE_CONTENT_HASH_FILES`` to the single tracked,
    authored ``charter.yaml`` -- these three files no longer feed
    ``charter_source``/``synced_bundle``/``synthesized_drg`` at all. Kept as
    a no-op-for-freshness-purposes companion (harmless; some non-freshness
    consumers under test may still reference them) alongside
    :func:`seed_charter_yaml`, which is what now actually drives freshness.
    """
    charter_dir = repo / ".kittify" / "charter"
    for name in ("governance.yaml", "directives.yaml", "references.yaml"):
        (charter_dir / name).write_text("schema_version: '1'\n", encoding="utf-8")


_CHARTER_YAML_BODY = (
    "schema_version: '2.0.0'\n"
    "governance: {}\n"
    "directives:\n"
    "  directives: []\n"
    "catalog:\n"
    "  mission: preflight-fixture\n"
    "  template_set: default\n"
    "  languages: []\n"
    "  references: []\n"
    "metadata:\n"
    "  generated_at: '2026-01-01T00:00:00+00:00'\n"
    "  bundle_schema_version: 2\n"
)


def seed_charter_yaml(repo: Path, *, valid: bool = True) -> Path:
    """Create ``.kittify/charter/charter.yaml`` -- the resolving freshness
    source (consolidate-charter-bundle WP06 / Landmine 2). This is the file
    ``charter_source``/``synced_bundle``/``synthesized_drg`` actually read
    post-mission; ``seed_charter``/``write_metadata``/``seed_bundle_files``
    above model the retired ``charter.md``-hash mechanism and no longer
    drive freshness on their own.

    ``valid=False`` writes genuinely malformed YAML so ``charter_source``
    reads ``invalid`` -- the only non-``fresh``, non-``missing`` state
    reachable once the file exists (the ``charter.md``-hash ``"stale"``
    branch is retired outright, not re-homed).
    """
    charter_dir = repo / ".kittify" / "charter"
    charter_dir.mkdir(parents=True, exist_ok=True)
    charter_yaml_path = charter_dir / "charter.yaml"
    body = _CHARTER_YAML_BODY if valid else "not: [valid: yaml: at: all"
    charter_yaml_path.write_text(body, encoding="utf-8")
    return charter_yaml_path


class _AutoHash:
    """Sentinel type distinguishing "caller left ``bundle_content_hash`` unset".

    An unset value (→ auto-compute a genuinely-fresh manifest) must be
    distinguishable from an explicit ``bundle_content_hash=None`` or a
    deliberately-wrong string (→ honor verbatim, e.g. to model staleness).
    A dedicated class keeps the parameter's union precise (``str | None |
    _AutoHash``) so ``isinstance`` narrows cleanly instead of collapsing to
    ``object``.
    """


_AUTO_HASH = _AutoHash()


def seed_manifest(
    repo: Path,
    *,
    built_in_only: bool,
    created_at: str = "2099-01-01T00:00:00+00:00",
    bundle_content_hash: str | None | _AutoHash = _AUTO_HASH,
) -> Path:
    """Create ``synthesis-manifest.yaml`` with ``built_in_only`` set as desired.

    ``bundle_content_hash`` is the content-identity digest of the synced
    bundle (see ``charter.bundle.compute_bundle_content_hash``) that the
    content-identity freshness reader compares against a fresh recompute
    (synthesized-drg-stale-refresh).

    Resolution of ``bundle_content_hash``:

    * **Left unset (default)** — auto-compute a genuinely-fresh manifest:
      when ``built_in_only=False`` AND the synced bundle files exist
      (``compute_bundle_content_hash`` returns non-None), stamp
      ``schema_version: '3'`` + the real hash so the synthesized DRG reads
      as ``fresh``. This is what a real ``spec-kitty charter synthesize``
      run writes, so ANY caller that seeded bundle files and expects a
      non-blocking synthesized_drg gets it without threading the hash
      through by hand. When ``built_in_only=True`` (short-circuits before
      the hash check) or no bundle files exist (nothing to hash), fall back
      to the hash-less ``schema_version: '2'`` shape.
    * **Explicit value (incl. ``None`` or a wrong string)** — honored
      verbatim: a real ``"sha256:..."`` forces fresh; ``None`` or a
      deliberately-wrong digest forces the hash-less / mismatched shape a
      staleness test wants.
    """
    resolved_hash = _resolve_bundle_hash(repo, built_in_only=built_in_only, bundle_content_hash=bundle_content_hash)
    manifest_path = repo / ".kittify" / "charter" / "synthesis-manifest.yaml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    schema_version = "3" if resolved_hash is not None else "2"
    hash_line = f"bundle_content_hash: {resolved_hash}\n" if resolved_hash is not None else ""
    manifest_path.write_text(
        dedent(
            f"""\
            schema_version: '{schema_version}'
            mission_id: null
            created_at: '{created_at}'
            run_id: 01JTESTRUNIDXXXXXXXXXXXXXX
            adapter_id: test
            adapter_version: '0.0.0'
            synthesizer_version: '0.0.0'
            manifest_hash: {"a" * 64}
            artifacts: []
            built_in_only: {str(built_in_only).lower()}
            """
        )
        + hash_line,
        encoding="utf-8",
    )
    return manifest_path


def _resolve_bundle_hash(
    repo: Path,
    *,
    built_in_only: bool,
    bundle_content_hash: str | None | _AutoHash,
) -> str | None:
    """Resolve the ``bundle_content_hash`` value to write into the manifest."""
    if not isinstance(bundle_content_hash, _AutoHash):
        # Explicit caller override (real digest, ``None``, or a wrong string).
        return bundle_content_hash
    if built_in_only:
        # built_in_only short-circuits before the hash check — no hash needed.
        return None
    # Auto-compute the genuinely-fresh digest (None when bundle files absent).
    from charter.bundle import compute_bundle_content_hash  # noqa: PLC0415

    # ``charter.*`` is ``follow_imports=skip``'d in the single-file (``spec-kitty
    # lint``) mypy invocation, so this call's declared return type collapses to
    # ``Any`` at the call site — cast it back, matching the repo-wide pattern
    # (this mission's tracer F7). Reads as ``redundant-cast`` only under the
    # advisory full-package run.
    return cast("str | None", compute_bundle_content_hash(repo))


def seed_graph(repo: Path) -> Path:
    """Create ``.kittify/charter-packs/graph.yaml`` (a minimal valid graph)."""
    graph_path = repo / ".kittify" / "charter-packs" / "graph.yaml"
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    graph_path.write_text("schema_version: '1.0'\nnodes: []\nedges: []\n", encoding="utf-8")
    return graph_path


#: ``PopulateSlashCommandsMigration.detect()`` (``m_0_10_1_populate_slash_commands.py:46``)
#: treats fewer than 8 ``spec-kitty.*.md`` files under ``.claude/commands/`` as "migration
#: needed", then routes into ``can_apply()``, which fails on a minimal package install (no
#: ``.kittify/missions/*/command-templates`` -- that subdirectory is generated at ``spec-kitty
#: init`` time, not shipped in the package `EnsureMissionsMigration` copies from). Matching
#: this exact threshold is what lets ``spec-kitty upgrade``'s sequential migration runner (which
#: stops on first failure, ``runner.py:177-178``) skip past this unrelated precondition instead
#: of halting on it.
_REALISTIC_AGENT_COMMAND_COUNT = 8


def seed_realistic_agent_scaffolding(repo: Path) -> None:
    """Seed ``.claude/commands/`` with placeholder ``spec-kitty.*.md`` files.

    **Why (added after WP01 review cycle 1 / contract C-EFF-7)**: F2 and F4 model a project
    that is *blocking* on ``charter_source``/``synced_bundle`` -- but that is not a state any
    real operator occupies in isolation. A real legacy-bundle or invalid-``charter.yaml``
    project is a real spec-kitty project, with the rest of its agent-command scaffolding
    already present from ``spec-kitty init``. Without this, a fixture built from only the
    charter-layer artifacts is artificially minimal: ``spec-kitty upgrade``'s migration runner
    halts on the unrelated ``0.10.1_populate_slash_commands`` precondition
    (``PopulateSlashCommandsMigration.can_apply`` -- "No mission command templates found")
    before ever reaching ``ConsolidateCharterBundleMigration``, the migration that actually
    composes ``charter.yaml`` from the legacy bundle. Against that artificial fixture, even a
    genuinely correct remediation reads as ineffective -- a false negative, which is worse than
    no gate at all because it looks like evidence.

    Seeding >= :data:`_REALISTIC_AGENT_COMMAND_COUNT` files makes
    ``PopulateSlashCommandsMigration.detect()`` report "not needed" on its own threshold, so the
    migration is skipped outright rather than routed around by a parallel test-only mechanism
    (DIRECTIVE_044).
    """
    commands_dir = repo / ".claude" / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)
    for i in range(_REALISTIC_AGENT_COMMAND_COUNT):
        (commands_dir / f"spec-kitty.placeholder{i}.md").write_text(
            f"# Placeholder command {i}\n\nFixture scaffolding -- not a real command.\n",
            encoding="utf-8",
        )


def build_f1_no_charter(repo: Path) -> Path:
    """F1 (data-model.md) — no charter at all; never initialised.

    Advisory / non-blocking treatment must not change (FR-006). Composed
    purely from :func:`init_git_repo` — no charter artifacts of any kind.
    """
    init_git_repo(repo)
    return repo


def build_f2_legacy_bundle_no_charter_yaml(repo: Path) -> Path:
    """F2 (data-model.md) — legacy multi-file bundle present, **no**
    ``charter.yaml``. The mission's trigger state (BC-2): a project that
    upgraded through the pre-consolidate-charter-bundle layout but never
    generated the authoritative ``charter.yaml``. Blocking, and the P0 fix
    target — its remediation must actually change ``charter_source`` /
    ``synced_bundle`` state (C-EFF-1).

    Includes :func:`seed_realistic_agent_scaffolding` (C-EFF-7, review cycle
    1) so the fixture represents a real spec-kitty project's trigger state,
    not an artificially minimal one that cannot support any remediation
    reaching completion.
    """
    init_git_repo(repo)
    charter_path, metadata_path = seed_charter(repo)
    write_metadata(metadata_path, charter_path)
    seed_bundle_files(repo)
    seed_realistic_agent_scaffolding(repo)
    return repo


def build_f3_valid_charter(repo: Path) -> Path:
    """F3 (data-model.md) — ``charter.yaml`` present and valid, full fresh
    stack. Expected treatment: passing. Delegates to :func:`make_fresh_repo`
    rather than re-seeding the same shape.
    """
    make_fresh_repo(repo)
    return repo


def build_f4_invalid_charter_yaml(repo: Path) -> Path:
    """F4 (data-model.md) — ``charter.yaml`` present but unparseable.
    Blocking, and distinguishable from F1 (FR-005): ``charter_source`` reads
    ``invalid``, not ``missing``.

    Includes :func:`seed_realistic_agent_scaffolding` (C-EFF-7, review cycle
    1) — same rationale as F2: a project with a broken ``charter.yaml`` is a
    real spec-kitty project with the rest of its scaffolding present, and
    this fixture feeds two of the driver's red cases (:318, :357), so it
    must be equally capable of supporting a genuinely effective remediation.
    """
    init_git_repo(repo)
    seed_charter_yaml(repo, valid=False)
    seed_realistic_agent_scaffolding(repo)
    return repo


def make_fresh_repo(repo: Path) -> None:
    """Materialise a fully-fresh repo: charter + bundle + synthesised graph.

    "Fresh" is defined by the content-identity freshness contract
    (synthesized-drg-stale-refresh, re-pointed at ``charter.yaml`` by
    consolidate-charter-bundle WP06): ``charter.yaml`` is seeded (via
    :func:`seed_charter_yaml`) before the manifest, so ``seed_manifest``'s
    default auto-compute (``_resolve_bundle_hash`` ->
    ``compute_bundle_content_hash``) stamps a manifest whose
    ``bundle_content_hash`` matches a fresh recompute of ``charter.yaml`` —
    exactly what a real ``spec-kitty charter synthesize`` run would write,
    so ``charter_source``/``synced_bundle``/``synthesized_drg`` all read
    ``fresh``. The legacy ``charter.md``/bundle-triad seeding is retained
    alongside it as a harmless companion for non-freshness consumers.
    """
    init_git_repo(repo)
    charter_path, metadata_path = seed_charter(repo)
    write_metadata(metadata_path, charter_path)
    seed_bundle_files(repo)
    seed_charter_yaml(repo)
    seed_manifest(repo, built_in_only=False)
    seed_graph(repo)
