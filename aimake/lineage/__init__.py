"""Lineage export: OpenLineage, MLflow, W&B artifact graphs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from aimake.config.schema import AimakeConfig, LineageConfig
from aimake.graph.dag import Graph
from aimake.project import Project


def build_openlineage_run(
    project: Project,
    *,
    run_id: str | None = None,
    event_time: str | None = None,
) -> dict[str, Any]:
    """Build an OpenLineage COMPLETE run event covering the project DAG."""
    cfg = project.config
    root = project.project_root
    graph = project.graph
    fps = project.runner.compute_fingerprints()
    rid = run_id or str(uuid4())
    ts = event_time or datetime.now(timezone.utc).isoformat()

    inputs = []
    outputs = []
    for node in graph:
        ds = {
            "namespace": cfg.project.name,
            "name": node.name,
            "facets": {
                "dataSource": {
                    "_producer": "https://aimake.dev",
                    "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/DataSourceDatasetFacet.json",
                    "name": "aimake",
                    "uri": f"file://{root.as_posix()}",
                },
                "version": {
                    "_producer": "https://aimake.dev",
                    "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/VersionDatasetFacet.json",
                    "datasetVersion": fps.get(node.name, ""),
                },
            },
        }
        # Roots as inputs, leaves-ish as outputs; also list all as outputs of the job
        if not node.dependencies:
            inputs.append(ds)
        outputs.append(ds)

    job_name = f"{cfg.project.name}.pipeline"
    return {
        "eventType": "COMPLETE",
        "eventTime": ts,
        "run": {
            "runId": rid,
            "facets": {
                "aimake": {
                    "_producer": "https://aimake.dev",
                    "project": cfg.project.name,
                    "version": cfg.project.version,
                    "root": str(root),
                }
            },
        },
        "job": {
            "namespace": cfg.project.name,
            "name": job_name,
            "facets": {
                "documentation": {
                    "_producer": "https://aimake.dev",
                    "description": f"aimake lineage for {cfg.project.name}",
                }
            },
        },
        "inputs": inputs,
        "outputs": outputs,
        "producer": "https://aimake.dev",
        "schemaURL": "https://openlineage.io/spec/1-0-5/OpenLineage.json",
    }


def build_openlineage_events(project: Project) -> list[dict[str, Any]]:
    """One OpenLineage event per artifact (parent→child edges via inputs)."""
    cfg = project.config
    fps = project.runner.compute_fingerprints()
    events = []
    ts = datetime.now(timezone.utc).isoformat()
    for node in project.graph:
        inputs = [
            {
                "namespace": cfg.project.name,
                "name": dep,
                "facets": {
                    "version": {
                        "_producer": "https://aimake.dev",
                        "datasetVersion": fps.get(dep, ""),
                    }
                },
            }
            for dep in node.dependencies
        ]
        outputs = [
            {
                "namespace": cfg.project.name,
                "name": node.name,
                "facets": {
                    "version": {
                        "_producer": "https://aimake.dev",
                        "datasetVersion": fps.get(node.name, ""),
                    },
                    "outputs": {
                        "_producer": "https://aimake.dev",
                        "paths": list(node.config.outputs),
                    },
                },
            }
        ]
        events.append(
            {
                "eventType": "COMPLETE",
                "eventTime": ts,
                "run": {"runId": str(uuid4())},
                "job": {
                    "namespace": cfg.project.name,
                    "name": f"{cfg.project.name}.{node.name}",
                },
                "inputs": inputs,
                "outputs": outputs,
                "producer": "https://aimake.dev",
                "schemaURL": "https://openlineage.io/spec/1-0-5/OpenLineage.json",
            }
        )
    return events


def build_mlflow_lineage(project: Project) -> dict[str, Any]:
    """MLflow-compatible artifact lineage graph (JSON, no MLflow required)."""
    fps = project.runner.compute_fingerprints()
    nodes = []
    edges = []
    for node in project.graph:
        nodes.append(
            {
                "id": node.name,
                "type": node.config.type,
                "fingerprint": fps.get(node.name),
                "outputs": list(node.config.outputs),
            }
        )
        for dep in node.dependencies:
            edges.append({"source": dep, "target": node.name})
    return {
        "format": "aimake.mlflow_lineage.v1",
        "experiment": project.config.project.name,
        "nodes": nodes,
        "edges": edges,
    }


def build_wandb_lineage(project: Project) -> dict[str, Any]:
    """W&B-style artifact graph description."""
    fps = project.runner.compute_fingerprints()
    artifacts = []
    for node in project.graph:
        artifacts.append(
            {
                "name": node.name,
                "type": node.config.type,
                "digest": fps.get(node.name),
                "used": list(node.dependencies),
                "logged_outputs": list(node.config.outputs),
            }
        )
    return {
        "format": "aimake.wandb_lineage.v1",
        "project": project.config.project.name,
        "artifacts": artifacts,
    }


def export_lineage(
    project: Project,
    *,
    formats: list[str] | None = None,
    output_dir: Path | None = None,
) -> dict[str, Path]:
    """Write lineage files; returns format → path."""
    cfg: LineageConfig = project.config.lineage
    fmts = formats or list(cfg.formats) or ["openlineage"]
    out = output_dir or (project.project_root / cfg.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    written: dict[str, Path] = {}

    for fmt in fmts:
        if fmt == "openlineage":
            payload = {
                "run": build_openlineage_run(project),
                "events": build_openlineage_events(project),
            }
            path = out / f"openlineage-{stamp}.json"
        elif fmt == "mlflow":
            payload = build_mlflow_lineage(project)
            path = out / f"mlflow-lineage-{stamp}.json"
        elif fmt == "wandb":
            payload = build_wandb_lineage(project)
            path = out / f"wandb-lineage-{stamp}.json"
        else:
            continue
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        written[fmt] = path
    return written


def lineage_graph_payload(project: Project) -> dict[str, Any]:
    """Compact graph for dashboard."""
    fps = project.runner.compute_fingerprints()
    statuses = project.runner.compute_statuses()
    return {
        "nodes": [
            {
                "name": n.name,
                "type": n.config.type,
                "fingerprint": fps.get(n.name),
                "status": statuses.get(n.name).value if n.name in statuses else None,
                "depends_on": list(n.dependencies),
            }
            for n in project.graph
        ],
        "edges": [
            {"from": d, "to": n.name} for n in project.graph for d in n.dependencies
        ],
        "formats": list(project.config.lineage.formats),
        "enabled": project.config.lineage.enabled,
    }
