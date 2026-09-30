"""Migration 3.2.0rc35: add agent-profile load and review-handoff guidance.

Updates four installed artifact paths in client projects so that agents load
the correct persona before implementing or reviewing a WP:

1. ``.kittify/missions/software-dev/command-templates/implement.md``
   - Fix stale field names: ``profile`` → ``agent_profile``, ``tool`` → ``agent``
   - Add ``model`` field entry if missing
   - Fix Section-2a fallback sentence
   - Insert Section 6 "Prepare for Review Hand-off" before ``## Output``

2. ``.kittify/missions/software-dev/command-templates/review.md``
   - Insert Section 2a "Load Agent Profile" after the Section 2 parse list

3. ``.kittify/overrides/missions/software-dev/templates/task-prompt-template.md``
   - Ensure ``agent_profile`` and ``role`` frontmatter fields are present
   - Ensure the ``⚡ Do This First: Load Agent Profile`` section is present

4. ``.agents/skills/spec-kitty.implement/SKILL.md``
   and ``.agents/skills/spec-kitty.review/SKILL.md``
   - Same insertions as the ``.kittify`` command-template copies above

All edits are idempotent: the migration checks for sentinel strings before
inserting content and skips silently when they are already present.

Detection: checks for the absence of "Prepare for Review Hand-off" in
``.kittify/missions/software-dev/command-templates/implement.md``.
Returns False if neither implement.md nor any skill file exists (nothing
to migrate).
"""

from __future__ import annotations

from pathlib import Path

from specify_cli.runtime.generated_writer import write_generated_file

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult


# ---------------------------------------------------------------------------
# Sentinel strings used for idempotency checks
# ---------------------------------------------------------------------------

_HANDOFF_SENTINEL = "Prepare for Review Hand-off"
_PROFILE_LOAD_SENTINEL = "Load Agent Profile"
_DO_THIS_FIRST_SENTINEL = "⚡ Do This First"

# ---------------------------------------------------------------------------
# Content blocks to insert
# ---------------------------------------------------------------------------

_IMPLEMENT_HANDOFF_BLOCK = """\

### 6. Prepare for Review Hand-off

Before moving this WP to `for_review`, update the `agent_profile` field in the WP
prompt frontmatter to a reviewer profile so the reviewing agent loads the correct
persona automatically.

1. Identify the appropriate reviewer profile:
   ```bash
   spec-kitty agent profile list --json | grep reviewer
   ```
   The default reviewer profile is `reviewer-renata`. Use it unless the mission or
   charter specifies a different reviewer.

2. Update the WP frontmatter:
   ```yaml
   agent_profile: "reviewer-renata"
   role: "reviewer"
   ```

3. Commit the updated frontmatter together with your implementation changes **before**
   running `spec-kitty agent tasks move-task WPxx --to for_review`.

The reviewer will then use `/ad-hoc-profile-load` with the reviewer profile and apply
its self-review gates automatically.
"""

_REVIEW_PROFILE_LOAD_BLOCK = """\

### 2a. Load Agent Profile

Before proceeding with the review, load the agent profile from the WP frontmatter
using the `/ad-hoc-profile-load` skill (or `spec-kitty agent profile list` to browse
available profiles). Apply the profile's reviewer guidance and self-review gates for
the rest of this review session.

The WP frontmatter should already have `agent_profile` set to a reviewer profile
(e.g., `reviewer-renata`) by the implementing agent before it moved the WP to
`for_review`. If `agent_profile` is still set to an implementer profile, load the
implementer profile anyway and note the oversight in your review comments.
"""

_TASK_PROMPT_DO_THIS_FIRST_BLOCK = """\

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the
frontmatter, and behave according to its guidance before parsing the rest of this
prompt.

If no profile is specified, run `spec-kitty agent profile list` and select the best
match for this work package's `task_type` and `authoritative_surface`.

---
"""

# Frontmatter fields to insert into task-prompt-template if missing
_AGENT_PROFILE_FIELD = "agent_profile:"
_ROLE_FIELD = "role:"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_implement(content: str) -> tuple[str, list[str]]:
    """Apply all implement.md patches; return (new_content, list_of_changes)."""
    changes: list[str] = []

    # Fix stale field names
    if "- `profile`" in content:
        content = content.replace("- `profile`", "- `agent_profile`")
        changes.append("fixed stale field: `profile` → `agent_profile`")
    if "- `tool`" in content:
        content = content.replace("- `tool`", "- `agent`")
        changes.append("fixed stale field: `tool` → `agent`")
    if "If `profile` is empty" in content:
        content = content.replace(
            "If `profile` is empty", "If `agent_profile` is empty"
        )
        changes.append("fixed stale Section-2a fallback sentence")

    # Insert Section 6 handoff block before ## Output (idempotent)
    if _HANDOFF_SENTINEL not in content:
        anchor = "## Output"
        content = content.replace(anchor, _IMPLEMENT_HANDOFF_BLOCK + anchor, 1) if anchor in content else content + _IMPLEMENT_HANDOFF_BLOCK
        changes.append("inserted Section 6 'Prepare for Review Hand-off'")

    return content, changes


def _patch_review(content: str) -> tuple[str, list[str]]:
    """Apply all review.md patches; return (new_content, list_of_changes)."""
    changes: list[str] = []

    if _PROFILE_LOAD_SENTINEL not in content:
        # Insert after "## 2. Parse WP frontmatter" or equivalent section marker.
        # Look for "### 3." as the anchor to insert before.
        anchor = "### 3."
        content = content.replace(anchor, _REVIEW_PROFILE_LOAD_BLOCK + anchor, 1) if anchor in content else content + _REVIEW_PROFILE_LOAD_BLOCK
        changes.append("inserted Section 2a 'Load Agent Profile'")

    return content, changes


