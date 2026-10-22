"""Tests for the canonical generated-file writer (FR-001/002, #3651).

Covers:
- T007: ``write_generated_file`` unit tests — the read-only permission
  lifecycle it owns (restore-before-write, strip-after-write, propagate
  genuine failures, idempotency).
- T004: a mechanical architectural guard so an in-scope generated-command/
  skill migration cannot reintroduce a bare ``write_text`` on a read-only-
  destined path without the guard catching it (prose audits alone silently
  regress).

T004 guard strategy — chosen approach and why:

A fully general AST/data-flow scan that proves *which* ``Path`` a given
``.write_text(...)`` call targets (to decide "is this a read-only-destined
generated command/skill surface?") requires tracing variable assignments
across branches and helper calls — fragile and easy to get subtly wrong in
a text-based guard. Instead this file uses the two-part strategy the FR-002
research explicitly allows as a fallback:

1. **Known in-scope list** (``_IN_SCOPE_GENERATED_SURFACE_MIGRATIONS``):
   every migration confirmed (by manual research + the #3679 adversarial
   review that found the 5 missed sites) to write a generated agent
   command/skill file. Each must contain zero bare ``.write_text(`` calls
   and must use ``write_generated_file``.
2. **Full-scan anti-pattern net** (``test_no_unrouted_bare_write_text_on_agent_surface_paths``):
   every migration file under ``_MIGRATIONS_DIR`` — not just the known
   list — is scanned for the *combination* of (a) a bare ``.write_text(``
   call and (b) any reference to the agent-command/skill-directory helpers
   (``get_agent_dirs_for_project``, ``AGENT_DIRS``, or a literal
   ``.agents`` + ``skills`` path-segment pair). This heuristic is
   deliberately broad (recall over precision — a docstring mention is
   enough to flag a file): a false positive only costs an explicit,
   rationale-carrying entry in ``_EXEMPT_AGENT_DIR_REFERENCING_WRITERS``,
   never a silent miss. This is the part of the guard that catches a
   *future* migration nobody enumerated yet — "cannot be forgotten again"
   for the whole class, not just the 21 files known today.

The exemption set requires a one-line rationale per entry (never bare
omission) and the test asserts *exact* set equality against what the scan
currently finds, so a stale exemption (the file changed and no longer
matches) fails loudly too.
"""

from __future__ import annotations

import stat
from pathlib import Path

import pytest

from specify_cli.runtime.generated_writer import generated_temporary_path, write_generated_file
from tests._support.eacces import deny_path_method

pytestmark = pytest.mark.fast

# ---------------------------------------------------------------------------
# T007 — write_generated_file unit tests
# ---------------------------------------------------------------------------


def test_write_over_read_only_target_succeeds_and_stays_read_only(tmp_path: Path) -> None:
    """(a) A pre-existing 0o444 target is rewritten and left read-only."""
    target = tmp_path / "command.md"
    target.write_text("stale\n", encoding="utf-8")
    target.chmod(0o444)

    write_generated_file(target, "fresh\n")

    assert target.read_text(encoding="utf-8") == "fresh\n"
    assert stat.S_IMODE(target.stat().st_mode) == 0o444


def test_write_over_missing_target_creates_it_read_only(tmp_path: Path) -> None:
    """(b) A missing target is created and left read-only."""
    target = tmp_path / "new-command.md"
    assert not target.exists()

    write_generated_file(target, "content\n")

    assert target.read_text(encoding="utf-8") == "content\n"
    assert stat.S_IMODE(target.stat().st_mode) & 0o222 == 0


def test_read_only_false_leaves_target_writable(tmp_path: Path) -> None:
    """(c) ``read_only=False`` leaves the target writable after the write."""
    target = tmp_path / "writable.md"

    write_generated_file(target, "content\n", read_only=False)

    assert target.read_text(encoding="utf-8") == "content\n"
    assert stat.S_IMODE(target.stat().st_mode) & 0o200 != 0


