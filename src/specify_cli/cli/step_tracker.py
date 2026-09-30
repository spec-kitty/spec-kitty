"""Progress tracking helpers for Spec Kitty CLI."""

from __future__ import annotations

import contextlib
from typing import Any

from rich.tree import Tree


class StepTracker:
    """Track and render hierarchical steps with Rich trees."""

    def __init__(self, title: str) -> None:
        self.title = title
        self.steps: list[dict[str, Any]] = []  # list of dicts: {key, label, status, detail}
        self._refresh_cb: Any = None  # callable to trigger UI refresh

    def attach_refresh(self, cb: Any) -> None:
        self._refresh_cb = cb

    def add(self, key: str, label: str) -> None:
        if key not in [s["key"] for s in self.steps]:
            self.steps.append({"key": key, "label": label, "status": "pending", "detail": ""})
            self._maybe_refresh()

    def start(self, key: str, detail: str = "") -> None:
        self._update(key, status="running", detail=detail)

    def complete(self, key: str, detail: str = "") -> None:
        self._update(key, status="done", detail=detail)

    def error(self, key: str, detail: str = "") -> None:
        self._update(key, status="error", detail=detail)

    def skip(self, key: str, detail: str = "") -> None:
        self._update(key, status="skipped", detail=detail)

    def _update(self, key: str, status: str, detail: str) -> None:
        for s in self.steps:
            if s["key"] == key:
                s["status"] = status
                if detail:
                    s["detail"] = detail
                self._maybe_refresh()
                return
        # If not present, add it
        self.steps.append({"key": key, "label": key, "status": status, "detail": detail})
        self._maybe_refresh()

    def _maybe_refresh(self) -> None:
        if self._refresh_cb:
            with contextlib.suppress(Exception):
                self._refresh_cb()

    def render(self) -> Tree:
        tree = Tree(f"[cyan]{self.title}[/cyan]", guide_style="grey50")
        for step in self.steps:
            label = step["label"]
            detail_text = step["detail"].strip() if step["detail"] else ""

            status = step["status"]
            if status == "done":
                symbol = "[green]●[/green]"
            elif status == "pending":
                symbol = "[green dim]○[/green dim]"
            elif status == "running":
                symbol = "[cyan]○[/cyan]"
            elif status == "error":
                symbol = "[red]●[/red]"
            elif status == "skipped":
                symbol = "[yellow]○[/yellow]"
            else:
                symbol = " "

            if status == "pending":
                if detail_text:
                    line = f"{symbol} [bright_black]{label} ({detail_text})[/bright_black]"
                else:
                    line = f"{symbol} [bright_black]{label}[/bright_black]"
            else:
                if detail_text:
                    line = f"{symbol} [white]{label}[/white] [bright_black]({detail_text})[/bright_black]"
                else:
                    line = f"{symbol} [white]{label}[/white]"

            tree.add(line)
        return tree


__all__ = ["StepTracker"]
