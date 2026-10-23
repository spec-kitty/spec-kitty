"""Tests for documentation mission templates."""

import pytest
from pathlib import Path

from specify_cli.mission import Mission

pytestmark = pytest.mark.fast
# The canonical documentation mission templates live in the packs copy; the
# src/specify_cli/missions/documentation/templates/ fork is frozen, migration-only (#5280).
REPO_ROOT = Path(__file__).resolve().parents[2]
MISSION_DIR = REPO_ROOT / "packs" / "built-in" / "missions" / "documentation"


# T058: Test Divio Template Frontmatter
@pytest.mark.parametrize(
    "template_name,expected_type",
    [
        ("divio/tutorial-template.md", "tutorial"),
        ("divio/howto-template.md", "how-to"),
        ("divio/reference-template.md", "reference"),
        ("divio/explanation-template.md", "explanation"),
    ],
)
def test_divio_template_has_frontmatter(template_name, expected_type):
    """Test Divio templates have YAML frontmatter with type field."""
    mission = Mission(MISSION_DIR)
    template = mission.get_template(template_name)
    content = template.read_text()

    # Check for frontmatter
    assert content.startswith("---"), f"{template_name} missing frontmatter"

    # Parse frontmatter
    from ruamel.yaml import YAML

    yaml = YAML()

    lines = content.split("\n")
    end_idx = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = i
            break

    assert end_idx is not None, f"{template_name} frontmatter not closed"

    frontmatter_text = "\n".join(lines[1:end_idx])
    frontmatter = yaml.load(frontmatter_text)

    # Check type field
    assert "type" in frontmatter, f"{template_name} missing type field"
    assert frontmatter["type"] == expected_type


# T059: Test Divio Template Sections
def test_tutorial_template_required_sections():
    """Test tutorial template has required sections."""
    mission = Mission(MISSION_DIR)
    template = mission.get_template("divio/tutorial-template.md")
    content = template.read_text()

    # Required sections for tutorials
    assert "## What You'll Learn" in content or "## What You'll Build" in content
    assert "## Prerequisites" in content or "## Before You Begin" in content
    assert "## Step 1:" in content or "# Step 1:" in content
    assert "## Next Steps" in content or "## What You've Accomplished" in content


def test_howto_template_required_sections():
    """Test how-to template has required sections."""
    mission = Mission(MISSION_DIR)
    template = mission.get_template("divio/howto-template.md")
    content = template.read_text()

    # Required sections for how-tos
    assert "How-To:" in content or "How to" in content  # Title
    assert "## Goal" in content or "## Prerequisites" in content
    assert "## Detailed Steps" in content or "### 1." in content
    assert "## Verification" in content or "## Related" in content or "## Troubleshooting" in content


def test_reference_template_required_sections():
    """Test reference template has required sections."""
    mission = Mission(MISSION_DIR)
    template = mission.get_template("divio/reference-template.md")
    content = template.read_text()

    # Reference should have structured technical info
    assert "# Reference:" in content or "## Overview" in content
    assert "## Parameters" in content or "### Syntax" in content or "## Examples" in content
    assert "## Related" in content or "## See Also" in content or "## Overview" in content


def test_explanation_template_required_sections():
    """Test explanation template has required sections."""
    mission = Mission(MISSION_DIR)
    template = mission.get_template("divio/explanation-template.md")
    content = template.read_text()

    # Explanations should have conceptual sections
    assert "## Background" in content or "## Overview" in content
    assert "## Concepts" in content or "## How It Works" in content
    assert "## Design" in content or "## Trade-offs" in content or "## Alternatives" in content


