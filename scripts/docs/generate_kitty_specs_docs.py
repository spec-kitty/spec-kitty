"""Generate dashboard-style DocFX pages from kitty-specs."""

from __future__ import annotations

import html
import json
import re
import shutil
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "kitty-specs"
GLOSSARY_SEED = ROOT / ".kittify" / "glossaries" / "spec_kitty_core.yaml"
# The glossary page assets used to live in the bundled dashboard; they moved
# here, as docs-site-only assets, when the dashboard was deleted (#5530).
GLOSSARY_PAGE_DIR = ROOT / "scripts" / "docs" / "glossary_page"
GLOSSARY_TEMPLATE = GLOSSARY_PAGE_DIR / "glossary.html"
GLOSSARY_CSS = GLOSSARY_PAGE_DIR / "glossary.css"
GLOSSARY_JS = GLOSSARY_PAGE_DIR / "glossary.js"
DEST = ROOT / "docs" / "kitty-specs"

LANES = ["planned", "doing", "for_review", "approved", "done"]
LANE_LABELS = {
    "planned": "📋 Planned",
    "doing": "🚀 Doing",
    "for_review": "👀 For Review",
    "approved": "👍 Approved",
    "done": "✅ Done",
}
ARTIFACTS = [
    ("overview", "Overview", "📊", None),
    ("spec", "Specification", "📄", "spec.md"),
    ("plan", "Implementation Plan", "🏗️", "plan.md"),
    ("tasks", "Task List", "📋", "tasks.md"),
    ("kanban", "Kanban Board", "🎯", None),
    ("research", "Research", "🔬", "research.md"),
    ("contracts", "Contracts", "📜", "contracts"),
    ("checklists", "Checklists", "✅", "checklists"),
    ("quickstart", "Quickstart Guide", "🚀", "quickstart.md"),
    ("data-model", "Data Model", "💾", "data-model.md"),
]


@dataclass(frozen=True)
class Mission:
    slug: str
    name: str
    meta: dict[str, Any]
    status: dict[str, Any]
    path: Path
    task_titles: dict[str, str]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def mission_name(path: Path, meta: dict[str, Any]) -> str:
    return (
        meta.get("friendly_name")
        or meta.get("name")
        or meta.get("mission_slug")
        or meta.get("slug")
        or path.name
    )


def sort_key(mission: Mission) -> tuple[int, str]:
    number = mission.meta.get("mission_number")
    if isinstance(number, (int, str)):
        try:
            return (-int(number), mission.name.lower())
        except ValueError:
            pass
    created = str(mission.meta.get("created_at") or "")
    return (0, f"{created} {mission.name}".lower())


def parse_task_titles(tasks_md: str) -> dict[str, str]:
    titles: dict[str, str] = {}
    for line in tasks_md.splitlines():
        match = re.match(r"^#{2,4}\s+(?:Work Package\s+)?(WP\d+)\s*:?\s*(.+?)\s*$", line)
        if match:
            titles[match.group(1)] = re.sub(r"\s+", " ", match.group(2)).strip()
    return titles


