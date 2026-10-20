"""The language settlement decides; storing is a separate step (#6540, #6542).

``charter.activation.language_settlement`` sits above both the language authority and the
code reader, so the only import edge between those two is code reader -> authority.
Settling the languages never writes ``config.yaml``; ``store_language_settlement`` does.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from ruamel.yaml import YAML

import charter.activation.api as activation_api

pytestmark = [pytest.mark.fast]

_ACTIVATION = Path(activation_api.__file__).parent
_AUTHORITY = "charter.activation.language_authority"
_CODE_READER = "charter.activation.evidence.code_reader"
_SETTLEMENT = "charter.activation.language_settlement"


def _imported_modules(path: Path) -> list[tuple[str, bool]]:
    """Return ``(module, module_level)`` for every import in *path*; ``TYPE_CHECKING`` blocks are not module level."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[tuple[str, bool]] = []

    def walk(node: ast.AST, module_level: bool) -> None:
        for child in ast.iter_child_nodes(node):
            level = module_level
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)):
                level = False
            if isinstance(child, ast.If) and "TYPE_CHECKING" in ast.unparse(child.test):
                level = False
            if isinstance(child, ast.ImportFrom) and child.module:
                found.append((child.module, level))
                found.extend((f"{child.module}.{alias.name}", level) for alias in child.names)
            elif isinstance(child, ast.Import):
                found.extend((alias.name, level) for alias in child.names)
            walk(child, level)

    walk(tree, True)
    return found


def test_the_authority_never_imports_the_code_reader() -> None:
    modules = [module for module, _ in _imported_modules(_ACTIVATION / "language_authority.py")]
    assert not [module for module in modules if module == _CODE_READER or module.startswith(_CODE_READER + ".")]


def test_the_code_reader_imports_the_authority_and_not_the_settlement() -> None:
    modules = [module for module, _ in _imported_modules(_ACTIVATION / "evidence" / "code_reader.py")]
    assert _AUTHORITY in modules
    assert _SETTLEMENT not in modules


def test_the_settlement_imports_both_at_module_level() -> None:
    module_level = {module for module, level in _imported_modules(_ACTIVATION / "language_settlement.py") if level}
    assert _AUTHORITY in module_level
    assert _CODE_READER in module_level


def _python_repo(root: Path) -> None:
    (root / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")


def _config_path(root: Path) -> Path:
    return root / ".kittify" / "config.yaml"


def _set_config(root: Path, text: str) -> None:
    _config_path(root).parent.mkdir(parents=True, exist_ok=True)
    _config_path(root).write_text(text, encoding="utf-8")


def _has_languages_key(root: Path) -> bool:
    if not _config_path(root).exists():
        return False
    loaded = YAML(typ="safe").load(_config_path(root).read_text(encoding="utf-8"))
    return isinstance(loaded, dict) and "languages" in loaded


def test_settling_without_asking_writes_nothing(tmp_path: Path) -> None:
    _python_repo(tmp_path)

    settlement = activation_api.settle_project_languages(tmp_path, ask=None)

    assert not _has_languages_key(tmp_path)
    assert settlement.source == "detected"
    assert settlement.languages == ("python",)
    assert settlement.detected == ("python",)
    assert settlement.notice is not None and "DETECTED, not confirmed" in settlement.notice


def test_settling_an_interactive_change_writes_nothing(tmp_path: Path) -> None:
    _python_repo(tmp_path)
    _set_config(tmp_path, "languages: [go]\n")

    settlement = activation_api.settle_project_languages(tmp_path, ask=lambda _proposal: "python, go")

    assert settlement.source == "confirmed"
    assert settlement.languages == ("python", "go")
    assert YAML(typ="safe").load(_config_path(tmp_path).read_text(encoding="utf-8"))["languages"] == ["go"]


def test_storing_the_settlement_writes_the_list(tmp_path: Path) -> None:
    _python_repo(tmp_path)
    settlement = activation_api.settle_project_languages(tmp_path, ask=None)

    activation_api.store_language_settlement(tmp_path, settlement)
    activation_api.store_language_settlement(tmp_path, settlement)  # idempotent

    assert YAML(typ="safe").load(_config_path(tmp_path).read_text(encoding="utf-8"))["languages"] == ["python"]
    assert activation_api.configured_languages(tmp_path) == ("python",)


def test_a_detected_settlement_never_overwrites_a_key_set_after_it_was_decided(tmp_path: Path) -> None:
    _python_repo(tmp_path)
    settlement = activation_api.settle_project_languages(tmp_path, ask=None)
    assert settlement.source == "detected"
    _set_config(tmp_path, "languages: [go]\n")  # the operator set it during the interview

    assert activation_api.store_language_settlement(tmp_path, settlement) is False

    assert YAML(typ="safe").load(_config_path(tmp_path).read_text(encoding="utf-8"))["languages"] == ["go"]


def test_storing_a_confirmed_change_writes_it(tmp_path: Path) -> None:
    _python_repo(tmp_path)
    _set_config(tmp_path, "languages: [go]\n")
    settlement = activation_api.settle_project_languages(tmp_path, ask=lambda _proposal: "python")

    assert activation_api.store_language_settlement(tmp_path, settlement) is True

    assert activation_api.configured_languages(tmp_path) == ("python",)


@pytest.mark.parametrize(
    "text",
    ["languages: [go]\n", "languages: [elixir]\n", "languages: python\n", "languages: [1, {a: b}]\n", "languages: [unclosed\n"],
)
def test_a_set_key_is_never_overwritten_non_interactively(tmp_path: Path, text: str) -> None:
    _python_repo(tmp_path)
    _set_config(tmp_path, text)
    before = _config_path(tmp_path).read_bytes()

    settlement = activation_api.settle_project_languages(tmp_path, ask=None)
    activation_api.store_language_settlement(tmp_path, settlement)

    assert _config_path(tmp_path).read_bytes() == before


def test_a_blank_answer_stores_nothing(tmp_path: Path) -> None:
    _python_repo(tmp_path)
    settlement = activation_api.settle_project_languages(tmp_path, ask=lambda _proposal: "none")

    activation_api.store_language_settlement(tmp_path, settlement)

    assert settlement.source == "none"
    assert not _has_languages_key(tmp_path)
