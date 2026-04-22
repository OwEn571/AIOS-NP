import json
import os
import re
import sys
import time
from typing import Any, Dict

from cerebrum.tool.apis import call_tool
from cerebrum.tool.core.owen.web_search_tool.entry import WebSearch


ERROR_PREFIXES = ("错误：", "搜索失败:")
DEFAULT_MAX_CORE_CONTENT_CHARS = int(
    os.getenv("NEWS_SEARCH_MAX_CORE_CONTENT_CHARS", "20000")
)


def truncate_search_content(content: str, max_length: int) -> str:
    results = re.findall(r"【结果 \d+】", content)
    if len(results) <= 1:
        return content[:max_length]

    current_content = content
    for index in range(len(results) - 1, 0, -1):
        last_result_pattern = results[index]
        last_result_pos = current_content.rfind(last_result_pattern)
        if last_result_pos == -1:
            break

        truncated = current_content[:last_result_pos].rstrip()
        if len(truncated) <= max_length:
            return truncated
        current_content = truncated

    return current_content[:max_length]


def separate_content_and_images(
    search_result: str,
    max_core_length: int = DEFAULT_MAX_CORE_CONTENT_CHARS,
) -> tuple[str, str]:
    knowledge_match = re.search(
        r"💡 知识图谱答案:\s*(.*?)(?=📊 返回结果数量:|$)",
        search_result,
        re.DOTALL,
    )
    knowledge_content = knowledge_match.group(1).strip() if knowledge_match else ""
    results = re.split(r"【结果 \d+】", search_result)

    core_parts = []
    image_parts = []

    if knowledge_content:
        core_parts.append(f"💡 知识图谱答案:\n{knowledge_content}")

    for index, result in enumerate(results):
        if index == 0:
            continue

        cleaned_result = result.strip()
        if not cleaned_result:
            continue

        title_match = re.search(r"标题:\s*(.*?)(?=链接:|$)", cleaned_result, re.DOTALL)
        link_match = re.search(
            r"链接:\s*(.*?)(?=内容摘要:|📄 清理后的核心内容[:：]|$)",
            cleaned_result,
            re.DOTALL,
        )
        core_match = re.search(
            r"📄 清理后的核心内容[:：]\s*(.*?)(?=🖼️ 相关图片[:：]|$)",
            cleaned_result,
            re.DOTALL,
        )
        image_match = re.search(
            r"🖼️ 相关图片:\s*(.*?)(?=📄 清理后的核心内容[:：]|$)",
            cleaned_result,
            re.DOTALL,
        )

        if image_match:
            image_content = image_match.group(1).strip()
            if image_content:
                image_parts.append(f"【结果 {index}】\n{image_content}")

        result_parts = []
        if title_match:
            result_parts.append(f"标题: {title_match.group(1).strip()}")
        if link_match:
            result_parts.append(f"链接: {link_match.group(1).strip()}")
        if core_match:
            result_parts.append(f"📄 清理后的核心内容:\n{core_match.group(1).strip()}")

        if result_parts:
            core_parts.append(f"【结果 {index}】\n" + "\n".join(result_parts))

    core_content = "\n\n".join(core_parts) if core_parts else ""
    image_content = "\n\n".join(image_parts) if image_parts else ""

    if len(core_content) > max_core_length:
        core_content = truncate_search_content(core_content, max_core_length)

    return core_content, image_content


def process_topic(
    *,
    topic: str,
    max_results: int,
    api_key: str | None = None,
) -> Dict[str, Any]:
    started_at = time.time()
    if api_key:
        os.environ["TAVILY_API_KEY"] = api_key

    raw_result = _run_topic_search(topic=topic, max_results=max_results)
    core_content, image_content = separate_content_and_images(raw_result)
    is_error = isinstance(raw_result, str) and raw_result.startswith(ERROR_PREFIXES)

    return {
        "status": "failed" if is_error else "success",
        "topic": topic,
        "core_content": core_content,
        "image_content": image_content,
        "raw_result_length": len(raw_result or ""),
        "raw_result_preview": (raw_result or "")[:600],
        "message": raw_result if is_error else None,
        "elapsed_seconds": round(time.time() - started_at, 3),
    }


def _run_topic_search(*, topic: str, max_results: int) -> str:
    try:
        response = call_tool(
            "web_search_topic_worker",
            [
                {
                    "name": "web_search",
                    "parameters": {
                        "query": topic,
                        "max_results": max_results,
                    },
                }
            ],
        )
        raw_result = _extract_tool_text(response)
        if raw_result:
            return raw_result
    except Exception:
        pass

    return WebSearch().run(
        {
            "query": topic,
            "max_results": max_results,
        }
    )


def _extract_tool_text(response: Any) -> str:
    if isinstance(response, dict):
        payload = response.get("response")
        if isinstance(payload, dict):
            message = payload.get("response_message")
            if isinstance(message, str):
                return message
    raise RuntimeError(f"invalid web_search tool response: {response!r}")


def main() -> None:
    try:
        payload = json.load(sys.stdin)
        result = process_topic(
            topic=str(payload.get("topic") or ""),
            max_results=int(payload.get("max_results") or 5),
            api_key=str(payload.get("api_key") or "") or None,
        )
    except Exception as exc:
        result = {
            "status": "failed",
            "topic": "",
            "core_content": "",
            "image_content": "",
            "raw_result_length": 0,
            "raw_result_preview": "",
            "message": f"topic worker failed: {exc}",
            "elapsed_seconds": 0,
        }

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