def _parse_frontmatter_and_body(markdown: str) -> tuple[dict[str, Any], str]:
    """Split a WP prompt's leading ``---`` frontmatter from its body.

    Local body-splitting variant that returns ``(frontmatter, body)`` — distinct
    from the canonical :func:`scripts.docs._inventory.parse_frontmatter`, which
    returns only the parsed mapping. Kept private to this generator so the shared
    name no longer collides across two different signatures.
    """
    lines = markdown.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, markdown
    end_index = next((index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"), None)
    if end_index is None:
        return {}, markdown

    frontmatter: dict[str, Any] = {}
    current_key = ""
    for raw in lines[1:end_index]:
        if raw.startswith("- ") and current_key:
            value = raw[2:].strip()
            frontmatter.setdefault(current_key, []).append(unquote_yaml_scalar(value))
            continue
        if ":" not in raw or raw.startswith((" ", "\t")):
            continue
        key, value = raw.split(":", 1)
        current_key = key.strip()
        value = value.strip()
        if value == "":
            frontmatter[current_key] = []
        elif value == "[]":
            frontmatter[current_key] = []
            current_key = ""
        else:
            frontmatter[current_key] = unquote_yaml_scalar(value)
            current_key = ""

    body = "\n".join(lines[end_index + 1 :]).lstrip()
    return frontmatter, body


def unquote_yaml_scalar(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def prompt_file_for_wp(mission: Mission, wp_id: str) -> Path | None:
    tasks_dir = mission.path / "tasks"
    if not tasks_dir.exists():
        return None
    matches = sorted(tasks_dir.glob(f"{wp_id}*.md"))
    return matches[0] if matches else None


def prompt_title(prompt_file: Path | None, markdown: str, wp_id: str, mission: Mission) -> str:
    match = re.search(r"^#\s+Work Package Prompt:\s+(.+?)\s*$", markdown, flags=re.MULTILINE)
    if match:
        return re.sub(r"\s+", " ", match.group(1)).strip()
    if prompt_file is not None:
        return prompt_file.stem
    return mission.task_titles.get(wp_id, "Work package")


def json_script(value: object) -> str:
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")


def missions() -> list[Mission]:
    result: list[Mission] = []
    for path in SOURCE.iterdir():
        if not path.is_dir():
            continue
        meta = read_json(path / "meta.json")
        status = read_json(path / "status.json")
        if not meta and not status and not (path / "spec.md").exists():
            continue
        result.append(
            Mission(
                slug=path.name,
                name=mission_name(path, meta),
                meta=meta,
                status=status,
                path=path,
                task_titles=parse_task_titles(read_text(path / "tasks.md")),
            )
        )
    return sorted(result, key=sort_key)


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def inline_md(text: str) -> str:
    value = esc(text)
    value = re.sub(r"`([^`]+)`", r"<code>\1</code>", value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", value)
    value = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", value)
    value = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        r'<span class="sk-source-link" title="\2">\1</span>',
        value,
    )
    return value


def slugify(value: str, fallback: str = "section") -> str:
    slug = re.sub(r"<[^>]+>", "", value).lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug or fallback


def table_to_html(rows: list[str]) -> str:
    parsed: list[list[str]] = []
    for row in rows:
        cells = [cell.strip() for cell in row.strip().strip("|").split("|")]
        parsed.append(cells)
    if len(parsed) < 2:
        return "\n".join(f"<p>{inline_md(row)}</p>" for row in rows)
    header = parsed[0]
    body_rows = parsed[2:] if re.fullmatch(r"\s*\|?[\s:|\\-]+\|?\s*", rows[1]) else parsed[1:]
    head_html = "".join(f"<th>{inline_md(cell)}</th>" for cell in header)
    body_html = []
    for body_row in body_rows:
        cells = body_row + [""] * max(0, len(header) - len(body_row))
        body_html.append("<tr>" + "".join(f"<td>{inline_md(cell)}</td>" for cell in cells[: len(header)]) + "</tr>")
    return f"<table><thead><tr>{head_html}</tr></thead><tbody>{''.join(body_html)}</tbody></table>"


def markdown_to_html(markdown: str) -> str:  # noqa: C901
    lines = markdown.splitlines()
    blocks: list[str] = []
    paragraph: list[str] = []
    list_items: list[str] = []
    table_rows: list[str] = []
    in_code = False
    code_lang = ""
    code_lines: list[str] = []

    def flush_paragraph() -> None:
        nonlocal paragraph
        if paragraph:
            blocks.append(f"<p>{inline_md(' '.join(paragraph).strip())}</p>")
            paragraph = []

    def flush_list() -> None:
        nonlocal list_items
        if list_items:
            blocks.append("<ul>" + "".join(f"<li>{item}</li>" for item in list_items) + "</ul>")
            list_items = []

    def flush_table() -> None:
        nonlocal table_rows
        if table_rows:
            blocks.append(table_to_html(table_rows))
            table_rows = []

    for raw in lines:
        line = raw.rstrip()
        if line.startswith("```"):
            if in_code:
                blocks.append(
                    f'<pre><code class="language-{esc(code_lang)}">{esc(chr(10).join(code_lines))}</code></pre>'
                )
                in_code = False
                code_lang = ""
                code_lines = []
            else:
                flush_paragraph()
                flush_list()
                in_code = True
                code_lang = line[3:].strip()
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not line.strip():
            flush_paragraph()
            flush_list()
            flush_table()
            continue
        if line.lstrip().startswith("|") and line.rstrip().endswith("|"):
            flush_paragraph()
            flush_list()
            table_rows.append(line)
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            flush_paragraph()
            flush_list()
            flush_table()
            level = min(len(heading.group(1)) + 1, 6)
            text = heading.group(2)
            blocks.append(f'<h{level} id="{esc(slugify(text))}">{inline_md(text)}</h{level}>')
            continue
        if re.match(r"^-{3,}$", line):
            flush_paragraph()
            flush_list()
            flush_table()
            blocks.append("<hr>")
            continue
        bullet = re.match(r"^\s*[-*]\s+(.+)$", line)
        task = re.match(r"^\s*[-*]\s+\[([ xX])\]\s+(.+)$", line)
        if task:
            flush_paragraph()
            checked = task.group(1).lower() == "x"
            label = "✅" if checked else "□"
            list_items.append(f"{label} {inline_md(task.group(2))}")
            continue
        if bullet:
            flush_paragraph()
            list_items.append(inline_md(bullet.group(1)))
            continue
        paragraph.append(line.strip())
    flush_paragraph()
    flush_list()
    flush_table()
    return "\n".join(blocks)


def artifact_exists(mission: Mission, key: str, source: str | None) -> bool:
    if key == "overview":
        return True
    if key == "kanban":
        return bool(mission.status.get("work_packages"))
    if not source:
        return False
    return (mission.path / source).exists()


def artifact_href(_mission: Mission, key: str) -> str:
    if key == "overview":
        return "index.html"
    return f"{key}.html"


def dashboard_header(
    mission_list: list[Mission],
    active: Mission | None,
    section_name: str = "All mission runs",
) -> str:
    options = ['<option value="" selected>Select mission run...</option>'] if active is None else []
    for mission in mission_list:
        selected = " selected" if active and mission.slug == active.slug else ""
        option_href = f"../{mission.slug}/index.html" if active else f"{mission.slug}/index.html"
        options.append(
            f'<option value="{esc(option_href)}"{selected}>{esc(mission.name)}</option>'
        )
    select = "\n".join(options)
    name = active.name if active else section_name
    return f"""
<div class="sk-dashboard">
  <div class="header">
    <div class="header-left">
      <div class="header-logo-wrapper">
        <img src="/assets/images/logo_small.webp" alt="Spec Kitty logo" class="header-logo">
      </div>
      <div class="header-info">
        <h1>Spec Kitty</h1>
        <pre class="tree-view">└─ kitty-specs
   └─ {esc(name)}</pre>
      </div>
      <div class="feature-selector">
        <label for="feature-select">Mission Run:</label>
        <select id="feature-select" onchange="if (this.value) location.href=this.value">
          {select}
        </select>
      </div>
    </div>
    <div class="header-right">
      <a class="docs-site-link" href="/">📚 Docs ↗</a>
    </div>
  </div>
"""


def sidebar(mission: Mission, active_key: str) -> str:
    items = []
    for key, label, icon, source in ARTIFACTS:
        exists = artifact_exists(mission, key, source)
        active = " active" if key == active_key else ""
        disabled = "" if exists else " disabled"
        if exists:
            items.append(
                f'<a class="sidebar-item{active}" href="{esc(artifact_href(mission, key))}" title="{esc(label)}">'
                f'{icon} <span class="sidebar-label">{esc(label)}</span></a>'
            )
        else:
            items.append(
                f'<span class="sidebar-item{disabled}" title="{esc(label)}">'
                f'{icon} <span class="sidebar-label">{esc(label)}</span></span>'
            )
    return "\n".join(items)


def stats(mission: Mission) -> dict[str, int | float]:
    summary = mission.status.get("summary") or {}
    wps = mission.status.get("work_packages") or {}
    lane_counts = dict.fromkeys(LANES, 0)
    for wp in wps.values():
        lane = str(wp.get("lane") or "planned")
        if lane == "in_review":
            lane = "for_review"
        if lane in lane_counts:
            lane_counts[lane] += 1
    for key, value in summary.items():
        normalized = "for_review" if key == "in_review" else key
        if normalized in lane_counts and not wps:
            with suppress(TypeError, ValueError):
                lane_counts[normalized] += int(value)
    total = sum(lane_counts.values())
    done = lane_counts["done"]
    pct = round(done / total * 100) if total else 0
    return {"total": total, **lane_counts, "weighted_percentage": pct}


def active_agents(mission: Mission) -> list[str]:
    agents: set[str] = set()
    for wp_id in (mission.status.get("work_packages") or {}):
        prompt_file = prompt_file_for_wp(mission, wp_id)
        if prompt_file is None:
            continue
        frontmatter, _ = _parse_frontmatter_and_body(read_text(prompt_file))
        agent = str(frontmatter.get("agent") or "")
        if agent:
            agents.add(agent)
    return sorted(agents)


def status_cards(mission: Mission, compact: bool = False) -> str:
    s = stats(mission)
    label = "Total Work Packages" if compact else "Total Tasks"
    agents = active_agents(mission) if compact else []
    agents_card = (
        f"""  <div class="status-card agents"><div class="status-label">Active Agents</div>
    <div class="status-value">{len(agents)}</div>
    <div class="status-detail">{esc(", ".join(agents) if agents else "none")}</div></div>
"""
        if compact
        else ""
    )
    return f"""
<div class="status-summary">
  <div class="status-card total"><div class="status-label">{label}</div><div class="status-value">{s['total']}</div>
    <div class="status-detail">{s['planned']} planned</div></div>
  <div class="status-card progress"><div class="status-label">In Progress</div><div class="status-value">{s['doing']}</div></div>
  <div class="status-card review"><div class="status-label">Review</div><div class="status-value">{s['for_review']}</div></div>
  <div class="status-card approved"><div class="status-label">Approved</div><div class="status-value">{s['approved']}</div></div>
  <div class="status-card completed"><div class="status-label">Completed</div><div class="status-value">{s['done']}</div>
    <div class="status-detail">{s['weighted_percentage']}% done</div><div class="progress-bar">
      <div class="progress-fill" style="width: {s['weighted_percentage']}%"></div>
    </div></div>
{agents_card}
</div>
"""


def overview(mission: Mission) -> str:
    purpose_tldr = mission.meta.get("purpose_tldr") or "View and track all artifacts for this mission run."
    purpose_context = mission.meta.get("purpose_context") or mission.meta.get("source_description") or ""
    artifact_rows = []
    for key, label, icon, source in ARTIFACTS[1:]:
        exists = artifact_exists(mission, key, source)
        cls = "available" if exists else "missing"
        text = "✅ Available" if exists else "❌ Not created"
        artifact_rows.append(
            f'<a class="artifact-row {cls}" href="{esc(artifact_href(mission, key))}">{icon} {esc(label)}: {text}</a>'
            if exists
            else f'<div class="artifact-row {cls}">{icon} {esc(label)}: {text}</div>'
        )
    return f"""
<h2>Mission Run Overview</h2>
<div class="overview-header">
  <h3>Mission Run: {esc(mission.name)}</h3>
  <p class="overview-tldr">{esc(purpose_tldr)}</p>
  <p class="overview-context">{esc(purpose_context)}</p>
</div>
{status_cards(mission)}
<h3 class="artifacts-heading">Available Artifacts</h3>
<div class="artifacts-grid">
  {''.join(artifact_rows)}
</div>
"""


def lanes(mission: Mission) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {lane: [] for lane in LANES}
    for wp_id, state in sorted((mission.status.get("work_packages") or {}).items()):
        raw_lane = str(state.get("lane") or "planned")
        column_lane = "for_review" if raw_lane == "in_review" else raw_lane
        if column_lane not in result:
            column_lane = "planned"
        prompt_file = prompt_file_for_wp(mission, wp_id)
        prompt_markdown = read_text(prompt_file) if prompt_file else ""
        frontmatter, prompt_body = _parse_frontmatter_and_body(prompt_markdown)
        subtasks = frontmatter.get("subtasks")
        if not isinstance(subtasks, list):
            subtasks = []
        result[column_lane].append(
            {
                "id": wp_id,
                "title": prompt_title(prompt_file, prompt_markdown, wp_id, mission),
                "lane": raw_lane,
                "subtasks": subtasks,
                "agent": str(frontmatter.get("agent") or ""),
                "model": str(frontmatter.get("model") or ""),
                "agent_profile": str(frontmatter.get("agent_profile") or ""),
                "role": str(frontmatter.get("role") or ""),
                "assignee": str(frontmatter.get("assignee") or ""),
                "phase": str(frontmatter.get("phase") or ""),
                "prompt_markdown": prompt_body,
                "prompt_html": markdown_to_html(prompt_body),
                "prompt_path": prompt_file.relative_to(ROOT).as_posix() if prompt_file else "",
            }
        )
    return result


def kanban(mission: Mission) -> str:
    columns = []
    all_lanes = lanes(mission)
    tasks_by_id = {task["id"]: task for tasks in all_lanes.values() for task in tasks}
    for lane, tasks in all_lanes.items():
        cards = []
        for task in tasks:
            badges = []
            if task["agent"]:
                badges.append(f'<span class="badge agent">{esc(task["agent"])}</span>')
            if task["agent_profile"]:
                badges.append(f'<span class="badge profile">{esc(task["agent_profile"])}</span>')
            if task["role"]:
                badges.append(f'<span class="badge role">{esc(task["role"])}</span>')
            if task["subtasks"]:
                count = len(task["subtasks"])
                badges.append(f'<span class="badge subtasks">{count} subtask{"s" if count != 1 else ""}</span>')
            card_class = "card in-review" if task["lane"] == "in_review" else "card"
            cards.append(
                f'<div class="{card_class}" role="button" tabindex="0" data-task-id="{esc(task["id"])}">'
                f'<div class="card-id">{esc(task["id"])}</div>'
                f'<div class="card-title">{esc(task["title"])}</div>'
                f'<div class="card-meta">{"".join(badges)}</div></div>'
            )
        body = "".join(cards) if cards else '<div class="empty-state">No tasks</div>'
        columns.append(
            f'<div class="lane {lane}"><div class="lane-header"><span>{LANE_LABELS[lane]}</span>'
            f'<span class="count">{len(tasks)}</span></div><div>{body}</div></div>'
        )
    return f"""
<h2>Kanban Board</h2>
<div id="kanban-status">{status_cards(mission, compact=True)}</div>
<div class="kanban-board">{''.join(columns)}</div>
<div id="prompt-modal" class="modal hidden" aria-hidden="true">
  <div class="modal-overlay"></div>
  <div class="modal-content" role="dialog" aria-modal="true" aria-labelledby="modal-title">
    <div class="modal-header">
      <div>
        <div class="modal-title" id="modal-title">Work Package Prompt</div>
        <div class="modal-subtitle" id="modal-subtitle"></div>
      </div>
      <button type="button" class="modal-close" id="modal-close-btn" aria-label="Close prompt viewer">✕</button>
    </div>
    <div class="modal-body" id="modal-body">
      <div class="modal-meta" id="modal-prompt-meta"></div>
      <div id="modal-prompt-content" class="markdown-content"></div>
    </div>
  </div>
</div>
<script
  src="https://cdn.jsdelivr.net/npm/marked@11.1.1/marked.min.js"
  integrity="sha384-zbcZAIxlvJtNE3Dp5nxLXdXtXyxwOdnILY1TDPVmKFhl4r4nSUG1r8bcFXGVa4Te"
  crossorigin="anonymous"
></script>
<script>
const KANBAN_TASKS = {json_script(tasks_by_id)};

function escapeHtml(value) {{
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}}

function formatLaneName(lane) {{
    if (!lane) return '';
    return lane.split('_').map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(' ');
}}

function showPromptModal(task) {{
    const modal = document.getElementById('prompt-modal');
    if (!modal) return;

    const titleEl = document.getElementById('modal-title');
    const subtitleEl = document.getElementById('modal-subtitle');
    const metaEl = document.getElementById('modal-prompt-meta');
    const contentEl = document.getElementById('modal-prompt-content');
    const modalBody = document.getElementById('modal-body');

    if (titleEl) {{
        titleEl.textContent = task.title || 'Work Package Prompt';
    }}
    if (subtitleEl) {{
        if (task.id) {{
            subtitleEl.textContent = task.id;
            subtitleEl.style.display = 'block';
        }} else {{
            subtitleEl.textContent = '';
            subtitleEl.style.display = 'none';
        }}
    }}

    if (metaEl) {{
        const metaItems = [];
        if (task.lane) metaItems.push(`<span>Lane: ${{escapeHtml(formatLaneName(task.lane))}}</span>`);
        if (task.subtasks?.length) {{
            metaItems.push(`<span>${{task.subtasks.length}} subtask${{task.subtasks.length !== 1 ? 's' : ''}}</span>`);
        }}
        if (task.phase) metaItems.push(`<span>Phase: ${{escapeHtml(task.phase)}}</span>`);
        if (task.prompt_path) metaItems.push(`<span>Source: ${{escapeHtml(task.prompt_path)}}</span>`);

        const identityBadges = [];
        if (task.agent) identityBadges.push(`<span class="badge agent">${{escapeHtml(task.agent)}}</span>`);
        if (task.agent_profile) identityBadges.push(`<span class="badge profile">${{escapeHtml(task.agent_profile)}}</span>`);
        if (task.role) identityBadges.push(`<span class="badge role">${{escapeHtml(task.role)}}</span>`);
        if (task.model) identityBadges.push(`<span class="badge model">${{escapeHtml(task.model)}}</span>`);

        if (identityBadges.length > 0) {{
            metaItems.push(`<span class="agent-identity-section"><span class="agent-identity-label">Agent:</span> ${{identityBadges.join(' ')}}</span>`);
        }}

        if (metaItems.length > 0) {{
            metaEl.innerHTML = metaItems.join('');
            metaEl.style.display = 'flex';
        }} else {{
            metaEl.innerHTML = '';
            metaEl.style.display = 'none';
        }}
    }}

    if (contentEl) {{
        if (task.prompt_markdown && window.marked) {{
            contentEl.innerHTML = marked.parse(task.prompt_markdown);
        }} else {{
            contentEl.innerHTML = task.prompt_html || '<div class="empty-state">Prompt content unavailable.</div>';
        }}
    }}

    if (modalBody) {{
        modalBody.scrollTop = 0;
    }}

    modal.classList.remove('hidden');
    modal.classList.add('show');
    modal.setAttribute('aria-hidden', 'false');
    document.body.classList.add('modal-open');
}}

function hidePromptModal() {{
    const modal = document.getElementById('prompt-modal');
    if (!modal) return;

    modal.classList.remove('show');
    modal.classList.add('hidden');
    modal.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('modal-open');
}}

document.querySelectorAll('[data-task-id]').forEach((card) => {{
    const task = KANBAN_TASKS[card.dataset.taskId];
    if (!task) return;
    card.addEventListener('click', () => showPromptModal(task));
    card.addEventListener('keydown', (event) => {{
        if (event.key === 'Enter' || event.key === ' ') {{
            event.preventDefault();
            showPromptModal(task);
        }}
    }});
}});

const modalOverlay = document.querySelector('#prompt-modal .modal-overlay');
if (modalOverlay) {{
    modalOverlay.addEventListener('click', hidePromptModal);
}}
const modalCloseButton = document.getElementById('modal-close-btn');
if (modalCloseButton) {{
    modalCloseButton.addEventListener('click', hidePromptModal);
}}
document.addEventListener('keydown', (event) => {{
    if (event.key === 'Escape') {{
        const modal = document.getElementById('prompt-modal');
        if (modal?.classList.contains('show')) {{
            hidePromptModal();
        }}
    }}
}});
</script>
"""


def collection_html(mission: Mission, folder: str) -> str:
    base = mission.path / folder
    if not base.exists():
        return '<div class="empty-state">No files</div>'
    parts = []
    for file_path in sorted(base.rglob("*")):
        if not file_path.is_file():
            continue
        rel = file_path.relative_to(base).as_posix()
        parts.append(f"<h3>{esc(rel)}</h3>")
        parts.append(markdown_to_html(read_text(file_path)))
    return "\n".join(parts) if parts else '<div class="empty-state">No files</div>'


def artifact_body(mission: Mission, key: str, source: str | None) -> str:
    if key == "overview":
        return overview(mission)
    if key == "kanban":
        return kanban(mission)
    if source in {"contracts", "checklists"}:
        return f"<h2>{esc(source.title())}</h2>\n{collection_html(mission, source)}"
    text = read_text(mission.path / source) if source else ""
    if not text:
        return '<div class="empty-state">Artifact not created</div>'
    return markdown_to_html(text)


def html_document(title: str, description: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{esc(title)} | Spec Kitty Documentation</title>
  <meta name="description" content="{esc(description)}">
  <link rel="icon" href="/assets/images/favicon.png">
  <link rel="stylesheet" href="/assets/css/custom.css">
</head>
<body class="tex2jax_ignore">
{body}
</body>
</html>
"""


def page(mission_list: list[Mission], mission: Mission, key: str, label: str, source: str | None) -> str:
    desc = mission.meta.get("purpose_tldr") or mission.meta.get("source_description") or f"{label} for {mission.name}."
    body = artifact_body(mission, key, source)
    dashboard = (
        dashboard_header(mission_list, mission)
        + f"""
  <div class="container">
    <div class="sidebar">
      {sidebar(mission, key)}
    </div>
    <div class="main-content">
      <div class="content-card markdown-content">
        {body}
      </div>
    </div>
  </div>
</div>
"""
    )
    return html_document(f"{label} | {mission.name}", str(desc).replace("\n", " ")[:260], dashboard)


def index_page(mission_list: list[Mission]) -> str:
    cards = []
    for mission in mission_list:
        s = stats(mission)
        desc = mission.meta.get("purpose_tldr") or mission.meta.get("source_description") or ""
        cards.append(
            f'<a class="mission-card" href="{esc(mission.slug)}/index.html">'
            f'<span class="mission-number">{esc(mission.meta.get("mission_number") or "mission")}</span>'
            f'<strong>{esc(mission.name)}</strong>'
            f'<span>{esc(str(desc)[:220])}</span>'
            f'<em>{s["total"]} work packages · {s["weighted_percentage"]}% done</em>'
            f'</a>'
        )
    dashboard = (
        dashboard_header(mission_list, None)
        + f"""
  <div class="container">
    <div class="sidebar">
      <a class="sidebar-item active" href="./">📊 <span class="sidebar-label">All Mission Runs</span></a>
      <a class="sidebar-item" href="glossary.html">📖 <span class="sidebar-label">Glossary</span></a>
    </div>
    <div class="main-content">
      <div class="content-card">
        <h2>Mission Runs</h2>
        <p class="overview-context">Static mirror of the local Spec Kitty dashboard. Every mission and artifact has
          a stable URL for sharing, indexing, and AI answer engines.</p>
        <div class="mission-grid">{''.join(cards)}</div>
      </div>
    </div>
  </div>
</div>
"""
    )
    return html_document(
        "Mission Runs",
        "Static Spec Kitty mission dashboard generated from kitty-specs with permanent links for every mission artifact.",
        dashboard,
    )


def yaml_scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def parse_glossary_seed(path: Path) -> list[dict[str, str | float]]:
    terms: list[dict[str, str | float]] = []
    current: dict[str, str | float] | None = None
    lines = path.read_text(encoding="utf-8").splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        stripped = line.strip()
        if line.startswith("  - "):
            if current:
                terms.append(current)
            current = {}
            key, _, value = stripped[2:].partition(":")
            current[key.strip()] = yaml_scalar(value)
            index += 1
            continue
        if current is not None and line.startswith("    ") and ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()
            if key == "definition" and value in {">", "|"}:
                block_lines: list[str] = []
                index += 1
                while index < len(lines) and (lines[index].startswith("      ") or not lines[index].strip()):
                    block_lines.append(lines[index][6:] if lines[index].startswith("      ") else "")
                    index += 1
                current[key] = "\n".join(block_lines).strip() if value == "|" else " ".join(part.strip() for part in block_lines).strip()
                continue
            if key == "confidence":
                with suppress(ValueError):
                    current[key] = float(value)
            elif key in {"surface", "definition", "status"}:
                current[key] = yaml_scalar(value)
        index += 1
    if current:
        terms.append(current)
    return [
        {
            "surface": str(term.get("surface") or ""),
            "definition": str(term.get("definition") or ""),
            "status": str(term.get("status") or "draft"),
            "confidence": float(term.get("confidence") or 0.0),
        }
        for term in terms
        if term.get("surface")
    ]


def assign_anchor_ids(terms: list[dict[str, str | float]]) -> list[dict[str, str | float]]:
    """Attach a stable, unique ``anchor_id`` to each glossary term.

    Per ``contracts/glossary-anchor-contract.md``: ``anchor_id`` is a lowercase,
    ASCII-only, hyphen-separated slug of the term's ``surface`` field. Two terms
    that slugify to the same base value collide; the collision is broken by
    appending a numeric suffix (``-2``, ``-3``, ...) in seed-file order — the
    order ``terms`` is already in, since :func:`parse_glossary_seed` yields
    entries in the order they appear in the YAML seed. This is deliberately the
    single source of anchor-id truth: ``scripts/docs/glossary_linker.py``
    imports this function so both the rendered glossary page and the term
    linker agree on every ``anchor_id`` without re-deriving the algorithm.
    """
    seen: dict[str, int] = {}
    result: list[dict[str, str | float]] = []
    for term in terms:
        base = slugify(str(term.get("surface") or ""), fallback="term")
        occurrence = seen.get(base, 0)
        anchor_id = base if occurrence == 0 else f"{base}-{occurrence + 1}"
        seen[base] = occurrence + 1
        result.append({**term, "anchor_id": anchor_id})
    return result


def glossary_page(_mission_list: list[Mission]) -> str:
    terms = assign_anchor_ids(parse_glossary_seed(GLOSSARY_SEED))
    template = GLOSSARY_TEMPLATE.read_text(encoding="utf-8")
    # The retired dashboard's CSP (#71) forced the template's styling and behaviour out to
    # same-origin glossary.css/glossary.js. The static docs site has no server to serve
    # those from, so this generator inlines both back into the page it writes.
    css = GLOSSARY_CSS.read_text(encoding="utf-8")
    script = GLOSSARY_JS.read_text(encoding="utf-8")
    static_loader = f"""
async function loadTerms() {{
  TERMS = {json.dumps(terms, ensure_ascii=False)};
  VALIDATION_ERRORS = [];
  renderValidationBanner();
  updateStats();
  buildAlphaNav();
  render();
}}
"""
    script = re.sub(
        r"async function loadTerms\(\) \{.*?\n\}\n\nfunction renderValidationBanner\(",
        lambda _match: static_loader + "\nfunction renderValidationBanner(",
        script,
        count=1,
        flags=re.DOTALL,
    )
    # FR-012: give every rendered term card a stable id="term-{anchor_id}" (plus a
    # data-surface attribute for debugging/inspection) so glossary_linker.py and any
    # external page can deep-link straight to a term with #term-{anchor_id}.
    script = script.replace(
        "      const card = document.createElement('article');\n"
        "      card.className = 'card';\n"
        "      card.dataset.status = t.status;\n",
        "      const card = document.createElement('article');\n"
        "      card.className = 'card';\n"
        "      card.id = 'term-' + t.anchor_id;\n"
        "      card.dataset.status = t.status;\n"
        "      card.dataset.surface = t.surface;\n",
    )
    template = template.replace('href="/" title="Dashboard Overview"', 'href="./" title="Mission Runs"')
    template = template.replace('href="/glossary" title="Glossary"', 'href="glossary.html" title="Glossary"')
    template = template.replace(
        '<link rel="stylesheet" href="/static/dashboard/glossary.css">',
        f"<style>\n{css}\n</style>",
    )
    template = template.replace(
        '<script src="/static/dashboard/glossary.js"></script>',
        f"<script>\n{script}\n</script>",
    )
    return template


def write_toc(mission_list: list[Mission]) -> None:
    lines = ["- name: Mission Runs", "  href: index.html", "  items:"]
    lines.append("    - name: Glossary")
    lines.append("      href: glossary.html")
    for mission in mission_list:
        lines.append(f"    - name: {json.dumps(mission.name, ensure_ascii=False)}")
        lines.append(f"      href: {mission.slug}/index.html")
    DEST.joinpath("toc.yml").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    if DEST.exists():
        shutil.rmtree(DEST)
    DEST.mkdir(parents=True)
    mission_list = missions()
    DEST.joinpath("index.html").write_text(index_page(mission_list), encoding="utf-8")
    DEST.joinpath("glossary.html").write_text(glossary_page(mission_list), encoding="utf-8")
    write_toc(mission_list)
    for mission in mission_list:
        mission_dir = DEST / mission.slug
        mission_dir.mkdir()
        for key, label, _icon, source in ARTIFACTS:
            if not artifact_exists(mission, key, source):
                continue
            name = "index.html" if key == "overview" else f"{key}.html"
            mission_dir.joinpath(name).write_text(
                page(mission_list, mission, key, label, source),
                encoding="utf-8",
            )
    print(f"Generated {len(mission_list)} mission dashboards in {DEST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
