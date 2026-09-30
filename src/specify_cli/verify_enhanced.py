"""
Enhanced verify_setup implementation for spec-kitty.
"""

from charter.activation.mission_type_key import read_mission_type
import logging
import subprocess
from collections import defaultdict
from pathlib import Path
from rich.console import Console
from rich.table import Table

from .manifest import FileManifest, WorktreeStatus
from .mission_metadata import load_meta_or_empty, resolve_mission_identity
from .skills.manifest import load_manifest as load_skill_manifest
from .skills.verifier import verify_installed_skills

logger = logging.getLogger(__name__)


def _resolve_mission_from_feature(feature_dir: Path) -> str | None:
    """Resolve mission key from a feature's meta.json.

    Returns the mission string or ``None`` when no meta.json exists or is malformed.
    """
    # rc3 M5 (FR-002): canonical field only via the one shared reader — the
    # legacy `mission` fallback is retired.
    meta = load_meta_or_empty(feature_dir)
    if meta:
        return read_mission_type(meta)
    return None


def _parse_skill_name_from_frontmatter(content: str) -> str | None:
    """Extract the ``name`` field from YAML frontmatter in a SKILL.md file.

    Returns ``None`` when no frontmatter or no ``name`` key is found.
    """
    if not content.startswith("---"):
        return None
    end = content.find("---", 3)
    if end == -1:
        return None
    frontmatter = content[3:end]
    for line in frontmatter.splitlines():
        stripped = line.strip()
        if stripped.startswith("name:"):
            value = stripped[len("name:"):].strip()
            # Remove optional surrounding quotes
            if len(value) >= 2 and value[0] in ('"', "'") and value[-1] == value[0]:
                value = value[1:-1]
            return value if value else None
    return None


