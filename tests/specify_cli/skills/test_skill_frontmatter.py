"""The single SKILL.md frontmatter authority (#6475, FR-012, FR-013)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
from ruamel.yaml import YAML

from specify_cli.skills.skill_frontmatter import (
    ALLOWED_FIELDS,
    NATIVE_SKILL_ROOTS,
    command_skill_fields,
    ensure_skill_frontmatter,
    is_shared_root,
    project_for_root,
    project_skill_bytes,
    render_frontmatter,
    root_of_installed_path,
    validate_skill_frontmatter,
    yaml_scalar,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_NEUTRAL = '---\nname: "acme-deploy"\ndescription: "Deploy."\nuser-invocable: true\ndisable-model-invocation: true\n---\n\n# Deploy\n'
_SHIPPED = '---\nname: spk-load\ndescription: >-\n  Load a profile,\n  on demand.\nargument-hint: "[profile]"\n---\n\n# Load\n'


def _frontmatter(text: str) -> dict[str, object]:
    data = YAML(typ="safe").load(text.split("---\n", 2)[1])
    assert isinstance(data, dict)
    return data


def test_native_roots_derive_from_agent_skill_config() -> None:
    assert {".claude/skills", ".qwen/skills", ".kilocode/skills"} == NATIVE_SKILL_ROOTS


@pytest.mark.parametrize(
    ("root", "shared"),
    [
        (".agents/skills", True),
        (".agents/skills/", True),
        (".claude/skills/", False),
        (".qwen/skills", False),
        (".kilocode\\skills", False),
        (".github/skills", True),
    ],
)
def test_is_shared_root(root: str, shared: bool) -> None:
    assert is_shared_root(root) is shared


def test_root_of_installed_path() -> None:
    assert root_of_installed_path(".agents/skills/x/refs/a.md", "x", "refs/a.md") == ".agents/skills"
    with pytest.raises(ValueError, match="does not end with"):
        root_of_installed_path(".agents/skills/y/SKILL.md", "x", "SKILL.md")


def test_shared_projection_moves_extras_under_metadata_as_strings() -> None:
    projected = project_for_root(_NEUTRAL, shared=True, skill_name="acme-deploy")
    assert projected == (
        '---\nname: "acme-deploy"\ndescription: "Deploy."\nmetadata:\n  user-invocable: "true"\n  disable-model-invocation: "true"\n---\n\n# Deploy\n'
    )
    data = _frontmatter(projected)
    assert set(data) <= ALLOWED_FIELDS
    assert data["metadata"] == {"user-invocable": "true", "disable-model-invocation": "true"}


def test_shared_projection_keeps_block_scalars_verbatim() -> None:
    projected = project_for_root(_SHIPPED, shared=True, skill_name="spk-load")
    assert projected.startswith('---\nname: spk-load\ndescription: >-\n  Load a profile,\n  on demand.\nmetadata:\n  argument-hint: "[profile]"\n---\n')


def test_native_projection_keeps_claude_keys() -> None:
    assert project_for_root(_NEUTRAL, shared=False, skill_name="acme-deploy") == _NEUTRAL
    assert project_for_root(_SHIPPED, shared=False, skill_name="spk-load") == _SHIPPED


def test_native_projection_lifts_claude_keys_out_of_metadata() -> None:
    spec = '---\nname: n\ndescription: d\nmetadata:\n  owner: "team"\n  user-invocable: "true"\n  argument-hint: "[x]"\n---\nbody\n'
    assert project_for_root(spec, shared=False, skill_name="n") == (
        '---\nname: n\ndescription: d\nmetadata:\n  owner: "team"\nuser-invocable: true\nargument-hint: "[x]"\n---\nbody\n'
    )


def test_native_projection_of_command_skill_matches_pre_rename_shape() -> None:
    spec = render_frontmatter(command_skill_fields("spec-kitty-plan", "Plan it")) + "\nbody\n"
    assert (
        project_for_root(spec, shared=False, skill_name="spec-kitty-plan") == "---\nname: spec-kitty-plan\ndescription: Plan it\nuser-invocable: true\n---\nbody\n"
    )


def test_native_projection_leaves_an_explicit_top_level_key() -> None:
    text = '---\nname: n\ndescription: d\nuser-invocable: false\nmetadata:\n  user-invocable: "true"\n---\n'
    assert project_for_root(text, shared=False, skill_name="n") == text


@pytest.mark.parametrize("shared", [True, False])
@pytest.mark.parametrize("source", [_NEUTRAL, _SHIPPED, "# Plain\n\nHello world.\n"])
def test_projection_is_idempotent(source: str, shared: bool) -> None:
    once = project_for_root(source, shared=shared, skill_name="acme-deploy")
    assert project_for_root(once, shared=shared, skill_name="acme-deploy") == once


def test_shared_projection_merges_into_existing_metadata_explicit_entry_wins() -> None:
    text = '---\nname: n\nmetadata:\n  owner: team\n  version: 2\ndescription: d\nversion: "1"\nlabels:\n- a\n- b\n---\n'
    projected = project_for_root(text, shared=True, skill_name="n")
    assert projected == '---\nname: n\nmetadata:\n  version: "2"\n  labels: "[\\"a\\", \\"b\\"]"\n  owner: "team"\ndescription: d\n---\n'
    assert _validate_text(projected, "n") == []


def test_projection_normalises_crlf_and_does_not_duplicate_frontmatter() -> None:
    crlf = _NEUTRAL.replace("\n", "\r\n")
    assert project_for_root(crlf, shared=False, skill_name="acme-deploy") == _NEUTRAL
    assert project_for_root(crlf, shared=True, skill_name="acme-deploy").count("---\n") == 2


def test_plain_markdown_gets_frontmatter_then_projection() -> None:
    assert ensure_skill_frontmatter("# T\n\nHello: world.\n", "x") == '---\nname: x\ndescription: "Hello: world."\n---\n# T\n\nHello: world.\n'
    assert project_for_root("# T\n\nHello.\n", shared=True, skill_name="x") == "---\nname: x\ndescription: Hello.\n---\n# T\n\nHello.\n"


def test_projection_refuses_unparseable_frontmatter() -> None:
    with pytest.raises(ValueError, match="not valid YAML"):
        project_for_root("---\nname: n\nextra: [unclosed\n---\n", shared=True, skill_name="n")
    with pytest.raises(ValueError, match="must be a mapping"):
        project_for_root("---\nname: n\nmetadata: text\nextra: 1\n---\n", shared=True, skill_name="n")


def test_project_skill_bytes_round_trips_utf8() -> None:
    assert project_skill_bytes(_NEUTRAL.encode(), shared=False, skill_name="acme-deploy") == _NEUTRAL.encode()


def test_render_frontmatter_block_style_only() -> None:
    assert render_frontmatter({"name": "n", "description": "a: b", "metadata": {"k": True}}) == '---\nname: n\ndescription: "a: b"\nmetadata:\n  k: "true"\n---'
    with pytest.raises(TypeError, match="Only 'metadata'"):
        render_frontmatter({"other": {"k": "v"}})


@pytest.mark.parametrize(
    ("value", "expected"),
    [(True, "true"), (False, "false"), (3, "3"), ("yes", '"yes"'), ('say "hi"\\', '"say \\"hi\\"\\\\"'), ("-x", '"-x"'), ("plain text", "plain text")],
)
def test_yaml_scalar(value: object, expected: str) -> None:
    assert yaml_scalar(value) == expected


def _validate_text(text: str, folder: str) -> list[str]:
    with tempfile.TemporaryDirectory() as directory:
        skill_dir = Path(directory) / folder
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(text, encoding="utf-8")
        return validate_skill_frontmatter(skill_dir)


def test_validator_accepts_projected_command_skill() -> None:
    text = render_frontmatter(command_skill_fields("spec-kitty-plan", "Plan")) + "\nbody\n"
    assert _validate_text(text, "spec-kitty-plan") == []


@pytest.mark.parametrize(
    ("text", "folder", "message"),
    [
        ("---\nname: a\ndescription: d\nuser-invocable: true\n---\n", "a", "Unexpected fields in frontmatter: user-invocable"),
        ("---\nname: spec-kitty.plan\ndescription: d\n---\n", "spec-kitty.plan", "invalid characters"),
        ("---\nname: Abc\ndescription: d\n---\n", "Abc", "must be lowercase"),
        ("---\nname: -a\ndescription: d\n---\n", "-a", "start or end with a hyphen"),
        ("---\nname: a--b\ndescription: d\n---\n", "a--b", "consecutive hyphens"),
        ("---\nname: a\ndescription: d\n---\n", "b", "must match skill name"),
        ("---\nname: " + "a" * 65 + "\ndescription: d\n---\n", "a" * 65, "exceeds 64 character limit (65 chars)"),
        ("---\nname: a\ndescription: " + "d" * 1025 + "\n---\n", "a", "exceeds 1024 character limit (1025 chars)"),
        ("---\nname: a\ndescription: d\ncompatibility: " + "c" * 501 + "\n---\n", "a", "exceeds 500 character limit"),
        ("---\nname: a\n---\n", "a", "Missing required field in frontmatter: description"),
        ("---\ndescription: d\n---\n", "a", "Missing required field in frontmatter: name"),
        ("---\nname: a\ndescription: d\nmetadata: {k: v}\n---\n", "a", "Flow-style YAML is not allowed"),
        ("---\nname: a\ndescription: d\nmetadata: text\n---\n", "a", "'metadata' must be a mapping"),
        ("---\nname: ''\ndescription: d\n---\n", "a", "'name' must be a non-empty string"),
        ("# no frontmatter\n", "a", "must start with a closed YAML frontmatter block"),
        ("---\n- a\n---\n", "a", "must be a YAML mapping"),
        ("---\nname: [a\n---\n", "a", "Invalid YAML in frontmatter"),
    ],
)
def test_validator_rules(text: str, folder: str, message: str) -> None:
    errors = _validate_text(text, folder)
    assert any(message in error for error in errors), errors


def test_validator_boundaries_accept_64_and_1024() -> None:
    name = "a" * 64
    assert _validate_text(f"---\nname: {name}\ndescription: {'d' * 1024}\n---\n", name) == []


def test_validator_missing_skill_md(tmp_path: Path) -> None:
    assert validate_skill_frontmatter(tmp_path) == ["Missing required file: SKILL.md"]


# WP07 review N1: a quoted scalar must parse back to exactly the source text.
_LINE_BREAK_TEXTS = ("two\nlines", "cr\rhere", "nel\x85here", "ls\u2028here", "ps\u2029here", "tab\there", "bell\x07", "del\x7f", 'mixed "q" \\ and\nbreak')


@pytest.mark.parametrize("text", _LINE_BREAK_TEXTS)
def test_yaml_scalar_round_trips_line_breaks_and_controls(text: str) -> None:
    emitted = yaml_scalar(text)
    assert emitted.startswith('"') and emitted.endswith('"')
    assert "\n" not in emitted and "\r" not in emitted
    assert not any(char in emitted for char in "\x85\u2028\u2029\x07\x7f")
    assert YAML(typ="safe").load(f"k: {emitted}\n") == {"k": text}


@pytest.mark.parametrize("text", _LINE_BREAK_TEXTS)
def test_render_frontmatter_round_trips_line_breaks_in_values_keys_and_metadata(text: str) -> None:
    block = render_frontmatter({"name": "n", "description": text, "metadata": {text: text}})
    assert _frontmatter(block + "\n") == {"name": "n", "description": text, "metadata": {text: text}}


def test_yaml_scalar_bare_path_unchanged_for_printable_text() -> None:
    """The bare-scalar path emits exactly the input for printable text (no byte change)."""
    assert yaml_scalar("Plan a mission") == "Plan a mission"
    assert yaml_scalar("café à la carte") == "café à la carte"


def test_validator_normalises_crlf_before_matching_the_fence(tmp_path: Path) -> None:
    """WP07 review N2: a CRLF SKILL.md validates like its LF twin (skills-ref accepts both)."""
    skill_dir = tmp_path / "abc"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_bytes(b"---\r\nname: abc\r\ndescription: d\r\n---\r\nbody\r\n")
    assert validate_skill_frontmatter(skill_dir) == []
    (skill_dir / "SKILL.md").write_bytes(b"---\rname: abc\rdescription: d\r---\rbody\r")
    assert validate_skill_frontmatter(skill_dir) == []


def test_validator_native_allowance_permits_claude_keys_only(tmp_path: Path) -> None:
    skill_dir = tmp_path / "a"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("---\nname: a\ndescription: d\nuser-invocable: true\nargument-hint: x\n---\n", encoding="utf-8")
    assert validate_skill_frontmatter(skill_dir, native=True) == []
    assert any("Unexpected fields" in error for error in validate_skill_frontmatter(skill_dir))
    (skill_dir / "SKILL.md").write_text("---\nname: a\ndescription: d\nother: x\n---\n", encoding="utf-8")
    assert any("Unexpected fields in frontmatter: other" in error for error in validate_skill_frontmatter(skill_dir, native=True))
