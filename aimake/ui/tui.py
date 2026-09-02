"""Interactive Rich full-screen TUI: plan → build → metrics."""

from __future__ import annotations

import sys
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from rich.align import Align
from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from aimake.models import ArtifactStatus, BuildAction, BuildPlan, BuildResult
from aimake.project import Project


HELP = (
    "[bold]keys[/bold]  "
    "[cyan]↑/↓[/cyan] select  "
    "[cyan]b[/cyan] build all  "
    "[cyan]enter[/cyan] build selected  "
    "[cyan]p[/cyan] replan  "
    "[cyan]r[/cyan] refresh  "
    "[cyan]q[/cyan] quit"
)


@dataclass
class TuiState:
    names: list[str] = field(default_factory=list)
    selected: int = 0
    plan: BuildPlan | None = None
    statuses: dict[str, ArtifactStatus] = field(default_factory=dict)
    last_result: BuildResult | None = None
    message: str = "Ready"
    busy: bool = False
    quit: bool = False


class AimakeTui:
    """lazygit-style pipeline console built on Rich Live."""

    def __init__(self, project: Project, *, console: Console | None = None) -> None:
        self.project = project
        self.console = console or Console()
        self.state = TuiState()
        self._lock = threading.Lock()

    def run(self) -> int:
        if not sys.stdin.isatty():
            self.console.print(
                "[yellow]aimake tui requires an interactive TTY. "
                "Use `aimake plan` / `aimake build` instead.[/yellow]"
            )
            return 1

        self._refresh()
        with Live(
            self._render(),
            console=self.console,
            screen=True,
            redirect_stderr=False,
            refresh_per_second=12,
        ) as live:
            while not self.state.quit:
                key = _read_key(timeout=0.08)
                if key:
                    self._handle_key(key)
                live.update(self._render())
        return 0

    def _refresh(self) -> None:
        with self._lock:
            self.state.busy = True
            self.state.message = "Refreshing…"
        try:
            statuses = self.project.status()
            plan = self.project.plan()
            names = list(self.project.graph.names())
            with self._lock:
                self.state.statuses = statuses
                self.state.plan = plan
                self.state.names = names
                if self.state.selected >= len(names):
                    self.state.selected = max(0, len(names) - 1)
                self.state.message = (
                    f"Plan: {len(plan.to_run)} run · {len(plan.to_restore)} restore · "
                    f"{len(plan.to_skip)} skip"
                )
        except Exception as e:
            with self._lock:
                self.state.message = f"Error: {e}"
        finally:
            with self._lock:
                self.state.busy = False

    def _handle_key(self, key: str) -> None:
        if self.state.busy:
            return
        if key in ("q", "Q", "\x03"):  # q or Ctrl-C
            self.state.quit = True
            return
        if key in ("r", "R"):
            self._refresh()
            return
        if key in ("p", "P"):
            self._refresh()
            return
        if key in ("b", "B"):
            self._run_build(None)
            return
        if key in ("\r", "\n"):
            if self.state.names:
                target = self.state.names[self.state.selected]
                self._run_build([target])
            return
        if key in ("up", "k"):
            if self.state.names:
                self.state.selected = (self.state.selected - 1) % len(self.state.names)
            return
        if key in ("down", "j"):
            if self.state.names:
                self.state.selected = (self.state.selected + 1) % len(self.state.names)
            return

    def _run_build(self, targets: list[str] | None) -> None:
        with self._lock:
            self.state.busy = True
            label = ", ".join(targets) if targets else "all"
            self.state.message = f"Building {label}…"
        try:
            result = self.project.build(targets=targets)
            with self._lock:
                self.state.last_result = result
                if result.success:
                    self.state.message = (
                        f"Build ok in {result.duration:.1f}s — "
                        f"{len(result.rebuilt)} rebuilt, {len(result.reused)} reused"
                    )
                else:
                    self.state.message = (
                        f"Build failed: {', '.join(result.failed) or 'unknown'}"
                    )
            self._refresh()
        except Exception as e:
            with self._lock:
                self.state.message = f"Build error: {e}"
                self.state.busy = False

    def _render(self) -> Layout:
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="body"),
            Layout(name="footer", size=3),
        )
        layout["body"].split_row(
            Layout(name="artifacts", ratio=2),
            Layout(name="side", ratio=3),
        )
        layout["side"].split_column(
            Layout(name="plan"),
            Layout(name="metrics"),
        )

        title = Text.from_markup(
            f"[bold cyan]aimake[/bold cyan]  "
            f"[white]{self.project.config.project.name}[/white]  "
            f"[dim]v{self.project.config.project.version}[/dim]"
        )
        layout["header"].update(Panel(Align.left(title), style="cyan"))
        layout["artifacts"].update(self._artifacts_panel())
        layout["plan"].update(self._plan_panel())
        layout["metrics"].update(self._metrics_panel())
        status = self.state.message
        if self.state.busy:
            status = f"[yellow]{status}[/yellow]"
        layout["footer"].update(
            Panel(Group(Text.from_markup(status), Text.from_markup(HELP)), style="dim")
        )
        return layout

    def _artifacts_panel(self) -> Panel:
        table = Table(expand=True, show_header=True, header_style="bold")
        table.add_column("", width=2)
        table.add_column("Artifact")
        table.add_column("Status")
        table.add_column("Type")

        actions = {}
        if self.state.plan:
            actions = {e.name: e.action for e in self.state.plan.entries}

        for i, name in enumerate(self.state.names):
            node = self.project.graph.get(name)
            status = self.state.statuses.get(name, ArtifactStatus.UNKNOWN)
            marker = "▶" if i == self.state.selected else " "
            action = actions.get(name)
            status_txt = status.value
            if action == BuildAction.RUN:
                status_txt = f"[yellow]{status_txt}[/yellow]"
            elif action == BuildAction.RESTORE:
                status_txt = f"[cyan]restore[/cyan]"
            elif action == BuildAction.SKIP:
                status_txt = f"[green]skip[/green]"
            table.add_row(marker, name, status_txt, node.config.type)

        return Panel(table, title="Artifacts", border_style="blue")

    def _plan_panel(self) -> Panel:
        plan = self.state.plan
        if not plan:
            return Panel("[dim]No plan[/dim]", title="Plan", border_style="magenta")
        table = Table(expand=True, show_header=True, header_style="bold")
        table.add_column("Artifact")
        table.add_column("Action")
        table.add_column("Cost")
        for e in plan.entries:
            cost = (
                f"${e.estimated_cost_usd:.2f}"
                if e.estimated_cost_usd is not None
                else "—"
            )
            color = {
                BuildAction.RUN: "yellow",
                BuildAction.RESTORE: "cyan",
                BuildAction.SKIP: "green",
            }.get(e.action, "white")
            table.add_row(e.name, f"[{color}]{e.action.value}[/{color}]", cost)
        total = plan.estimated_total_cost_usd or 0
        subtitle = f"est. ${total:.2f}" if total else "up to date"
        return Panel(table, title=f"Plan · {subtitle}", border_style="magenta")

    def _metrics_panel(self) -> Panel:
        result = self.state.last_result
        lines: list[str] = []
        if result is None:
            lines.append("[dim]No build yet — press [cyan]b[/cyan][/dim]")
        else:
            lines.append(
                f"{'OK' if result.success else 'FAILED'} in {result.duration:.1f}s"
            )
            lines.append(
                f"rebuilt={len(result.rebuilt)} reused={len(result.reused)} "
                f"failed={len(result.failed)}"
            )
            if result.metrics:
                lines.append("")
                lines.append("[bold]Metrics[/bold]")
                for k, v in list(result.metrics.items())[:12]:
                    lines.append(f"  {k}: {v}")
            if result.git_commit:
                lines.append("")
                lines.append(
                    f"[dim]git {result.git_branch}@"
                    f"{result.git_commit[:8]}"
                    f"{' dirty' if result.git_dirty else ''}[/dim]"
                )
        return Panel(
            "\n".join(lines),
            title="Last build / metrics",
            border_style="green",
        )


