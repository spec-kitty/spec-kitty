"""Machine-readable state contract for spec-kitty CLI state surfaces."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from specify_cli.core.constants import WORKTREES_DIR

_NEXT_INTERNAL_RUNTIME_OWNER = "next/_internal_runtime"
_CHARTER_SYNTHESIS_OWNER = "charter synthesizer write pipeline"
_CHARTER_SYNTHESIS_TRIGGER = "spec-kitty charter synthesize"


# ---------------------------------------------------------------------------
# T001 -- State Enums
# ---------------------------------------------------------------------------


class StateRoot(StrEnum):
    """Root directory that anchors a family of state surfaces.

    ``GLOBAL_SYNC`` surface patterns below carry a documentation-only
    ``~/.spec-kitty/`` prefix; their absolute resolution is NOT computed here.
    Resolution is anchored at the authoritative runtime root
    (``specify_cli.paths.get_runtime_root().base``), which honors
    ``SPEC_KITTY_HOME`` and defaults to ``~/.spec-kitty`` on POSIX (FR-009/010).
    """

    PROJECT = "project"  # .kittify/
    FEATURE = "feature"  # kitty-specs/<feature>/
    GLOBAL_RUNTIME = "global_runtime"  # ~/.kittify/
    GLOBAL_SYNC = "global_sync"  # get_runtime_root().base (default ~/.spec-kitty/)
    GIT_INTERNAL = "git_internal"  # .git/spec-kitty/


class AuthorityClass(StrEnum):
    """How authoritative a surface is for its data domain."""

    AUTHORITATIVE = "authoritative"
    DERIVED = "derived"
    COMPATIBILITY = "compatibility"
    LOCAL_RUNTIME = "local_runtime"
    SECRET = "secret"  # noqa: S105
    GIT_INTERNAL = "git_internal"
    DEPRECATED = "deprecated"


class GitClass(StrEnum):
    """Relationship of the surface to Git version control."""

    TRACKED = "tracked"
    IGNORED = "ignored"
    INSIDE_REPO_NOT_IGNORED = "inside_repo_not_ignored"
    GIT_INTERNAL = "git_internal"
    OUTSIDE_REPO = "outside_repo"


class StateFormat(StrEnum):
    """On-disk serialization format of the surface."""

    JSON = "json"
    YAML = "yaml"
    TOML = "toml"
    JSONL = "jsonl"
    SQLITE = "sqlite"
    MARKDOWN = "markdown"
    TEXT = "text"
    LOCKFILE = "lockfile"
    DIRECTORY = "directory"
    SYMLINK = "symlink"


# ---------------------------------------------------------------------------
# T002 -- StateSurface frozen dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StateSurface:
    """A single durable state surface in the spec-kitty CLI."""

    name: str
    path_pattern: str
    root: StateRoot
    format: StateFormat
    authority: AuthorityClass
    git_class: GitClass
    owner_module: str
    creation_trigger: str
    deprecated: bool = False
    atomic_write: bool = False
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dictionary representation."""
        return {
            "name": self.name,
            "path_pattern": self.path_pattern,
            "root": self.root.value,
            "format": self.format.value,
            "authority": self.authority.value,
            "git_class": self.git_class.value,
            "owner_module": self.owner_module,
            "creation_trigger": self.creation_trigger,
            "deprecated": self.deprecated,
            "atomic_write": self.atomic_write,
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# T003 -- STATE_SURFACES registry
# ---------------------------------------------------------------------------

STATE_SURFACES: tuple[StateSurface, ...] = (
    # -----------------------------------------------------------------------
    # Section A -- Project-Level State (.kittify/)
    # -----------------------------------------------------------------------
    StateSurface(
        name="project_config",
        path_pattern=".kittify/config.yaml",
        root=StateRoot.PROJECT,
        format=StateFormat.YAML,
        authority=AuthorityClass.AUTHORITATIVE,
        git_class=GitClass.TRACKED,
        owner_module="init/config writers",
        creation_trigger="spec-kitty init",
    ),
    StateSurface(
        name="project_metadata",
        path_pattern=".kittify/metadata.yaml",
        root=StateRoot.PROJECT,
        format=StateFormat.YAML,
        authority=AuthorityClass.AUTHORITATIVE,
        git_class=GitClass.TRACKED,
        owner_module="init/upgrade",
        creation_trigger="spec-kitty init or upgrade",
    ),
    StateSurface(
        name="dashboard_control",
        path_pattern=".kittify/.dashboard",
        root=StateRoot.PROJECT,
        format=StateFormat.TEXT,
        authority=AuthorityClass.LOCAL_RUNTIME,
        git_class=GitClass.IGNORED,
        owner_module="dashboard lifecycle",
        creation_trigger="spec-kitty dashboard start",
    ),
    StateSurface(
        name="workspace_context",
        path_pattern=".kittify/workspaces/<feature>-<WP>.json",
        root=StateRoot.PROJECT,
        format=StateFormat.JSON,
        authority=AuthorityClass.LOCAL_RUNTIME,
        git_class=GitClass.IGNORED,
        owner_module="workspace_context",
        creation_trigger="spec-kitty implement",
    ),
    StateSurface(
        name="merge_resume_state",
        path_pattern=".kittify/merge-state.json",
        root=StateRoot.PROJECT,
        format=StateFormat.JSON,
        authority=AuthorityClass.LOCAL_RUNTIME,
        git_class=GitClass.IGNORED,
        owner_module="merge/state",
        creation_trigger="spec-kitty merge",
    ),
    StateSurface(
        name="charter_lint_report",
        path_pattern=".kittify/lint-report.json",
        root=StateRoot.PROJECT,
        format=StateFormat.JSON,
        authority=AuthorityClass.LOCAL_RUNTIME,
        git_class=GitClass.IGNORED,
        owner_module="charter_runtime/lint/engine",
        creation_trigger="spec-kitty charter lint",
        notes=(
            "Machine-local decay-scan diagnostic; never commit (#3435). "
            "sync/lint_report_staging.py copies its contents into the "
            "TRACKED kitty-specs/<mission>/ dossier on record — that staged "
            "copy is a separate, intentionally-committed artifact, not this "
            "surface."
        ),
    ),
    StateSurface(
        name="sync_local_commit_state",
        path_pattern=".kittify/sync-state.json",
        root=StateRoot.PROJECT,
        format=StateFormat.JSON,
        authority=AuthorityClass.LOCAL_RUNTIME,
        git_class=GitClass.IGNORED,
        owner_module="legacy",
        creation_trigger="historical",
        atomic_write=True,
        notes=(
            "Historical residue: previously owned by sync/local_commit "
            "(machine-local SaaS sync relay queue), deleted with the sync "
            "transport (#114); not referenced by current 2.x source. Never "
            "commit if still present on disk."
        ),
    ),
    StateSurface(
        name="encoding_provenance_global_log",
        path_pattern=".kittify/encoding-provenance/global.jsonl",
        root=StateRoot.PROJECT,
        format=StateFormat.JSONL,
        authority=AuthorityClass.LOCAL_RUNTIME,
        git_class=GitClass.IGNORED,
        owner_module="charter/_io",
        creation_trigger="charter file decoding outside kitty-specs/<mission>/",
        notes="Machine-local encoding audit log; never commit.",
    ),
    StateSurface(
        name="runtime_feature_index",
        path_pattern=".kittify/runtime/feature-runs.json",
        root=StateRoot.PROJECT,
        format=StateFormat.JSON,
        authority=AuthorityClass.LOCAL_RUNTIME,
        git_class=GitClass.IGNORED,
        owner_module="next/runtime_bridge",
        creation_trigger="spec-kitty next (runtime mode)",
        notes="Legacy filename. Stores mission-slug to mission-run linkage until compatibility rename is completed.",
    ),
    StateSurface(
        name="runtime_run_snapshot",
        path_pattern=".kittify/runtime/runs/<run_id>/state.json",
        root=StateRoot.PROJECT,
        format=StateFormat.JSON,
        authority=AuthorityClass.LOCAL_RUNTIME,
        git_class=GitClass.IGNORED,
        owner_module=_NEXT_INTERNAL_RUNTIME_OWNER,
        creation_trigger="mission run start",
    ),
    StateSurface(
        name="runtime_run_event_log",
        path_pattern=".kittify/runtime/runs/<run_id>/run.events.jsonl",
        root=StateRoot.PROJECT,
        format=StateFormat.JSONL,
        authority=AuthorityClass.LOCAL_RUNTIME,
        git_class=GitClass.IGNORED,
        owner_module=_NEXT_INTERNAL_RUNTIME_OWNER,
        creation_trigger="mission run events",
    ),
    StateSurface(
        name="runtime_frozen_template",
        path_pattern=".kittify/runtime/runs/<run_id>/mission_template_frozen.yaml",
        root=StateRoot.PROJECT,
        format=StateFormat.YAML,
        authority=AuthorityClass.LOCAL_RUNTIME,
        git_class=GitClass.IGNORED,
        owner_module=_NEXT_INTERNAL_RUNTIME_OWNER,
        creation_trigger="mission run start",
    ),
    StateSurface(
        name="derived_mission_views",
        path_pattern=".kittify/derived/<mission_slug>/lifecycle.json",
        root=StateRoot.PROJECT,
        format=StateFormat.JSON,
        authority=AuthorityClass.DERIVED,
        git_class=GitClass.IGNORED,
        owner_module="status/lifecycle + status/views",
        creation_trigger="spec-kitty materialize",
        notes=(
            "Regenerable machine-facing views (lifecycle.json / status.json / "
            "board-summary.json / progress.json) under .kittify/derived/<slug>/. "
            "Ignored: materialize output must not dirty the tree or gate accept "
            "(#2369). Collapses to the .kittify/derived/ gitignore entry."
        ),
    ),
    StateSurface(
        name="migration_state_ledger",
        path_pattern=".kittify/mission-state-audit/<run_id>.json",
        root=StateRoot.PROJECT,
        format=StateFormat.JSON,
        authority=AuthorityClass.LOCAL_RUNTIME,
        git_class=GitClass.TRACKED,
        owner_module="migration/mission_state",
        creation_trigger="spec-kitty doctor mission-state --fix / upgrade repair",
        notes=(
            "Mission-state repair manifests plus verbatim quarantined-row backups "
            "under .kittify/mission-state-audit/. The durable audit trail of a "
            "destructive repair: TRACKED so it survives `git clean` and can be "
            "committed as the record of what a repair did (#4928). Write-only — "
            "`--fix` never commits; the operator commits the trail (the exit "
            "summary says so). Previously IGNORED under .kittify/migrations/ so a "
            "repair would not dirty the tree or gate accept (#2384); that "
            "non-gating property is now preserved by classifying this root as "
            "self-bookkeeping churn (coordination/coherence.py) instead of "
            "ignoring it — durable AND non-gating. NOT emitted to .gitignore "
            "(TRACKED surfaces are excluded from get_runtime_gitignore_entries); "
            "the legacy .kittify/migrations/ ignore stays for back-compat with "
            "pre-#4928 trails."
        ),
    ),
    StateSurface(
        name="legacy_migration_scratch",
        path_pattern=".kittify/migrations/",
        root=StateRoot.PROJECT,
        format=StateFormat.DIRECTORY,
        authority=AuthorityClass.LOCAL_RUNTIME,
        git_class=GitClass.IGNORED,
        owner_module="migration/mission_state",
        creation_trigger="pre-#4928 mission-state repair / general migration scratch",
        notes=(
            "Back-compat ignore for the legacy .kittify/migrations/ tree (#4928, "
            "#2384). The mission-state repair audit trail MOVED to the tracked "
            ".kittify/mission-state-audit/ root (see migration_state_ledger), but "
            "pre-#4928 projects still carry old repair trails here and the ignore "
            "must stay so they are not suddenly surfaced/committed. Retained as a "
            "derived IGNORED surface so .kittify/migrations/ keeps appearing in "
            "get_runtime_gitignore_entries() and the m_3_2_4 backfill stays "
            "coherent. No new writer targets this path."
        ),
    ),
    StateSurface(
        name="runtime_agent_logs",
        path_pattern=".kittify/logs/<mission>_<wp>_<phase>.log",
        root=StateRoot.PROJECT,
        format=StateFormat.TEXT,
        authority=AuthorityClass.LOCAL_RUNTIME,
        git_class=GitClass.IGNORED,
        owner_module="spec-kitty-orchestrator (external driver)",
        creation_trigger="orchestrator per-WP implementation/review run",
        notes=(
            "Per-WP implementation/review console logs under .kittify/logs/, "
            "written by the external orchestrator. Local runtime output; ignored "
            "so it never dirties the tree or gates accept (#2384). spec-kitty owns "
            ".kittify/ gitignore hygiene even though the orchestrator is the "
            "producer. Collapses to the .kittify/logs/ gitignore entry."
        ),
    ),
    StateSurface(
        name="glossary_fallback_events",
        path_pattern=".kittify/events/glossary/<mission_id>.events.jsonl",
        root=StateRoot.PROJECT,
        format=StateFormat.JSONL,
        authority=AuthorityClass.LOCAL_RUNTIME,
        git_class=GitClass.IGNORED,
        owner_module="glossary event adapter",
        creation_trigger="glossary event persistence",
    ),
    StateSurface(
        name="dossier_snapshot",
        path_pattern="kitty-specs/<feature>/.kittify/dossiers/<feature>/snapshot-latest.json",
        root=StateRoot.FEATURE,
        format=StateFormat.JSON,
        authority=AuthorityClass.DERIVED,
        git_class=GitClass.IGNORED,
        owner_module="dossier snapshot save",
        creation_trigger="dossier snapshot",
        notes=(
            "FIX-M2-05: root corrected PROJECT->FEATURE. save_snapshot() "
            "(dossier/snapshot.py) writes under feature_dir/.kittify/dossiers/<slug>/, "
            "i.e. NESTED INSIDE kitty-specs/<feature>/ -- not the project-root "
            ".kittify/ (that is dossier_parity_baseline's genuinely PROJECT-rooted "
            "sibling: drift_detector.py (deleted, #274) wrote "
            "repo_root/.kittify/dossiers/<slug>/parity-baseline.json, a "
            "different physical location despite the shared "
            "'dossiers' naming). The prior PROJECT-rooted declaration made "
            "get_runtime_gitignore_entries() emit a root-anchored .kittify/dossiers/ "
            "pattern that never matched the real mission-nested write location, so a "
            "fresh spec-kitty init's .gitignore never protected it: ordinary "
            "commit-routing staged and committed the file like any other mission "
            "artifact, and the resulting per-worktree drift then blocked "
            "git/ref_advance.py's merge-time dirty-worktree resync (#1826) on the "
            "coordination worktree."
        ),
    ),
    StateSurface(
        name="mission_pycache",
        path_pattern=".kittify/missions/__pycache__/",
        root=StateRoot.PROJECT,
        format=StateFormat.DIRECTORY,
        authority=AuthorityClass.LOCAL_RUNTIME,
        git_class=GitClass.IGNORED,
        owner_module="python runtime",
        creation_trigger="Python bytecode compilation",
        notes="Python cache artifact, not architectural state",
    ),
    StateSurface(
        name="dossier_parity_baseline",
        path_pattern=".kittify/dossiers/<feature>/parity-baseline.json",
        root=StateRoot.PROJECT,
        format=StateFormat.JSON,
        authority=AuthorityClass.LOCAL_RUNTIME,
        git_class=GitClass.IGNORED,
        owner_module="dossier drift detector (deleted, #274)",
        creation_trigger="dossier parity baseline accept",
        notes=(
            "#274 deleted dossier/drift_detector.py, this surface's sole "
            "writer -- nothing currently creates this path. Kept IGNORED "
            "defensively (harmless over-inclusion in .gitignore) in case a "
            "future feature reuses .kittify/dossiers/<feature>/"
            "parity-baseline.json; see #277."
        ),
    ),
    StateSurface(
        name="op_invocation_record",
        path_pattern="kitty-ops/<op_id>.jsonl",
        root=StateRoot.PROJECT,
        format=StateFormat.JSONL,
        authority=AuthorityClass.AUTHORITATIVE,
        git_class=GitClass.TRACKED,
        owner_module="invocation/writer",
        creation_trigger="profile-invocation start/complete",
        notes=(
            "Durable per-Op audit record; committed for traceability. "
            "kitty-ops/ never collapses to a fully-ignored top dir in "
            "get_runtime_gitignore_entries() because both kitty-ops surfaces "
            "are 2-segment paths (the collapse guard requires >=3 segments) -- "
            "not because this TRACKED sibling exists. A future 3-segment "
            "IGNORED surface under kitty-ops/ would rely on the mixed-git_class "
            "exclusion instead; see test_contract_runtime_entries_include_ops_index."
        ),
    ),
    StateSurface(
        name="op_invocation_index",
        path_pattern="kitty-ops/ops-index.jsonl",
        root=StateRoot.PROJECT,
        format=StateFormat.JSONL,
        authority=AuthorityClass.LOCAL_RUNTIME,
        git_class=GitClass.IGNORED,
        owner_module="invocation/writer",
        creation_trigger="profile-invocation start (index append)",
        notes=("Machine-local reverse-scan performance cache; never commit. Durable records live in kitty-ops/<op_id>.jsonl."),
    ),
    StateSurface(
        name="worktrees_root",
        path_pattern=f"{WORKTREES_DIR}/",
        root=StateRoot.PROJECT,
        format=StateFormat.DIRECTORY,
        authority=AuthorityClass.LOCAL_RUNTIME,
        git_class=GitClass.IGNORED,
        owner_module="core/worktree",
        creation_trigger="mission worktree creation (WORKTREES_DIR)",
        notes=(
            "Execution worktrees root: every mission worktree is a full "
            "checkout under .worktrees/<slug>-<mid8>. Must be gitignored in "
            "the main checkout -- an unignored root shows as permanent "
            "untracked dirt and a stray `git add -A` stages entire nested "
            "checkouts. Historically only migration 0.13.1 excluded it (via "
            "the local-only .git/info/exclude), so projects initialised "
            "since then had no coverage; registering it here makes init "
            "emit it through get_runtime_gitignore_entries(), and the "
            "3.2.6rc3_worktrees_gitignore_backfill migration heals "
            "existing projects (#3689)."
        ),
    ),
    StateSurface(
        name="shared_skills_projection",
        path_pattern=".agents/skills/<skill_name>/",
        root=StateRoot.PROJECT,
        format=StateFormat.DIRECTORY,
        authority=AuthorityClass.DERIVED,
        git_class=GitClass.IGNORED,
        owner_module="skills/installer",
        creation_trigger="spec-kitty init/upgrade skill projection",
        notes=(
            "Shared Agent-Skills projection root for codex/vibe/pi/letta. "
            "Files are projected from the user-global canonical root as "
            "copies (delivery_mode: copy) -- absolute symlinks were retired "
            "because they dangle in dev-containers and defeat sandboxed "
            "harnesses (#2412, ADR 2026-07-19-1). Still machine-generated "
            "state regenerated on every init/upgrade, never commit. Unlike "
            ".claude/ etc., .agents/ is NOT in GitignoreManager's "
            "AGENT_DIRECTORIES, so this surface is its only ignore coverage. "
            "Collapses to the .agents/skills/ gitignore entry."
        ),
    ),
    StateSurface(
        name="skills_install_manifest",
        path_pattern=".kittify/skills-manifest.json",
        root=StateRoot.PROJECT,
        format=StateFormat.JSON,
        authority=AuthorityClass.LOCAL_RUNTIME,
        git_class=GitClass.IGNORED,
        owner_module="skills/manifest",
        creation_trigger="spec-kitty init/upgrade skill projection",
        notes=(
            "Per-machine skill install ledger (installed_at timestamps, "
            "content hashes, per-machine delivery_mode); never commit "
            "(#2412). Regenerated by the next install/repair run. "
            "NAMING NOTE: distinct from .kittify/command-skills-manifest.json "
            "(TRACKED, managed by manifest_store.py) which records which "
            "slash-command skill paths are installed for each agent -- that "
            "file IS committed. This surface is the per-machine install ledger "
            "only; it is IGNORED."
        ),
    ),
    # -----------------------------------------------------------------------
    # Section B -- Charter State (.kittify/charter/)
    # -----------------------------------------------------------------------
    StateSurface(
        name="charter_source",
        path_pattern=".kittify/charter/charter.md",
        root=StateRoot.PROJECT,
        format=StateFormat.MARKDOWN,
        authority=AuthorityClass.AUTHORITATIVE,
        git_class=GitClass.TRACKED,
        owner_module="charter compiler",
        creation_trigger="charter init or user edit",
    ),
    StateSurface(
        name="charter_interview_answers",
        path_pattern=".kittify/charter/interview/answers.yaml",
        root=StateRoot.PROJECT,
        format=StateFormat.YAML,
        authority=AuthorityClass.AUTHORITATIVE,
        git_class=GitClass.TRACKED,
        owner_module="charter interview",
        creation_trigger="charter interview flow",
        notes="Policy enforced in feature 054: commit answers + library, ignore references",
    ),
    StateSurface(
        name="charter_library",
        path_pattern=".kittify/charter/library/*.md",
        root=StateRoot.PROJECT,
        format=StateFormat.MARKDOWN,
        authority=AuthorityClass.AUTHORITATIVE,
        git_class=GitClass.TRACKED,
        owner_module="charter compiler",
        creation_trigger="charter compile",
        notes="Policy enforced in feature 054: commit answers + library, ignore references",
    ),
    StateSurface(
        name="charter_yaml",
        path_pattern=".kittify/charter/charter.yaml",
        root=StateRoot.PROJECT,
        format=StateFormat.YAML,
        authority=AuthorityClass.AUTHORITATIVE,
        git_class=GitClass.TRACKED,
        owner_module="charter compiler / activation engine / migration",
        creation_trigger="charter generate, charter activate/deactivate, or the consolidate_charter_bundle_fold upgrade migration",
        notes=(
            "consolidate-charter-bundle (WP07): retires the four legacy "
            "IGNORED/DERIVED bundle surfaces this replaces (charter_governance, "
            "charter_directives, charter_sync_metadata, charter_references) -- "
            "governance/directives are hand-authored sections and catalog is a "
            "DERIVED-but-committed projection, all living inside this single "
            "git-tracked file (data-model.md Landmine 1). Three writers "
            "(activation_engine.commit_plan, pack_manager.merge_defaults, "
            "compiler.write_compiled_charter) route through the shared INV-9 "
            "load->mutate-owned-section->round-trip-save helper "
            "(charter.activation.charter_yaml_io) so section-preservation is structural."
        ),
    ),
    StateSurface(
        name="charter_context_state",
        path_pattern=".kittify/charter/context-state.json",
        root=StateRoot.PROJECT,
        format=StateFormat.JSON,
        authority=AuthorityClass.LOCAL_RUNTIME,
        git_class=GitClass.IGNORED,
        owner_module="charter context",
        creation_trigger="charter context bootstrap",
    ),
    StateSurface(
        name="charter_synthesis_manifest",
        path_pattern=".kittify/charter/synthesis-manifest.yaml",
        root=StateRoot.PROJECT,
        format=StateFormat.YAML,
        authority=AuthorityClass.DERIVED,
        git_class=GitClass.TRACKED,
        owner_module=_CHARTER_SYNTHESIS_OWNER,
        creation_trigger=_CHARTER_SYNTHESIS_TRIGGER,
        atomic_write=True,
        notes="KD-2 commit marker for synthesized charter/doctrine artifacts.",
    ),
    StateSurface(
        name="charter_synthesis_provenance",
        path_pattern=".kittify/charter/provenance/*.yaml",
        root=StateRoot.PROJECT,
        format=StateFormat.YAML,
        authority=AuthorityClass.DERIVED,
        git_class=GitClass.TRACKED,
        owner_module=_CHARTER_SYNTHESIS_OWNER,
        creation_trigger=_CHARTER_SYNTHESIS_TRIGGER,
        atomic_write=True,
        notes="Per-artifact provenance sidecars written by charter synthesize.",
    ),
    StateSurface(
        name="project_doctrine_graph",
        path_pattern=".kittify/doctrine/graph.yaml",
        root=StateRoot.PROJECT,
        format=StateFormat.YAML,
        authority=AuthorityClass.DERIVED,
        git_class=GitClass.TRACKED,
        owner_module=_CHARTER_SYNTHESIS_OWNER,
        creation_trigger=_CHARTER_SYNTHESIS_TRIGGER,
        atomic_write=True,
        notes="Project-layer DRG overlay generated by charter synthesize.",
    ),
    # -----------------------------------------------------------------------
    # Section C -- Feature State (kitty-specs/<feature>/)
    # -----------------------------------------------------------------------
    StateSurface(
        name="feature_metadata",
        path_pattern="kitty-specs/<feature>/meta.json",
        root=StateRoot.FEATURE,
        format=StateFormat.JSON,
        authority=AuthorityClass.AUTHORITATIVE,
        git_class=GitClass.TRACKED,
        owner_module="feature creation/acceptance",
        creation_trigger="spec-kitty specify",
        atomic_write=True,
    ),
    StateSurface(
        name="canonical_status_log",
        path_pattern="kitty-specs/<feature>/status.events.jsonl",
        root=StateRoot.FEATURE,
        format=StateFormat.JSONL,
        authority=AuthorityClass.AUTHORITATIVE,
        git_class=GitClass.TRACKED,
        owner_module="status emit",
        creation_trigger="first status transition",
        atomic_write=True,
    ),
    StateSurface(
        name="canonical_status_snapshot",
        path_pattern="kitty-specs/<feature>/status.json",
        root=StateRoot.FEATURE,
        format=StateFormat.JSON,
        authority=AuthorityClass.DERIVED,
        git_class=GitClass.TRACKED,
        owner_module="status reducer",
        creation_trigger="status materialize",
        atomic_write=True,
    ),
    StateSurface(
        name="wp_prompt_frontmatter",
        path_pattern="kitty-specs/<feature>/tasks/WP*.md",
        root=StateRoot.FEATURE,
        format=StateFormat.YAML,
        authority=AuthorityClass.COMPATIBILITY,
        git_class=GitClass.TRACKED,
        owner_module="task creation/move-task/legacy bridge",
        creation_trigger="spec-kitty tasks",
        notes="YAML frontmatter in WP markdown files",
    ),
    StateSurface(
        name="wp_activity_log",
        path_pattern="kitty-specs/<feature>/tasks/WP*.md body",
        root=StateRoot.FEATURE,
        format=StateFormat.MARKDOWN,
        authority=AuthorityClass.COMPATIBILITY,
        git_class=GitClass.TRACKED,
        owner_module="move-task/manual edits",
        creation_trigger="status transitions and manual edits",
        notes="Markdown body section of WP files",
    ),
    StateSurface(
        name="tasks_status_block",
        path_pattern="kitty-specs/<feature>/tasks.md",
        root=StateRoot.FEATURE,
        format=StateFormat.MARKDOWN,
        authority=AuthorityClass.DERIVED,
        git_class=GitClass.TRACKED,
        owner_module="legacy bridge",
        creation_trigger="status materialize/legacy bridge",
    ),
    # -----------------------------------------------------------------------
    # Section D -- Git-Internal State
    # -----------------------------------------------------------------------
    StateSurface(
        name="review_feedback_artifact",
        path_pattern=".git/spec-kitty/feedback/<feature>/<WP>/<timestamp>-<id>.md",
        root=StateRoot.GIT_INTERNAL,
        format=StateFormat.MARKDOWN,
        authority=AuthorityClass.GIT_INTERNAL,
        git_class=GitClass.GIT_INTERNAL,
        owner_module="agent tasks move-task",
        creation_trigger="move-task --review-feedback-file",
    ),
    # -----------------------------------------------------------------------
    # Section E -- User-Home Sync (~/.spec-kitty/) -- partly historical, see below
    # -----------------------------------------------------------------------
    StateSurface(
        name="sync_config",
        path_pattern="~/.spec-kitty/config.toml",
        root=StateRoot.GLOBAL_SYNC,
        format=StateFormat.TOML,
        authority=AuthorityClass.AUTHORITATIVE,
        git_class=GitClass.OUTSIDE_REPO,
        owner_module="auth/server_target",
        creation_trigger="operator-authored; no command writes this file",
    ),
    StateSurface(
        name="sync_credentials",
        path_pattern="~/.spec-kitty/credentials",
        root=StateRoot.GLOBAL_SYNC,
        format=StateFormat.TOML,
        authority=AuthorityClass.SECRET,
        git_class=GitClass.OUTSIDE_REPO,
        owner_module="tracker/credentials",
        creation_trigger="spec-kitty tracker bind",
    ),
    # -----------------------------------------------------------------------
    # The lamport_clock through scoped_queue and project_sync_store through
    # project_sync_migration_reports runs below describe on-disk surfaces of
    # the hosted CLI<->SaaS sync transport deleted in #114 (clock, offline
    # queue, sync daemon, ProjectSyncStore, machine layout generation,
    # project-store migration). They are frozen/historical and fully
    # tombstoned: no current module creates or reads any of these paths, and
    # tracker_cache above remains a live AUTHORITATIVE surface.
    # -----------------------------------------------------------------------
    StateSurface(
        name="lamport_clock",
        path_pattern="~/.spec-kitty/clock.json",
        root=StateRoot.GLOBAL_SYNC,
        format=StateFormat.JSON,
        authority=AuthorityClass.DEPRECATED,
        git_class=GitClass.OUTSIDE_REPO,
        owner_module="legacy",
        creation_trigger="historical",
        deprecated=True,
        notes="Historical residue: previously owned by sync/clock, deleted with the sync transport (#114); not referenced by current 2.x source.",
    ),
    StateSurface(
        name="active_queue_scope",
        path_pattern="~/.spec-kitty/active_queue_scope",
        root=StateRoot.GLOBAL_SYNC,
        format=StateFormat.TEXT,
        authority=AuthorityClass.DEPRECATED,
        git_class=GitClass.OUTSIDE_REPO,
        owner_module="legacy",
        creation_trigger="historical",
        deprecated=True,
        notes="Historical residue: previously owned by sync/queue, deleted with the sync transport (#114); not referenced by current 2.x source.",
    ),
    StateSurface(
        name="sync_daemon_control",
        path_pattern="~/.spec-kitty/sync-daemon",
        root=StateRoot.GLOBAL_SYNC,
        format=StateFormat.TEXT,
        authority=AuthorityClass.DEPRECATED,
        git_class=GitClass.OUTSIDE_REPO,
        owner_module="legacy",
        creation_trigger="historical",
        deprecated=True,
        notes=(
            "Historical residue: previously owned by sync/daemon (trigger "
            "was machine-global sync daemon bootstrap), deleted with the "
            "sync transport (#114); not referenced by current 2.x source."
        ),
    ),
    StateSurface(
        name="legacy_queue",
        path_pattern="~/.spec-kitty/queue.db",
        root=StateRoot.GLOBAL_SYNC,
        format=StateFormat.SQLITE,
        authority=AuthorityClass.DEPRECATED,
        git_class=GitClass.OUTSIDE_REPO,
        owner_module="legacy",
        creation_trigger="historical",
        deprecated=True,
        notes=(
            "Historical residue: previously owned by sync/queue "
            "(unauthenticated offline queue), deleted with the sync "
            "transport (#114); not referenced by current 2.x source."
        ),
    ),
    StateSurface(
        name="scoped_queue",
        path_pattern="~/.spec-kitty/queues/queue-<hash>.db",
        root=StateRoot.GLOBAL_SYNC,
        format=StateFormat.SQLITE,
        authority=AuthorityClass.DEPRECATED,
        git_class=GitClass.OUTSIDE_REPO,
        owner_module="legacy",
        creation_trigger="historical",
        deprecated=True,
        notes=(
            "Historical residue: previously owned by sync/queue "
            "(authenticated-scope offline queue), deleted with the sync "
            "transport (#114); not referenced by current 2.x source."
        ),
    ),
    StateSurface(
        name="tracker_cache",
        path_pattern="~/.spec-kitty/trackers/<scope>.db",
        root=StateRoot.GLOBAL_SYNC,
        format=StateFormat.SQLITE,
        authority=AuthorityClass.AUTHORITATIVE,
        git_class=GitClass.OUTSIDE_REPO,
        owner_module="tracker/store",
        creation_trigger="tracker sync or cache init",
    ),
    StateSurface(
        name="project_sync_store",
        path_pattern="~/.spec-kitty/projects/<canonical-uuid>/sync/sync.db",
        root=StateRoot.GLOBAL_SYNC,
        format=StateFormat.SQLITE,
        authority=AuthorityClass.DEPRECATED,
        git_class=GitClass.OUTSIDE_REPO,
        owner_module="legacy",
        creation_trigger="historical",
        deprecated=True,
        notes=(
            "Historical residue: previously owned by sync/project_store "
            "(one transactionally coherent hosted-sync aggregate per "
            "canonical UUID), deleted with the sync transport (#114); not "
            "referenced by current 2.x source."
        ),
    ),
    StateSurface(
        name="project_sync_egress_lock",
        path_pattern="~/.spec-kitty/projects/<canonical-uuid>/sync/egress.lock",
        root=StateRoot.GLOBAL_SYNC,
        format=StateFormat.LOCKFILE,
        authority=AuthorityClass.DEPRECATED,
        git_class=GitClass.OUTSIDE_REPO,
        owner_module="legacy",
        creation_trigger="historical",
        deprecated=True,
        notes=(
            "Historical residue: previously owned by sync/project_store "
            "(transport/result barrier acquisition), deleted with the "
            "sync transport (#114); not referenced by current 2.x source."
        ),
    ),
    StateSurface(
        name="project_sync_layout_generation",
        path_pattern="~/.spec-kitty/projects/.layout-generation.json",
        root=StateRoot.GLOBAL_SYNC,
        format=StateFormat.JSON,
        authority=AuthorityClass.DEPRECATED,
        git_class=GitClass.OUTSIDE_REPO,
        owner_module="legacy",
        creation_trigger="historical",
        deprecated=True,
        notes=(
            "Historical residue: previously owned by sync/layout_generation "
            "(machine-wide current-writer generation and cutover mode), "
            "deleted with the sync transport (#114); not referenced by "
            "current 2.x source."
        ),
    ),
    StateSurface(
        name="project_sync_layout_generation_lock",
        path_pattern="~/.spec-kitty/projects/.layout-generation.lock",
        root=StateRoot.GLOBAL_SYNC,
        format=StateFormat.LOCKFILE,
        authority=AuthorityClass.DEPRECATED,
        git_class=GitClass.OUTSIDE_REPO,
        owner_module="legacy",
        creation_trigger="historical",
        deprecated=True,
        notes=(
            "Historical residue: previously owned by sync/layout_generation "
            "(machine layout authority acquisition), deleted with the sync "
            "transport (#114); not referenced by current 2.x source."
        ),
    ),
    StateSurface(
        name="project_sync_layout_generation_marker",
        path_pattern="~/.spec-kitty/projects/.layout-generation.initialized",
        root=StateRoot.GLOBAL_SYNC,
        format=StateFormat.TEXT,
        authority=AuthorityClass.DEPRECATED,
        git_class=GitClass.OUTSIDE_REPO,
        owner_module="legacy",
        creation_trigger="historical",
        deprecated=True,
        notes=(
            "Historical residue: previously owned by sync/layout_generation "
            "(fail-closed evidence that a missing layout record is data "
            "loss), deleted with the sync transport (#114); not referenced "
            "by current 2.x source."
        ),
    ),
    StateSurface(
        name="project_sync_migration_reports",
        path_pattern=("~/.spec-kitty/projects/<canonical-uuid>/sync/migration/reports/"),
        root=StateRoot.GLOBAL_SYNC,
        format=StateFormat.DIRECTORY,
        authority=AuthorityClass.DEPRECATED,
        git_class=GitClass.OUTSIDE_REPO,
        owner_module="legacy",
        creation_trigger="historical",
        deprecated=True,
        notes=(
            "Historical residue: previously owned by "
            "sync/project_store_migration (non-sensitive counts, IDs, "
            "hashes, phases, and reason codes only), deleted with the sync "
            "transport (#114); not referenced by current 2.x source."
        ),
    ),
    # -----------------------------------------------------------------------
    # Section F -- Global Runtime (~/.kittify/)
    # -----------------------------------------------------------------------
    StateSurface(
        name="runtime_version_stamp",
        path_pattern="~/.kittify/cache/version.lock",
        root=StateRoot.GLOBAL_RUNTIME,
        format=StateFormat.TEXT,
        authority=AuthorityClass.LOCAL_RUNTIME,
        git_class=GitClass.OUTSIDE_REPO,
        owner_module="runtime/bootstrap",
        creation_trigger="runtime bootstrap",
    ),
    StateSurface(
        name="runtime_update_lock",
        path_pattern="~/.kittify/cache/.update.lock",
        root=StateRoot.GLOBAL_RUNTIME,
        format=StateFormat.LOCKFILE,
        authority=AuthorityClass.LOCAL_RUNTIME,
        git_class=GitClass.OUTSIDE_REPO,
        owner_module="runtime/bootstrap",
        creation_trigger="runtime asset update",
    ),
    StateSurface(
        name="runtime_staging_dirs",
        path_pattern="~/.kittify_update_*",
        root=StateRoot.GLOBAL_RUNTIME,
        format=StateFormat.DIRECTORY,
        authority=AuthorityClass.LOCAL_RUNTIME,
        git_class=GitClass.OUTSIDE_REPO,
        owner_module="runtime/bootstrap",
        creation_trigger="runtime asset update",
        notes="Transient staging area, removed after update completes",
    ),
    # -----------------------------------------------------------------------
    # Section G -- Legacy
    # -----------------------------------------------------------------------
    StateSurface(
        name="legacy_session_json",
        path_pattern="~/.spec-kitty/session.json",
        root=StateRoot.GLOBAL_SYNC,
        format=StateFormat.JSON,
        authority=AuthorityClass.DEPRECATED,
        git_class=GitClass.OUTSIDE_REPO,
        owner_module="legacy",
        creation_trigger="historical",
        deprecated=True,
        notes="Historical residue, not referenced by current 2.x source",
    ),
    StateSurface(
        name="legacy_lamport_clock",
        path_pattern="~/.spec-kitty/events/lamport_clock.json",
        root=StateRoot.GLOBAL_SYNC,
        format=StateFormat.JSON,
        authority=AuthorityClass.DEPRECATED,
        git_class=GitClass.OUTSIDE_REPO,
        owner_module="legacy",
        creation_trigger="historical",
        deprecated=True,
        notes="Historical residue, not referenced by current 2.x source",
    ),
    StateSurface(
        name="legacy_mission_sessions",
        path_pattern="~/.spec-kitty/missions/*/session.json",
        root=StateRoot.GLOBAL_SYNC,
        format=StateFormat.JSON,
        authority=AuthorityClass.DEPRECATED,
        git_class=GitClass.OUTSIDE_REPO,
        owner_module="legacy",
        creation_trigger="historical",
        deprecated=True,
        notes="Historical residue, not referenced by current 2.x source",
    ),
    StateSurface(
        name="legacy_reset_backups",
        path_pattern="~/.spec-kitty/reset-backup-*",
        root=StateRoot.GLOBAL_SYNC,
        format=StateFormat.DIRECTORY,
        authority=AuthorityClass.DEPRECATED,
        git_class=GitClass.OUTSIDE_REPO,
        owner_module="legacy",
        creation_trigger="historical",
        deprecated=True,
        notes="Historical residue, not referenced by current 2.x source",
    ),
)


# ---------------------------------------------------------------------------
# T004 -- Helper functions
# ---------------------------------------------------------------------------


def get_surfaces_by_root(root: StateRoot) -> list[StateSurface]:
    """Return all surfaces that belong to the given root."""
    return [s for s in STATE_SURFACES if s.root == root]


def get_surfaces_by_git_class(git_class: GitClass) -> list[StateSurface]:
    """Return all surfaces that have the given git class."""
    return [s for s in STATE_SURFACES if s.git_class == git_class]


def get_surfaces_by_authority(authority: AuthorityClass) -> list[StateSurface]:
    """Return all surfaces that have the given authority class."""
    return [s for s in STATE_SURFACES if s.authority == authority]


def _fully_ignored_top_dirs() -> set[str]:
    """Return top-level subdirectory patterns where ALL project surfaces are IGNORED.

    For example, if every surface under ``.kittify/runtime/`` is IGNORED,
    ``".kittify/runtime/"`` is returned. Directories with mixed git classes
    (some TRACKED, some IGNORED) are excluded.

    Surfaces whose path ends with ``__pycache__/`` are excluded from collapse
    consideration because they are Python cache artifacts, not representative
    of the parent directory's actual contents.
    """
    project_surfaces = [s for s in STATE_SURFACES if s.root == StateRoot.PROJECT]
    top_dir_git_classes: dict[str, list[GitClass]] = {}
    for s in project_surfaces:
        # Skip __pycache__ entries — they are cache artifacts and should not
        # cause their parent directory to be collapsed.
        if s.path_pattern.rstrip("/").endswith("__pycache__"):
            continue
        parts = s.path_pattern.split("/")
        if len(parts) >= 3:  # noqa: PLR2004
            top_dir = "/".join(parts[:2])
            top_dir_git_classes.setdefault(top_dir, []).append(s.git_class)
    return {d + "/" for d, classes in top_dir_git_classes.items() if all(gc == GitClass.IGNORED for gc in classes)}


_KITTY_SPECS_SEGMENT = "kitty-specs"
# Every StateRoot.FEATURE surface's path_pattern is anchored at exactly this
# two-segment prefix ("kitty-specs/<feature>/…", Section C above).
_FEATURE_PREFIX_SEGMENTS = 2


def _feature_relative_pattern(pattern: str) -> str | None:
    """Strip the ``kitty-specs/<feature>/`` prefix from a FEATURE-rooted pattern.

    Returns the feature-relative remainder (e.g. ``.kittify/dossiers/<feature>/
    snapshot-latest.json``), or ``None`` when *pattern* is not anchored under
    ``kitty-specs/<feature>/`` -- defensive; every current
    :class:`StateRoot.FEATURE` surface is.
    """
    parts = pattern.split("/")
    if len(parts) <= _FEATURE_PREFIX_SEGMENTS or parts[0] != _KITTY_SPECS_SEGMENT:
        return None
    return "/".join(parts[_FEATURE_PREFIX_SEGMENTS:])


def _fully_ignored_feature_subdirs() -> set[str]:
    """Feature-relative analogue of :func:`_fully_ignored_top_dirs`.

    Returns FEATURE-relative directory patterns (e.g. ``.kittify/dossiers/``)
    where every :class:`StateRoot.FEATURE` surface nested under it is IGNORED
    -- so a mission-nested ignored directory (e.g. the dossier-sync snapshot's
    ``kitty-specs/<feature>/.kittify/dossiers/``) collapses to one directory
    entry instead of a per-placeholder pattern that could over- or
    under-match. Mirrors :func:`_fully_ignored_top_dirs` one level deeper,
    below the mandatory ``kitty-specs/<feature>/`` anchor.
    """
    feature_surfaces = [s for s in STATE_SURFACES if s.root == StateRoot.FEATURE]
    top_dir_git_classes: dict[str, list[GitClass]] = {}
    for s in feature_surfaces:
        rel = _feature_relative_pattern(s.path_pattern)
        if rel is None:
            continue
        parts = rel.split("/")
        if len(parts) >= 3:  # noqa: PLR2004
            top_dir = "/".join(parts[:2])
            top_dir_git_classes.setdefault(top_dir, []).append(s.git_class)
    return {d + "/" for d, classes in top_dir_git_classes.items() if all(gc == GitClass.IGNORED for gc in classes)}


def _collapse_placeholder_pattern(pattern: str) -> str | None:
    """Collapse a path pattern with placeholders to its clean parent directory.

    Returns ``None`` if no clean prefix exists.
    """
    parts = pattern.split("/")
    clean_parts: list[str] = []
    for part in parts:
        if "<" in part or "*" in part:
            break
        clean_parts.append(part)
    return "/".join(clean_parts) + "/" if clean_parts else None


def _remove_subsumed(entries: set[str]) -> set[str]:
    """Remove entries that are subsumed by a parent directory entry."""
    return {entry for entry in entries if not any(other != entry and other.endswith("/") and entry.startswith(other) for other in entries)}


def get_runtime_gitignore_entries() -> list[str]:
    """Return deduplicated gitignore patterns for runtime-ignored surfaces.

    Includes every PROJECT-rooted surface with git_class=IGNORED (root-anchored
    patterns), plus every FEATURE-rooted surface with git_class=IGNORED
    (mission-nested patterns under ``kitty-specs/*/…`` -- FIX-M2-05: a FEATURE
    surface's real write location is nested inside each mission's own
    ``kitty-specs/<feature>/`` tree, not the project root, so it needs its own
    ``<feature>``-glob leg; folding it into the PROJECT leg would silently
    mismatch the physical path, as the pre-fix ``dossier_snapshot`` entry did).
    Patterns containing placeholder tokens (``<...>``) or wildcards are
    collapsed to their parent directory (with trailing ``/``), then
    deduplicated so the result is directly consumable by ``.gitignore``.

    When ALL project surfaces under a top-level subdirectory (e.g.
    ``.kittify/runtime/``) are IGNORED, the entire subdirectory is emitted
    as a single entry rather than listing individual files/subdirs; the same
    collapse applies one level deeper for FEATURE surfaces sharing a
    mission-nested subdirectory (e.g. ``kitty-specs/*/.kittify/dossiers/``).
    """
    fully_ignored = _fully_ignored_top_dirs()
    fully_ignored_feature = _fully_ignored_feature_subdirs()
    raw: set[str] = set()

    for s in STATE_SURFACES:
        if s.git_class != GitClass.IGNORED:
            continue

        if s.root == StateRoot.FEATURE:
            rel = _feature_relative_pattern(s.path_pattern)
            if rel is None:
                continue
            parts = rel.split("/")
            if len(parts) >= 3:  # noqa: PLR2004
                top_dir_rel = "/".join(parts[:2]) + "/"
                if top_dir_rel in fully_ignored_feature:
                    raw.add(f"{_KITTY_SPECS_SEGMENT}/*/{top_dir_rel}")
            # No current FEATURE-rooted IGNORED surface falls outside a
            # fully-ignored mission-nested subdirectory; add a finer-grained
            # (placeholder-substitution) fallback here if one ever does.
            continue

        if s.root != StateRoot.PROJECT:
            continue
        pattern = s.path_pattern

        # Check if this surface falls under a fully-ignored top dir
        parts = pattern.split("/")
        if len(parts) >= 3:  # noqa: PLR2004
            top_dir_pattern = "/".join(parts[:2]) + "/"
            if top_dir_pattern in fully_ignored:
                raw.add(top_dir_pattern)
                continue

        # Collapse placeholders to parent directory
        if "<" in pattern or "*" in pattern:
            collapsed = _collapse_placeholder_pattern(pattern)
            if collapsed:
                raw.add(collapsed)
            continue

        raw.add(pattern)

    return sorted(_remove_subsumed(raw))
