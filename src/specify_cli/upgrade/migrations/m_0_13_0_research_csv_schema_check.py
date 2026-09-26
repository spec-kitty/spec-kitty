"""Migration: Detect research CSV schema mismatches (informational only).

This migration scans all research features for CSV files with non-standard
schemas and reports mismatches to help users migrate their data to the
canonical schemas.

No auto-fix is applied - users are given tips to manually migrate with LLM help.
"""

from __future__ import annotations

from pathlib import Path

from ..registry import MigrationRegistry
from .base import BaseMigration, MigrationResult
from specify_cli.validators.research import (
    EVIDENCE_REQUIRED_COLUMNS,
    SOURCE_REGISTER_REQUIRED_COLUMNS,
)
from specify_cli.mission_metadata import load_meta
from specify_cli.validators.csv_schema import validate_csv_schema


@MigrationRegistry.register
class ResearchCSVSchemaCheckMigration(BaseMigration):
    """Detect research CSV schema mismatches and inform users.

    This migration:
    1. Finds all research features (mission: research in meta.json)
    2. Validates evidence-log.csv and source-register.csv schemas
    3. Reports mismatches with actionable migration tips
    4. Does NOT auto-fix (users must manually migrate data)
    """

    migration_id = "0.13.0_research_csv_schema_check"
    description = "Detect research CSV schema mismatches (informational)"
    target_version = "0.13.0"

    def detect(self, project_path: Path) -> bool:
        """Check if any research features have schema mismatches."""
        kitty_specs = project_path / "kitty-specs"
        if not kitty_specs.exists():
            return False

        # Find research features with potential schema issues
        for feature_dir in kitty_specs.iterdir():
            if not feature_dir.is_dir():
                continue

            meta_json = feature_dir / "meta.json"
            if not meta_json.exists():
                continue

            # Canonical reader (#2477): a malformed meta.json reads as None and is skipped.
            meta = load_meta(feature_dir, on_malformed="none")
            if meta is None or meta.get("mission") != "research":
                continue

            # Check CSVs
            try:
                evidence_log = feature_dir / "research" / "evidence-log.csv"
                source_register = feature_dir / "research" / "source-register.csv"

                if evidence_log.exists():
                    result = validate_csv_schema(evidence_log, EVIDENCE_REQUIRED_COLUMNS)
                    if not result.schema_valid:
                        return True

                if source_register.exists():
                    result = validate_csv_schema(source_register, SOURCE_REGISTER_REQUIRED_COLUMNS)
                    if not result.schema_valid:
                        return True

            except Exception:  # noqa: S112
                continue

        return False

    def can_apply(self, project_path: Path) -> tuple[bool, str]:  # noqa: ARG002
        """Always can apply - this is informational only."""
        return True, ""

    def apply(self, project_path: Path, dry_run: bool = False) -> MigrationResult:  # noqa: ARG002
        """Scan all research features for schema mismatches."""
        changes: list[str] = []
        warnings: list[str] = []
        errors: list[str] = []

        kitty_specs = project_path / "kitty-specs"
        if not kitty_specs.exists():
            changes.append("No kitty-specs/ directory found - nothing to check")
            return MigrationResult(
                success=True,
                changes_made=changes,
                errors=errors,
                warnings=warnings,
            )

        mismatches: list[tuple[str, str, str, str]] = []  # (feature, csv_name, expected, actual)

        # Scan all features
        for feature_dir in kitty_specs.iterdir():
            if not feature_dir.is_dir():
                continue

            meta_json = feature_dir / "meta.json"
            if not meta_json.exists():
                continue

            # Check if research mission. Canonical reader (#2477): a malformed
            # meta.json reads as None and is skipped.
            meta = load_meta(feature_dir, on_malformed="none")
            if meta is None or meta.get("mission") != "research":
                continue

            # Validate evidence-log.csv
            evidence_log = feature_dir / "research" / "evidence-log.csv"
            if evidence_log.exists():
                result = validate_csv_schema(evidence_log, EVIDENCE_REQUIRED_COLUMNS)
                if not result.schema_valid:
                    mismatches.append(
                        (
                            feature_dir.name,
                            "evidence-log.csv",
                            ",".join(EVIDENCE_REQUIRED_COLUMNS),
                            ",".join(result.actual_columns or ["<missing>"]),
                        )
                    )

            # Validate source-register.csv
            source_register = feature_dir / "research" / "source-register.csv"
            if source_register.exists():
                result = validate_csv_schema(source_register, SOURCE_REGISTER_REQUIRED_COLUMNS)
                if not result.schema_valid:
                    mismatches.append(
                        (
                            feature_dir.name,
                            "source-register.csv",
                            ",".join(SOURCE_REGISTER_REQUIRED_COLUMNS),
                            ",".join(result.actual_columns or ["<missing>"]),
                        )
                    )

        # Report findings
        if mismatches:
            report_lines = [
                "",
                "=" * 70,
                "📋 Research CSV Schema Check (Informational)",
                "=" * 70,
                "",
                f"Found {len(mismatches)} CSV file(s) with non-standard schemas:",
                "",
            ]

            for feature, csv_name, expected, actual in mismatches:
                report_lines.extend(
                    [
                        f"{feature}/research/{csv_name}:",
                        f"  Expected: {expected}",
                        f"  Actual:   {actual}",
                        "",
                        "  💡 To fix this schema mismatch:",
                        "     1. Read canonical schema in .claude/commands/spec-kitty.implement.md",
                        "     2. Create new CSV with correct headers",
                        "     3. Map old data → new schema (LLM agents can help)",
                        "     4. Replace old file",
                        "",
                    ]
                )

            report_lines.extend(
                [
                    "=" * 70,
                    "ℹ️  This is INFORMATIONAL only - no files were modified.",
                    "   Use LLM agents to help migrate data to canonical schemas.",
                    "=" * 70,
                    "",
                ]
            )

            # Print to stdout for user visibility
            for line in report_lines:
                print(line)

            changes.append(f"Detected {len(mismatches)} schema mismatch(es) - see report above")
        else:
            changes.append("All research CSV schemas are correct ✅")

        return MigrationResult(
            success=True,  # Always success - this is informational
            changes_made=changes,
            errors=errors,
            warnings=warnings,
        )
