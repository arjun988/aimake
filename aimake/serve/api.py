"""HTTP API for the aimake dashboard."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, is_dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from aimake.project import Project
from aimake.policy import PolicyError


def _json_default(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    if hasattr(obj, "value"):
        return obj.value
    if isinstance(obj, Path):
        return str(obj)
    return str(obj)


def _serialize(data: Any) -> bytes:
    return json.dumps(data, default=_json_default, indent=2).encode("utf-8")


class DashboardAPI:
    """Serialize project state for the web UI."""

    def __init__(self, project: Project) -> None:
        self.project = project

    def overview(self) -> dict[str, Any]:
        plan = self.project.plan()
        statuses = self.project.status()
        history = self.project.history(10)
        cache = self._safe_cache_status()
        experiments = self.project.experiments(5)
        registry = []
        try:
            registry = [
                {
                    "artifact_name": e.artifact_name,
                    "version": e.version,
                    "stage": e.stage,
                    "fingerprint": e.fingerprint,
                    "tags": e.tags,
                    "metrics": e.metrics,
                    "build_id": e.build_id,
                }
                for e in self.project.registry_list(limit=8)
            ]
        except Exception:
            registry = []

        rebuilt = sum(
            1
            for s in statuses.values()
            if s.value in ("changed", "stale", "unknown", "failed")
        )
        cached = sum(
            1 for s in statuses.values() if s.value in ("up_to_date", "cached")
        )

        return {
            "project": {
                "name": self.project.config.project.name,
                "version": self.project.config.project.version,
                "root": str(self.project.project_root),
            },
            "stats": {
                "artifacts": len(statuses),
                "to_rebuild": len(plan.to_run),
                "cached": cached,
                "stale": rebuilt,
                "estimated_cost_usd": plan.estimated_total_cost_usd,
                "estimated_tokens": plan.estimated_total_tokens,
                "builds": len(history),
                "experiments": len(experiments),
                "registry_entries": len(registry),
            },
            "plan": {
                "to_run": plan.to_run,
                "to_skip": plan.to_skip,
                "to_restore": plan.to_restore,
                "entries": [
                    {
                        "name": e.name,
                        "action": e.action.value,
                        "status": e.status.value,
                        "reason": e.reason,
                        "estimated_cost_usd": e.estimated_cost_usd,
                        "estimated_tokens": e.estimated_tokens,
                    }
                    for e in plan.entries
                ],
            },
            "statuses": {k: v.value for k, v in statuses.items()},
            "recent_builds": history,
            "cache": cache,
            "recent_experiments": experiments,
            "registry_preview": registry,
        }

    def graph(self) -> dict[str, Any]:
        statuses = self.project.status()
        nodes: list[dict[str, Any]] = []
        edges: list[dict[str, str]] = []
        for node in self.project.graph:
            st = statuses.get(node.name)
            nodes.append(
                {
                    "name": node.name,
                    "type": node.config.type,
                    "depends_on": list(node.dependencies),
                    "command": node.config.command,
                    "outputs": list(node.config.outputs),
                    "status": st.value if st else "unknown",
                }
            )
            for dep in node.dependencies:
                edges.append({"from": dep, "to": node.name})
        return {"nodes": nodes, "edges": edges, "dot": self.project.graph_dot()}

    def builds(self, limit: int = 50) -> dict[str, Any]:
        return {"builds": self.project.history(limit)}

    def compare(self, baseline: str = "previous", candidate: str = "latest") -> dict[str, Any]:
        result = self.project.compare_builds(baseline, candidate)
        return {
            "baseline_id": result.baseline_id,
            "candidate_id": result.candidate_id,
            "summary": result.summary,
            "baseline_metrics": result.baseline_metrics,
            "candidate_metrics": result.candidate_metrics,
            "metric_deltas": [
                {
                    "name": d.name,
                    "baseline": d.baseline,
                    "candidate": d.candidate,
                    "delta": d.delta,
                    "improved": d.improved,
                }
                for d in result.metric_deltas
            ],
            "parameter_changes": {
                k: {"baseline": v[0], "candidate": v[1]}
                for k, v in result.parameter_changes.items()
            },
            "baseline_git_commit": result.baseline_git_commit,
            "candidate_git_commit": result.candidate_git_commit,
        }

    def experiments(self, limit: int = 50) -> dict[str, Any]:
        return {"experiments": self.project.experiments(limit)}

    def experiment_detail(self, experiment_id: int) -> dict[str, Any]:
        exp = self.project.cache.state_db.get_experiment(experiment_id)
        if not exp:
            raise ValueError(f"Experiment #{experiment_id} not found")
        trials = self.project.experiment_trials(experiment_id)
        return {"experiment": exp, "trials": trials}

    def registry(
        self,
        artifact: str | None = None,
        stage: str | None = None,
        tag: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        entries = self.project.registry_list(
            artifact, stage=stage, tag=tag, limit=limit
        )
        return {
            "entries": [
                {
                    "artifact_name": e.artifact_name,
                    "version": e.version,
                    "stage": e.stage,
                    "fingerprint": e.fingerprint,
                    "tags": e.tags,
                    "metrics": e.metrics,
                    "metadata": e.metadata,
                    "build_id": e.build_id,
                    "created_at": str(e.created_at) if getattr(e, "created_at", None) else None,
                }
                for e in entries
            ],
            "enabled": self.project.config.registry.enabled,
            "remote": (
                {
                    "type": self.project.config.registry.remote.type,
                    "auto_push_on_promote": self.project.config.registry.remote.auto_push_on_promote,
                }
                if self.project.config.registry.remote
                else None
            ),
            "policy": self._policy_summary(),
        }

    def _policy_summary(self) -> dict[str, Any] | None:
        if not self.project.config.policy or not self.project.config.policy.promote:
            return None
        p = self.project.config.policy.promote
        return {
            "stages": p.stages,
            "metrics": {
                k: {"minimum": g.minimum, "maximum": g.maximum, "required": g.required}
                for k, g in p.metrics.items()
            },
            "max_cost_usd": p.max_cost_usd,
            "require_tag": p.require_tag,
            "require_approval_env": p.require_approval_env,
        }

    def promote(
        self,
        artifact: str,
        version: str,
        stage: str,
        *,
        force: bool = False,
        push: bool | None = None,
    ) -> dict[str, Any]:
        entry, push_result = self.project.registry_promote(
            artifact, version, stage, force=force, push=push
        )
        payload: dict[str, Any] = {
            "artifact_name": entry.artifact_name,
            "version": entry.version,
            "stage": entry.stage,
            "tags": entry.tags,
        }
        if push_result:
            payload["remote_push"] = {
                "backend": push_result.backend,
                "uri": push_result.uri,
                "ok": push_result.ok,
                "detail": push_result.detail,
            }
        return payload

    def registry_push(self, artifact: str, version: str) -> dict[str, Any]:
        result = self.project.registry_push(artifact, version)
        return {
            "backend": result.backend,
            "uri": result.uri,
            "ok": result.ok,
            "detail": result.detail,
        }

    def policy_check(self, artifact: str, version: str, stage: str) -> dict[str, Any]:
        violations = self.project.policy_check_promote(artifact, version, stage)
        return {
            "ok": len(violations) == 0,
            "violations": [{"code": v.code, "message": v.message} for v in violations],
        }

    def settings(self) -> dict[str, Any]:
        cfg = self.project.config
        n = cfg.notifications
        return {
            "project": {
                "name": cfg.project.name,
                "version": cfg.project.version,
                "root": str(self.project.project_root),
            },
            "cache": self._safe_cache_status(),
            "registry": {
                "enabled": cfg.registry.enabled,
                "remote": (
                    {"type": cfg.registry.remote.type}
                    if cfg.registry.remote
                    else None
                ),
            },
            "policy": self._policy_summary(),
            "notifications": {
                "slack": bool(n and n.slack and n.slack.enabled),
                "discord": bool(n and n.discord and n.discord.enabled),
                "email": bool(n and n.email and n.email.enabled),
            },
            "schedule_jobs": list((cfg.schedule.jobs if cfg.schedule else {}).keys()),
            "secrets": {
                "dotenv": cfg.secrets.dotenv,
                "providers": [p.type for p in cfg.secrets.providers],
            },
        }

    def tag(self, artifact: str, version: str, tags: list[str]) -> dict[str, Any]:
        entry = self.project.registry_tag(artifact, version, tags)
        return {
            "artifact_name": entry.artifact_name,
            "version": entry.version,
            "tags": entry.tags,
        }

    def cache(self) -> dict[str, Any]:
        return self._safe_cache_status()

    def plan(self) -> dict[str, Any]:
        plan = self.project.plan()
        return {
            "to_run": plan.to_run,
            "to_skip": plan.to_skip,
            "to_restore": plan.to_restore,
            "estimated_total_cost_usd": plan.estimated_total_cost_usd,
            "estimated_total_tokens": plan.estimated_total_tokens,
            "entries": [
                {
                    "name": e.name,
                    "action": e.action.value,
                    "status": e.status.value,
                    "reason": e.reason,
                    "estimated_cost_usd": e.estimated_cost_usd,
                    "estimated_tokens": e.estimated_tokens,
                }
                for e in plan.entries
            ],
        }

    def _safe_cache_status(self) -> dict[str, Any]:
        try:
            status = self.project.cache_status()
            # Normalize for dashboard: nest remote vs local-ish fields
            team = status.get("team") or {}
            return {
                "local": {
                    "entries": status.get("local_entries", 0),
                    "enabled": True,
                },
                "remote": (
                    {
                        "enabled": status.get("enabled", False),
                        "type": status.get("type"),
                        "entries": status.get("remote_entries", 0),
                        "synced": len(status.get("synced") or []),
                        "only_local": len(status.get("only_local") or []),
                        "only_remote": len(status.get("only_remote") or []),
                        "team_id": team.get("team_id"),
                        "bucket": team.get("bucket"),
                        "prefix": team.get("prefix"),
                    }
                    if status.get("enabled")
                    else None
                ),
                "raw": status,
            }
        except Exception as e:
            return {"local": {}, "remote": None, "error": str(e)}


def create_handler(api: DashboardAPI) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            pass

        def _cors(self) -> None:
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

        def _send(self, code: int, payload: Any) -> None:
            body = _serialize(payload)
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self._cors()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _error(self, code: int, message: str) -> None:
            self._send(code, {"error": message})

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/") or "/"
            qs = parse_qs(parsed.query)

            try:
                if path in ("/", "/api/health"):
                    self._send(200, {"ok": True, "service": "aimake-dashboard-api"})
                elif path == "/api/overview":
                    self._send(200, api.overview())
                elif path == "/api/graph":
                    self._send(200, api.graph())
                elif path == "/api/plan":
                    self._send(200, api.plan())
                elif path == "/api/builds":
                    limit = int(qs.get("limit", ["50"])[0])
                    self._send(200, api.builds(limit))
                elif path == "/api/compare":
                    baseline = qs.get("baseline", ["previous"])[0]
                    candidate = qs.get("candidate", ["latest"])[0]
                    self._send(200, api.compare(baseline, candidate))
                elif path == "/api/experiments":
                    limit = int(qs.get("limit", ["50"])[0])
                    self._send(200, api.experiments(limit))
                elif path.startswith("/api/experiments/"):
                    exp_id = int(path.rsplit("/", 1)[-1])
                    self._send(200, api.experiment_detail(exp_id))
                elif path == "/api/registry":
                    self._send(
                        200,
                        api.registry(
                            artifact=qs.get("artifact", [None])[0],
                            stage=qs.get("stage", [None])[0],
                            tag=qs.get("tag", [None])[0],
                            limit=int(qs.get("limit", ["100"])[0]),
                        ),
                    )
                elif path == "/api/cache":
                    self._send(200, api.cache())
                elif path == "/api/settings":
                    self._send(200, api.settings())
                elif path == "/api/policy/check":
                    self._send(
                        200,
                        api.policy_check(
                            qs.get("artifact", [""])[0],
                            qs.get("version", [""])[0],
                            qs.get("stage", ["production"])[0],
                        ),
                    )
                else:
                    self._error(404, f"Not found: {path}")
            except ValueError as e:
                self._error(400, str(e))
            except Exception as e:
                self._error(500, str(e))

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path.rstrip("/")
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            try:
                body = json.loads(raw.decode("utf-8") or "{}")
            except json.JSONDecodeError:
                self._error(400, "Invalid JSON body")
                return

            try:
                if path == "/api/registry/promote":
                    try:
                        self._send(
                            200,
                            api.promote(
                                body["artifact"],
                                body["version"],
                                body.get("stage", "production"),
                                force=bool(body.get("force", False)),
                                push=body.get("push"),
                            ),
                        )
                    except PolicyError as e:
                        self._error(403, str(e))
                        return
                elif path == "/api/registry/tag":
                    tags = body.get("tags") or [body["tag"]]
                    self._send(
                        200,
                        api.tag(body["artifact"], body["version"], tags),
                    )
                elif path == "/api/registry/push":
                    self._send(
                        200,
                        api.registry_push(body["artifact"], body["version"]),
                    )
                else:
                    self._error(404, f"Not found: {path}")
            except KeyError as e:
                self._error(400, f"Missing field: {e}")
            except ValueError as e:
                self._error(400, str(e))
            except Exception as e:
                self._error(500, str(e))

    return Handler


def run_server(
    project: Project,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> ThreadingHTTPServer:
    """Start the dashboard API server (blocking)."""
    api = DashboardAPI(project)
    handler = create_handler(api)
    server = ThreadingHTTPServer((host, port), handler)
    return server


def serve_in_background(
    project: Project,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> tuple[ThreadingHTTPServer, threading.Thread]:
    server = run_server(project, host=host, port=port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread
