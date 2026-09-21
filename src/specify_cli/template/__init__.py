"""Template management for spec-kitty."""

from .manager import (
    back_up_operator_subtrees,
    copy_package_tree,
    copy_specify_base_from_local,
    copy_specify_base_from_package,
    get_local_repo_root,
)
from .renderer import (
    DEFAULT_PATH_PATTERNS,
    parse_frontmatter,
    render_template,
    rewrite_paths,
)
from .asset_generator import (
    generate_agent_assets,
    prepare_command_templates,
    render_command_template,
)

__all__ = [
    "back_up_operator_subtrees",
    "copy_package_tree",
    "copy_specify_base_from_local",
    "copy_specify_base_from_package",
    "DEFAULT_PATH_PATTERNS",
    "generate_agent_assets",
    "get_local_repo_root",
    "parse_frontmatter",
    "prepare_command_templates",
    "render_command_template",
    "render_template",
    "rewrite_paths",
]
