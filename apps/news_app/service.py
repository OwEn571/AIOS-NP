from __future__ import annotations

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from project_paths import OUTPUT_DIR
from runtime_support.artifacts import describe_artifact_store
from runtime_support.env import load_project_env
from runtime_support.memory import get_workflow_memory_recorder

from .agent_registry import AgentRegistryManager
from .dashboard import build_dashboard_html
from .ecosystem import NewsEcosystemSettings, NewsRunManager, NewsScheduler
from .mcp_support import get_news_mcp_metadata


class RunRequest(BaseModel):
    mode: Literal["serial", "parallel"] = "serial"
    source: str = "manual"
    stages: list[str] | None = Field(default=None, description="Optional subset of workflow stages")
    resume: bool = Field(default=False, description="Resume from existing intermediate artifacts")


class AgentRegistrationRequest(BaseModel):
    id: str | None = None
    name: str
    description: str = ""
    agent_type: Literal["prompt", "tool_call", "python_callable"] = "prompt"
    system_prompt: str | None = None
    model: str | None = None
    require_kernel: bool = True
    enabled: bool = True
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    tools: list[dict[str, Any]] = Field(default_factory=list)
    module: str | None = None
    file_path: str | None = None
    callable_name: str = "run"


class AgentRunRequest(BaseModel):
    input: str
    context: dict[str, Any] = Field(default_factory=dict)
    include_latest_report: bool = False
    include_latest_metrics: bool = False
    include_latest_state: bool = False
    include_latest_snapshot: bool = False
    model: str | None = None
    require_kernel: bool | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_project_env()
    settings = NewsEcosystemSettings.load()
    manager = NewsRunManager(settings=settings)
    agent_registry = AgentRegistryManager(news_manager=manager)
    scheduler = NewsScheduler(manager=manager, settings=settings)
    app.state.manager = manager
    app.state.agent_registry = agent_registry
    app.state.scheduler = scheduler
    scheduler.start()
    try:
        yield
    finally:
        scheduler.stop()


