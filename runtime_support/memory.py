from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from runtime_support.env import load_project_env


def _bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _optional_positive_float_env(name: str) -> float | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    try:
        value = float(raw.strip())
    except ValueError:
        return None
    return value if value > 0 else None


@dataclass
class WorkflowMemoryRecorder:
    agent_name: str
    base_url: str
    enabled: bool
    timeout_seconds: float
    ttl_seconds: float | None = None
    write_count: int = 0
    failed_write_count: int = 0
    search_count: int = 0
    failed_search_count: int = 0
    expired_filter_count: int = 0
    expired_prune_count: int = 0
    last_memory_id: str | None = None
    last_error: str | None = None
    last_search_query: str | None = None

    @classmethod
    def from_env(cls) -> "WorkflowMemoryRecorder":
        load_project_env()
        timeout_raw = os.getenv("AIOS_WORKFLOW_MEMORY_TIMEOUT_SECONDS", "8").strip()
        try:
            timeout_seconds = float(timeout_raw)
        except ValueError:
            timeout_seconds = 8.0
        return cls(
            agent_name=os.getenv("AIOS_WORKFLOW_MEMORY_AGENT_NAME", "news_workflow_memory").strip(),
            base_url=os.getenv("CEREBRUM_KERNEL_URL", "http://127.0.0.1:8001").strip(),
            enabled=_bool_env("AIOS_WORKFLOW_MEMORY_ENABLED", True),
            timeout_seconds=timeout_seconds if timeout_seconds > 0 else 8.0,
            ttl_seconds=_optional_positive_float_env("AIOS_WORKFLOW_MEMORY_TTL_SECONDS"),
        )

    def describe(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "agent_name": self.agent_name,
            "base_url": self.base_url,
            "timeout_seconds": self.timeout_seconds,
            "ttl_seconds": self.ttl_seconds,
            "write_count": self.write_count,
            "failed_write_count": self.failed_write_count,
            "search_count": self.search_count,
            "failed_search_count": self.failed_search_count,
            "expired_filter_count": self.expired_filter_count,
            "expired_prune_count": self.expired_prune_count,
            "last_memory_id": self.last_memory_id,
            "last_error": self.last_error,
            "last_search_query": self.last_search_query,
        }

    def record(
        self,
        *,
        content: str,
        metadata: dict[str, Any],
        agent_name: str | None = None,
        agentic: bool = False,
    ) -> bool:
        if not self.enabled:
            return False

        try:
            from cerebrum.memory.apis import create_agentic_memory, create_memory

            request_fn = create_agentic_memory if agentic else create_memory
            response = request_fn(
                agent_name or self.agent_name,
                content,
                metadata=metadata,
                base_url=self.base_url,
                timeout=self.timeout_seconds,
            )
            payload = self._unwrap_response(response)
            success = bool(payload.get("success") or payload.get("memory_id"))
            if success:
                self.write_count += 1
                self.last_memory_id = payload.get("memory_id")
                self.last_error = None
                return True
            self.failed_write_count += 1
            self.last_error = str(payload.get("error") or "Unknown memory write error")
            return False
        except Exception as exc:
            self.failed_write_count += 1
            self.last_error = str(exc)
            return False

    def search(self, query: str, *, k: int = 5) -> list[dict[str, Any]]:
        if not self.enabled or not query.strip():
            return []

        self.last_search_query = query
        try:
            from cerebrum.memory.apis import search_memories

            response = search_memories(
                self.agent_name,
                query,
                k=k,
                base_url=self.base_url,
                timeout=self.timeout_seconds,
            )
            payload = self._unwrap_response(response)
            results = payload.get("search_results") or []
            if not isinstance(results, list):
                results = []
            expired_ids: list[str] = []
            filtered_results: list[dict[str, Any]] = []
            for result in results:
                if not isinstance(result, dict):
                    continue
                if self._is_expired(result):
                    self.expired_filter_count += 1
                    memory_id = str(result.get("memory_id") or "").strip()
                    if memory_id:
                        expired_ids.append(memory_id)
                    continue
                filtered_results.append(result)
            self.search_count += 1
            self.last_error = None
            if expired_ids:
                self._prune_memories(expired_ids)
            return filtered_results
        except Exception as exc:
            self.failed_search_count += 1
            self.last_error = str(exc)
            return []

    def search_editorial_decisions(
        self,
        query: str,
        *,
        category: str | None = None,
        decision_kind: str | None = None,
        k: int = 5,
    ) -> list[dict[str, Any]]:
        matches = self.search(query, k=max(k, 8))
        filtered: list[dict[str, Any]] = []

        for item in matches:
            tags = [str(tag) for tag in (item.get("tags") or [])]
            item_category = str(item.get("category") or "")

            parsed = dict(item)
            parsed_body = self._parse_content_json(parsed.get("content"))
            if parsed_body:
                parsed["body"] = parsed_body
                if category and str(parsed_body.get("category") or item_category) != category:
                    continue
                if decision_kind and str(parsed_body.get("decision_kind") or "") != decision_kind:
                    continue
            else:
                if "editorial_decision" not in tags:
                    continue
                if category and item_category != category:
                    continue
                if decision_kind and decision_kind not in tags:
                    continue
            filtered.append(parsed)

        return filtered[:k]

    def record_editorial_decision(
        self,
        *,
        decision_kind: str,
        category: str,
        topic: str,
        accepted: bool,
        score: int,
        reasons: list[str],
        metadata: dict[str, Any] | None = None,
    ) -> bool:
        extra = dict(metadata or {})
        body = {
            "decision_kind": decision_kind,
            "category": category,
            "topic": topic,
            "accepted": accepted,
            "score": score,
            "reasons": reasons,
            **extra,
        }
        content = json.dumps(body, ensure_ascii=False, indent=2)
        tags = [
            "workflow",
            "editorial_decision",
            decision_kind,
            "accepted" if accepted else "rejected",
            category,
        ]
        return self.record(
            content=content,
            metadata={
                "kind": "editorial_decision",
                "decision_kind": decision_kind,
                "category": category,
                "topic": topic,
                "accepted": accepted,
                "score": score,
                "context": f"{decision_kind}:{'accepted' if accepted else 'rejected'}",
                "tags": tags,
                **extra,
            },
            agentic=False,
        )

    def _unwrap_response(self, response: Any) -> dict[str, Any]:
        if isinstance(response, dict) and isinstance(response.get("response"), dict):
            return response["response"]
        if isinstance(response, dict):
            return response
        return {}

    def _parse_content_json(self, content: Any) -> dict[str, Any] | None:
        if not isinstance(content, str) or not content.strip():
            return None
        try:
            parsed = json.loads(content)
        except Exception:
            return None
        return parsed if isinstance(parsed, dict) else None

    def _is_expired(self, item: dict[str, Any]) -> bool:
        if not self.ttl_seconds or self.ttl_seconds <= 0:
            return False
        timestamp = self._extract_timestamp(item)
        if timestamp is None:
            return False
        age_seconds = (datetime.now() - timestamp).total_seconds()
        return age_seconds > self.ttl_seconds

    def _extract_timestamp(self, item: dict[str, Any]) -> datetime | None:
        raw_timestamp = item.get("timestamp")
        metadata = item.get("metadata")
        if not raw_timestamp and isinstance(metadata, dict):
            raw_timestamp = metadata.get("timestamp")
        if raw_timestamp is None:
            return None
        if isinstance(raw_timestamp, datetime):
            return raw_timestamp
        if isinstance(raw_timestamp, (int, float)):
            try:
                return datetime.fromtimestamp(raw_timestamp)
            except (OSError, OverflowError, ValueError):
                return None
        if not isinstance(raw_timestamp, str):
            return None

        value = raw_timestamp.strip()
        if not value:
            return None
        for fmt in ("%Y%m%d%H%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        return parsed.replace(tzinfo=None) if parsed.tzinfo else parsed

    def _prune_memories(self, memory_ids: list[str]) -> None:
        unique_ids = list(dict.fromkeys(memory_ids))
        if not unique_ids:
            return
        try:
            from cerebrum.memory.apis import delete_memory

            for memory_id in unique_ids:
                try:
                    response = delete_memory(
                        self.agent_name,
                        memory_id,
                        base_url=self.base_url,
                        timeout=self.timeout_seconds,
                    )
                    payload = self._unwrap_response(response)
                    if bool(payload.get("success")):
                        self.expired_prune_count += 1
                except Exception:
                    continue
        except Exception:
            return


_DEFAULT_RECORDER: WorkflowMemoryRecorder | None = None


def get_workflow_memory_recorder() -> WorkflowMemoryRecorder:
    global _DEFAULT_RECORDER
    if _DEFAULT_RECORDER is None:
        _DEFAULT_RECORDER = WorkflowMemoryRecorder.from_env()
    return _DEFAULT_RECORDER


def reset_workflow_memory_recorder() -> None:
    global _DEFAULT_RECORDER
    _DEFAULT_RECORDER = None