def run_enhanced_verify(
    repo_root: Path,
    project_root: Path,
    cwd: Path,
    feature: str | None,
    json_output: bool,
    check_files: bool,
    console: Console,
    feature_dir: Path | None = None,
) -> dict:
    """
    Run the enhanced verification with manifest checking and worktree status.

    Returns a dict suitable for JSON output if needed.
    """
    output_data = {
        "environment": {},
        "feature_detection": {},
        "worktree_status": {},
        "file_integrity": {},
        "feature_analysis": {},
        "recommendations": []
    }

    # Resolve mission from feature-level meta.json when available
    mission_type: str | None = None
    if feature_dir is not None:
        mission_type = _resolve_mission_from_feature(feature_dir)
    elif feature:
        # WP09/FR-001 (kind-correct): ``_resolve_mission_from_feature`` reads
        # ``meta.json`` — route through the seam on ``PRIMARY_METADATA`` rather
        # than the kind-blind resolver (NFR-001).
        from mission_runtime import MissionArtifactKind, placement_seam

        candidate = placement_seam(project_root, feature).read_dir(
            MissionArtifactKind.PRIMARY_METADATA
        )
        if candidate.is_dir():
            mission_type = _resolve_mission_from_feature(candidate)

    # Initialize helpers
    kittify_dir = project_root / ".kittify"
    manifest = FileManifest(kittify_dir, mission_type=mission_type)
    worktree_status = WorktreeStatus(repo_root)

    # 1. Environment Information
    in_worktree = '.worktrees' in str(cwd)

    try:
        current_branch = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=True
        ).stdout.strip()
    except subprocess.CalledProcessError:
        current_branch = None

    output_data["environment"] = {
        "working_directory": str(cwd),
        "repo_root": str(repo_root),
        "project_root": str(project_root),
        "in_worktree": in_worktree,
        "current_branch": current_branch,
        "active_mission": mission_type or "no mission context"
    }

    if not json_output:
        console.print("\n[bold]System Integrity Check[/bold]\n")

        # Environment section
        console.print("[cyan]1. Environment[/cyan]")
        console.print(f"   Working directory: {cwd}")
        console.print(f"   Repository root: {repo_root}")

        if in_worktree:
            console.print("   [green]✓[/green] In worktree")
        else:
            console.print("   [dim]○[/dim] Not in worktree")

        if current_branch:
            console.print(f"   Current branch: {current_branch}")
            if current_branch in ("main", "master"):
                console.print(f"   [yellow]⚠[/yellow] On {current_branch} branch")
        else:
            console.print("   [yellow]⚠[/yellow] Could not detect branch")

    # 2. File Integrity Check
    total_missing = 0
    if check_files:
        file_check = manifest.check_files()
        expected_files = manifest.get_expected_files()

        total_expected = sum(len(files) for files in expected_files.values())
        total_present = len(file_check["present"])
        total_missing = len(file_check["missing"])

        output_data["file_integrity"] = {
            "active_mission": mission_type or "no mission context",
            "total_expected": total_expected,
            "total_present": total_present,
            "total_missing": total_missing,
            "missing_files": file_check["missing"],
            "categories": {}
        }

        # Count by category
        for category, files in expected_files.items():
            present_in_category = sum(1 for f in files if f in file_check["present"])
            output_data["file_integrity"]["categories"][category] = {
                "expected": len(files),
                "present": present_in_category,
                "missing": len(files) - present_in_category
            }

        if not json_output:
            console.print("\n[cyan]2. Mission File Integrity[/cyan]")
            console.print(f"   Active mission: {mission_type or 'no mission context'}")

            if total_missing == 0:
                console.print(f"   [green]✓[/green] All {total_expected} expected files present")
            else:
                console.print(f"   [yellow]⚠[/yellow] {total_missing} of {total_expected} files missing")

                # Show missing by category
                for category in ["commands", "templates", "scripts"]:
                    cat_missing = [f for f, c in file_check["missing"].items() if c == category]
                    if cat_missing:
                        console.print(f"   Missing {category}:")
                        for file in cat_missing[:3]:  # Show first 3
                            console.print(f"     - {file}")
                        if len(cat_missing) > 3:
                            console.print(f"     ... and {len(cat_missing) - 3} more")

    # 3. Worktree Status Overview
    worktree_summary = worktree_status.get_worktree_summary()
    output_data["worktree_status"] = worktree_summary

    if not json_output:
        console.print("\n[cyan]3. Worktree Overview[/cyan]")
        console.print(f"   Total features: {worktree_summary['total_features']}")
        console.print(f"   Active worktrees: {worktree_summary['active_worktrees']}")
        console.print(f"   Merged features: {worktree_summary['merged_features']}")
        console.print(f"   In development: {worktree_summary['in_development']}")

    # 4. Feature Analysis (only when an explicit feature is provided)
    try:
        if not feature:
            raise ValueError("No --mission provided; skipping feature analysis.")
        mission_slug = feature.strip()
        # WP09/FR-001 (kind-correct): ``resolve_mission_identity`` reads
        # ``meta.json`` — route through the seam on ``PRIMARY_METADATA``
        # rather than the kind-blind resolver (NFR-001).
        from mission_runtime import MissionArtifactKind, placement_seam

        resolved_feature_dir = feature_dir or placement_seam(
            project_root, mission_slug
        ).read_dir(MissionArtifactKind.PRIMARY_METADATA)
        identity = resolve_mission_identity(resolved_feature_dir)

        output_data["feature_detection"] = {
            "detected": True,
            "mission_slug": identity.mission_slug,
            "mission_number": identity.mission_number,
            "mission_type": identity.mission_type,
        }

        # Get detailed status for this feature
        feature_status = worktree_status.get_feature_status(mission_slug)
        output_data["feature_analysis"] = feature_status

        if not json_output:
            console.print("\n[cyan]4. Current Feature Status[/cyan]")
            console.print(f"   Feature: {mission_slug}")
            console.print(f"   State: {feature_status['state'].upper()}")

            # Status indicators
            if feature_status["branch_exists"]:
                status_text = "merged" if feature_status["branch_merged"] else "active"
                console.print(f"   [green]✓[/green] Branch exists ({status_text})")
            else:
                console.print("   [dim]○[/dim] No branch")

            if feature_status["worktree_exists"]:
                console.print(f"   [green]✓[/green] Worktree at: {feature_status['worktree_path']}")
            else:
                console.print("   [dim]○[/dim] No worktree")

            # Artifacts
            if feature_status["artifacts_in_main"]:
                console.print(f"   Artifacts in main: {', '.join(feature_status['artifacts_in_main'])}")
            if feature_status["artifacts_in_worktree"]:
                console.print(f"   Artifacts in worktree: {', '.join(feature_status['artifacts_in_worktree'])}")

            # State-based observations
            if feature_status["state"] == "merged":
                console.print("   [green]✓[/green] Feature appears to be merged")
            elif feature_status["state"] == "in_development":
                console.print("   [blue]●[/blue] Feature is in active development")
            elif feature_status["state"] == "not_started":
                console.print("   [dim]○[/dim] Feature not yet started")

    except (ValueError, Exception) as exc:
        output_data["feature_detection"] = {
            "detected": False,
            "error": str(exc)
        }

        if not json_output:
            console.print("\n[cyan]4. Feature Analysis[/cyan]")
            console.print(f"   [yellow]⚠[/yellow] Skipped: {exc}")

    # 5. All Features Status Table
    all_features = worktree_status.get_all_features()

    if not json_output and all_features:
        console.print("\n[cyan]5. All Features Status[/cyan]")

        table = Table(show_header=True, header_style="bold")
        table.add_column("Feature", style="cyan")
        table.add_column("State", style="white")
        table.add_column("Branch", style="white")
        table.add_column("Worktree", style="white")
        table.add_column("Artifacts", style="white")

        for feat in all_features[:10]:  # Show first 10
            feat_status = worktree_status.get_feature_status(feat)

            # Determine display values
            state_display = {
                "merged": "[green]MERGED[/green]",
                "in_development": "[yellow]ACTIVE[/yellow]",
                "ready_to_merge": "[blue]READY[/blue]",
                "not_started": "[dim]NOT STARTED[/dim]",
                "unknown": "[dim]?[/dim]"
            }.get(feat_status["state"], feat_status["state"])

            branch_display = "✓" if feat_status["branch_exists"] else "-"
            if feat_status["branch_merged"]:
                branch_display = "merged"

            worktree_display = "✓" if feat_status["worktree_exists"] else "-"

            artifact_count = len(feat_status["artifacts_in_main"]) + len(feat_status["artifacts_in_worktree"])
            artifacts_display = str(artifact_count) if artifact_count > 0 else "-"

            table.add_row(
                feat,
                state_display,
                branch_display,
                worktree_display,
                artifacts_display
            )

        console.print(table)

        if len(all_features) > 10:
            console.print(f"   [dim]... and {len(all_features) - 10} more features[/dim]")

    # 6. Managed Skills
    skill_verify_data: dict = {"status": "skipped"}
    skill_warnings: list[str] = []
    skill_has_issues = False

    try:
        skill_manifest = load_skill_manifest(project_root)
        if skill_manifest is None:
            skill_verify_data = {"status": "no_manifest"}
            if not json_output:
                console.print("\n[cyan]6. Managed Skills[/cyan]")
                console.print("   [dim]○[/dim] No skill manifest found")
        else:
            skill_result = verify_installed_skills(project_root)
            total_entries = len(skill_manifest.entries)
            n_missing = len(skill_result.missing)
            n_drifted = len(skill_result.drifted)
            n_errors = len(skill_result.errors)
            n_ok = total_entries - n_missing - n_drifted - n_errors

            skill_verify_data = {
                "status": "ok" if skill_result.ok else "issues_found",
                "total_files": total_entries,
                "ok": n_ok,
                "missing": n_missing,
                "drifted": n_drifted,
                "errors": n_errors,
                "missing_files": [e.installed_path for e in skill_result.missing],
                "drifted_files": [
                    {"path": e.installed_path, "skill": e.skill_name}
                    for e, _hash in skill_result.drifted
                ],
                "error_messages": skill_result.errors,
            }

            if not skill_result.ok:
                skill_has_issues = True

            if not json_output:
                console.print("\n[cyan]6. Managed Skills[/cyan]")
                if skill_result.ok:
                    console.print(f"   [green]✓[/green] All {total_entries} files intact")
                else:
                    console.print(f"   [yellow]⚠[/yellow] {n_missing + n_drifted + n_errors} issue(s) in {total_entries} managed files")

                    if skill_result.missing:
                        console.print(f"   Missing ({n_missing}):")
                        for entry in skill_result.missing:
                            console.print(f"     - {entry.installed_path} (skill: {entry.skill_name})")

                    if skill_result.drifted:
                        console.print(f"   Drifted ({n_drifted}):")
                        for entry, _actual_hash in skill_result.drifted:
                            console.print(f"     - {entry.installed_path} (skill: {entry.skill_name})")

                    if skill_result.errors:
                        console.print(f"   Errors ({n_errors}):")
                        for err_msg in skill_result.errors:
                            console.print(f"     - {err_msg}")

            # T030: Detect duplicate skill names across roots
            # Scan installed skill roots for SKILL.md files and parse name
            # from YAML frontmatter to detect naming conflicts.
            skill_name_to_roots: dict[str, list[str]] = defaultdict(list)
            seen_roots: set[str] = set()

            # Collect unique skill roots from manifest entries
            for entry in skill_manifest.entries:
                parts = Path(entry.installed_path).parts
                # installed_path like ".claude/skills/my-skill/SKILL.md"
                # root is ".claude/skills"
                if len(parts) >= 3:
                    root_key = str(Path(parts[0]) / parts[1])
                    seen_roots.add(root_key)

            # Scan each root for SKILL.md files and parse name from frontmatter
            for root_key in sorted(seen_roots):
                root_dir = project_root / root_key
                if not root_dir.is_dir():
                    continue
                for skill_dir in sorted(root_dir.iterdir()):
                    if not skill_dir.is_dir():
                        continue
                    skill_md = skill_dir / "SKILL.md"
                    if not skill_md.is_file():
                        continue
                    try:
                        content = skill_md.read_text(encoding="utf-8")
                        skill_name = _parse_skill_name_from_frontmatter(content)
                        if skill_name:
                            skill_name_to_roots[skill_name].append(root_key)
                    except OSError:
                        continue

            for name, roots in sorted(skill_name_to_roots.items()):
                if len(roots) > 1:
                    # A skill in both .agents/skills/ (shared root) and a
                    # vendor-native root (e.g. .claude/skills/) is normal for
                    # mixed-agent installs — not a duplicate.
                    shared_root = ".agents/skills"
                    non_shared = [r for r in roots if r != shared_root]
                    if shared_root in roots and len(non_shared) <= 1:
                        continue  # Expected mixed-agent layout
                    warning = f"Duplicate skill '{name}' found in: {', '.join(sorted(roots))}"
                    skill_warnings.append(warning)

            if skill_warnings:
                skill_verify_data["duplicate_warnings"] = skill_warnings
                if not json_output:
                    for warning in skill_warnings:
                        console.print(f"   [yellow]⚠[/yellow] {warning}")

    except Exception as exc:
        logger.warning("Skill verification failed: %s", exc)
        skill_verify_data = {"status": "error", "error": str(exc)}
        if not json_output:
            console.print("\n[cyan]6. Managed Skills[/cyan]")
            console.print(f"   [yellow]⚠[/yellow] Skill verification failed: {exc}")

    output_data["managed_skills"] = skill_verify_data

    # 7. Observations (not recommendations)
    observations = []

    if current_branch in ("main", "master") and in_worktree:
        observations.append("Unusual: In worktree but on main branch")

    if output_data.get("feature_analysis", {}).get("state") == "in_development":
        if not output_data["feature_analysis"].get("worktree_exists"):
            observations.append(f"Feature {mission_slug} has no worktree but has development artifacts")

    if total_missing > 0 and check_files:
        observations.append(f"Mission integrity: {total_missing} expected files not found")

    if skill_has_issues:
        observations.append("Managed skills: some files are missing or drifted (run spec-kitty init --here to restore)")

    output_data["observations"] = observations

    if not json_output and observations:
        console.print("\n[cyan]7. Observations[/cyan]")
        for obs in observations:
            console.print(f"   • {obs}")

    # Final summary
    if not json_output:
        console.print("\n[bold green]✓ Verification complete[/bold green]\n")

    return output_data
