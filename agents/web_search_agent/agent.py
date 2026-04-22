import os
import json
import subprocess
import sys
import time
from typing import Callable, Dict, Any

from cerebrum.tool.core.owen.web_search_tool.entry import WebSearch
from project_paths import INTERMEDIATE_DIR, PROJECT_ROOT
from apps.news_app.news_registry import news_category_file_map
from runtime_support.artifacts import get_artifact_store


class WebSearchAgent:
    def __init__(
        self,
        agent_name: str = "web_search_agent",
        api_key: str | None = None,
        max_results: int = 5,
        max_topics_per_category: int | None = None,
        event_handler: Callable[..., None] | None = None,
    ):
        self.agent_name = agent_name
        self.web_search_tool = WebSearch()
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        self.max_results = max_results
        self.max_topics_per_category = max_topics_per_category
        self.event_handler = event_handler
        self.store = get_artifact_store()
        self.category_files = news_category_file_map()
        self.topic_timeout_seconds = int(
            os.getenv(
                "NEWS_TOPIC_SEARCH_TIMEOUT_SECONDS",
                str(max(self.web_search_tool.search_timeout + 25, 60)),
            )
        )
        
    def run(self, output_dir: str = str(INTERMEDIATE_DIR)) -> Dict[str, Any]:
        """
        运行web搜索任务，处理6个分类文件
        
        Args:
            output_dir: 输出目录
            
        Returns:
            包含搜索结果的字典
        """
        try:
            print("🔍 开始Web搜索任务...")
            print("=" * 50)

            if not self.api_key:
                return {
                    "status": "failed",
                    "message": "未提供 TAVILY_API_KEY",
                    "search_files": [],
                }
            
            # 设置API密钥环境变量
            if self.api_key:
                os.environ['TAVILY_API_KEY'] = self.api_key
                print("✅ API密钥已设置")
            
            # 定义6个分类文件
            all_search_files = []
            total_topics = 0
            processed_categories = 0
            failed_topics = []
            topic_results = []
            
            # 处理每个分类文件
            for category, filename in self.category_files.items():
                file_path = os.path.join(output_dir, filename)
                
                if not self.store.exists(file_path):
                    print(f"⚠️ 分类文件不存在，跳过: {filename}")
                    continue
                
                print(f"\n📂 处理分类: {category}")
                print("-" * 30)
                processed_categories += 1
                
                # 读取该分类的热点数据
                hot_topics = [
                    self._normalize_topic_line(line)
                    for line in self.store.read_text(file_path).splitlines()
                    if line.strip()
                ]
                hot_topics = [topic for topic in hot_topics if topic]
                if self.max_topics_per_category:
                    hot_topics = hot_topics[: self.max_topics_per_category]
                
                if not hot_topics:
                    print(f"⚠️ {category} 没有热点数据，跳过")
                    continue
                
                print(f"📊 读取到 {len(hot_topics)} 个热点")
                
                # 对该分类的每个热点进行搜索
                category_search_files = []
                for idx, topic in enumerate(hot_topics):
                    print(f"🔍 搜索 {category} 热点 {idx + 1}/{len(hot_topics)}: {topic}")
                    topic_started_at = time.time()
                    self._emit_event(
                        "search_topic_started",
                        category=category,
                        topic=topic,
                        topic_index=idx,
                        topic_position=idx + 1,
                        category_topic_count=len(hot_topics),
                        timeout_seconds=self.topic_timeout_seconds,
                    )

                    topic_result = self._run_topic_worker(topic)
                    topic_duration = round(time.time() - topic_started_at, 3)
                    topic_meta = {
                        "category": category,
                        "topic": topic,
                        "topic_index": idx,
                        "topic_position": idx + 1,
                        "category_topic_count": len(hot_topics),
                        "status": topic_result.get("status"),
                        "duration_seconds": topic_duration,
                        "message": topic_result.get("message"),
                        "raw_result_length": topic_result.get("raw_result_length", 0),
                        "raw_result_preview": topic_result.get("raw_result_preview"),
                    }
                    self._write_topic_meta(output_dir, category, idx, topic_meta)
                    topic_results.append(topic_meta)

                    if topic_result.get("status") != "success":
                        failed_topics.append(topic_meta)
                        print(
                            f"⚠️ 跳过热点 {category}_{idx}: "
                            f"{topic_result.get('message') or '未知错误'}"
                        )
                        self._emit_event(
                            "search_topic_finished",
                            category=category,
                            topic=topic,
                            topic_index=idx,
                            status=topic_result.get("status"),
                            duration=topic_duration,
                            message=topic_result.get("message"),
                            raw_result_length=topic_result.get("raw_result_length", 0),
                        )
                        continue

                    search_filename = f"{category}_{idx}_search.txt"
                    search_filepath = os.path.join(output_dir, search_filename)
                    image_filename = f"{category}_{idx}_image.txt"
                    image_filepath = os.path.join(output_dir, image_filename)

                    self.store.write_text(
                        search_filepath,
                        topic_result.get("core_content") or "",
                    )
                    self.store.write_text(
                        image_filepath,
                        topic_result.get("image_content") or "",
                    )

                    category_search_files.append(search_filepath)
                    all_search_files.append(search_filepath)
                    total_topics += 1
                    print(f"✅ 搜索结果已保存: {search_filename}")
                    self._emit_event(
                        "search_topic_finished",
                        category=category,
                        topic=topic,
                        topic_index=idx,
                        status="success",
                        duration=topic_duration,
                        message=None,
                        raw_result_length=topic_result.get("raw_result_length", 0),
                        search_file=search_filepath,
                    )
                
                print(f"✅ {category} 分类搜索完成，生成 {len(category_search_files)} 个文件")
            
            print("=" * 50)
            print("🎯 Web搜索任务完成!")
            print(f"📁 共处理 {processed_categories} 个分类")
            print(f"📊 总共搜索 {total_topics} 个热点")
            print(f"📁 共生成 {len(all_search_files)} 个搜索文件")
            if failed_topics:
                print(f"⚠️ 共跳过 {len(failed_topics)} 个热点")

            if not all_search_files:
                return {
                    "status": "failed",
                    "message": "没有生成任何搜索结果，请先检查分类阶段是否产出热点",
                    "search_files": [],
                    "total_topics": 0,
                    "categories_processed": processed_categories,
                    "failed_topics": failed_topics,
                    "topic_results": topic_results,
                }
            
            message = "Web搜索任务完成"
            if failed_topics:
                message += f"（跳过 {len(failed_topics)} 个热点）"

            return {
                "status": "success",
                "message": message,
                "search_files": all_search_files,
                "total_topics": total_topics,
                "categories_processed": processed_categories,
                "failed_topics": failed_topics,
                "topic_results": topic_results,
            }
            
        except Exception as e:
            print(f"❌ Web搜索任务失败: {e}")
            return {
                "status": "failed",
                "message": f"Web搜索任务失败: {e}",
                "search_files": []
            }

    def _normalize_topic_line(self, topic: str) -> str:
        normalized = topic.strip()
        if normalized.startswith("- "):
            normalized = normalized[2:].strip()
        return normalized

    def _emit_event(self, event_type: str, **payload: Any) -> None:
        if not self.event_handler:
            return
        self.event_handler(event_type, **payload)

    def _run_topic_worker(self, topic: str) -> Dict[str, Any]:
        payload = {
            "topic": topic,
            "max_results": self.max_results,
            "api_key": self.api_key,
        }
        env = os.environ.copy()
        if self.api_key:
            env["TAVILY_API_KEY"] = self.api_key
        python_path_entries = [
            str(PROJECT_ROOT),
            env.get("PYTHONPATH", ""),
        ]
        env["PYTHONPATH"] = os.pathsep.join(
            [entry for entry in python_path_entries if entry]
        )

        try:
            result = subprocess.run(
                [sys.executable, "-m", "agents.web_search_agent.topic_worker"],
                input=json.dumps(payload, ensure_ascii=False),
                capture_output=True,
                text=True,
                env=env,
                cwd=str(PROJECT_ROOT),
                timeout=self.topic_timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            return {
                "status": "timeout",
                "message": f"单个热点搜索超时（>{self.topic_timeout_seconds}秒）",
                "raw_result_length": 0,
                "raw_result_preview": "",
                "core_content": "",
                "image_content": "",
            }

        stdout = (result.stdout or "").strip()
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            return {
                "status": "failed",
                "message": stderr or stdout or "topic worker exited with error",
                "raw_result_length": 0,
                "raw_result_preview": "",
                "core_content": "",
                "image_content": "",
            }

        if not stdout:
            return {
                "status": "failed",
                "message": "topic worker returned empty output",
                "raw_result_length": 0,
                "raw_result_preview": "",
                "core_content": "",
                "image_content": "",
            }

        try:
            return json.loads(stdout.splitlines()[-1])
        except json.JSONDecodeError:
            return {
                "status": "failed",
                "message": f"topic worker returned invalid JSON: {stdout[:300]}",
                "raw_result_length": len(stdout),
                "raw_result_preview": stdout[:600],
                "core_content": "",
                "image_content": "",
            }

    def _write_topic_meta(
        self,
        output_dir: str,
        category: str,
        topic_index: int,
        payload: Dict[str, Any],
    ) -> None:
        meta_filename = f"{category}_{topic_index}_search_meta.json"
        meta_filepath = os.path.join(output_dir, meta_filename)
        self.store.write_json(meta_filepath, payload)

def main():
    """测试函数"""
    agent = WebSearchAgent("test_web_search_agent")
    result = agent.run()
    print(f"搜索结果: {result}")

if __name__ == "__main__":
    main()
