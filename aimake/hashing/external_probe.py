"""Probe external model/API providers for revision / etag drift."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from aimake.config.schema import ExternalDependencyConfig


@dataclass
class ProbeResult:
    name: str
    provider: str | None
    model: str | None
    pinned_revision: str | None
    live_revision: str | None
    drifted: bool
    detail: str = ""
    ok: bool = True


def _head(url: str, headers: dict[str, str] | None = None, timeout: float = 10.0) -> dict[str, str]:
    req = urllib.request.Request(url, method="HEAD", headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return {k.lower(): v for k, v in resp.headers.items()}


def _get_json(url: str, headers: dict[str, str] | None = None, timeout: float = 15.0) -> Any:
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def probe_external(dep: ExternalDependencyConfig) -> ProbeResult:
    """Fetch live revision/etag for an external dependency."""
    provider = (dep.provider or "").lower()
    model = dep.model or dep.name
    pinned = dep.revision

    try:
        if dep.probe_url:
            headers = _head(dep.probe_url)
            live = (
                headers.get("etag")
                or headers.get("x-amz-version-id")
                or headers.get("last-modified")
            )
            if live:
                live = live.strip('"')
            return ProbeResult(
                name=dep.name,
                provider=dep.provider,
                model=model,
                pinned_revision=pinned,
                live_revision=live,
                drifted=bool(pinned and live and pinned != live),
                detail=f"HEAD {dep.probe_url}",
            )

        if provider in ("openai", "openai.com"):
            return _probe_openai(dep, model, pinned)
        if provider in ("huggingface", "hf", "huggingface.co"):
            return _probe_huggingface(dep, model, pinned)
        if provider in ("ollama",):
            return _probe_ollama(dep, model, pinned)
        if provider in ("anthropic",):
            # Anthropic has no public model-list etag; use pinned only
            return ProbeResult(
                name=dep.name,
                provider=dep.provider,
                model=model,
                pinned_revision=pinned,
                live_revision=pinned,
                drifted=False,
                detail="anthropic: no public revision API; using pin",
            )

        return ProbeResult(
            name=dep.name,
            provider=dep.provider,
            model=model,
            pinned_revision=pinned,
            live_revision=None,
            drifted=False,
            ok=False,
            detail=f"No probe implementation for provider '{dep.provider}'",
        )
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, KeyError) as e:
        return ProbeResult(
            name=dep.name,
            provider=dep.provider,
            model=model,
            pinned_revision=pinned,
            live_revision=None,
            drifted=False,
            ok=False,
            detail=str(e),
        )


def _probe_openai(dep: ExternalDependencyConfig, model: str, pinned: str | None) -> ProbeResult:
    key = os.environ.get("OPENAI_API_KEY", "")
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    data = _get_json(f"https://api.openai.com/v1/models/{model}", headers=headers)
    live = data.get("created")
    live_s = str(live) if live is not None else data.get("id")
    return ProbeResult(
        name=dep.name,
        provider=dep.provider,
        model=model,
        pinned_revision=pinned,
        live_revision=str(live_s) if live_s is not None else None,
        drifted=bool(pinned and live_s is not None and str(pinned) != str(live_s)),
        detail="openai /v1/models",
    )


def _probe_huggingface(dep: ExternalDependencyConfig, model: str, pinned: str | None) -> ProbeResult:
    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    url = f"https://huggingface.co/api/models/{model}"
    data = _get_json(url, headers=headers)
    live = data.get("sha") or data.get("lastModified")
    return ProbeResult(
        name=dep.name,
        provider=dep.provider,
        model=model,
        pinned_revision=pinned,
        live_revision=live,
        drifted=bool(pinned and live and pinned != live),
        detail="huggingface model sha",
    )


def _probe_ollama(dep: ExternalDependencyConfig, model: str, pinned: str | None) -> ProbeResult:
    host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    data = _get_json(f"{host}/api/show", headers={"Content-Type": "application/json"})
    # /api/show expects POST with model — fallback to tags list
    try:
        req = urllib.request.Request(
            f"{host}/api/show",
            data=json.dumps({"name": model}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        live = data.get("digest") or data.get("modelfile", "")[:32]
    except Exception:
        tags = _get_json(f"{host}/api/tags")
        live = None
        for m in tags.get("models") or []:
            if m.get("name") == model or m.get("model") == model:
                live = m.get("digest")
                break
    return ProbeResult(
        name=dep.name,
        provider=dep.provider,
        model=model,
        pinned_revision=pinned,
        live_revision=live,
        drifted=bool(pinned and live and pinned != live),
        detail="ollama digest",
    )


def probe_artifact_externals(
    deps: list[ExternalDependencyConfig],
) -> list[ProbeResult]:
    return [probe_external(d) for d in deps if d.probe and not d.volatile]


def effective_revision(dep: ExternalDependencyConfig, probe: ProbeResult | None) -> str | None:
    """Revision string to include in fingerprints."""
    if dep.volatile:
        return None
    if (
        dep.probe
        and dep.probe_mode == "invalidate"
        and probe
        and probe.ok
        and probe.live_revision
    ):
        return probe.live_revision
    return dep.revision
