"""Regression guard against language-specific tool bias in generic shipped artifacts."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from charter.offering.shared.scoping import normalize_languages

pytestmark = [pytest.mark.fast, pytest.mark.doctrine, pytest.mark.corpus]


REPO_ROOT = Path(__file__).resolve().parents[2]
DENYLIST = (
    r"\bpytest\b",
    r"\bjunit\b",
    r"\bjest\b",
    r"\bcargo\s+test\b",
    r"\bxctest\b",
    r"\bmypy\b",
    r"\bruff\b",
    r"\bgradle\b",
    r"\bmaven\b",
    r"\bphpunit\b",
    r"\brspec\b",
)
GENERIC_SURFACES = (
    Path("packs/built-in/agent_profiles"),
    Path("src/charter/offering/skills"),
    Path("packs/built-in/tactics"),
    Path("src/charter/offering/templates"),
    Path("packs/built-in/missions/software-dev/templates"),
    Path("src/specify_cli/templates"),
    Path("src/charter/defaults.yaml"),
)
ALLOWED_PATH_SNIPPETS = (
    "python-",
    "PYTHON_",
    "claudeignore-template",
)


def _iter_generic_artifacts() -> list[Path]:
    paths: list[Path] = []
    for surface in GENERIC_SURFACES:
        absolute = REPO_ROOT / surface
        if absolute.is_file():
            paths.append(absolute)
            continue
        if not absolute.is_dir():
            continue
        paths.extend(path for path in absolute.rglob("*") if path.is_file())
    return sorted(paths)


#: Sentinels that ``doctrine validate`` rejects and the runtime treats as unscoped.
_SENTINEL_SCOPES = frozenset({"any", "all"})


def _declares_real_language_scope(path: Path, content: str) -> bool:
    """Return True only for a parsed, non-empty, non-sentinel ``applies_to_languages``.

    A textual mention of the key (prose, an empty list, ``[any]``) is *not* a
    language-specific declaration and must not exempt an artifact from the
    language-bias check (FR-018).
    """
    if path.suffix not in {".yaml", ".yml"}:
        return False
    try:
        data = YAML(typ="safe").load(content)
    except YAMLError:
        return False
    if not isinstance(data, dict):
        return False
    raw = data.get("applies_to_languages")
    if not isinstance(raw, list):
        return False
    scope = set(normalize_languages(str(item) for item in raw))
    return bool(scope) and not scope <= _SENTINEL_SCOPES


def _is_allowlisted(path: Path, content: str) -> bool:
    as_posix = path.as_posix()
    if any(snippet in as_posix for snippet in ALLOWED_PATH_SNIPPETS):
        return True
    return _declares_real_language_scope(path, content)


def test_generic_shipped_artifacts_do_not_embed_language_specific_tool_bias() -> None:
    violations: list[str] = []

    for path in _iter_generic_artifacts():
        content = path.read_text(encoding="utf-8")
        if _is_allowlisted(path, content):
            continue

        for pattern in DENYLIST:
            if re.search(pattern, content, flags=re.IGNORECASE):
                violations.append(f"{path.relative_to(REPO_ROOT)} matches {pattern}")

    assert violations == []


@pytest.mark.parametrize(
    "scope_line",
    ["applies_to_languages: []", "applies_to_languages:", "applies_to_languages: [any]", "applies_to_languages: [all]"],
)
def test_empty_or_sentinel_scope_does_not_exempt_an_artifact(scope_line: str) -> None:
    content = f"id: x\n{scope_line}\nsteps:\n  - run pytest\n"
    assert not _is_allowlisted(Path("packs/built-in/tactics/x.tactic.yaml"), content)


def test_prose_mention_of_scope_key_does_not_exempt_an_artifact() -> None:
    content = "id: x\npurpose: >\n  mentions applies_to_languages: [python] in prose\n"
    assert not _is_allowlisted(Path("packs/built-in/tactics/x.tactic.yaml"), content)


def test_real_language_scope_still_exempts_an_artifact() -> None:
    content = "id: x\napplies_to_languages:\n  - python\nsteps:\n  - run pytest\n"
    assert _is_allowlisted(Path("packs/built-in/tactics/x.tactic.yaml"), content)
    inline = "id: x\napplies_to_languages: [java]\n"
    assert _is_allowlisted(Path("packs/built-in/tactics/x.tactic.yaml"), inline)
