"""Test dependency graph."""

import pytest

from aimake.config.schema import AimakeConfig, ArtifactConfig, ProjectConfig
from aimake.graph.dag import Graph, GraphError


def _make_config(artifacts: dict) -> AimakeConfig:
    return AimakeConfig(
        project=ProjectConfig(name="test"),
        artifacts={
            name: ArtifactConfig(**cfg) for name, cfg in artifacts.items()
        },
    )


def test_simple_dag() -> None:
    config = _make_config({
        "a": {"type": "dataset", "source": "a.txt"},
        "b": {"type": "dataset", "source": "b.txt", "depends_on": ["a"]},
    })
    graph = Graph.from_config(config)
    order = graph.names()
    assert order.index("a") < order.index("b")


def test_multiple_dependencies() -> None:
    config = _make_config({
        "a": {"type": "dataset", "source": "a.txt"},
        "b": {"type": "prompt", "source": "b.txt"},
        "c": {
            "type": "evaluation",
            "source": "c.txt",
            "depends_on": ["a", "b"],
        },
    })
    graph = Graph.from_config(config)
    order = graph.names()
    assert order.index("a") < order.index("c")
    assert order.index("b") < order.index("c")


def test_cycle_detection() -> None:
    config = _make_config({
        "a": {"type": "generic", "source": "a.txt", "depends_on": ["c"]},
        "b": {"type": "generic", "source": "b.txt", "depends_on": ["a"]},
        "c": {"type": "generic", "source": "c.txt", "depends_on": ["b"]},
    })
    with pytest.raises(GraphError, match="Circular dependency"):
        Graph.from_config(config)


def test_subgraph() -> None:
    config = _make_config({
        "a": {"type": "dataset", "source": "a.txt"},
        "b": {"type": "dataset", "source": "b.txt", "depends_on": ["a"]},
        "c": {"type": "dataset", "source": "c.txt", "depends_on": ["b"]},
    })
    graph = Graph.from_config(config)
    sub = graph.subgraph_for_targets(["c"])
    assert set(sub.names()) == {"a", "b", "c"}


def test_parallel_groups() -> None:
    config = _make_config({
        "root": {"type": "dataset", "source": "r.txt"},
        "left": {"type": "embedding", "source": "l.txt", "depends_on": ["root"]},
        "right": {"type": "embedding", "source": "r.txt", "depends_on": ["root"]},
        "merge": {"type": "vector_index", "source": "m.txt", "depends_on": ["left", "right"]},
    })
    graph = Graph.from_config(config)
    groups = graph.parallel_groups()
    assert groups[0] == ["root"]
    assert set(groups[1]) == {"left", "right"}


def test_to_dot() -> None:
    config = _make_config({
        "a": {"type": "dataset", "source": "a.txt"},
        "b": {"type": "dataset", "source": "b.txt", "depends_on": ["a"]},
    })
    graph = Graph.from_config(config)
    dot = graph.to_dot()
    assert "digraph aimake" in dot
    assert '"a" -> "b"' in dot