def run_tui(project: Project) -> int:
    return AimakeTui(project).run()


def _read_key(timeout: float = 0.1) -> str | None:
    """Read a single keypress; returns None on timeout."""
    if sys.platform == "win32":
        return _read_key_windows(timeout)
    return _read_key_posix(timeout)


def _read_key_windows(timeout: float) -> str | None:
    try:
        import msvcrt
    except ImportError:
        return None
    end = time.time() + timeout
    while time.time() < end:
        if msvcrt.kbhit():
            ch = msvcrt.getwch()
            if ch in ("\x00", "\xe0"):
                ch2 = msvcrt.getwch()
                return {"H": "up", "P": "down"}.get(ch2, "")
            return ch
        time.sleep(0.01)
    return None


def _read_key_posix(timeout: float) -> str | None:
    import select
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        r, _, _ = select.select([sys.stdin], [], [], timeout)
        if not r:
            return None
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            # arrow sequences
            r2, _, _ = select.select([sys.stdin], [], [], 0.02)
            if r2:
                ch2 = sys.stdin.read(1)
                if ch2 == "[":
                    r3, _, _ = select.select([sys.stdin], [], [], 0.02)
                    if r3:
                        ch3 = sys.stdin.read(1)
                        return {"A": "up", "B": "down"}.get(ch3, "")
            return ch
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
