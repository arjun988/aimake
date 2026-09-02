"""SDK, TUI render, and developer API smoke tests."""

from __future__ import annotations

from pathlib import Path

from aimake.sdk import Aimake, load
from aimake.ui.tui import AimakeTui


def _mini_project(tmp_path: Path):
    (tmp_path / "aimake.yaml").write_text(
        """
project:
  name: sdk-demo
artifacts:
  data:
    type: dataset
    source: data.txt
""",
        encoding="utf-8",
    )
    (tmp_path / "data.txt").write_text("x", encoding="utf-8")
    return tmp_path / "aimake.yaml"


def test_sdk_aimake_context_manager(tmp_path: Path) -> None:
    cfg = _mini_project(tmp_path)
    with Aimake.load(cfg) as ai:
        plan = ai.plan()
        assert "data" in [e.name for e in plan.entries]
        result = ai.build()
        assert result.success


def test_sdk_load_helper(tmp_path: Path) -> None:
    cfg = _mini_project(tmp_path)
    proj = load(cfg)
    assert proj.config.project.name == "sdk-demo"
    proj.close()


def test_tui_render_panels(tmp_path: Path) -> None:
    cfg = _mini_project(tmp_path)
    proj = load(cfg)
    tui = AimakeTui(proj)
    tui._refresh()
    layout = tui._render()
    # Ensure layout tree exists without requiring a TTY
    assert layout is not None
    assert tui.state.names == ["data"]
    proj.close()


def test_developer_api_payload(tmp_path: Path) -> None:
    from aimake.serve.api import DashboardAPI

    cfg = _mini_project(tmp_path)
    proj = load(cfg)
    api = DashboardAPI(proj)
    info = api.developer()
    assert "ghcr.io/" in info["docker"]["image"]
    assert "Aimake" in info["python_sdk"]["import"]
    assert info["tui"]["command"] == "aimake tui"
    assert "@aimake/sdk" == info["typescript_sdk"]["package"]
    proj.close()