def _patch_task_prompt_template(content: str) -> tuple[str, list[str]]:
    """Apply task-prompt-template.md patches; return (new_content, list_of_changes)."""
    changes: list[str] = []

    # Ensure agent_profile and role fields exist in frontmatter
    if content.startswith("---"):
        end_fm = content.find("---", 3)
        if end_fm != -1:
            frontmatter = content[3:end_fm]
            new_fm = frontmatter
            if _AGENT_PROFILE_FIELD not in frontmatter:
                new_fm = new_fm.rstrip() + '\nagent_profile: ""\n'
                changes.append("added agent_profile field to frontmatter")
            if _ROLE_FIELD not in frontmatter:
                new_fm = new_fm.rstrip() + '\nrole: ""\n'
                changes.append("added role field to frontmatter")
            if new_fm != frontmatter:
                content = "---" + new_fm + "---" + content[end_fm + 3 :]

    # Insert ⚡ Do This First block after the first heading
    if _DO_THIS_FIRST_SENTINEL not in content:
        lines = content.split("\n")
        insert_at = -1
        for i, line in enumerate(lines):
            if line.startswith("# ") and i > 0:
                insert_at = i + 1
                break
        if insert_at >= 0:
            lines.insert(insert_at, _TASK_PROMPT_DO_THIS_FIRST_BLOCK)
            content = "\n".join(lines)
        else:
            content = content + _TASK_PROMPT_DO_THIS_FIRST_BLOCK
        changes.append("inserted '⚡ Do This First: Load Agent Profile' section")

    return content, changes


def _apply_patch_to_file(
    path: Path, patch_fn: object, dry_run: bool, *, read_only: bool = False
) -> list[str]:
    """Read file, apply patch function, write back if changed. Return change list.

    ``read_only`` must be ``True`` for targets the generation layer marks
    read-only after writing (currently the ``.agents/skills/spec-kitty.*``
    SKILL.md files) so a re-write does not raise ``PermissionError`` on a
    previously-generated file (#3651) and the file is left in the same
    managed, read-only state afterward. The ``.kittify`` command-template and
    override targets are plain project files and stay writable.
    """
    if not path.exists():
        return []
    content = path.read_text(encoding="utf-8")
    new_content, changes = patch_fn(content)  # type: ignore[operator]
    if changes and not dry_run:
        write_generated_file(path, new_content, read_only=read_only)
    return [f"{path}: {c}" for c in changes]


# ---------------------------------------------------------------------------
# Migration class
# ---------------------------------------------------------------------------


@MigrationRegistry.register
class KittifyProfileHandoffMigration(BaseMigration):
    """Add agent-profile load and review-handoff guidance to installed templates."""

    migration_id = "3.2.0rc35_kittify_profile_handoff"
    description = (
        "Insert profile-load and review-handoff blocks into .kittify command "
        "templates and .agents/skills skill files"
    )
    target_version = "3.2.0rc35"

    def can_apply(self, _project_path: Path) -> tuple[bool, str]:
        """Always safe to apply — patches are additive and idempotent."""
        return True, ""

    def detect(self, project_path: Path) -> bool:
        """Return True if implement.md lacks the handoff sentinel or skills missing it."""
        implement_path = (
            project_path
            / ".kittify"
            / "missions"
            / "software-dev"
            / "command-templates"
            / "implement.md"
        )
        if implement_path.exists():
            content = implement_path.read_text(encoding="utf-8")
            if _HANDOFF_SENTINEL not in content:
                return True

        skill_implement = (
            project_path / ".agents" / "skills" / "spec-kitty.implement" / "SKILL.md"
        )
        if skill_implement.exists():
            content = skill_implement.read_text(encoding="utf-8")
            if _HANDOFF_SENTINEL not in content:
                return True

        return False

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:
        """Apply profile-handoff patches to all four artifact paths."""
        all_changes: list[str] = []

        # 1. .kittify implement.md
        implement_path = (
            project_path
            / ".kittify"
            / "missions"
            / "software-dev"
            / "command-templates"
            / "implement.md"
        )
        all_changes += _apply_patch_to_file(implement_path, _patch_implement, dry_run)

        # 2. .kittify review.md
        review_path = (
            project_path
            / ".kittify"
            / "missions"
            / "software-dev"
            / "command-templates"
            / "review.md"
        )
        all_changes += _apply_patch_to_file(review_path, _patch_review, dry_run)

        # 3. .kittify overrides task-prompt-template.md
        override_path = (
            project_path
            / ".kittify"
            / "overrides"
            / "missions"
            / "software-dev"
            / "templates"
            / "task-prompt-template.md"
        )
        all_changes += _apply_patch_to_file(
            override_path, _patch_task_prompt_template, dry_run
        )

        # 4. .agents/skills skill files
        skill_implement = (
            project_path / ".agents" / "skills" / "spec-kitty.implement" / "SKILL.md"
        )
        all_changes += _apply_patch_to_file(
            skill_implement, _patch_implement, dry_run, read_only=True
        )

        skill_review = (
            project_path / ".agents" / "skills" / "spec-kitty.review" / "SKILL.md"
        )
        all_changes += _apply_patch_to_file(
            skill_review, _patch_review, dry_run, read_only=True
        )

        return MigrationResult(
            success=True,
            changes_made=all_changes,
        )
