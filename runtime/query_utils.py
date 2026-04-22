from typing import Any

from cerebrum.llm.apis import LLMQuery


def rebuild_llm_query(request_query: LLMQuery, llms: list[dict[str, Any]] | None) -> LLMQuery:
    """Rebuild an incoming LLMQuery while preserving all caller-supplied fields."""
    payload = request_query.model_dump()
    payload["llms"] = llms
    return LLMQuery(**payload)
