"""CLI tests for ``spec-kitty doctrine org init`` and ``doctrine org validate``.

WP08 / T039 RED tests.  All four tests FAIL on the planning base because the
``org`` subapp does not exist in ``doctrine.py`` yet.

Owner: ``src/specify_cli/cli/commands/doctrine.py``
Mission: slice-f-multi-context-extensibility-01KRX5C8
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands.doctrine import app

runner = CliRunner()

pytestmark = [pytest.mark.unit, pytest.mark.fast]


# ---------------------------------------------------------------------------
# T039-a: doctrine org init scaffolds a minimal org pack skeleton
# ---------------------------------------------------------------------------


def test_doctrine_org_init_scaffolds_minimal_pack(tmp_path: Path) -> None:
    """``doctrine org init <path>`` creates the three required skeleton files.

    Expected layout::

        <path>/
          org-charter.yaml
          drg/
            fragment.yaml   # carries pydantic_model: + expect: frontmatter
          README.md
    """
    pack_dir = tmp_path / "my-org-pack"

    result = runner.invoke(app, ["org", "init", str(pack_dir)])

    assert result.exit_code == 0, result.output

    # org-charter.yaml must exist and parse as OrgCharterPolicy
    org_charter = pack_dir / "org-charter.yaml"
    assert org_charter.exists(), "org-charter.yaml was not created"

    from ruamel.yaml import YAML

    data = YAML(typ="safe").load(org_charter.read_text(encoding="utf-8"))
    assert data is not None
    from specify_cli.doctrine.org_charter import OrgCharterPolicy

    OrgCharterPolicy.model_validate(data)  # must not raise

    # drg/fragment.yaml must exist and parse as OrgDRGFragment
    fragment = pack_dir / "drg" / "fragment.yaml"
    assert fragment.exists(), "drg/fragment.yaml was not created"

    frag_text = fragment.read_text(encoding="utf-8")
    # Must carry pydantic_model: + expect: frontmatter (FR-140 round-trip)
    assert "# pydantic_model:" in frag_text, "fragment.yaml missing pydantic_model frontmatter"
    assert "# expect: valid" in frag_text, "fragment.yaml missing expect: valid frontmatter"

    # strip frontmatter comment lines before parsing
    payload_lines = [
        line for line in frag_text.splitlines()
        if not line.strip().startswith("#")
    ]
    payload_text = "\n".join(payload_lines)
    frag_data = YAML(typ="safe").load(payload_text)
    assert frag_data is not None
    from charter.drg import OrgDRGFragment

    OrgDRGFragment.model_validate(frag_data)  # must not raise

    # README.md must exist
    readme = pack_dir / "README.md"
    assert readme.exists(), "README.md was not created"


# ---------------------------------------------------------------------------
# T039-b: doctrine org init refuses to overwrite an existing pack
# ---------------------------------------------------------------------------


def test_doctrine_org_init_refuses_to_overwrite_existing(tmp_path: Path) -> None:
    """``doctrine org init`` exits non-zero when the target dir already exists
    (without ``--force``).
    """
    pack_dir = tmp_path / "existing-pack"
    pack_dir.mkdir()

    result = runner.invoke(app, ["org", "init", str(pack_dir)])

    assert result.exit_code != 0, "Expected non-zero exit when target dir exists"
    assert "already exists" in result.output.lower() or "exists" in result.output.lower()


# ---------------------------------------------------------------------------
# T039-c: doctrine org validate accepts a valid pack
# ---------------------------------------------------------------------------


def test_doctrine_org_validate_accepts_valid_pack(tmp_path: Path) -> None:
    """``doctrine org validate <path>`` exits 0 for a pack that passes schema checks."""
    pack_dir = tmp_path / "valid-pack"

    # Scaffold a pack using the init command so we always test against
    # canonically generated content.
    init_result = runner.invoke(app, ["org", "init", str(pack_dir)])
    assert init_result.exit_code == 0, f"init failed: {init_result.output}"

    result = runner.invoke(app, ["org", "validate", str(pack_dir)])

    assert result.exit_code == 0, result.output


# ---------------------------------------------------------------------------
# T039-d: doctrine org validate rejects a pack with invalid kind in fragment
# ---------------------------------------------------------------------------


def test_doctrine_org_validate_rejects_invalid_kind(tmp_path: Path) -> None:
    """``doctrine org validate`` exits non-zero when fragment.yaml has an
    unknown ``kind`` value (not in the 8-kind canonical set).
    """
    pack_dir = tmp_path / "bad-pack"
    pack_dir.mkdir()

    # Write a minimal org-charter.yaml
    (pack_dir / "org-charter.yaml").write_text(
        dedent(
            """\
            schema_version: "1"
            org_name: test-org
            """
        ),
        encoding="utf-8",
    )

    # Write a drg/ fragment with an unknown kind
    drg_dir = pack_dir / "drg"
    drg_dir.mkdir()
    (drg_dir / "fragment.yaml").write_text(
        dedent(
            f"""\
            pack_name: bad-pack
            source_kind: local_path
            source_ref: {pack_dir}
            layer_index: 1
            provenance_marker: org
            nodes:
              - id: bad-node
                kind: not_a_real_kind
                title: Bad node
            edges: []
            """
        ),
        encoding="utf-8",
    )

    result = runner.invoke(app, ["org", "validate", str(pack_dir)])

    assert result.exit_code != 0, "Expected non-zero exit for invalid kind"


# ---------------------------------------------------------------------------
# Template render path (doctrine-org-init-from-template WP03)
# ---------------------------------------------------------------------------


def _write_mini_template(root: Path) -> None:
    (root / "pack").mkdir()
    (root / "pack" / "org-charter.yaml").write_text(
        'org_name: "{{ORG_NAME}}"\npath: "{{LOCAL_PATH}}"\n',
        encoding="utf-8",
    )
    (root / "README.md").write_text("# {{ORG_NAME}}\n", encoding="utf-8")
    (root / "kitty-specs").mkdir()
    (root / "kitty-specs" / "skip.md").write_text("skip\n", encoding="utf-8")
    (root / ".templateignore").write_text("kitty-specs/\n", encoding="utf-8")


def test_doctrine_org_init_template_happy_path(tmp_path: Path) -> None:
    """``--template`` renders full tree with tokens substituted and ignores applied."""
    tpl = tmp_path / "tpl"
    tpl.mkdir()
    _write_mini_template(tpl)
    dest = tmp_path / "out"

    result = runner.invoke(
        app,
        [
            "org",
            "init",
            str(dest),
            "--template",
            str(tpl),
            "--org-name",
            "acme-corp",
        ],
    )

    assert result.exit_code == 0, result.output
    charter = (dest / "pack" / "org-charter.yaml").read_text(encoding="utf-8")
    assert "acme-corp" in charter
    assert "pack" in charter  # default LOCAL_PATH
    assert "{{ORG_NAME}}" not in charter
    assert not (dest / "kitty-specs").exists()
    assert "rendered" in result.output.lower() or "Org doctrine" in result.output


def test_doctrine_org_init_template_requires_org_name(tmp_path: Path) -> None:
    tpl = tmp_path / "tpl"
    tpl.mkdir()
    _write_mini_template(tpl)
    dest = tmp_path / "out"

    result = runner.invoke(
        app,
        ["org", "init", str(dest), "--template", str(tpl)],
    )

    assert result.exit_code != 0
    assert "org_name" in result.output.lower() or "ORG_NAME" in result.output


def test_doctrine_org_init_template_rejects_invalid_org_name(tmp_path: Path) -> None:
    tpl = tmp_path / "tpl"
    tpl.mkdir()
    _write_mini_template(tpl)
    dest = tmp_path / "out"

    result = runner.invoke(
        app,
        [
            "org",
            "init",
            str(dest),
            "--template",
            str(tpl),
            "--org-name",
            "Acme",
        ],
    )

    assert result.exit_code != 0
    assert "org_name.format" in result.output
    assert not dest.exists()


def test_doctrine_org_init_template_force_overwrite(tmp_path: Path) -> None:
    tpl = tmp_path / "tpl"
    tpl.mkdir()
    _write_mini_template(tpl)
    dest = tmp_path / "out"
    dest.mkdir()
    (dest / "stale.txt").write_text("old\n", encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "org",
            "init",
            str(dest),
            "--template",
            str(tpl),
            "--org-name",
            "acme-corp",
            "--force",
        ],
    )

    assert result.exit_code == 0, result.output
    assert (dest / "pack" / "org-charter.yaml").is_file()
    assert not (dest / "stale.txt").exists()


def test_doctrine_org_init_from_local_folder(tmp_path: Path) -> None:
    """Operator path: ``--template`` points at a local doctrine-template folder."""
    local_folder = tmp_path / "doctrine-template"
    local_folder.mkdir()
    _write_mini_template(local_folder)
    dest = tmp_path / "rendered-pack"

    result = runner.invoke(
        app,
        [
            "org",
            "init",
            str(dest),
            "--template",
            str(local_folder),
            "--org-name",
            "acme-corp",
            "--local-path",
            "pack",
        ],
    )

    assert result.exit_code == 0, result.output
    charter = (dest / "pack" / "org-charter.yaml").read_text(encoding="utf-8")
    assert "acme-corp" in charter
    assert "{{ORG_NAME}}" not in charter
    assert not (dest / ".templateignore").exists()
    assert not (dest / "kitty-specs").exists()


def test_doctrine_org_init_from_bitbucket_ssh_at_ref(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Git TEMPLATE: ssh://git@…@feat/… clones via GitSource with parsed ref."""
    from specify_cli.doctrine.sources.protocol import FetchResult

    calls: dict[str, object] = {}

    class FakeGitSource:
        def __init__(self, url: str, ref: str | None = None) -> None:
            calls["url"] = url
            calls["ref"] = ref

        def fetch(self, target_dir: Path) -> FetchResult:
            _write_mini_template(target_dir)
            return FetchResult(
                ok=True, artifacts_written=2, pack_version="deadbeef", errors=[]
            )

    monkeypatch.setattr(
        "specify_cli.doctrine.template_render.resolve.GitSource",
        FakeGitSource,
    )

    template = (
        "ssh://git@git.example.com:7999/org/doctrine-template.git"
        "@feat/make-embeddable-template"
    )
    dest = tmp_path / "from-git"

    result = runner.invoke(
        app,
        [
            "org",
            "init",
            str(dest),
            "--template",
            template,
            "--org-name",
            "acme-corp",
        ],
    )

    assert result.exit_code == 0, result.output
    assert calls["url"] == (
        "ssh://git@git.example.com:7999/org/doctrine-template.git"
    )
    assert calls["ref"] == "feat/make-embeddable-template"
    assert (dest / "pack" / "org-charter.yaml").is_file()
    assert "acme-corp" in (dest / "pack" / "org-charter.yaml").read_text(
        encoding="utf-8"
    )
    assert not (dest / ".git").exists()
    assert not (dest / ".templateignore").exists()