def test_genuine_write_failure_propagates(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """(d) A genuine failure (unwritable parent directory) is not swallowed."""
    blocked_dir = tmp_path / "blocked"
    blocked_dir.mkdir()
    target = blocked_dir / "command.md"

    # An unwritable directory refuses the temporary sibling the writer creates.
    # Deny that write at the seam: a chmod(0o555) directory does not deny root (#5691).
    deny_path_method(monkeypatch, "write_text", generated_temporary_path(target))
    with pytest.raises(PermissionError):
        write_generated_file(target, "content\n")
    assert not target.exists()


def test_idempotent_double_write(tmp_path: Path) -> None:
    """(e) Writing the same content twice in a row is a clean no-op state."""
    target = tmp_path / "command.md"

    write_generated_file(target, "content\n")
    write_generated_file(target, "content\n")

    assert target.read_text(encoding="utf-8") == "content\n"
    assert stat.S_IMODE(target.stat().st_mode) == 0o444


def test_default_encoding_is_utf8(tmp_path: Path) -> None:
    """Non-ASCII content round-trips under the default UTF-8 encoding."""
    target = tmp_path / "unicode.md"

    write_generated_file(target, "spec-kitty 🐱 café\n")

    assert target.read_text(encoding="utf-8") == "spec-kitty 🐱 café\n"


# ---------------------------------------------------------------------------
# T004 — mechanical architectural guard: no bare write_text in in-scope
# migrations (see kitty-specs/.../research.md, "FR-002 write-site
# enumeration" for the classification rule and confirmed in-scope list).
# ---------------------------------------------------------------------------

_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "src" / "specify_cli" / "upgrade" / "migrations"

# Every migration confirmed in-scope by research.md's FR-002 enumeration: its
# write target is a generated command/skill file the generation layer later
# makes read-only. Each must route its write(s) through write_generated_file
# instead of a bare Path.write_text(...) call.
_IN_SCOPE_GENERATED_SURFACE_MIGRATIONS = [
    "m_2_1_4_enforce_command_file_state.py",
    "m_2_1_2_install_git_workflow_skill.py",
    "m_2_1_2_install_mission_system_skill.py",
    "m_2_1_3_restore_prompt_commands.py",
    "m_0_10_2_update_slash_commands.py",
    "m_0_10_1_populate_slash_commands.py",
    "m_0_10_14_update_implement_slash_command.py",
    "m_0_11_1_update_implement_slash_command.py",
    "m_0_13_0_update_research_implement_templates.py",
    "m_0_13_5_add_commit_workflow_to_templates.py",
    "m_3_2_0rc35_update_planning_templates.py",
    "m_2_0_1_fix_generated_command_templates.py",
    "m_0_10_0_python_only.py",
    "m_0_10_6_workflow_simplification.py",
    "m_0_11_1_improved_workflow_templates.py",
    "m_0_11_2_improved_workflow_templates.py",
    # --- routed by the #3679 adversarial-review follow-up (5 missed sites) ---
    "m_3_2_0rc35_kittify_profile_handoff.py",
    "m_0_11_3_workflow_agent_flag.py",
    "m_2_1_3_fix_planning_repository_terminology.py",
    "m_3_2_0rc35_repository_root_checkout_terminology.py",
    "m_3_1_1_charter_rename.py",
]


@pytest.mark.parametrize("filename", _IN_SCOPE_GENERATED_SURFACE_MIGRATIONS)
def test_in_scope_migration_has_no_bare_write_text(filename: str) -> None:
    """An in-scope generated-surface migration must not reintroduce #3651.

    A bare ``.write_text(`` call on a read-only-destined path is exactly the
    pattern that caused #3651: it bypasses the canonical writer's
    restore-before-write step. Every confirmed in-scope migration must route
    through ``write_generated_file`` instead.
    """
    module_path = _MIGRATIONS_DIR / filename
    assert module_path.is_file(), f"expected migration file at {module_path}"

    source = module_path.read_text(encoding="utf-8")
    assert ".write_text(" not in source, f"{filename} contains a bare '.write_text(' call — route it through write_generated_file() instead (see FR-002 / #3651)"
    assert "write_generated_file" in source, (
        f"{filename} is in-scope for the canonical writer but does not import/use write_generated_file — has its write site been converted?"
    )


# ---------------------------------------------------------------------------
# T004 (full scan) — anti-pattern net over every migration, not just the
# known in-scope list. See module docstring for the strategy rationale.
# ---------------------------------------------------------------------------

# Migrations that reference the agent-command/skill-directory helpers (so the
# broad heuristic below flags them) but whose bare ``.write_text()`` call
# provably targets a plain, non-read-only project file — never a generated
# command/skill surface the runtime layer chmods read-only. Every entry
# carries a one-line rationale; a file may not be dropped from the scan by
# omission, only added here with justification.
_EXEMPT_AGENT_DIR_REFERENCING_WRITERS: dict[str, str] = {
    "m_0_9_1_complete_lane_migration.py": (
        "Defines/re-exports get_agent_dirs_for_project() — it is the "
        "canonical source of AGENT_DIRS (see CLAUDE.md) — but its own "
        ".write_text() call targets a kitty-specs WP task file during "
        "lane-flattening (`target = tasks_dir / item.name`), not a "
        "generated agent command/skill surface."
    ),
    "m_0_9_3_surface_repair_wiring.py": (
        "Mentions get_agent_dirs_for_project() only in a docstring "
        "describing C-005 compliance elsewhere in the codebase; its own "
        ".write_text() call writes a sentinel marker at "
        "`.kittify/surface_repair_wired`, not a generated agent "
        "command/skill surface."
    ),
    "m_2_0_6_consistency_sweep.py": (
        "Imports AGENT_DIRS only to unlink/rmtree stale worktree agent-"
        "command symlinks/dirs during cleanup (no write_text on any agent "
        "surface); its two .write_text() calls target a kitty-specs WP "
        "task file (frontmatter-lane normalization) and tasks.md (prompt-"
        "path rewrite), neither a generated agent command/skill surface."
    ),
}


def _references_agent_dir_or_skill_paths(source: str) -> bool:
    """Broad (recall-over-precision) heuristic: does *source* touch the
    agent-command/skill-directory surface in any way?

    Matches the canonical helper/constant names in any form (call, import,
    re-export, or docstring mention) plus the literal ``.agents`` + ``skills``
    path-segment pair used by the Codex/Vibe/Pi/Letta skill-surface agents.
    A false positive here only costs an explicit exemption entry above —
    never a silent miss of a real read-only-destined write site.
    """
    if "get_agent_dirs_for_project" in source or "AGENT_DIRS" in source:
        return True
    return ".agents" in source and "skills" in source


def test_no_unrouted_bare_write_text_on_agent_surface_paths() -> None:
    """Full-scan guard: a migration cannot reintroduce #3651 by omission.

    Unlike ``test_in_scope_migration_has_no_bare_write_text`` (which only
    checks the migrations already known to be in-scope), this test scans
    *every* migration file. A migration that combines a bare
    ``.write_text(`` call with any reference to the agent command/skill
    directory helpers must either route the write through
    ``write_generated_file`` or be listed in
    ``_EXEMPT_AGENT_DIR_REFERENCING_WRITERS`` with a rationale — so a
    *future* migration writing to a read-only-destined surface cannot slip
    through unnoticed, and a stale exemption (the file changed and no
    longer matches) is caught too via the exact-set-equality assertion.
    """
    flagged = {
        module_path.name
        for module_path in sorted(_MIGRATIONS_DIR.glob("*.py"))
        for source in [module_path.read_text(encoding="utf-8")]
        if ".write_text(" in source and "write_generated_file" not in source and _references_agent_dir_or_skill_paths(source)
    }

    exempted = set(_EXEMPT_AGENT_DIR_REFERENCING_WRITERS)
    unexplained = flagged - exempted
    stale = exempted - flagged

    assert not unexplained, (
        "Migration(s) write via bare .write_text() and reference agent "
        "command/skill directory helpers, but are neither routed through "
        f"write_generated_file() nor exempted with a rationale: {sorted(unexplained)}. "
        "If the write targets a generated read-only command/skill surface, "
        "route it through write_generated_file() (see FR-002 / #3651). If it "
        "targets a plain project file, add it to "
        "_EXEMPT_AGENT_DIR_REFERENCING_WRITERS with a one-line rationale."
    )
    assert not stale, (
        f"Stale exemption entries no longer match the scan: {sorted(stale)}. "
        "Remove them from _EXEMPT_AGENT_DIR_REFERENCING_WRITERS or confirm "
        "the migration still needs the exemption."
    )
