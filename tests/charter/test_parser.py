"""Tests for charter parser module."""

import pytest

from charter.parser import CharterParser, CharterSection

pytestmark = pytest.mark.fast

class TestCharterSection:
    """Tests for CharterSection dataclass."""

    def test_section_creation(self):
        """T001: CharterSection can be instantiated with required fields."""
        section = CharterSection(
            heading="Testing",
            level=2,
            content="## Testing\nContent here.",
        )
        assert section.heading == "Testing"
        assert section.level == 2
        assert section.structured_data == {}
        assert section.requires_ai is True


class TestCharterParser:
    """Tests for CharterParser."""

    @pytest.fixture
    def parser(self):
        """Provide parser instance."""
        return CharterParser()

    def test_empty_content_returns_empty_list(self, parser):
        """T002: Parsing empty content returns empty list."""
        result = parser.parse("")
        assert result == []

    def test_no_headings_returns_single_preamble_section(self, parser):
        """T003: Content without headings returns single preamble section."""
        content = "Just some text\nwith no headings"
        result = parser.parse(content)

        assert len(result) == 1
        assert result[0].heading == "preamble"
        assert result[0].level == 0
        assert "Just some text" in result[0].content

    def test_single_h2_heading(self, parser):
        """T004: Single ## heading creates one section."""
        content = "## Testing\nTest content here."
        result = parser.parse(content)

        assert len(result) == 1
        assert result[0].heading == "Testing"
        assert result[0].level == 2
        assert "Test content here" in result[0].content

    def test_multiple_h2_headings(self, parser):
        """T005: Multiple ## headings create multiple sections."""
        content = """## First Section
Content one.

## Second Section
Content two."""
        result = parser.parse(content)

        assert len(result) == 2
        assert result[0].heading == "First Section"
        assert result[1].heading == "Second Section"

    def test_preamble_before_first_heading(self, parser):
        """T006: Content before first heading captured as preamble."""
        content = """Preamble text here.

## First Section
Content here."""
        result = parser.parse(content)

        assert len(result) == 2
        assert result[0].heading == "preamble"
        assert result[0].level == 0
        assert "Preamble text" in result[0].content
        assert result[1].heading == "First Section"

    def test_h3_subsections(self, parser):
        """T007: ### subsections captured with level 3."""
        content = """## Main Section
Main content.

### Subsection
Sub content."""
        result = parser.parse(content)

        assert len(result) == 2
        assert result[0].level == 2
        assert result[0].heading == "Main Section"
        assert result[1].level == 3
        assert result[1].heading == "Subsection"

    def test_parse_table_simple(self, parser):
        """T008: Parse simple markdown table into list of dicts."""
        content = """| Key | Value |
|-----|-------|
| Python | 3.11+ |
| Framework | pytest |"""
        result = parser.parse_table(content)

        assert len(result) == 2
        assert result[0] == {"Key": "Python", "Value": "3.11+"}
        assert result[1] == {"Key": "Framework", "Value": "pytest"}

    def test_parse_table_with_three_columns(self, parser):
        """T009: Parse table with three columns."""
        content = """| Check | Status | Notes |
|-------|--------|-------|
| Python 3.11+ | ✅ | Required |
| pytest | ✅ | 90%+ coverage |"""
        result = parser.parse_table(content)

        assert len(result) == 2
        assert result[0]["Check"] == "Python 3.11+"
        assert result[0]["Status"] == "✅"
        assert result[0]["Notes"] == "Required"

    def test_parse_table_empty_content(self, parser):
        """T010: Parsing empty content for tables returns empty list."""
        result = parser.parse_table("")
        assert result == []

    def test_parse_yaml_blocks(self, parser):
        """T011: Parse YAML code blocks into list of dicts."""
        content = """Some text.

```yaml
key1: value1
key2: value2
```

More text."""
        result = parser.parse_yaml_blocks(content)

        assert len(result) == 1
        assert result[0] == {"key1": "value1", "key2": "value2"}

    def test_parse_yaml_blocks_multiple(self, parser):
        """T012: Parse multiple YAML blocks."""
        content = """```yaml
block1: data1
```

```yaml
block2: data2
```"""
        result = parser.parse_yaml_blocks(content)

        assert len(result) == 2
        assert result[0] == {"block1": "data1"}
        assert result[1] == {"block2": "data2"}

    def test_parse_yaml_blocks_invalid_yaml(self, parser):
        """T013: Invalid YAML blocks are skipped silently."""
        content = """```yaml
invalid: [unclosed
```"""
        result = parser.parse_yaml_blocks(content)
        assert result == []

    def test_parse_numbered_lists(self, parser):
        """T014: Extract numbered list items."""
        content = """1. First item
2. Second item
3. Third item"""
        result = parser.parse_numbered_lists(content)

        assert len(result) == 3
        assert result[0] == "First item"
        assert result[1] == "Second item"
        assert result[2] == "Third item"

    def test_parse_numbered_lists_with_whitespace(self, parser):
        """T015: Numbered lists handle extra whitespace."""
        content = """1.    Indented item
2. Normal item"""
        result = parser.parse_numbered_lists(content)

        assert len(result) == 2
        assert result[0] == "Indented item"

    def test_extract_keywords_coverage(self, parser):
        """T016: Extract coverage percentage."""
        content = "Minimum 90% coverage required."
        result = parser.extract_keywords(content)

        assert "min_coverage" in result
        assert result["min_coverage"] == 90

    def test_extract_keywords_tdd_required(self, parser):
        """T017: Extract TDD requirement."""
        content = "TDD required for all missions."
        result = parser.extract_keywords(content)

        assert "tdd_required" in result
        assert result["tdd_required"] is True

    def test_extract_keywords_timeout(self, parser):
        """T018: Extract timeout value."""
        content = "Operations must complete in < 2 seconds."
        result = parser.extract_keywords(content)

        assert "timeout_seconds" in result
        assert result["timeout_seconds"] == 2.0

    def test_extract_keywords_conventional_commits(self, parser):
        """T019: Extract conventional commits convention."""
        content = "Use conventional commits for all messages."
        result = parser.extract_keywords(content)

        assert "convention" in result
        assert result["convention"] == "conventional"

    def test_extract_keywords_pre_commit_hooks(self, parser):
        """T020: Extract pre-commit hooks requirement."""
        content = "Enable pre-commit hooks for validation."
        result = parser.extract_keywords(content)

        assert "pre_commit_hooks" in result
        assert result["pre_commit_hooks"] is True

    def test_extract_keywords_multiple_patterns(self, parser):
        """T021: Extract multiple keywords from same content."""
        content = """
        Testing requires 90% coverage.
        TDD mandatory.
        Operations < 2 seconds.
        """
        result = parser.extract_keywords(content)

        assert result["min_coverage"] == 90
        assert result["tdd_required"] is True
        assert result["timeout_seconds"] == 2.0

    def test_extract_keywords_case_insensitive(self, parser):
        """T022: Keyword extraction is case-insensitive."""
        content = "TDD REQUIRED and conventional COMMITS."
        result = parser.extract_keywords(content)

        assert result["tdd_required"] is True
        assert result["convention"] == "conventional"

    def test_section_integration_with_table(self, parser):
        """T023: Section with table has structured_data and requires_ai=False."""
        content = """## Testing

| Tool | Command |
|------|---------|
| pytest | pytest -v |"""
        result = parser.parse(content)

        assert len(result) == 1
        section = result[0]
        assert "tables" in section.structured_data
        assert len(section.structured_data["tables"]) == 1
        assert section.requires_ai is False

    def test_section_integration_with_keywords(self, parser):
        """T024: Section with keywords has structured_data and requires_ai=False."""
        content = """## Performance

Operations must complete in < 2 seconds."""
        result = parser.parse(content)

        assert len(result) == 1
        section = result[0]
        assert "keywords" in section.structured_data
        assert section.structured_data["keywords"]["timeout_seconds"] == 2.0
        assert section.requires_ai is False

    def test_section_integration_prose_only(self, parser):
        """T025: Section with only prose has requires_ai=True."""
        content = """## Philosophy

We believe in clear specifications."""
        result = parser.parse(content)

        assert len(result) == 1
        section = result[0]
        assert section.structured_data == {}
        assert section.requires_ai is True

    def test_real_charter_parsing(self, parser):
        """T026: Parse real charter file successfully."""
        from pathlib import Path


        charter_path = Path(".kittify/charter/charter.md")
        if not charter_path.exists():
            pytest.skip("Real charter not found")

        content = charter_path.read_text()
        result = parser.parse(content)

        # Verify we got sections
        assert len(result) > 0

        # Verify some expected sections exist
        section_headings = [s.heading for s in result]
        assert "Purpose" in section_headings or "Technical Standards" in section_headings

        # Verify at least some sections have structured data
        structured_sections = [s for s in result if not s.requires_ai]
        assert len(structured_sections) > 0
