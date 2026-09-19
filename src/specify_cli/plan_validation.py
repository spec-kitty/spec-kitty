"""Plan validation utilities for Spec Kitty CLI.

Detects whether a plan.md file has been meaningfully filled out or is still in template form.
"""

from __future__ import annotations

from pathlib import Path


# Template markers that indicate an unfilled plan
TEMPLATE_MARKERS = [
    "[FEATURE]",
    "[###-feature-name]",
    "[DATE]",
    "[link]",
    "[Extract from feature spec:",
    "ACTION REQUIRED: Replace the content",
    "[e.g., Python 3.11",
    "or NEEDS CLARIFICATION",
    "# [REMOVE IF UNUSED]",
    "[Gates determined based on charter file]",
    "[Document the selected structure",
]

# Minimum number of template markers that must be removed for plan to be considered filled
MIN_MARKERS_TO_REMOVE = 5


class PlanValidationError(Exception):
    """Raised when plan.md validation fails."""

    pass


def detect_unfilled_plan(plan_path: Path) -> tuple[bool, list[str]]:
    """Check if plan.md is still in template form.

    Args:
        plan_path: Path to the plan.md file

    Returns:
        Tuple of (is_unfilled, list of markers found)
        - is_unfilled: True if the plan appears to be unfilled template
        - markers: List of template markers still present in the file
    """
    if not plan_path.exists():
        return False, []

    try:
        content = plan_path.read_text(encoding="utf-8-sig")
    except Exception:
        # If we can't read it, assume it's filled (don't block progress)
        return False, []

    found_markers = []
    for marker in TEMPLATE_MARKERS:
        if marker in content:
            found_markers.append(marker)

    # Consider unfilled if multiple key markers are still present
    is_unfilled = len(found_markers) >= MIN_MARKERS_TO_REMOVE

    return is_unfilled, found_markers


def validate_plan_filled(
    plan_path: Path,
    *,
    mission_slug: str | None = None,
    strict: bool = True,
) -> None:
    """Validate that plan.md has been filled out.

    Args:
        plan_path: Path to the plan.md file
        mission_slug: Optional feature slug for error messages
        strict: If True, raise error on unfilled plan. If False, just warn.

    Raises:
        PlanValidationError: If plan is unfilled and strict=True
    """
    is_unfilled, markers = detect_unfilled_plan(plan_path)

    if not is_unfilled:
        return

    feature_display = f" for feature '{mission_slug}'" if mission_slug else ""
    marker_list = "\n  - ".join(markers[:5])  # Show first 5 markers
    more_markers = f"\n  ... and {len(markers) - 5} more" if len(markers) > 5 else ""

    error_msg = (
        f"plan.md{feature_display} appears to be unfilled (template form).\n"
        f"Found {len(markers)} template markers:\n  - {marker_list}{more_markers}\n\n"
        f"Please complete the /spec-kitty.plan workflow inside your coding agent (Claude Code, Codex, Cursor) "
        f"before proceeding to research or tasks.\n"
        f"The plan.md file must have technical details filled in, not just template placeholders."
    )

    if strict:
        raise PlanValidationError(error_msg)
    else:
        import sys

        print(f"Warning: {error_msg}", file=sys.stderr)


__all__ = ["PlanValidationError", "detect_unfilled_plan", "validate_plan_filled"]
