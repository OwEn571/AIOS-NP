#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from cerebrum.config.config_manager import config
from cerebrum.llm.apis import llm_chat
from apps.news_app.editorial import (
    build_story_dedupe_key,
    evaluate_publishability,
    filter_display_sources,
    route_story_category,
)
from apps.news_app.news_registry import news_category_names
from project_paths import INTERMEDIATE_DIR, OUTPUT_DIR
from runtime_support.artifacts import get_artifact_store
from runtime_support.memory import get_workflow_memory_recorder


class MakerAgent:
    ALLOWED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".avif"}
    BAD_IMAGE_MARKERS = (
        ".pdf",
        "app-screenshot",
        "avatar",
        "default/7bd4e141/20251230/sina.png",
        "icon",
        "logo",
        "qhimg.com",
        "sexno",
        "sexyes",
        "sprite",
    )
    SMALL_IMAGE_MARKERS = (
        "w35h32",
        "w85h85",
        "w550h57",
        "w730h78",
        "418-58",
        "512x139",
        "730x78",
    )
    SECTION_ACCENTS = {
        "社会热点与公共事务": "#1e4f8f",
        "娱乐与文化": "#8c355d",
        "商业与经济": "#915b15",
        "科技与创新": "#106368",
        "民生与健康": "#2f6b36",
        "争议事件": "#7b2f2f",
    }

    def __init__(self):
        self.agent_name = "maker_agent"
        self.categories = list(news_category_names())
        self.store = get_artifact_store()
        self.memory_recorder = get_workflow_memory_recorder()

    def run(
        self,
        intermediate_dir: str = str(INTERMEDIATE_DIR),
        output_dir: str = str(OUTPUT_DIR),
    ) -> dict:
        try:
            print("📰 开始制作新闻报...")
            print("=" * 50)

            output_path = Path(output_dir)
            self.store.ensure_dir(output_path)

            sections = self.collect_report_sections(intermediate_dir)
            if not sections:
                return {
                    "agent_name": self.agent_name,
                    "result": "❌ 没有找到任何可展示的新闻内容",
                    "status": "failed",
                }

            title_and_overview = self.generate_title_and_overview(sections)
            report_document = self.build_report_document(title_and_overview, sections)
            text_report = self.render_text_report(report_document)
            html_report = self.render_html_report(report_document)

            timestamp = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d_%H%M%S")
            report_filepath = output_path / f"新闻报_{timestamp}.txt"
            report_json_path = output_path / f"新闻报_{timestamp}.json"
            report_html_path = output_path / f"新闻报_{timestamp}.html"

            self.store.write_text(report_filepath, text_report)
            self.store.write_json(report_json_path, report_document)
            self.store.write_text(report_html_path, html_report)

            print(f"✅ 文本日报已保存: {report_filepath}")
            print(f"✅ 结构化日报已保存: {report_json_path}")
            print(f"✅ HTML 日报已保存: {report_html_path}")

            return {
                "agent_name": self.agent_name,
                "result": "✅ 新闻报制作成功！",
                "status": "success",
                "report_file": str(report_filepath),
                "report_json_file": str(report_json_path),
                "report_html_file": str(report_html_path),
                "news_count": report_document["metrics"]["total_articles"],
                "metrics": report_document["metrics"],
            }
        except Exception as exc:
            print(f"❌ 新闻报制作失败: {exc}")
            return {
                "agent_name": self.agent_name,
                "result": f"❌ 新闻报制作失败: {exc}",
                "status": "failed",
            }

    def collect_report_sections(self, intermediate_dir: str) -> list[dict]:
        all_articles: list[dict] = []
        for category in self.categories:
            all_articles.extend(self.collect_category_articles(intermediate_dir, category))

        deduped_articles = self._dedupe_articles(all_articles)
        grouped_articles = {category: [] for category in self.categories}
        for article in deduped_articles:
            grouped_articles[article["display_category"]].append(article)

        sections: list[dict] = []
        for category in self.categories:
            articles = grouped_articles[category]
            if not articles:
                continue
            sections.append(
                {
                    "name": category,
                    "accent": self.SECTION_ACCENTS.get(category, "#3d4a63"),
                    "article_count": len(articles),
                    "articles": articles,
                }
            )
        return sections

    def collect_category_articles(self, intermediate_dir: str, category: str) -> list[dict]:
        root = Path(intermediate_dir)
        topic_category_map = self._load_topic_category_map(root)
        topic_index_map = self._load_topic_index_map(root)
        candidate_rows: list[tuple[Path, Path | None]] = []
        seen_article_paths: set[str] = set()

        for file_path in root.glob(f"{category}_*_news.txt"):
            match = re.search(rf"^{re.escape(category)}_(\d+)_news\.txt$", file_path.name)
            if match:
                source_path = root / f"{category}_{match.group(1)}_sources.json"
                candidate_rows.append((file_path, source_path if self.store.exists(source_path) else None))

        for file_path in root.glob(f"{category}_*_reviewed.txt"):
            match = re.search(rf"^{re.escape(category)}_(\d+)_reviewed\.txt$", file_path.name)
            if match:
                source_path = root / f"{category}_{match.group(1)}_sources.json"
                candidate_rows.append((file_path, source_path if self.store.exists(source_path) else None))

        # 新版生成链路使用“热点标题”作为文件名前缀，这里通过 sources.json 里的 topic
        # 反查所属栏目，兼容新的 topic-based artifacts。
        for source_path in root.glob("*_sources.json"):
            sources_payload = self.store.read_json(source_path)
            topic = str(sources_payload.get("topic") or "").strip()
            if topic_category_map.get(self._normalize_topic_key(topic)) != category:
                continue

            stem = source_path.name[: -len("_sources.json")]
            reviewed_path = root / f"{stem}_reviewed.txt"
            news_path = root / f"{stem}_news.txt"
            article_path = reviewed_path if self.store.exists(reviewed_path) else news_path
            if not self.store.exists(article_path):
                continue
            candidate_rows.append((article_path, source_path))

        articles: list[dict] = []
        for row_index, (article_path, source_path) in enumerate(sorted(candidate_rows), start=1):
            article_key = str(article_path)
            if article_key in seen_article_paths:
                continue
            seen_article_paths.add(article_key)

            raw_content = self.store.read_text(article_path)
            parsed = self._parse_article_content(raw_content)
            sources_payload = self.store.read_json(source_path) if source_path and self.store.exists(source_path) else {}
            topic = str(sources_payload.get("topic") or "").strip()
            sources = filter_display_sources(self._normalize_sources(sources_payload.get("sources", [])))
            memory_hints = self.memory_recorder.search_editorial_decisions(
                f"{category} {topic or parsed['title']} {parsed['title']}",
                category=category,
                decision_kind="publishability_gate",
                k=3,
            )
            if memory_hints:
                print(f"🧠 找到 {len(memory_hints)} 条相似出报记忆: {parsed['title'] or topic}")
            publishability = evaluate_publishability(
                category=category,
                topic=topic,
                title=parsed["title"],
                sources=sources,
                memory_hints=memory_hints,
            )
            try:
                self.memory_recorder.record_editorial_decision(
                    decision_kind="publishability_gate",
                    category=category,
                    topic=topic or parsed["title"],
                    accepted=publishability.accepted,
                    score=publishability.score,
                    reasons=list(publishability.reasons),
                    metadata={
                        "title": parsed["title"],
                        "artifact_path": str(article_path),
                        "source_count": len(sources),
                        "top_source_score": max((source["relevance_score"] for source in sources), default=0),
                        "trusted_source_count": publishability.trusted_source_count,
                        "memory_hint_count": publishability.memory_hint_count,
                        "memory_score_delta": publishability.memory_score_delta,
                    },
                )
            except Exception:
                pass
            if not publishability.accepted:
                print(f"⛔ 日报过滤稿件: {parsed['title'] or article_path.name}")
                for reason in publishability.reasons:
                    print(f"   - {reason}")
                continue
            image = self._resolve_article_image(
                root,
                category,
                article_path,
                topic,
                sources,
                topic_index_map,
            )
            articles.append(
                {
                    "index": row_index - 1,
                    "file_path": str(article_path),
                    "topic": topic,
                    "original_category": category,
                    "display_category": route_story_category(category, topic, parsed["title"]),
                    "title": parsed["title"] or f"{category} #{row_index}",
                    "summary": parsed["summary"],
                    "content": parsed["content"],
                    "sources": sources,
                    "source_count": len(sources),
                    "top_source_score": max((source["relevance_score"] for source in sources), default=0),
                    "trusted_source_count": publishability.trusted_source_count,
                    "image": image,
                    "editorial_gate": publishability.to_dict(),
                }
            )
        return articles

    def _dedupe_articles(self, articles: list[dict]) -> list[dict]:
        best_by_key: dict[str, dict] = {}
        for article in articles:
            dedupe_key = build_story_dedupe_key(
                article["display_category"],
                article.get("topic", ""),
                article["title"],
            )
            existing = best_by_key.get(dedupe_key)
            if existing is None or self._article_priority(article) > self._article_priority(existing):
                best_by_key[dedupe_key] = article

        category_order = {name: index for index, name in enumerate(self.categories)}
        return sorted(
            best_by_key.values(),
            key=lambda article: (
                category_order.get(article["display_category"], 999),
                -self._article_priority(article),
                article["title"],
            ),
        )

    def _article_priority(self, article: dict) -> int:
        score = 0
        score += int(article.get("top_source_score") or 0) * 10
        score += int(article.get("source_count") or 0) * 6
        score += int(article.get("trusted_source_count") or 0) * 8
        score += min(len(article.get("content") or "") // 80, 8)
        if article.get("display_category") == article.get("original_category"):
            score += 5
        return score

    def _load_topic_category_map(self, root: Path) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for category in self.categories:
            category_path = root / f"{category}_api.txt"
            if not self.store.exists(category_path):
                continue
            for raw_line in self.store.read_text(category_path).splitlines():
                topic = raw_line.strip()
                if topic.startswith("- "):
                    topic = topic[2:].strip()
                if topic:
                    mapping.setdefault(self._normalize_topic_key(topic), category)
        return mapping

    def _load_topic_index_map(self, root: Path) -> dict[str, dict[str, int]]:
        mapping: dict[str, dict[str, int]] = {}
        for category in self.categories:
            category_path = root / f"{category}_api.txt"
            if not self.store.exists(category_path):
                continue
            topic_lookup: dict[str, int] = {}
            for index, raw_line in enumerate(self.store.read_text(category_path).splitlines()):
                topic = raw_line.strip()
                if topic.startswith("- "):
                    topic = topic[2:].strip()
                if topic:
                    topic_lookup.setdefault(self._normalize_topic_key(topic), index)
            if topic_lookup:
                mapping[category] = topic_lookup
        return mapping

    def _normalize_topic_key(self, raw_topic: str) -> str:
        return re.sub(r"[^\w\u4e00-\u9fff]+", "", str(raw_topic or "").lower())

    def _parse_article_content(self, raw_content: str) -> dict[str, str]:
        title_match = re.search(r"标题[：:]\s*(.*?)(?:\n\n|$)", raw_content, re.DOTALL)
        summary_match = re.search(r"摘要[：:]\s*(.*?)(?:\n\n|$)", raw_content, re.DOTALL)
        content_match = re.search(r"内容[：:]\s*(.*)$", raw_content, re.DOTALL)
        return {
            "title": title_match.group(1).strip() if title_match else "",
            "summary": summary_match.group(1).strip() if summary_match else "",
            "content": content_match.group(1).strip() if content_match else raw_content.strip(),
        }

    def _normalize_sources(self, raw_sources: list[dict]) -> list[dict]:
        normalized_sources: list[dict] = []
        for source in raw_sources[:4]:
            normalized_sources.append(
                {
                    "title": source.get("title", "未知标题"),
                    "link": source.get("link", ""),
                    "relevance_score": int(source.get("relevance_score", 0) or 0),
                    "relevance_reason": source.get("relevance_reason", ""),
                    "key_info": source.get("key_info", ""),
                }
            )
        return normalized_sources

    def _resolve_article_image(
        self,
        root: Path,
        category: str,
        article_path: Path,
        topic: str,
        sources: list[dict[str, Any]],
        topic_index_map: dict[str, dict[str, int]],
    ) -> dict[str, Any] | None:
        search_path, image_path = self._resolve_search_and_image_paths(
            root,
            category,
            article_path,
            topic,
            topic_index_map,
        )
        if not search_path or not image_path:
            return None

        search_results = self._parse_search_results(self.store.read_text(search_path))
        image_candidates = self._parse_image_candidates(self.store.read_text(image_path))
        if not search_results or not image_candidates:
            return None

        ranked_sources = sorted(
            sources,
            key=lambda item: (-int(item.get("relevance_score") or 0), str(item.get("title") or "")),
        )
        for source in ranked_sources:
            if int(source.get("relevance_score") or 0) < 80:
                continue
            result_index = self._match_source_result_index(source, search_results)
            if result_index is None:
                continue
            urls = image_candidates.get(result_index) or []
            valid_urls = [url for url in urls if self._is_displayable_image_url(url)]
            if not valid_urls:
                continue
            return {
                "url": valid_urls[0],
                "source_title": source.get("title", ""),
                "source_link": source.get("link", ""),
                "relevance_score": int(source.get("relevance_score", 0) or 0),
                "search_result_index": result_index,
                "candidate_count": len(valid_urls),
            }
        return None

    def _resolve_search_and_image_paths(
        self,
        root: Path,
        category: str,
        article_path: Path,
        topic: str,
        topic_index_map: dict[str, dict[str, int]],
    ) -> tuple[Path | None, Path | None]:
        match = re.search(
            rf"^{re.escape(category)}_(\d+)_(?:news|reviewed)\.txt$",
            article_path.name,
        )
        index: int | None = int(match.group(1)) if match else None
        if index is None:
            index = (topic_index_map.get(category) or {}).get(self._normalize_topic_key(topic))
        if index is None:
            return None, None

        search_path = root / f"{category}_{index}_search.txt"
        image_path = root / f"{category}_{index}_image.txt"
        if not self.store.exists(search_path) or not self.store.exists(image_path):
            return None, None
        return search_path, image_path

    def _parse_search_results(self, raw_content: str) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for match in re.finditer(
            r"【结果 (\d+)】\s*(.*?)(?=(?:\n【结果 \d+】)|\Z)",
            raw_content,
            re.DOTALL,
        ):
            payload = match.group(2).strip()
            title_match = re.search(r"标题:\s*(.*?)(?=\n链接:|$)", payload, re.DOTALL)
            link_match = re.search(r"链接:\s*(.*?)(?=\n|$)", payload)
            results.append(
                {
                    "index": int(match.group(1)),
                    "title": (title_match.group(1).strip() if title_match else ""),
                    "link": (link_match.group(1).strip() if link_match else ""),
                }
            )
        return results

    def _parse_image_candidates(self, raw_content: str) -> dict[int, list[str]]:
        grouped: dict[int, list[str]] = {}
        for match in re.finditer(
            r"【结果 (\d+)】\s*(.*?)(?=(?:\n【结果 \d+】)|\Z)",
            raw_content,
            re.DOTALL,
        ):
            result_index = int(match.group(1))
            urls: list[str] = []
            for line in match.group(2).splitlines():
                line = line.strip()
                if not line:
                    continue
                url_match = re.search(r"\d+\.\s*(https?://\S+)", line)
                if not url_match:
                    continue
                cleaned_url = self._clean_image_url(url_match.group(1))
                if cleaned_url and cleaned_url not in urls:
                    urls.append(cleaned_url)
            if urls:
                grouped[result_index] = urls
        return grouped

    def _clean_image_url(self, raw_url: str) -> str:
        cleaned = raw_url.strip()
        if ")](" in cleaned:
            cleaned = cleaned.split(")](", 1)[0]
        while cleaned and cleaned[-1] in ").,;]":
            cleaned = cleaned[:-1]
        return cleaned

    def _match_source_result_index(
        self,
        source: dict[str, Any],
        search_results: list[dict[str, Any]],
    ) -> int | None:
        normalized_source_link = self._normalize_url_for_match(source.get("link", ""))
        normalized_source_title = self._normalize_text_for_match(source.get("title", ""))

        for result in search_results:
            if normalized_source_link and normalized_source_link == self._normalize_url_for_match(result["link"]):
                return int(result["index"])

        for result in search_results:
            if normalized_source_title and normalized_source_title == self._normalize_text_for_match(result["title"]):
                return int(result["index"])

        return None

    def _normalize_url_for_match(self, raw_url: str) -> str:
        text = str(raw_url or "").strip()
        if not text:
            return ""
        parsed = urlparse(text)
        if not parsed.scheme or not parsed.netloc:
            return text.rstrip("/").lower()
        query = f"?{parsed.query}" if parsed.query else ""
        return f"{parsed.scheme.lower()}://{parsed.netloc.lower()}{parsed.path.rstrip('/')}{query}"

    def _normalize_text_for_match(self, raw_text: str) -> str:
        return re.sub(r"[^\w\u4e00-\u9fff]+", "", str(raw_text or "").lower())

    def _is_displayable_image_url(self, raw_url: str) -> bool:
        url = str(raw_url or "").strip()
        if not url.startswith(("http://", "https://")):
            return False

        lowered = url.lower()
        if any(marker in lowered for marker in self.BAD_IMAGE_MARKERS):
            return False
        if any(marker in lowered for marker in self.SMALL_IMAGE_MARKERS):
            return False

        parsed = urlparse(url)
        suffix = Path(parsed.path).suffix.lower()
        if suffix:
            return suffix in self.ALLOWED_IMAGE_SUFFIXES
        return bool(re.search(r"\.(?:jpg|jpeg|png|webp|gif|bmp|avif)(?:[?&]|$)", lowered))

    def generate_title_and_overview(self, sections: list[dict]) -> dict:
        print("📝 生成新闻报标题和总览...")
        all_titles = [article["title"] for section in sections for article in section["articles"]]
        titles_text = "\n".join(f"- {title}" for title in all_titles)

        prompt = f"""基于以下新闻标题，为今日新闻日报生成标题和总览。

新闻标题列表：
{titles_text}

要求：
1. report_title 固定为“今日新闻现场”。
2. report_subtitle 生成一句有编辑感但克制的副标题，20 字以内。
3. overview 生成 120-180 字中文总览，概括今天最值得关注的趋势。
4. 只返回 JSON，不要带代码块。

JSON 格式：
{{
  "report_title": "今日新闻现场",
  "report_subtitle": "一句副标题",
  "overview": "总览内容"
}}"""

        fallback = {
            "report_title": "今日新闻现场",
            "report_subtitle": "把今天真正重要的变化留在一页里",
            "overview": "这份日报聚合了今日更值得追踪的公共议题、产业动向、科技更新与社会情绪，帮助读者在碎片化热搜之外，快速建立更完整的新闻轮廓。",
        }

        try:
            response = llm_chat(
                agent_name=self.agent_name,
                messages=[{"role": "user", "content": prompt}],
                base_url=config.get_kernel_url(),
            )
            response_text = response["response"]["response_message"].strip()
            response_text = re.sub(r"<think>.*?</think>", "", response_text, flags=re.DOTALL)
            response_text = re.sub(r"^```(?:json)?\s*", "", response_text)
            response_text = re.sub(r"\s*```$", "", response_text)
            parsed = json.loads(response_text)
            parsed["report_title"] = "今日新闻现场"
            parsed.setdefault("report_subtitle", fallback["report_subtitle"])
            parsed.setdefault("overview", fallback["overview"])
            return parsed
        except Exception as exc:
            print(f"⚠️ 标题和总览生成失败，使用默认文案: {exc}")
            return fallback

    def build_report_document(self, title_and_overview: dict, sections: list[dict]) -> dict:
        now = datetime.now(ZoneInfo("Asia/Shanghai"))
        total_articles = sum(section["article_count"] for section in sections)
        total_sources = sum(
            len(article["sources"])
            for section in sections
            for article in section["articles"]
        )
        memory_assisted_articles = sum(
            1
            for section in sections
            for article in section["articles"]
            if int(((article.get("editorial_gate") or {}).get("memory_hint_count") or 0)) > 0
        )
        memory_penalized_articles = sum(
            1
            for section in sections
            for article in section["articles"]
            if int(((article.get("editorial_gate") or {}).get("memory_score_delta") or 0)) < 0
        )
        highlights = [
            {
                "category": section["name"],
                "title": article["title"],
                "summary": article["summary"],
            }
            for section in sections
            for article in section["articles"][:1]
        ][:6]

        return {
            "report_title": title_and_overview.get("report_title", "今日新闻现场"),
            "report_subtitle": title_and_overview.get("report_subtitle", ""),
            "overview": title_and_overview.get("overview", ""),
            "generated_at": now.isoformat(),
            "date_label": now.strftime("%Y年%m月%d日"),
            "time_label": now.strftime("%H:%M"),
            "metrics": {
                "total_articles": total_articles,
                "active_sections": len(sections),
                "total_sources": total_sources,
                "highlight_count": len(highlights),
                "memory_assisted_articles": memory_assisted_articles,
                "memory_penalized_articles": memory_penalized_articles,
            },
            "highlights": highlights,
            "sections": sections,
        }

    def render_text_report(self, report_document: dict) -> str:
        lines = [
            "=" * 64,
            f"📰 {report_document['report_title']}",
            report_document["report_subtitle"],
            f"📅 {report_document['date_label']} {report_document['time_label']}",
            "=" * 64,
            "",
            "今日概览",
            "-" * 32,
            report_document["overview"],
            "",
        ]

        for section in report_document["sections"]:
            lines.append(f"【{section['name']}】")
            lines.append("-" * 32)
            for index, article in enumerate(section["articles"], start=1):
                lines.append(f"{index}. {article['title']}")
                if article["summary"]:
                    lines.append(f"摘要：{article['summary']}")
                if article.get("image"):
                    lines.append(f"配图：{article['image']['url']}")
                lines.append(article["content"])
                if article["sources"]:
                    lines.append("信源：")
                    for source in article["sources"]:
                        lines.append(
                            f"  - {source['title']} ({source['relevance_score']}%) {source['link']}".rstrip()
                        )
                lines.append("")
            lines.append("")

        return "\n".join(lines).strip()

    def render_html_report(self, report_document: dict) -> str:
        highlight_cards = "\n".join(
            f"""
            <article class="highlight-card">
              <span class="highlight-category">{escape(item['category'])}</span>
              <h3>{escape(item['title'])}</h3>
              <p>{escape(item.get('summary') or '这条新闻值得继续追踪。')}</p>
            </article>
            """
            for item in report_document["highlights"]
        )

        section_blocks = []
        for section in report_document["sections"]:
            article_cards = []
            for article in section["articles"]:
                image = article.get("image") or {}
                image_block = ""
                if image.get("url"):
                    image_source_link = escape(str(image.get("source_link") or ""))
                    image_source_title = escape(str(image.get("source_title") or "配图来源"))
                    image_score = int(image.get("relevance_score") or 0)
                    caption = (
                        f'<a href="{image_source_link}" target="_blank" rel="noreferrer">{image_source_title}</a>'
                        if image_source_link
                        else image_source_title
                    )
                    image_block = f"""
                    <figure class="story-image">
                      <img
                        src="{escape(str(image['url']))}"
                        alt="{escape(article['title'])}"
                        loading="lazy"
                        referrerpolicy="no-referrer"
                        onerror="this.closest('figure').style.display='none';"
                      />
                      <figcaption>配图来源：{caption} · {image_score}%</figcaption>
                    </figure>
                    """
                source_items = "".join(
                    f"""
                    <li>
                      <a href="{escape(source['link'])}" target="_blank" rel="noreferrer">{escape(source['title'])}</a>
                      <strong>{source['relevance_score']}%</strong>
                      <p>{escape(source.get('relevance_reason') or '')}</p>
                    </li>
                    """
                    for source in article["sources"]
                )
                source_block = (
                    f"""
                    <aside class="source-panel">
                      <div class="source-heading">参考信源</div>
                      <ul>{source_items}</ul>
                    </aside>
                    """
                    if source_items
                    else ""
                )
                article_cards.append(
                    f"""
                    <article class="story-card">
                      <div class="story-meta">
                        <span>#{article['index'] + 1}</span>
                        <span>{article['source_count']} 个信源</span>
                      </div>
                      <h3>{escape(article['title'])}</h3>
                      <p class="story-summary">{escape(article.get('summary') or '暂无摘要')}</p>
                      {image_block}
                      <div class="story-content">{self._htmlize_paragraphs(article['content'])}</div>
                      {source_block}
                    </article>
                    """
                )

            section_blocks.append(
                f"""
                <section class="section-block" style="--section-accent:{section['accent']}">
                  <div class="section-header">
                    <div>
                      <span class="section-kicker">Section</span>
                      <h2>{escape(section['name'])}</h2>
                    </div>
                    <div class="section-count">{section['article_count']} stories</div>
                  </div>
                  <div class="story-grid">
                    {''.join(article_cards)}
                  </div>
                </section>
                """
            )

        return f"""<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{escape(report_document['report_title'])}</title>
    <style>
      :root {{
        --bg: #f4efe6;
        --paper: rgba(255, 251, 244, 0.92);
        --ink: #1f2430;
        --muted: #5e6472;
        --line: rgba(31, 36, 48, 0.12);
        --hero: linear-gradient(135deg, #f7e0b5 0%, #e7c8a0 32%, #d4dceb 100%);
        --shadow: 0 20px 60px rgba(47, 39, 24, 0.14);
        --radius: 28px;
      }}
      * {{ box-sizing: border-box; }}
      body {{
        margin: 0;
        font-family: "Georgia", "Noto Serif SC", "Source Han Serif SC", serif;
        color: var(--ink);
        background:
          radial-gradient(circle at top right, rgba(210, 159, 87, 0.18), transparent 32%),
          radial-gradient(circle at bottom left, rgba(55, 95, 149, 0.12), transparent 28%),
          var(--bg);
      }}
      .page {{
        width: min(1180px, calc(100vw - 32px));
        margin: 24px auto 56px;
      }}
      .hero {{
        background: var(--hero);
        border-radius: 36px;
        padding: 40px 40px 32px;
        box-shadow: var(--shadow);
        position: relative;
        overflow: hidden;
      }}
      .hero::after {{
        content: "";
        position: absolute;
        inset: auto -12% -28% auto;
        width: 320px;
        height: 320px;
        border-radius: 999px;
        background: rgba(255,255,255,0.24);
        filter: blur(10px);
      }}
      .eyebrow {{
        display: inline-flex;
        align-items: center;
        gap: 10px;
        padding: 8px 14px;
        border-radius: 999px;
        background: rgba(255,255,255,0.58);
        border: 1px solid rgba(255,255,255,0.55);
        font-size: 13px;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }}
      h1 {{
        margin: 18px 0 10px;
        font-size: clamp(2.4rem, 4vw, 4.2rem);
        line-height: 1.02;
      }}
      .subtitle {{
        margin: 0;
        font-size: 1.08rem;
        color: rgba(31, 36, 48, 0.74);
      }}
      .overview {{
        margin-top: 20px;
        max-width: 760px;
        font-size: 1.08rem;
        line-height: 1.8;
      }}
      .stats {{
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 14px;
        margin-top: 28px;
      }}
      .stat {{
        background: rgba(255,255,255,0.7);
        border: 1px solid rgba(255,255,255,0.65);
        border-radius: 22px;
        padding: 18px 20px;
      }}
      .stat-label {{
        font-size: 0.82rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--muted);
      }}
      .stat-value {{
        margin-top: 6px;
        font-size: 2rem;
        font-weight: 700;
      }}
      .content {{
        display: grid;
        gap: 22px;
        margin-top: 26px;
      }}
      .panel {{
        background: var(--paper);
        border-radius: var(--radius);
        border: 1px solid var(--line);
        box-shadow: var(--shadow);
        padding: 28px;
      }}
      .panel h2 {{
        margin: 0 0 16px;
        font-size: 1.45rem;
      }}
      .highlight-grid {{
        display: grid;
        grid-template-columns: repeat(3, minmax(0, 1fr));
        gap: 16px;
      }}
      .highlight-card {{
        padding: 20px;
        border-radius: 22px;
        background: linear-gradient(180deg, rgba(255,255,255,0.9), rgba(247, 242, 233, 0.92));
        border: 1px solid var(--line);
      }}
      .highlight-category {{
        display: inline-block;
        font-size: 0.8rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--muted);
      }}
      .highlight-card h3 {{
        margin: 12px 0 8px;
        font-size: 1.08rem;
        line-height: 1.45;
      }}
      .highlight-card p {{
        margin: 0;
        color: var(--muted);
        line-height: 1.7;
      }}
      .section-block {{
        background: var(--paper);
        border-radius: 30px;
        border: 1px solid var(--line);
        box-shadow: var(--shadow);
        padding: 28px;
        position: relative;
        overflow: hidden;
      }}
      .section-block::before {{
        content: "";
        position: absolute;
        inset: 0 auto 0 0;
        width: 7px;
        background: var(--section-accent);
      }}
      .section-header {{
        display: flex;
        justify-content: space-between;
        gap: 16px;
        align-items: end;
        margin-bottom: 18px;
      }}
      .section-kicker {{
        font-size: 0.78rem;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--muted);
      }}
      .section-header h2 {{
        margin: 6px 0 0;
        font-size: 1.8rem;
      }}
      .section-count {{
        font-size: 0.94rem;
        color: var(--muted);
      }}
      .story-grid {{
        display: grid;
        gap: 18px;
      }}
      .story-card {{
        display: grid;
        gap: 14px;
        padding: 22px;
        border-radius: 24px;
        background: rgba(255,255,255,0.74);
        border: 1px solid rgba(31,36,48,0.08);
      }}
      .story-meta {{
        display: flex;
        justify-content: space-between;
        color: var(--muted);
        font-size: 0.9rem;
      }}
      .story-card h3 {{
        margin: 0;
        font-size: 1.36rem;
        line-height: 1.42;
      }}
      .story-summary {{
        margin: 0;
        font-size: 1rem;
        line-height: 1.7;
        color: rgba(31, 36, 48, 0.78);
      }}
      .story-image {{
        margin: 0;
        display: grid;
        gap: 8px;
      }}
      .story-image img {{
        width: 100%;
        aspect-ratio: 16 / 9;
        object-fit: cover;
        border-radius: 18px;
        background: rgba(31, 36, 48, 0.06);
      }}
      .story-image figcaption {{
        color: var(--muted);
        font-size: 0.86rem;
        line-height: 1.5;
      }}
      .story-image a {{
        color: inherit;
      }}
      .story-content {{
        display: grid;
        gap: 12px;
        color: #262c39;
        line-height: 1.86;
      }}
      .story-content p {{
        margin: 0;
      }}
      .source-panel {{
        border-top: 1px dashed rgba(31,36,48,0.14);
        padding-top: 14px;
      }}
      .source-heading {{
        font-size: 0.84rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--muted);
        margin-bottom: 10px;
      }}
      .source-panel ul {{
        list-style: none;
        padding: 0;
        margin: 0;
        display: grid;
        gap: 10px;
      }}
      .source-panel li {{
        display: grid;
        grid-template-columns: 1fr auto;
        gap: 12px;
        font-size: 0.95rem;
      }}
      .source-panel a {{
        color: var(--ink);
        text-decoration: none;
        font-weight: 600;
      }}
      .source-panel a:hover {{
        text-decoration: underline;
      }}
      .source-panel p {{
        grid-column: 1 / -1;
        margin: 0;
        color: var(--muted);
        font-size: 0.88rem;
        line-height: 1.6;
      }}
      .footer-note {{
        margin-top: 14px;
        text-align: center;
        color: var(--muted);
        font-size: 0.92rem;
      }}
      @media (max-width: 960px) {{
        .stats,
        .highlight-grid {{
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }}
        .hero,
        .panel,
        .section-block {{
          padding: 24px;
        }}
      }}
      @media (max-width: 640px) {{
        .page {{
          width: min(100vw - 20px, 100%);
          margin: 12px auto 28px;
        }}
        .stats,
        .highlight-grid {{
          grid-template-columns: 1fr;
        }}
        .section-header,
        .story-meta,
        .source-panel li {{
          display: block;
        }}
        .section-count,
        .story-meta span + span,
        .source-panel strong {{
          margin-top: 6px;
          display: block;
        }}
      }}
    </style>
  </head>
  <body>
    <main class="page">
      <section class="hero">
        <div class="eyebrow">
          <span>AIOS-NP Daily Brief</span>
          <span>{escape(report_document['date_label'])}</span>
        </div>
        <h1>{escape(report_document['report_title'])}</h1>
        <p class="subtitle">{escape(report_document['report_subtitle'])}</p>
        <p class="overview">{escape(report_document['overview'])}</p>
        <div class="stats">
          <div class="stat"><div class="stat-label">Stories</div><div class="stat-value">{report_document['metrics']['total_articles']}</div></div>
          <div class="stat"><div class="stat-label">Sections</div><div class="stat-value">{report_document['metrics']['active_sections']}</div></div>
          <div class="stat"><div class="stat-label">Sources</div><div class="stat-value">{report_document['metrics']['total_sources']}</div></div>
          <div class="stat"><div class="stat-label">Updated</div><div class="stat-value">{escape(report_document['time_label'])}</div></div>
        </div>
      </section>
      <section class="content">
        <section class="panel">
          <h2>今日值得先看</h2>
          <div class="highlight-grid">{highlight_cards}</div>
        </section>
        {''.join(section_blocks)}
      </section>
      <div class="footer-note">Generated by AIOS-NP agent ecosystem</div>
    </main>
  </body>
</html>
"""

    def _htmlize_paragraphs(self, content: str) -> str:
        paragraphs = [paragraph.strip() for paragraph in content.split("\n") if paragraph.strip()]
        if not paragraphs:
            return "<p>暂无正文。</p>"
        return "".join(f"<p>{escape(paragraph)}</p>" for paragraph in paragraphs)


def main():
    parser = argparse.ArgumentParser(description="新闻报制作Agent")
    parser.add_argument("--intermediate_dir", type=str, default=str(INTERMEDIATE_DIR), help="中间文件目录")
    parser.add_argument("--output_dir", type=str, default=str(OUTPUT_DIR), help="输出目录")

    args = parser.parse_args()

    agent = MakerAgent()
    result = agent.run(args.intermediate_dir, args.output_dir)

    print(f"结果: {result['result']}")
    print(f"状态: {result['status']}")
    if "report_file" in result:
        print(f"新闻报文件: {result['report_file']}")


if __name__ == "__main__":
    main()
