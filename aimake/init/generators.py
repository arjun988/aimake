"""Generate aimake.yaml from Makefile, DVC, Prefect, or Airflow projects."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Callable

GeneratorFn = Callable[[Path, str], str]

SUPPORTED_SOURCES = ("makefile", "dvc", "prefect", "airflow-dag")


def supported_sources() -> tuple[str, ...]:
    return SUPPORTED_SOURCES


def generate_from(source: str, root: Path, project_name: str) -> str:
    """Return aimake.yaml content generated from an existing layout."""
    key = source.lower().replace("_", "-")
    generators: dict[str, GeneratorFn] = {
        "makefile": _from_makefile,
        "dvc": _from_dvc,
        "prefect": _from_prefect,
        "airflow-dag": _from_airflow,
    }
    if key not in generators:
        raise ValueError(
            f"Unknown --from source '{source}'. "
            f"Supported: {', '.join(SUPPORTED_SOURCES)}"
        )
    return generators[key](root.resolve(), project_name)


def _header(project_name: str, source: str) -> str:
    return f"""project:
  name: {project_name}
  version: "1.0"
  atomic_outputs: true

# Generated from {source} — review commands before running `aimake build`.

artifacts:
"""


def _yaml_quote(s: str) -> str:
    if any(c in s for c in ':"\\{}[]'):
        escaped = s.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return s


def _artifact_block(
    name: str,
    *,
    command: str | None = None,
    source: str | None = None,
    depends_on: list[str] | None = None,
    outputs: list[str] | None = None,
    artifact_type: str = "generic",
) -> str:
    lines = [f"  {name}:", f"    type: {artifact_type}"]
    if depends_on:
        lines.append("    depends_on:")
        for dep in depends_on:
            lines.append(f"      - {dep}")
    if source:
        lines.append(f"    source: {_yaml_quote(source)}")
    if command:
        lines.append(f"    command: {_yaml_quote(command)}")
    if outputs:
        lines.append("    outputs:")
        for out in outputs:
            lines.append(f"      - {_yaml_quote(out)}")
    return "\n".join(lines) + "\n"


def _from_makefile(root: Path, project_name: str) -> str:
    makefile = root / "Makefile"
    if not makefile.is_file():
        makefile = root / "makefile"
    if not makefile.is_file():
        raise FileNotFoundError(f"No Makefile found in {root}")

    text = makefile.read_text(encoding="utf-8", errors="replace")
    rules: list[tuple[str, list[str], str]] = []
    current_target: str | None = None
    current_deps: list[str] = []
    current_cmds: list[str] = []

    for line in text.splitlines():
        if line.startswith(".") or line.strip().startswith("#"):
            continue
        rule_match = re.match(r"^([a-zA-Z0-9_.-]+)\s*:(.*)$", line)
        if rule_match and not line.startswith("\t") and not line.startswith(" "):
            if current_target and current_cmds:
                rules.append((current_target, current_deps, " && ".join(current_cmds)))
            current_target = rule_match.group(1).split(".")[0]
            dep_part = rule_match.group(2).split("#")[0]
            current_deps = [d.strip() for d in dep_part.split() if d.strip()]
            current_cmds = []
            continue
        if current_target and (line.startswith("\t") or line.startswith("    ")):
            cmd = line.strip()
            if cmd and not cmd.startswith("#") and not cmd.startswith("@") and cmd != "-":
                cmd = cmd.lstrip("@")
                if cmd.startswith("-"):
                    cmd = cmd[1:].strip()
                current_cmds.append(cmd)

    if current_target and current_cmds:
        rules.append((current_target, current_deps, " && ".join(current_cmds)))

    if not rules:
        raise ValueError("No Makefile targets with commands found")

    skip = {"all", "clean", "help", "test", ".PHONY"}
    blocks: list[str] = []
    for target, deps, command in rules:
        if target in skip or target.startswith("."):
            continue
        aimake_deps = [d for d in deps if d not in skip and d != target]
        outputs = [f"build/{target}/"]
        blocks.append(
            _artifact_block(
                _sanitize_name(target),
                command=command,
                depends_on=[_sanitize_name(d) for d in aimake_deps] or None,
                outputs=outputs,
                artifact_type="generic",
            )
        )

    if not blocks:
        raise ValueError("No usable Makefile targets found (skipped .PHONY/all/clean)")

    return _header(project_name, "Makefile") + "\n".join(blocks)


def _from_dvc(root: Path, project_name: str) -> str:
    dvc_yaml = root / "dvc.yaml"
    blocks: list[str] = []

    if dvc_yaml.is_file():
        text = dvc_yaml.read_text(encoding="utf-8", errors="replace")
        stage_pattern = re.compile(
            r"^\s{2}(\w[\w-]*):\s*\n(?:^\s{4}.+\n)*",
            re.MULTILINE,
        )
        for match in stage_pattern.finditer(text):
            stage_name = match.group(1)
            block = match.group(0)
            cmd_match = re.search(r"cmd:\s*(.+)", block)
            dep_match = re.search(r"deps:\s*\n((?:\s+-\s+.+\n)+)", block)
            out_match = re.search(r"outs:\s*\n((?:\s+-\s+.+\n)+)", block)
            if not cmd_match:
                continue
            command = cmd_match.group(1).strip().strip("'\"")
            depends: list[str] = []
            if dep_match:
                for line in dep_match.group(1).splitlines():
                    m = re.search(r"-\s+(.+)", line)
                    if m:
                        dep_path = m.group(1).strip().strip("'\"")
                        parent_stage = _guess_dvc_stage_from_path(dep_path)
                        if parent_stage and parent_stage != stage_name:
                            depends.append(_sanitize_name(parent_stage))
            outputs: list[str] = []
            if out_match:
                for line in out_match.group(1).splitlines():
                    m = re.search(r"-\s+(.+)", line)
                    if m:
                        outputs.append(m.group(1).strip().strip("'\""))
            blocks.append(
                _artifact_block(
                    _sanitize_name(stage_name),
                    command=command,
                    depends_on=depends or None,
                    outputs=outputs or [f"build/{stage_name}/"],
                    artifact_type="dataset",
                )
            )

    if not blocks:
        dvc_files = sorted(root.rglob("*.dvc"))
        dvc_files = [p for p in dvc_files if ".aimake" not in p.parts]
        if not dvc_files:
            raise FileNotFoundError(f"No dvc.yaml or .dvc files found in {root}")
        for i, dvc_file in enumerate(dvc_files[:20]):
            rel = dvc_file.relative_to(root).as_posix()
            data_path = rel[:-4] if rel.endswith(".dvc") else rel
            name = _sanitize_name(Path(data_path).stem or f"data_{i}")
            blocks.append(
                _artifact_block(
                    name,
                    source=data_path,
                    artifact_type="dataset",
                    outputs=[data_path] if not data_path.endswith("/") else None,
                )
            )
            blocks[-1] = blocks[-1].rstrip() + "\n    metadata:\n      dvc:\n        tracked: true\n        path: " + _yaml_quote(rel) + "\n"

    return _header(project_name, "DVC") + "\n".join(blocks)


def _from_prefect(root: Path, project_name: str) -> str:
    candidates = list(root.rglob("*.py")) + list(root.rglob("prefect.yaml"))
    flows: list[tuple[str, str, list[str]]] = []

    for path in candidates:
        if ".aimake" in path.parts or "venv" in path.parts:
            continue
        if path.suffix != ".py":
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "@flow" not in text and "Flow(" not in text:
            continue
        rel = path.relative_to(root).as_posix()
        for fn_match in re.finditer(r"def\s+(\w+)\s*\([^)]*\):", text):
            fn_name = fn_match.group(1)
            window = text[fn_match.start() : fn_match.start() + 200]
            if "@flow" in text[max(0, fn_match.start() - 120) : fn_match.start()] or "@flow" in window:
                flows.append((f"{path.stem}_{fn_name}", rel, [fn_name]))

    if not flows:
        raise FileNotFoundError(
            f"No Prefect @flow functions found under {root}. "
            "Add a Python file with @flow-decorated functions."
        )

    blocks = []
    for i, (name, rel, fns) in enumerate(flows[:15]):
        fn = fns[0]
        blocks.append(
            _artifact_block(
                _sanitize_name(name),
                command=f"python -c \"from importlib import import_module; import sys; sys.path.insert(0, '.'); m=import_module('{rel.replace('/', '.').replace('.py', '')}'); m.{fn}()\"",
                outputs=[f"build/{_sanitize_name(name)}/"],
                artifact_type="generic",
            )
        )

    return _header(project_name, "Prefect") + "\n".join(blocks)


def _from_airflow(root: Path, project_name: str) -> str:
    dag_files = []
    for path in root.rglob("*.py"):
        if ".aimake" in path.parts or "venv" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "DAG(" in text or "dag_id" in text:
            dag_files.append((path, text))

    if not dag_files:
        raise FileNotFoundError(f"No Airflow DAG files found under {root}")

    blocks = []
    for path, text in dag_files[:10]:
        dag_id_match = re.search(r"dag_id\s*=\s*['\"]([^'\"]+)['\"]", text)
        dag_id = dag_id_match.group(1) if dag_id_match else path.stem
        rel = path.relative_to(root).as_posix()
        mod = rel.replace("/", ".").replace(".py", "")

        task_ids = re.findall(
            r"(?:PythonOperator|BashOperator|EmptyOperator)\(\s*task_id\s*=\s*['\"]([^'\"]+)['\"]",
            text,
        )
        if not task_ids:
            task_ids = [f"run_{path.stem}"]

        prev: str | None = None
        for task_id in task_ids[:12]:
            name = _sanitize_name(f"{dag_id}_{task_id}")
            blocks.append(
                _artifact_block(
                    name,
                    command=f"python -m airflow tasks test {_yaml_quote(dag_id).strip(chr(34))} {task_id} $(date +%Y-%m-%d) 2>/dev/null || echo 'Configure Airflow CLI for task {task_id}'",
                    depends_on=[prev] if prev else None,
                    outputs=[f"build/{name}/"],
                    artifact_type="generic",
                )
            )
            prev = name

    return _header(project_name, "Airflow DAG") + "\n".join(blocks)


def _sanitize_name(name: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]", "_", name).strip("_").lower()
    if not clean:
        return "artifact"
    if clean[0].isdigit():
        return f"a_{clean}"
    return clean


def _guess_dvc_stage_from_path(path: str) -> str | None:
    stem = Path(path.split("/")[-1]).stem
    return stem if stem else None
