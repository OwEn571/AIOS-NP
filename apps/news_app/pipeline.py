from __future__ import annotations

import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

from project_paths import PROJECT_ROOT, ensure_runtime_directories

from agents.hot_api_agent.agent import HotApiAgent
from agents.maker_agent.agent import MakerAgent
from agents.sort_agent.agent import SortAgent
from agents.web_search_agent.agent import WebSearchAgent
from runtime_support.artifacts import get_artifact_store
from runtime_support.env import load_project_env
from runtime_support.memory import get_workflow_memory_recorder

from .config import NewsAppConfig, load_news_app_config
from .editorial import evaluate_generation_input
from .news_registry import news_category_file_map


news_gen_path = PROJECT_ROOT / "agents" / "news_generation_agent"
if str(news_gen_path) not in sys.path:
    sys.path.insert(0, str(news_gen_path))
from test_parallel_agents import ParallelNewsTest  # type: ignore


MODE_LABELS = {
    "parallel": "并行",
    "serial": "串行",
}

STAGE_LABELS = {
    "hot_api": "热榜获取",
    "sort": "分类整理",
    "search": "Web搜索",
    "generate": "新闻生成",
    "review": "新闻审阅",
    "report": "新闻报制作",
}


class NewsWorkflowApp:
    """AIOS-NP 新闻应用层。

    这层只负责业务工作流编排，把 AIOS 内核、agent 和新闻任务解耦开。
    """

    def __init__(
        self,
        mode: str = "parallel",
        config_path: str | Path | None = None,
        zh_api_key: str | None = None,
        tavily_api_key: str | None = None,
        stage_order_override: list[str] | tuple[str, ...] | None = None,
        resume_from_existing: bool = False,
        event_handler: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        if mode not in MODE_LABELS:
            raise ValueError(f"Unsupported workflow mode: {mode}")

        load_project_env()
        self.mode = mode
        self.config: NewsAppConfig = load_news_app_config(config_path)
        self.zh_api_key = zh_api_key or os.getenv("ZH_API_KEY")
        self.tavily_api_key = tavily_api_key or os.getenv("TAVILY_API_KEY")
        self.workflow_stage_order = tuple(stage_order_override or self.config.workflow_stage_order)
        self.resume_from_existing = bool(
            resume_from_existing
            or (self.workflow_stage_order and self.workflow_stage_order[0] != "hot_api")
        )
        self.event_handler = event_handler
        self.category_files = news_category_file_map()
        self.store = get_artifact_store()
        self.memory_recorder = get_workflow_memory_recorder()

        ensure_runtime_directories()
        self.intermediate_dir = self.config.intermediate_dir
        self.output_dir = self.config.output_dir
        self.store.ensure_dir(self.intermediate_dir)
        self.store.ensure_dir(self.output_dir)
        self._components: dict[str, Any] = {}

    @property
    def domain_workers(self) -> int:
        if self.mode == "parallel":
            return self.config.parallel_domain_workers
        return self.config.serial_domain_workers

    def run(self) -> dict[str, Any]:
        print(f"🚀 开始 AIOS 新闻应用工作流（{MODE_LABELS[self.mode]}模式）...")
        print("=" * 60)
        print(f"📦 App 配置: {self.config.config_path}")
        self._emit_event(
            "run_started",
            mode=self.mode,
            config_path=str(self.config.config_path),
            stages=list(self.workflow_stage_order),
            resume_from_existing=self.resume_from_existing,
        )

        if self.resume_from_existing:
            print("♻️ 进入恢复执行模式，保留已有输入产物...")
            self._prepare_resume_artifacts()
        else:
            print("🧹 清空 intermediate 目录...")
            self._clean_intermediate_dir()

        pipeline_time_stats: dict[str, float] = {}
        raw_stage_results: dict[str, dict[str, Any]] = {}
        started_at = time.time()

        try:
            for stage_name in self.workflow_stage_order:
                stage_label = self._format_stage_label(stage_name)
                print(f"\n🧩 阶段: {stage_label}")
                print("-" * 40)
                self._emit_event("stage_started", stage=stage_name, label=stage_label)
                step_started_at = time.time()
                result = self._run_stage(stage_name)
                stage_duration = time.time() - step_started_at
                pipeline_time_stats[stage_label] = stage_duration
                raw_stage_results[stage_name] = result
                self._emit_event(
                    "stage_finished",
                    stage=stage_name,
                    label=stage_label,
                    duration=stage_duration,
                    status=result.get("status"),
                    summary=self._result_message(result),
                    output_count=self._estimate_stage_output_count(stage_name, result),
                    domain_breakdown=self._summarize_stage_domains(result),
                )

                if result.get("status") != "success":
                    raise RuntimeError(f"{stage_label}失败: {self._result_message(result)}")

            total_time = time.time() - started_at
            print("\n" + "=" * 60)
            print(f"🎉 {MODE_LABELS[self.mode]}工作流完成！")
            print("=" * 60)
            print(f"⏱️ 总耗时: {total_time:.2f} 秒")

            print("\n📊 详细时间统计:")
            print("-" * 40)
            for step, duration in pipeline_time_stats.items():
                percentage = (duration / total_time) * 100 if total_time > 0 else 0
                print(f"  {step}: {duration:.2f}秒 ({percentage:.1f}%)")

            run_result = {
                "status": "success",
                "message": f"{MODE_LABELS[self.mode]}工作流完成",
                "mode": self.mode,
                "total_time": total_time,
                "pipeline_time_stats": pipeline_time_stats,
                "stage_results": raw_stage_results,
                "results": self._build_compatibility_results(raw_stage_results),
            }
            self._emit_event(
                "run_finished",
                status="success",
                total_time=total_time,
                stage_count=len(self.workflow_stage_order),
            )
            return run_result

        except Exception as exc:
            print(f"\n❌ 工作流执行失败: {exc}")
            self._emit_event(
                "run_finished",
                status="failed",
                error=str(exc),
                stage_count=len(raw_stage_results),
            )
            return {
                "status": "failed",
                "message": f"工作流执行失败: {exc}",
                "mode": self.mode,
                "pipeline_time_stats": pipeline_time_stats,
                "stage_results": raw_stage_results,
            }

    def _build_compatibility_results(
        self,
        raw_stage_results: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        search_result = raw_stage_results.get("search")
        generation_result = raw_stage_results.get("generate")
        review_result = raw_stage_results.get("review")

        compatibility_results: dict[str, Any] = {
            "hot_api": raw_stage_results.get("hot_api"),
            "sort": raw_stage_results.get("sort"),
            "web_search": search_result,
            "news_generation": generation_result,
            "news_review": review_result,
            "news_report": raw_stage_results.get("report"),
        }

        if generation_result or review_result:
            compatibility_results["news_processing"] = {
                "status": "success",
                "message": "新闻生成和审阅完成",
                "news_files": (generation_result or {}).get("news_files", [])
                + (review_result or {}).get("news_files", []),
            }

        return compatibility_results

    def _format_stage_label(self, stage_name: str) -> str:
        label = STAGE_LABELS[stage_name]
        if stage_name in {"search", "generate", "review"}:
            return f"{MODE_LABELS[self.mode]}{label}"
        return label

    def _run_stage(self, stage_name: str) -> dict[str, Any]:
        stage_handlers: dict[str, Callable[[], dict[str, Any]]] = {
            "hot_api": self._run_hot_api_stage,
            "sort": self._run_sort_stage,
            "search": self._run_search_stage,
            "generate": self._run_generate_stage,
            "review": self._run_review_stage,
            "report": self._run_report_stage,
        }
        return stage_handlers[stage_name]()

    def _clean_intermediate_dir(self) -> None:
        try:
            if not self.intermediate_dir.exists():
                return

            for file_path in sorted(self.intermediate_dir.iterdir()):
                if file_path.is_file():
                    try:
                        file_path.unlink()
                        print(f"  删除: {file_path.name}")
                    except Exception as exc:
                        print(f"  删除失败 {file_path.name}: {exc}")
            print("✅ intermediate 目录已清空")
        except Exception as exc:
            print(f"⚠️ 清理 intermediate 目录失败: {exc}")

    def _prepare_resume_artifacts(self) -> None:
        if not self.workflow_stage_order:
            return

        cleanup_patterns = self._resume_cleanup_patterns(self.workflow_stage_order[0])
        if not cleanup_patterns:
            print("♻️ 当前恢复阶段不需要清理旧产物")
            return

        removed = 0
        for pattern in cleanup_patterns:
            for file_path in sorted(self.intermediate_dir.glob(pattern)):
                if not file_path.is_file():
                    continue
                try:
                    file_path.unlink()
                    removed += 1
                    print(f"  删除旧产物: {file_path.name}")
                except Exception as exc:
                    print(f"  删除失败 {file_path.name}: {exc}")
        print(f"♻️ 恢复执行准备完成，清理了 {removed} 个旧产物")

    def _resume_cleanup_patterns(self, first_stage: str) -> list[str]:
        if first_stage == "hot_api":
            return ["*"]
        if first_stage == "sort":
            return [
                "*_api.txt",
                "*_search.txt",
                "*_image.txt",
                "*_news.txt",
                "*_reviewed.txt",
                "*_sources.json",
            ]
        if first_stage == "search":
            return [
                "*_search.txt",
                "*_image.txt",
                "*_news.txt",
                "*_reviewed.txt",
                "*_sources.json",
            ]
        if first_stage == "generate":
            return ["*_news.txt", "*_reviewed.txt", "*_sources.json"]
        if first_stage == "review":
            return ["*_reviewed.txt"]
        return []

    def _run_hot_api_stage(self) -> dict[str, Any]:
        if not self.zh_api_key:
            return {"status": "skipped", "result": "未提供 ZH_API_KEY"}

        return self._hot_api_agent().run(
            task_input="获取热榜",
            api_key=self.zh_api_key,
            platform=self.config.hot_api_platform,
            platforms=self.config.hot_api_platforms,
            max_items=self.config.hot_api_max_items,
        )

    def _run_sort_stage(self) -> dict[str, Any]:
        hot_data_file = self.intermediate_dir / "hot_api.txt"
        return self._sort_agent().run(str(hot_data_file))

    def _run_search_stage(self) -> dict[str, Any]:
        if not self.tavily_api_key:
            return {"status": "skipped", "message": "未提供 TAVILY_API_KEY"}

        return self._web_search_agent().run(str(self.intermediate_dir))

    def _run_generate_stage(self) -> dict[str, Any]:
        search_files = self._discover_files("_search.txt")
        if not search_files:
            return {"status": "failed", "message": "没有找到搜索文件"}

        domain_groups = self._group_files_by_domain(search_files)
        return self._run_domain_stage(
            domain_groups=domain_groups,
            phase_label="新闻生成",
            process_domain=self._process_domain_generation,
            result_collection_key="news_files",
            success_summary="成功生成 {count} 条新闻",
        )

    def _run_review_stage(self) -> dict[str, Any]:
        news_files = self._discover_files("_news.txt")
        if not news_files:
            return {"status": "failed", "message": "没有找到新闻文件"}

        domain_groups = self._group_files_by_domain(news_files)
        return self._run_domain_stage(
            domain_groups=domain_groups,
            phase_label="新闻审阅",
            process_domain=self._process_domain_review,
            result_collection_key="reviewed_files",
            success_summary="成功审阅 {count} 条新闻",
        )

    def _run_report_stage(self) -> dict[str, Any]:
        return self._maker_agent().run(str(self.intermediate_dir), str(self.output_dir))

    def _run_domain_stage(
        self,
        *,
        domain_groups: dict[str, list[str]],
        phase_label: str,
        process_domain: Callable[[str, list[str]], dict[str, Any]],
        result_collection_key: str,
        success_summary: str,
    ) -> dict[str, Any]:
        print(f"📊 发现 {len(domain_groups)} 个领域")

        collected_files: list[str] = []
        domain_results: dict[str, dict[str, Any]] = {}

        if self.mode == "parallel":
            max_workers = min(max(len(domain_groups), 1), self.domain_workers)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = {
                    executor.submit(process_domain, domain, files): domain
                    for domain, files in domain_groups.items()
                }
                for future in as_completed(futures):
                    domain = futures[future]
                    try:
                        result = future.result()
                    except Exception as exc:
                        result = {"status": "failed", "domain": domain, "error": str(exc)}

                    domain_results[domain] = result
                    collected_files.extend(result.get(result_collection_key, []))
                    self._print_domain_outcome(domain, phase_label, result)
        else:
            for domain, files in domain_groups.items():
                started_at = time.time()
                result = process_domain(domain, files)
                domain_results[domain] = result
                collected_files.extend(result.get(result_collection_key, []))
                self._print_domain_outcome(
                    domain,
                    phase_label,
                    result,
                    elapsed=time.time() - started_at,
                )

        failed_domains = [
            domain
            for domain, result in domain_results.items()
            if result.get("status") != "success"
        ]
        if failed_domains:
            return {
                "status": "failed",
                "message": f"{phase_label}失败: {', '.join(failed_domains)}",
                "domain_results": domain_results,
            }

        return {
            "status": "success",
            "message": success_summary.format(count=len(collected_files)),
            "news_files": collected_files,
            "domain_results": domain_results,
        }

    def _print_domain_outcome(
        self,
        domain: str,
        phase_label: str,
        result: dict[str, Any],
        elapsed: float | None = None,
    ) -> None:
        status = "✅" if result.get("status") == "success" else "❌"
        count = result.get("count")
        suffix = f"，产出 {count} 个文件" if count is not None else ""
        duration = f"，耗时 {elapsed:.2f}s" if elapsed is not None else ""
        print(f"{status} {domain} {phase_label}{suffix}{duration}")
        self._emit_event(
            "domain_finished",
            domain=domain,
            phase=phase_label,
            status=result.get("status"),
            count=count,
            elapsed=elapsed,
        )

    def _discover_files(self, suffix: str) -> list[str]:
        if not self.intermediate_dir.exists():
            return []
        return sorted(
            str(path)
            for path in self.intermediate_dir.iterdir()
            if path.is_file() and path.name.endswith(suffix)
        )

    def _group_files_by_domain(self, file_paths: list[str]) -> dict[str, list[str]]:
        domain_groups: dict[str, list[str]] = {}
        for file_path in sorted(file_paths):
            filename = Path(file_path).name
            domain = filename.split("_", 1)[0]
            domain_groups.setdefault(domain, []).append(file_path)
        return domain_groups

    def _process_domain_generation(self, domain: str, search_files: list[str]) -> dict[str, Any]:
        try:
            print(f"🔧 生成 {domain} 领域新闻，{len(search_files)} 个文件")
            generated_news = []
            for search_file in search_files:
                news_file = self._generate_news_from_search(search_file, domain)
                if news_file:
                    generated_news.append(news_file)

            return {
                "status": "success",
                "domain": domain,
                "news_files": generated_news,
                "count": len(generated_news),
            }
        except Exception as exc:
            return {"status": "failed", "domain": domain, "error": str(exc)}

    def _process_domain_review(self, domain: str, news_files: list[str]) -> dict[str, Any]:
        try:
            print(f"🔧 审阅 {domain} 领域新闻，{len(news_files)} 个文件")
            reviewed_files = []
            for news_file in news_files:
                reviewed_file = self._review_news(news_file, domain)
                if reviewed_file:
                    reviewed_files.append(reviewed_file)

            return {
                "status": "success",
                "domain": domain,
                "reviewed_files": reviewed_files,
                "count": len(reviewed_files),
            }
        except Exception as exc:
            return {"status": "failed", "domain": domain, "error": str(exc)}

    def _generate_news_from_search(self, search_file: str, domain: str) -> str | None:
        max_retries = self.config.generation_retry_limit
        search_path = Path(search_file)
        topic = self._resolve_topic_for_search_file(search_path, domain)
        last_error_message = ""
        last_generation_result: dict[str, Any] | None = None
        attempted_count = 0

        for attempt in range(max_retries):
            attempted_count = attempt + 1
            try:
                search_content = self.store.read_text(search_path)
                memory_hints = self.memory_recorder.search_editorial_decisions(
                    f"{domain} {topic}",
                    category=domain,
                    decision_kind="generation_gate",
                    k=3,
                )
                if memory_hints:
                    print(f"🧠 找到 {len(memory_hints)} 条相似编辑记忆: {topic}")
                generation_gate = evaluate_generation_input(
                    domain,
                    topic,
                    search_content,
                    memory_hints=memory_hints,
                )
                self._persist_generation_gate(search_path, generation_gate, memory_hints)
                if not generation_gate.accepted:
                    print(f"⛔ 跳过不具备新闻性的主题: {topic}")
                    for reason in generation_gate.reasons:
                        print(f"   - {reason}")
                    return None

                print(f"🔄 尝试生成新闻 (第{attempt + 1}次): {search_path.name}")
                news_result = self._news_generator().generate_news(
                    search_content,
                    topic,
                    domain,
                )
                last_generation_result = news_result

                if not news_result or not all(
                    news_result.get(part) for part in ("title", "summary", "content")
                ):
                    raise RuntimeError(news_result.get("error") or "新闻生成结果为空或格式错误")

                from agents.news_generation_agent.judge_agent import JudgeAgent

                judge_agent = JudgeAgent()
                news_filepath = judge_agent.save_news_to_file(
                    news_result["title"],
                    news_result["summary"],
                    news_result["content"],
                    topic,
                    search_content,
                )

                if news_filepath:
                    failure_path = search_path.with_name(
                        search_path.name.replace("_search.txt", "_generation_failure.json")
                    )
                    if self.store.exists(failure_path):
                        self.store.delete_file(failure_path)
                    print(f"✅ 生成新闻成功: {Path(news_filepath).name}")
                    return news_filepath

                raise RuntimeError("新闻保存失败")

            except Exception as exc:
                error_message = str(exc)
                last_error_message = error_message
                print(f"❌ 生成新闻失败 (第{attempt + 1}次): {error_message}")
                if self._is_length_error(error_message) and self._remove_last_search_result(search_file):
                    print("🔄 搜索结果已截断，准备重试...")
                    continue
                break

        self._persist_generation_failure(
            search_path=search_path,
            category=domain,
            topic=topic,
            attempted_count=attempted_count,
            error_message=last_error_message or "新闻生成结果为空或格式错误",
            generation_result=last_generation_result,
        )
        print(f"❌ 生成新闻最终失败: {search_file}")
        return None

    def _resolve_topic_for_search_file(self, search_path: Path, domain: str) -> str:
        match = re.search(rf"^{re.escape(domain)}_(\d+)_search\.txt$", search_path.name)
        if not match:
            return domain

        topic_index = int(match.group(1))
        category_filename = self.category_files.get(domain)
        if not category_filename:
            return f"{domain}新闻{topic_index}"

        category_path = self.intermediate_dir / category_filename
        if not category_path.exists():
            return f"{domain}新闻{topic_index}"

        topics: list[str] = []
        for line in self.store.read_text(category_path).splitlines():
            normalized = line.strip()
            if normalized.startswith("- "):
                normalized = normalized[2:].strip()
            if normalized:
                topics.append(normalized)

        if topic_index < len(topics):
            return topics[topic_index]
        return f"{domain}新闻{topic_index}"

    def _persist_generation_gate(
        self,
        search_path: Path,
        gate_result: Any,
        memory_hints: list[dict[str, Any]] | None = None,
    ) -> None:
        gate_path = search_path.with_name(search_path.name.replace("_search.txt", "_gate.json"))
        payload = gate_result.to_dict() if hasattr(gate_result, "to_dict") else dict(gate_result)
        if memory_hints:
            payload["memory_hints"] = [
                {
                    "memory_id": hint.get("memory_id"),
                    "category": hint.get("category"),
                    "tags": hint.get("tags") or [],
                    "score": hint.get("score"),
                    "body": hint.get("body") or {},
                }
                for hint in memory_hints
            ]
        self.store.write_json(gate_path, payload)
        try:
            self.memory_recorder.record_editorial_decision(
                decision_kind="generation_gate",
                category=str(payload.get("category") or ""),
                topic=str(payload.get("topic") or search_path.stem),
                accepted=bool(payload.get("accepted", False)),
                score=int(payload.get("score") or 0),
                reasons=list(payload.get("reasons") or []),
                metadata={
                    "artifact_path": str(gate_path),
                    "source_count": int(payload.get("source_count") or 0),
                    "trusted_source_count": int(payload.get("trusted_source_count") or 0),
                    "low_signal_source_count": int(payload.get("low_signal_source_count") or 0),
                    "memory_hint_count": int(payload.get("memory_hint_count") or 0),
                    "memory_score_delta": int(payload.get("memory_score_delta") or 0),
                },
            )
        except Exception:
            pass

    def _persist_generation_failure(
        self,
        *,
        search_path: Path,
        category: str,
        topic: str,
        attempted_count: int,
        error_message: str,
        generation_result: dict[str, Any] | None = None,
    ) -> None:
        failure_path = search_path.with_name(
            search_path.name.replace("_search.txt", "_generation_failure.json")
        )
        payload: dict[str, Any] = {
            "topic": topic,
            "category": category,
            "attempted_count": attempted_count,
            "error": error_message,
            "search_file": str(search_path),
        }

        if generation_result:
            payload["judgments"] = generation_result.get("judgments") or {}
            payload["partial_outputs"] = {
                part: generation_result.get(part) or ""
                for part in ("title", "summary", "content")
            }

        self.store.write_json(failure_path, payload)

    def _is_length_error(self, error_message: str) -> bool:
        lower = error_message.lower()
        return any(
            marker in lower
            for marker in (
                "maximum context length",
                "token limit",
                "context length",
                "too long",
                "exceeds maximum",
                "nonetype",
                "attribute 'strip'",
            )
        )

    def _remove_last_search_result(self, search_file: str) -> bool:
        try:
            search_path = Path(search_file)
            content = self.store.read_text(search_path)
            result_blocks = re.split(r"【结果 \d+】", content)
            if len(result_blocks) <= 2:
                print(f"⚠️ 搜索结果太少，无法截断: {search_path.name}")
                return False

            new_content = result_blocks[0]
            for index, block in enumerate(result_blocks[1:-1], start=1):
                new_content += f"【结果 {index}】{block}"

            self.store.write_text(search_path, new_content)
            print(f"✂️ 已删除最后一个搜索结果: {search_path.name}")
            return True
        except Exception as exc:
            print(f"❌ 删除搜索结果失败: {exc}")
            return False

    def _review_news(self, news_file: str, domain: str) -> str | None:
        try:
            from agents.workflow_agent.agent import WorkflowAgent

            workflow_agent = WorkflowAgent("workflow_agent")
            workflow_result = workflow_agent.run_workflow_with_domain(news_file, domain)
            if workflow_result.get("status") == "success":
                reviewed_file = workflow_result.get("reviewed_file")
                if reviewed_file:
                    print(f"✅ 审阅完成: {Path(reviewed_file).name}")
                return reviewed_file

            print(f"⚠️ 审阅失败: {Path(news_file).name}")
            return None
        except Exception as exc:
            print(f"❌ 审阅异常 {news_file}: {exc}")
            return None

    def _result_message(self, result: dict[str, Any]) -> str:
        for key in ("message", "result", "error"):
            value = result.get(key)
            if value:
                return str(value)
        return "未知错误"

    def _estimate_stage_output_count(self, stage_name: str, result: dict[str, Any]) -> int:
        if stage_name == "hot_api":
            payload = result.get("payload") or {}
            return int(payload.get("total_topics") or 0)
        if stage_name == "sort":
            return len(result.get("saved_files") or [])
        if stage_name == "search":
            return len(result.get("search_files") or [])
        if stage_name == "generate":
            return len(result.get("news_files") or [])
        if stage_name == "review":
            return len(result.get("reviewed_files") or result.get("news_files") or [])
        if stage_name == "report":
            return int(bool(result.get("report_file")))
        return 0

    def _summarize_stage_domains(self, result: dict[str, Any]) -> dict[str, int]:
        domain_results = result.get("domain_results") or {}
        if not domain_results:
            return {"success_domains": 0, "failed_domains": 0, "total_outputs": 0}

        success_domains = 0
        failed_domains = 0
        total_outputs = 0
        for domain_result in domain_results.values():
            if domain_result.get("status") == "success":
                success_domains += 1
            else:
                failed_domains += 1
            total_outputs += int(domain_result.get("count") or 0)

        return {
            "success_domains": success_domains,
            "failed_domains": failed_domains,
            "total_outputs": total_outputs,
        }

    def _emit_event(self, event_type: str, **payload: Any) -> None:
        if not self.event_handler:
            return

        event = {
            "event": event_type,
            "timestamp": time.time(),
            **payload,
        }
        self.event_handler(event)

    def _hot_api_agent(self) -> HotApiAgent:
        if "hot_api_agent" not in self._components:
            self._components["hot_api_agent"] = HotApiAgent("hot_api_agent")
        return self._components["hot_api_agent"]

    def _sort_agent(self) -> SortAgent:
        if "sort_agent" not in self._components:
            self._components["sort_agent"] = SortAgent()
        return self._components["sort_agent"]

    def _web_search_agent(self) -> WebSearchAgent:
        if "web_search_agent" not in self._components:
            self._components["web_search_agent"] = WebSearchAgent(
                "web_search_agent",
                self.tavily_api_key,
                max_results=self.config.web_search_max_results,
                max_topics_per_category=self.config.max_news_per_category,
                event_handler=self._emit_event,
            )
        return self._components["web_search_agent"]

    def _maker_agent(self) -> MakerAgent:
        if "maker_agent" not in self._components:
            self._components["maker_agent"] = MakerAgent()
        return self._components["maker_agent"]

    def _news_generator(self) -> ParallelNewsTest:
        if "news_generator" not in self._components:
            self._components["news_generator"] = ParallelNewsTest()
        return self._components["news_generator"]
