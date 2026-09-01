"""Test hashing and fingerprinting."""

from pathlib import Path

from aimake.config.schema import AimakeConfig, ArtifactConfig, ProjectConfig
from aimake.graph.dag import Graph
from aimake.hashing.directories import expand_glob, hash_inputs
from aimake.hashing.files import hash_file, hash_string
from aimake.hashing.fingerprint import Fingerprinter


def test_hash_file_deterministic(tmp_path: Path) -> None:
    f = tmp_path / "test.txt"
    f.write_text("hello world")
    h1 = hash_file(f)
    h2 = hash_file(f)
    assert h1 == h2
    assert h1.startswith("sha256:")


def test_hash_file_changes(tmp_path: Path) -> None:
    f = tmp_path / "test.txt"
    f.write_text("hello")
    h1 = hash_file(f)
    f.write_text("world")
    h2 = hash_file(f)
    assert h1 != h2


def test_hash_string() -> None:
    assert hash_string("abc") == hash_string("abc")
    assert hash_string("abc") != hash_string("def")


def test_directory_hash(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")
    h1 = hash_inputs(["*"], tmp_path)
    h2 = hash_inputs(["*"], tmp_path)
    assert h1 == h2


def test_glob_expansion(tmp_path: Path) -> None:
    sub = tmp_path / "data"
    sub.mkdir()
    (sub / "a.jsonl").write_text("{}")
    (sub / "b.jsonl").write_text("{}")
    files = expand_glob("data/**", tmp_path)
    assert len(files) == 2


def test_fingerprint_includes_dependencies(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("a")
    (tmp_path / "b.txt").write_text("b")

    config = AimakeConfig(
        project=ProjectConfig(name="test"),
        artifacts={
            "a": ArtifactConfig(type="dataset", source="a.txt"),
            "b": ArtifactConfig(type="dataset", source="b.txt", depends_on=["a"]),
        },
    )
    graph = Graph.from_config(config)
    fp = Fingerprinter(tmp_path, config, graph)
    fps = fp.fingerprint_all()
    assert "a" in fps
    assert "b" in fps
    assert fps["a"] != fps["b"]


def test_fingerprint_changes_with_content(tmp_path: Path) -> None:
    f = tmp_path / "prompt.txt"
    f.write_text("version 1")

    config = AimakeConfig(
        project=ProjectConfig(name="test"),
        artifacts={
            "prompt": ArtifactConfig(type="prompt", source="prompt.txt"),
        },
    )
    graph = Graph.from_config(config)
    fp = Fingerprinter(tmp_path, config, graph)
    h1 = fp.fingerprint("prompt")

    f.write_text("version 2")
    fp2 = Fingerprinter(tmp_path, config, graph)
    h2 = fp2.fingerprint("prompt")
    assert h1 != h2