app = FastAPI(
    title="AIOS-NP News Ecosystem",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_manager(request: Request) -> NewsRunManager:
    return request.app.state.manager


def get_scheduler(request: Request) -> NewsScheduler:
    return request.app.state.scheduler


def get_agent_registry(request: Request) -> AgentRegistryManager:
    return request.app.state.agent_registry


def artifact_store_status(request: Request) -> dict:
    manager = get_manager(request)
    registry = get_agent_registry(request)
    manager_store = describe_artifact_store(getattr(manager.store, "store", None))
    registry_store = describe_artifact_store(getattr(registry.store, "store", None))
    payload = {
        "manager_store": manager_store,
        "registry_store": registry_store,
    }
    if manager_store == registry_store:
        payload["shared"] = True
    return payload


def workflow_memory_status() -> dict:
    return get_workflow_memory_recorder().describe()


def latest_output_file(suffix: str) -> Path | None:
    candidates = sorted(
        OUTPUT_DIR.glob(f"新闻报_*.{suffix}"),
        key=lambda file_path: file_path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


@app.get("/", response_class=HTMLResponse)
def dashboard_home(request: Request) -> HTMLResponse:
    manager = get_manager(request)
    payload = manager.dashboard()
    return HTMLResponse(content=build_dashboard_html(payload))


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request) -> HTMLResponse:
    return dashboard_home(request)


@app.get("/health")
def health(request: Request) -> dict:
    manager = get_manager(request)
    agent_registry = get_agent_registry(request)
    scheduler = get_scheduler(request)
    return {
        "status": "ok",
        "service": "news-ecosystem",
        "manager": manager.status(),
        "artifact_store": artifact_store_status(request),
        "workflow_memory": workflow_memory_status(),
        "agent_registry": agent_registry.status(),
        "scheduler": scheduler.status(),
    }


@app.get("/api/ecosystem/status")
def ecosystem_status(request: Request) -> dict:
    manager = get_manager(request)
    agent_registry = get_agent_registry(request)
    scheduler = get_scheduler(request)
    return {
        "manager": manager.status(),
        "artifact_store": artifact_store_status(request),
        "workflow_memory": workflow_memory_status(),
        "agent_registry": agent_registry.status(),
        "scheduler": scheduler.status(),
    }


@app.get("/api/ecosystem/mcp")
def ecosystem_mcp() -> dict:
    return get_news_mcp_metadata()


@app.get("/api/ecosystem/workflow-memory/search")
def search_workflow_memory(
    q: str,
    request: Request,
    k: int = 5,
    category: str | None = None,
    decision_kind: str | None = None,
) -> dict:
    recorder = get_workflow_memory_recorder()
    results = recorder.search_editorial_decisions(
        q,
        category=category,
        decision_kind=decision_kind,
        k=k,
    )
    return {
        "query": q,
        "k": k,
        "category": category,
        "decision_kind": decision_kind,
        "count": len(results),
        "results": results,
        "workflow_memory": recorder.describe(),
    }


@app.get("/api/ecosystem/dashboard")
def ecosystem_dashboard(request: Request, limit: int = 8) -> dict:
    manager = get_manager(request)
    return manager.dashboard(limit=limit)


@app.post("/api/ecosystem/runs")
def trigger_run(payload: RunRequest, request: Request) -> dict:
    manager = get_manager(request)
    result = manager.trigger_run(
        mode=payload.mode,
        source=payload.source,
        stages=payload.stages,
        resume_from_existing=payload.resume,
    )
    if not result.get("accepted"):
        raise HTTPException(status_code=409, detail=result)
    return result


@app.get("/api/ecosystem/runs")
def list_runs(request: Request, limit: int = 20) -> list[dict]:
    manager = get_manager(request)
    return manager.list_runs(limit=limit)


@app.get("/api/ecosystem/runs/{run_id}")
def get_run(run_id: str, request: Request) -> dict:
    manager = get_manager(request)
    result = manager.get_run(run_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return result


@app.get("/api/ecosystem/runs/{run_id}/state")
def get_run_state(run_id: str, request: Request) -> dict:
    manager = get_manager(request)
    result = manager.get_state(run_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"State for run {run_id} not found")
    return result


@app.get("/api/ecosystem/runs/{run_id}/metrics")
def get_run_metrics(run_id: str, request: Request) -> dict:
    manager = get_manager(request)
    result = manager.get_metrics(run_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Metrics for run {run_id} not found")
    return result


@app.get("/api/ecosystem/news/latest")
def latest_news(request: Request) -> dict:
    manager = get_manager(request)
    snapshot = manager.latest_snapshot()
    if not snapshot:
        raise HTTPException(status_code=404, detail="No news snapshot available")
    return snapshot


@app.get("/api/ecosystem/state/latest")
def latest_state(request: Request) -> dict:
    manager = get_manager(request)
    state = manager.latest_state()
    if not state:
        raise HTTPException(status_code=404, detail="No workflow state available")
    return state


@app.get("/api/ecosystem/metrics/latest")
def latest_metrics(request: Request) -> dict:
    manager = get_manager(request)
    metrics = manager.latest_metrics()
    if not metrics:
        raise HTTPException(status_code=404, detail="No workflow metrics available")
    return metrics


@app.get("/api/ecosystem/news/{run_id}")
def news_snapshot(run_id: str, request: Request) -> dict:
    manager = get_manager(request)
    snapshot = manager.get_snapshot(run_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Snapshot for run {run_id} not found")
    return snapshot


@app.get("/api/ecosystem/reports/latest/html", response_class=HTMLResponse)
def latest_report_html(request: Request) -> HTMLResponse:
    manager = get_manager(request)
    snapshot = manager.latest_snapshot()
    if not snapshot:
        raise HTTPException(status_code=404, detail="No news snapshot available")
    html = ((snapshot.get("report") or {}).get("html")) or ""
    if not html:
        raise HTTPException(status_code=404, detail="Latest report HTML not available")
    return HTMLResponse(content=html)


@app.get("/api/ecosystem/reports/{run_id}/html", response_class=HTMLResponse)
def report_html(run_id: str, request: Request) -> HTMLResponse:
    manager = get_manager(request)
    snapshot = manager.get_snapshot(run_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail=f"Snapshot for run {run_id} not found")
    html = ((snapshot.get("report") or {}).get("html")) or ""
    if not html:
        raise HTTPException(status_code=404, detail=f"Report HTML for run {run_id} not available")
    return HTMLResponse(content=html)


@app.get("/api/ecosystem/output/report/latest")
def latest_output_report() -> dict:
    report_json = latest_output_file("json")
    if not report_json:
        raise HTTPException(status_code=404, detail="No output report JSON available")
    return json.loads(report_json.read_text(encoding="utf-8"))


@app.get("/api/ecosystem/output/report/latest/html", response_class=HTMLResponse)
def latest_output_report_html() -> HTMLResponse:
    report_html = latest_output_file("html")
    if not report_html:
        raise HTTPException(status_code=404, detail="No output report HTML available")
    return HTMLResponse(content=report_html.read_text(encoding="utf-8"))


@app.get("/api/agents")
def list_agents(request: Request) -> list[dict]:
    registry = get_agent_registry(request)
    return registry.list_agents()


@app.post("/api/agents/register")
def register_agent(payload: AgentRegistrationRequest, request: Request) -> dict:
    registry = get_agent_registry(request)
    try:
        return registry.register_agent(payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/agents/runs")
def list_agent_runs(request: Request, limit: int = 20, agent_id: str | None = None) -> list[dict]:
    registry = get_agent_registry(request)
    return registry.list_runs(limit=limit, agent_id=agent_id)


@app.get("/api/agents/runs/{run_id}")
def get_agent_run(run_id: str, request: Request) -> dict:
    registry = get_agent_registry(request)
    result = registry.get_run(run_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Agent run {run_id} not found")
    return result


@app.get("/api/agents/{agent_id}")
def get_agent(agent_id: str, request: Request) -> dict:
    registry = get_agent_registry(request)
    result = registry.get_agent(agent_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    return result


@app.delete("/api/agents/{agent_id}")
def delete_agent(agent_id: str, request: Request) -> dict:
    registry = get_agent_registry(request)
    deleted = registry.delete_agent(agent_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Agent {agent_id} not found")
    return {"deleted": True, "agent_id": agent_id}


@app.post("/api/agents/{agent_id}/run")
def run_agent(agent_id: str, payload: AgentRunRequest, request: Request) -> dict:
    registry = get_agent_registry(request)
    try:
        return registry.run_agent(
            agent_id,
            input_text=payload.input,
            context=payload.context,
            include_latest_report=payload.include_latest_report,
            include_latest_metrics=payload.include_latest_metrics,
            include_latest_state=payload.include_latest_state,
            include_latest_snapshot=payload.include_latest_snapshot,
            model=payload.model,
            require_kernel=payload.require_kernel,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
