from __future__ import annotations

import importlib
import importlib.util
import inspect
import re
import threading
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from cerebrum.llm.apis import llm_call_tool, llm_chat
from project_paths import (
    ECOSYSTEM_AGENT_RUNS_DIR,
    ECOSYSTEM_AGENTS_DIR,
    PROJECT_ROOT,
    ensure_runtime_directories,
)
from runtime_support.artifacts import ArtifactStore, get_artifact_store
from runtime_support.env import load_project_env


SUPPORTED_AGENT_TYPES = {"prompt", "tool_call", "python_callable"}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def _slugify(text: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", (text or "").strip().lower()).strip("-")
    if normalized:
        return normalized[:48]
    return f"agent-{uuid.uuid4().hex[:8]}"


def _parse_iso_timestamp(value: str | None) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(value).timestamp()
    except ValueError:
        return 0.0


class AgentRegistryStore:
    def __init__(
        self,
        store: ArtifactStore | None = None,
        agents_dir: Path = ECOSYSTEM_AGENTS_DIR,
        agent_runs_dir: Path = ECOSYSTEM_AGENT_RUNS_DIR,
        max_run_history: int = 200,
    ) -> None:
        ensure_runtime_directories()
        self.store = store or get_artifact_store()
        self.agents_dir = agents_dir
        self.agent_runs_dir = agent_runs_dir
        self.max_run_history = max_run_history
        self.agents_dir.mkdir(parents=True, exist_ok=True)
        self.agent_runs_dir.mkdir(parents=True, exist_ok=True)

    def agent_path(self, agent_id: str) -> Path:
        return self.agents_dir / f"{agent_id}.json"

    def run_path(self, run_id: str) -> Path:
        return self.agent_runs_dir / f"{run_id}.json"

    def save_agent(self, spec: dict[str, Any]) -> str:
        return self.store.write_json(self.agent_path(spec["id"]), spec)

    def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        path = self.agent_path(agent_id)
        if not self.store.exists(path):
            return None
        return self.store.read_json(path)

    def delete_agent(self, agent_id: str) -> bool:
        path = self.agent_path(agent_id)
        if not self.store.exists(path):
            return False
        path.unlink(missing_ok=True)
        return True

    def list_agents(self) -> list[dict[str, Any]]:
        records = [self.store.read_json(path) for path in self.agents_dir.glob("*.json")]
        records.sort(
            key=lambda item: (
                _parse_iso_timestamp(item.get("updated_at")),
                _parse_iso_timestamp(item.get("created_at")),
            ),
            reverse=True,
        )
        return records

    def save_run(self, record: dict[str, Any]) -> str:
        path = self.run_path(record["id"])
        self.store.write_json(path, record)
        self._trim_run_history()
        return str(path)

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        path = self.run_path(run_id)
        if not self.store.exists(path):
            return None
        return self.store.read_json(path)

    def list_runs(self, limit: int = 20, agent_id: str | None = None) -> list[dict[str, Any]]:
        records = [self.store.read_json(path) for path in self.agent_runs_dir.glob("*.json")]
        if agent_id:
            records = [item for item in records if item.get("agent_id") == agent_id]
        records.sort(
            key=lambda item: (
                _parse_iso_timestamp(item.get("started_at")),
                _parse_iso_timestamp(item.get("created_at")),
            ),
            reverse=True,
        )
        return records[:limit]

    def _trim_run_history(self) -> None:
        files = list(self.agent_runs_dir.glob("*.json"))
        files.sort(
            key=lambda path: _parse_iso_timestamp(self.store.read_json(path).get("created_at")),
            reverse=True,
        )
        for stale_file in files[self.max_run_history :]:
            stale_file.unlink(missing_ok=True)


class AgentRegistryManager:
    def __init__(
        self,
        news_manager: Any | None = None,
        store: AgentRegistryStore | None = None,
    ) -> None:
        load_project_env()
        self.news_manager = news_manager
        self.store = store or AgentRegistryStore()
        self._lock = threading.RLock()

    def status(self) -> dict[str, Any]:
        agents = self.store.list_agents()
        return {
            "agent_count": len(agents),
            "enabled_agent_count": sum(1 for item in agents if item.get("enabled", True)),
            "latest_agent": self._summarize_agent(agents[0]) if agents else None,
            "latest_run": self._summarize_run(self.store.list_runs(limit=1)[0]) if self.store.list_runs(limit=1) else None,
        }

    def list_agents(self) -> list[dict[str, Any]]:
        return [self._summarize_agent(item) for item in self.store.list_agents()]

    def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        return self.store.get_agent(agent_id)

    def register_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            normalized = self._normalize_agent_payload(payload)
            existing = self.store.get_agent(normalized["id"])
            if existing:
                normalized["created_at"] = existing.get("created_at") or normalized["created_at"]
            self.store.save_agent(normalized)
            return normalized

    def delete_agent(self, agent_id: str) -> bool:
        with self._lock:
            return self.store.delete_agent(agent_id)

    def list_runs(self, limit: int = 20, agent_id: str | None = None) -> list[dict[str, Any]]:
        return [self._summarize_run(item) for item in self.store.list_runs(limit=limit, agent_id=agent_id)]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        return self.store.get_run(run_id)

    def run_agent(
        self,
        agent_id: str,
        *,
        input_text: str,
        context: dict[str, Any] | None = None,
        include_latest_report: bool = False,
        include_latest_metrics: bool = False,
        include_latest_state: bool = False,
        include_latest_snapshot: bool = False,
        model: str | None = None,
        require_kernel: bool | None = None,
    ) -> dict[str, Any]:
        spec = self.store.get_agent(agent_id)
        if not spec:
            raise ValueError(f"Agent not found: {agent_id}")
        if not spec.get("enabled", True):
            raise ValueError(f"Agent is disabled: {agent_id}")

        run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
        run_record = {
            "id": run_id,
            "agent_id": spec["id"],
            "agent_name": spec["name"],
            "agent_type": spec["agent_type"],
            "status": "running",
            "created_at": now_iso(),
            "started_at": now_iso(),
            "finished_at": None,
            "request": {
                "input": input_text,
                "context": context or {},
                "include_latest_report": include_latest_report,
                "include_latest_metrics": include_latest_metrics,
                "include_latest_state": include_latest_state,
                "include_latest_snapshot": include_latest_snapshot,
                "model_override": model,
                "require_kernel_override": require_kernel,
            },
            "response": None,
            "output_text": None,
            "tool_calls": None,
            "error": None,
            "traceback": None,
        }
        self.store.save_run(run_record)

        try:
            context_bundle = self._build_context_bundle(
                context=context,
                include_latest_report=include_latest_report,
                include_latest_metrics=include_latest_metrics,
                include_latest_state=include_latest_state,
                include_latest_snapshot=include_latest_snapshot,
            )

            if spec["agent_type"] == "prompt":
                response = self._run_prompt_agent(
                    spec,
                    input_text=input_text,
                    context_bundle=context_bundle,
                    model=model,
                    require_kernel=require_kernel,
                )
            elif spec["agent_type"] == "tool_call":
                response = self._run_tool_call_agent(
                    spec,
                    input_text=input_text,
                    context_bundle=context_bundle,
                    model=model,
                )
            elif spec["agent_type"] == "python_callable":
                response = self._run_python_callable_agent(
                    spec,
                    input_text=input_text,
                    context_bundle=context_bundle,
                )
            else:
                raise ValueError(f"Unsupported agent type: {spec['agent_type']}")

            response_payload = self._extract_response_payload(response)
            run_record["status"] = "success"
            run_record["finished_at"] = now_iso()
            run_record["response"] = response_payload
            run_record["output_text"] = self._extract_output_text(response_payload, response)
            run_record["tool_calls"] = response_payload.get("tool_calls")
            self.store.save_run(run_record)
            return run_record
        except Exception as exc:
            run_record["status"] = "failed"
            run_record["finished_at"] = now_iso()
            run_record["error"] = str(exc)
            run_record["traceback"] = traceback.format_exc()
            self.store.save_run(run_record)
            raise

    def _normalize_agent_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        agent_type = str(payload.get("agent_type") or "prompt").strip()
        if agent_type not in SUPPORTED_AGENT_TYPES:
            raise ValueError(f"Unsupported agent_type: {agent_type}")

        name = str(payload.get("name") or "").strip()
        if not name:
            raise ValueError("Agent name is required")

        agent_id = str(payload.get("id") or _slugify(name)).strip()
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{1,63}", agent_id):
            raise ValueError("Agent id must match [a-zA-Z0-9][a-zA-Z0-9_-]{1,63}")

        spec = {
            "id": agent_id,
            "name": name,
            "description": str(payload.get("description") or "").strip(),
            "agent_type": agent_type,
            "enabled": bool(payload.get("enabled", True)),
            "tags": list(payload.get("tags") or []),
            "metadata": dict(payload.get("metadata") or {}),
            "model": str(payload.get("model") or "").strip() or None,
            "require_kernel": bool(payload.get("require_kernel", True)),
            "created_at": now_iso(),
            "updated_at": now_iso(),
        }

        if agent_type in {"prompt", "tool_call"}:
            system_prompt = str(payload.get("system_prompt") or "").strip()
            if not system_prompt:
                raise ValueError("system_prompt is required for prompt/tool_call agents")
            spec["system_prompt"] = system_prompt

        if agent_type == "tool_call":
            tools = list(payload.get("tools") or [])
            if not tools:
                raise ValueError("tools are required for tool_call agents")
            spec["tools"] = tools

        if agent_type == "python_callable":
            module = str(payload.get("module") or "").strip() or None
            file_path = str(payload.get("file_path") or "").strip() or None
            callable_name = str(payload.get("callable_name") or "run").strip()
            if not module and not file_path:
                raise ValueError("module or file_path is required for python_callable agents")
            spec["module"] = module
            spec["file_path"] = file_path
            spec["callable_name"] = callable_name

        return spec

    def _build_context_bundle(
        self,
        *,
        context: dict[str, Any] | None,
        include_latest_report: bool,
        include_latest_metrics: bool,
        include_latest_state: bool,
        include_latest_snapshot: bool,
    ) -> dict[str, Any]:
        bundle: dict[str, Any] = {}
        if context:
            bundle["user_context"] = context

        if not self.news_manager:
            return bundle

        if include_latest_report:
            latest_state = self.news_manager.latest_state()
            if latest_state:
                bundle["latest_report"] = latest_state.get("report")

        if include_latest_metrics:
            latest_metrics = self.news_manager.latest_metrics()
            if latest_metrics:
                bundle["latest_metrics"] = latest_metrics

        if include_latest_state:
            latest_state = self.news_manager.latest_state()
            if latest_state:
                bundle["latest_state"] = {
                    "run": latest_state.get("run"),
                    "coverage": latest_state.get("coverage"),
                    "evaluation": latest_state.get("evaluation"),
                    "report": latest_state.get("report"),
                }

        if include_latest_snapshot:
            latest_snapshot = self.news_manager.latest_snapshot()
            if latest_snapshot:
                bundle["latest_snapshot"] = {
                    "run_id": latest_snapshot.get("run_id"),
                    "generated_at": latest_snapshot.get("generated_at"),
                    "metrics": latest_snapshot.get("metrics"),
                    "report_excerpt": (latest_snapshot.get("report") or {}).get("excerpt"),
                }

        return bundle

    def _build_messages(
        self,
        spec: dict[str, Any],
        *,
        input_text: str,
        context_bundle: dict[str, Any],
    ) -> list[dict[str, str]]:
        user_message = input_text.strip()
        if context_bundle:
            user_message = (
                f"任务：\n{user_message}\n\n"
                f"可用上下文（JSON）：\n{self._format_json(context_bundle)}"
            )

        return [
            {"role": "system", "content": spec["system_prompt"]},
            {"role": "user", "content": user_message},
        ]

    def _run_prompt_agent(
        self,
        spec: dict[str, Any],
        *,
        input_text: str,
        context_bundle: dict[str, Any],
        model: str | None,
        require_kernel: bool | None,
    ) -> dict[str, Any]:
        return llm_chat(
            agent_name=spec["id"],
            messages=self._build_messages(spec, input_text=input_text, context_bundle=context_bundle),
            llms=self._llm_layers(spec, model),
            require_kernel=spec.get("require_kernel", True) if require_kernel is None else require_kernel,
        )

    def _run_tool_call_agent(
        self,
        spec: dict[str, Any],
        *,
        input_text: str,
        context_bundle: dict[str, Any],
        model: str | None,
    ) -> dict[str, Any]:
        return llm_call_tool(
            agent_name=spec["id"],
            messages=self._build_messages(spec, input_text=input_text, context_bundle=context_bundle),
            tools=list(spec.get("tools") or []),
            llms=self._llm_layers(spec, model),
        )

    def _run_python_callable_agent(
        self,
        spec: dict[str, Any],
        *,
        input_text: str,
        context_bundle: dict[str, Any],
    ) -> dict[str, Any]:
        target = self._load_python_callable(spec)
        payload = {
            "input": input_text,
            "context": context_bundle,
            "agent_spec": spec,
        }

        signature = inspect.signature(target)
        if len(signature.parameters) == 0:
            result = target()
        elif len(signature.parameters) == 1:
            result = target(payload)
        else:
            result = target(
                input_text,
                context_bundle,
                spec,
            )

        return {"response": {"response_class": "agent", "response_message": result, "finished": True}}

    def _load_python_callable(self, spec: dict[str, Any]) -> Any:
        module_name = spec.get("module")
        file_path = spec.get("file_path")
        callable_name = spec.get("callable_name") or "run"

        if module_name:
            module = importlib.import_module(module_name)
        else:
            path = Path(str(file_path))
            if not path.is_absolute():
                path = (PROJECT_ROOT / path).resolve()
            if not path.exists():
                raise FileNotFoundError(f"Python agent file not found: {path}")

            dynamic_module_name = f"aios_dynamic_agent_{spec['id']}_{uuid.uuid4().hex[:8]}"
            module_spec = importlib.util.spec_from_file_location(dynamic_module_name, path)
            if not module_spec or not module_spec.loader:
                raise ImportError(f"Unable to load python agent module: {path}")
            module = importlib.util.module_from_spec(module_spec)
            module_spec.loader.exec_module(module)

        target = getattr(module, callable_name, None)
        if not callable(target):
            raise AttributeError(f"Callable not found: {callable_name}")
        return target

    def _llm_layers(self, spec: dict[str, Any], model: str | None) -> list[dict[str, Any]] | None:
        target_model = model or spec.get("model")
        if not target_model:
            return None
        return [
            {
                "name": target_model,
                "backend": "openai",
                "provider": "openai",
            }
        ]

    def _extract_response_payload(self, response: Any) -> dict[str, Any]:
        if isinstance(response, dict) and isinstance(response.get("response"), dict):
            return response["response"]
        if isinstance(response, dict):
            return response
        return {"response_message": response, "finished": True}

    def _extract_output_text(self, payload: dict[str, Any], fallback: Any) -> str:
        message = payload.get("response_message")
        if isinstance(message, str):
            return message
        if message is not None:
            return self._format_json(message)
        if fallback is None:
            return ""
        if isinstance(fallback, str):
            return fallback
        return self._format_json(fallback)

    def _format_json(self, payload: Any) -> str:
        import json

        return json.dumps(payload, ensure_ascii=False, indent=2)

    def _summarize_agent(self, spec: dict[str, Any] | None) -> dict[str, Any] | None:
        if not spec:
            return None
        return {
            "id": spec.get("id"),
            "name": spec.get("name"),
            "description": spec.get("description"),
            "agent_type": spec.get("agent_type"),
            "enabled": spec.get("enabled", True),
            "tags": spec.get("tags") or [],
            "updated_at": spec.get("updated_at"),
            "require_kernel": spec.get("require_kernel", True),
        }

    def _summarize_run(self, record: dict[str, Any] | None) -> dict[str, Any] | None:
        if not record:
            return None
        return {
            "id": record.get("id"),
            "agent_id": record.get("agent_id"),
            "agent_name": record.get("agent_name"),
            "agent_type": record.get("agent_type"),
            "status": record.get("status"),
            "created_at": record.get("created_at"),
            "started_at": record.get("started_at"),
            "finished_at": record.get("finished_at"),
            "error": record.get("error"),
            "output_text": record.get("output_text"),
        }
