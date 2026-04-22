from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from typing import Any
from urllib.parse import urlparse


RESULT_PATTERN = re.compile(
    r"【结果\s*\d+】\s*"
    r"标题:\s*(?P<title>.+?)\n"
    r"链接:\s*(?P<link>.+?)\n"
    r"📄 清理后的核心内容:\s*(?P<content>.*?)(?=\n【结果\s*\d+】|\Z)",
    re.DOTALL,
)

LOW_SIGNAL_DOMAIN_KEYWORDS = (
    "wikipedia.org",
    "wiki",
    "tieba.baidu.com",
    "baike.baidu.com",
    "zaojv.com",
    "chengyu",
    "dict",
    "zenodo.org",
    "download",
    "tool",
    "bbs",
    "forum",
)

TRUSTED_NEWS_DOMAIN_KEYWORDS = (
    "fact.qq.com",
    "news.qq.com",
    "xinhuanet.com",
    "news.cn",
    "people.com.cn",
    "cctv.com",
    "news.cctv.com",
    "thepaper.cn",
    "stcn.com",
    "ifeng.com",
    "sina.com.cn",
    "sina.cn",
    "163.com",
    "sohu.com",
    "bjnews.com.cn",
    "caixin.com",
    "yicai.com",
    "eastmoney.com",
    "dw.com",
    "chinanews.com.cn",
    "china.com",
    "dongqiudi.com",
    "zhibo8.com",
    "ctdsb.net",
)

LOW_SIGNAL_TEXT_KEYWORDS = (
    "成语",
    "造句",
    "词典",
    "百科",
    "贴吧",
    "接龙",
    "释义",
    "拼音",
    "注音",
    "作谓语",
    "虚构",
    "剧情",
    "设定",
    "角色",
    "番剧",
    "网文",
    "小说",
    "游戏攻略",
)

FICTION_TEXT_KEYWORDS = (
    "虚构",
    "剧情",
    "系列作品",
    "角色关系",
    "骑士",
    "背叛",
    "家族责任",
    "编剧",
    "观众反馈",
)

HISTORY_TOPIC_PATTERN = re.compile(r"^\d{4}年[-—]")
PLACEHOLDER_REASON_MARKERS = ("由搜索结果文本自动提取", "供日报展示使用")
DISPLAY_SOURCE_MIN_RELEVANCE = 35
DISPLAY_SOURCE_MAX_ITEMS = 4

CONTROVERSY_SIGNAL_KEYWORDS = (
    "争议",
    "冲突",
    "暴力",
    "袭击",
    "遇难",
    "身亡",
    "诈骗",
    "被骗",
    "事故",
    "违法",
    "违纪",
    "调查",
    "起诉",
    "打假",
    "风波",
    "丑闻",
    "禁令",
    "危机",
)

ENTERTAINMENT_SPORTS_KEYWORDS = (
    "夺冠",
    "冠军",
    "加冕",
    "捧杯",
    "首冠",
    "晋级",
    "决赛",
    "巡回锦标赛",
    "斯诺克",
    "世界杯",
    "演员",
    "影",
    "剧",
    "综艺",
    "歌手",
    "演唱会",
    "票房",
    "赵心童",
    "王楚钦",
    "郭艾伦",
    "TVB",
)

BUSINESS_KEYWORDS = (
    "集团",
    "量产",
    "化债",
    "债务",
    "调仓",
    "etf",
    "股",
    "债",
    "企业",
    "公司",
    "财经",
    "机器人",
    "市场",
)

TECH_KEYWORDS = (
    "模型",
    "agent",
    "ai",
    "芯片",
    "微信",
    "小程序",
    "停运",
    "机器人",
    "科技",
    "医院",
    "nasa",
    "外星",
    "调用量",
)

LIVELIHOOD_KEYWORDS = (
    "心梗",
    "医院",
    "专家",
    "健康",
    "洗衣液",
    "洗衣粉",
    "自闭症",
    "孩子",
    "妈妈",
    "民生",
    "生活",
)

EVENT_KEYWORD_FAMILIES = (
    ("夺冠", ("夺冠", "冠军", "加冕", "捧杯", "首冠", "夺得", "大胜")),
    ("去世", ("去世", "离世", "病逝", "身亡")),
    ("停运", ("停运", "停止服务", "停服", "下线")),
    ("心梗", ("心梗", "急诊", "医院")),
    ("模型", ("模型", "调用量", "openrouter", "国产大模型")),
    ("机器人", ("机器人", "人形机器人")),
)


@dataclass
class SearchSource:
    title: str
    link: str
    content: str
    domain: str
    trusted_news: bool
    low_signal: bool


@dataclass
class EditorialDecision:
    accepted: bool
    score: int
    reasons: list[str]
    topic: str
    category: str
    trusted_source_count: int
    low_signal_source_count: int
    source_count: int
    memory_hint_count: int = 0
    memory_accept_count: int = 0
    memory_reject_count: int = 0
    memory_score_delta: int = 0
    strongest_memory_similarity: float = 0.0
    memory_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_search_sources(search_data: str) -> list[SearchSource]:
    sources: list[SearchSource] = []
    for match in RESULT_PATTERN.finditer(search_data):
        title = match.group("title").strip()
        link = match.group("link").strip()
        content = match.group("content").strip()
        domain = _normalize_domain(link)
        lowered = f"{title}\n{link}\n{content}".lower()
        trusted_news = any(keyword in domain for keyword in TRUSTED_NEWS_DOMAIN_KEYWORDS)
        low_signal = any(keyword in lowered for keyword in LOW_SIGNAL_TEXT_KEYWORDS) or any(
            keyword in domain for keyword in LOW_SIGNAL_DOMAIN_KEYWORDS
        )
        sources.append(
            SearchSource(
                title=title,
                link=link,
                content=content,
                domain=domain,
                trusted_news=trusted_news,
                low_signal=low_signal,
            )
        )
    return sources


def evaluate_generation_input(
    category: str,
    topic: str,
    search_data: str,
    *,
    memory_hints: list[dict[str, Any]] | None = None,
) -> EditorialDecision:
    stripped = search_data.strip()
    if not stripped:
        return EditorialDecision(
            accepted=False,
            score=0,
            reasons=["搜索结果为空，无法支撑新闻生成。"],
            topic=topic,
            category=category,
            trusted_source_count=0,
            low_signal_source_count=0,
            source_count=0,
        )

    sources = extract_search_sources(stripped)
    trusted_source_count = sum(1 for source in sources if source.trusted_news)
    low_signal_source_count = sum(1 for source in sources if source.low_signal)

    reasons: list[str] = []
    score = 100
    topic_lower = topic.lower()
    body_lower = stripped.lower()

    if HISTORY_TOPIC_PATTERN.search(topic):
        score -= 45
        reasons.append("热点标题更像历史纪念或词条，不像当日新闻。")

    if not sources:
        score -= 60
        reasons.append("搜索结果没有解析出有效信源。")

    if trusted_source_count == 0:
        score -= 45
        reasons.append("搜索结果里没有可信新闻站点，只有词典/社区/资料站等低信号来源。")

    if low_signal_source_count >= max(2, len(sources) - 1) and trusted_source_count == 0:
        score -= 55
        reasons.append("搜索结果主要是词条、百科、贴吧或资料页，不具备新闻报道基础。")

    if any(keyword in topic for keyword in ("成语", "造句", "接龙")):
        score -= 55
        reasons.append("热点标题本身像词条解释，不像新闻事件。")

    if any(keyword in topic_lower for keyword in FICTION_TEXT_KEYWORDS) or any(
        keyword in body_lower for keyword in FICTION_TEXT_KEYWORDS
    ):
        score -= 60
        reasons.append("搜索结果更像虚构剧情或作品讨论，不像可核验的现实新闻。")

    if "means changing from arrogance to humility" in body_lower or "is a chinese idiom" in body_lower:
        score -= 55
        reasons.append("知识图谱答案表明这是成语解释，不是新闻。")

    memory_feedback = summarize_editorial_memory_feedback(
        topic=topic,
        memory_hints=memory_hints or [],
    )
    score += memory_feedback["score_delta"]
    reasons.extend(memory_feedback["reasons"])

    accepted = score >= 40 and not any(
        reason
        for reason in reasons
        if "不具备新闻报道基础" in reason
        or "不像新闻" in reason
        or "搜索结果为空" in reason
        or "虚构剧情" in reason
    )

    return EditorialDecision(
        accepted=accepted,
        score=max(score, 0),
        reasons=reasons,
        topic=topic,
        category=category,
        trusted_source_count=trusted_source_count,
        low_signal_source_count=low_signal_source_count,
        source_count=len(sources),
        memory_hint_count=memory_feedback["hint_count"],
        memory_accept_count=memory_feedback["accepted_hint_count"],
        memory_reject_count=memory_feedback["rejected_hint_count"],
        memory_score_delta=memory_feedback["score_delta"],
        strongest_memory_similarity=memory_feedback["strongest_similarity"],
        memory_reasons=memory_feedback["reasons"],
    )


def evaluate_publishability(
    *,
    category: str,
    topic: str,
    title: str,
    sources: list[dict[str, Any]],
    memory_hints: list[dict[str, Any]] | None = None,
) -> EditorialDecision:
    if not sources:
        return EditorialDecision(
            accepted=False,
            score=0,
            reasons=["缺少可展示的参考信源，不能进入日报。"],
            topic=topic or title,
            category=category,
            trusted_source_count=0,
            low_signal_source_count=0,
            source_count=0,
        )

    normalized_sources = []
    for source in sources:
        link = str(source.get("link") or "")
        domain = _normalize_domain(link)
        title_text = str(source.get("title") or "")
        blob = f"{title_text}\n{link}".lower()
        normalized_sources.append(
            {
                "domain": domain,
                "trusted_news": any(keyword in domain for keyword in TRUSTED_NEWS_DOMAIN_KEYWORDS),
                "low_signal": any(keyword in blob for keyword in LOW_SIGNAL_TEXT_KEYWORDS)
                or any(keyword in domain for keyword in LOW_SIGNAL_DOMAIN_KEYWORDS),
                "relevance_score": int(source.get("relevance_score", 0) or 0),
            }
        )

    scores = [item["relevance_score"] for item in normalized_sources]
    max_score = max(scores) if scores else 0
    avg_score = round(sum(scores) / len(scores), 2) if scores else 0.0
    trusted_source_count = sum(1 for item in normalized_sources if item["trusted_news"])
    low_signal_source_count = sum(1 for item in normalized_sources if item["low_signal"])

    reasons: list[str] = []
    score = 100
    hard_blocked = False

    if max_score < 35:
        score -= 60
        reasons.append("最高信源匹配度过低，说明这篇稿件缺少可靠事实支撑。")
        hard_blocked = True

    if avg_score < 25:
        score -= 35
        reasons.append("整体信源匹配度过低，不适合进入最终日报。")
        hard_blocked = True

    if trusted_source_count == 0 and low_signal_source_count >= 1:
        score -= 45
        reasons.append("参考来源主要是低信号页面，不适合作为新闻信源。")
        hard_blocked = True

    if any(keyword in (title or topic).lower() for keyword in FICTION_TEXT_KEYWORDS):
        score -= 50
        reasons.append("标题呈现出明显的虚构剧情特征，不进入日报。")
        hard_blocked = True

    memory_feedback = summarize_editorial_memory_feedback(
        topic=topic or title,
        memory_hints=memory_hints or [],
    )
    score += memory_feedback["score_delta"]
    reasons.extend(memory_feedback["reasons"])

    accepted = score >= 40 and not hard_blocked

    return EditorialDecision(
        accepted=accepted,
        score=max(score, 0),
        reasons=reasons,
        topic=topic or title,
        category=category,
        trusted_source_count=trusted_source_count,
        low_signal_source_count=low_signal_source_count,
        source_count=len(sources),
        memory_hint_count=memory_feedback["hint_count"],
        memory_accept_count=memory_feedback["accepted_hint_count"],
        memory_reject_count=memory_feedback["rejected_hint_count"],
        memory_score_delta=memory_feedback["score_delta"],
        strongest_memory_similarity=memory_feedback["strongest_similarity"],
        memory_reasons=memory_feedback["reasons"],
    )


def filter_display_sources(
    raw_sources: list[dict[str, Any]],
    *,
    min_score: int = DISPLAY_SOURCE_MIN_RELEVANCE,
    max_items: int = DISPLAY_SOURCE_MAX_ITEMS,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    seen_links: set[str] = set()

    for source in raw_sources:
        title = str(source.get("title") or "").strip()
        link = str(source.get("link") or "").strip()
        if not title or not link or link in seen_links:
            continue

        score = int(source.get("relevance_score", 0) or 0)
        if score < min_score:
            continue

        reason = sanitize_source_reason(score, str(source.get("relevance_reason") or ""))
        filtered.append(
            {
                "title": title,
                "link": link,
                "relevance_score": score,
                "relevance_reason": reason,
                "key_info": str(source.get("key_info") or "").strip(),
            }
        )
        seen_links.add(link)

    return filtered[:max_items]


def sanitize_source_reason(score: int, reason: str) -> str:
    stripped = reason.strip()
    if stripped and not any(marker in stripped for marker in PLACEHOLDER_REASON_MARKERS):
        return stripped

    if score >= 85:
        return "与主题高度相关，可作为核心参考信源。"
    if score >= 60:
        return "与主题基本相关，可作为补充参考信源。"
    return "与主题关联度有限，仅供延伸阅读时参考。"


def route_story_category(category: str, topic: str, title: str) -> str:
    text = f"{title}\n{topic}".lower()

    if category == "争议事件":
        if any(keyword in text for keyword in CONTROVERSY_SIGNAL_KEYWORDS):
            return "争议事件"
        if any(keyword.lower() in text for keyword in ENTERTAINMENT_SPORTS_KEYWORDS):
            return "娱乐与文化"
        if any(keyword.lower() in text for keyword in BUSINESS_KEYWORDS):
            return "商业与经济"
        if any(keyword.lower() in text for keyword in TECH_KEYWORDS):
            return "科技与创新"
        if any(keyword.lower() in text for keyword in LIVELIHOOD_KEYWORDS):
            return "民生与健康"
        return "社会热点与公共事务"

    return category


def build_story_dedupe_key(category: str, topic: str, title: str) -> str:
    base_text = f"{title} {topic}".strip()
    normalized = re.sub(r"[^\w\u4e00-\u9fff]+", "", base_text.lower())
    if not normalized:
        return f"{category}:unknown"

    chinese_lead = re.match(r"([\u4e00-\u9fff]{2,})", normalized)
    if chinese_lead:
        lead = chinese_lead.group(1)[:3]
    else:
        lead_match = re.match(r"([a-z]{2,12}|\d+(?:\.\d+)?万亿元etf)", normalized)
        lead = lead_match.group(1) if lead_match else normalized[:8]

    event_tag = ""
    for canonical, keywords in EVENT_KEYWORD_FAMILIES:
        if any(keyword.lower() in base_text.lower() for keyword in keywords):
            event_tag = canonical
            break

    if event_tag:
        return f"{lead}:{event_tag}"
    return f"{category}:{normalized[:18]}"


def summarize_editorial_memory_feedback(
    *,
    topic: str,
    memory_hints: list[dict[str, Any]],
) -> dict[str, Any]:
    used_hints: list[dict[str, Any]] = []

    for hint in memory_hints:
        body = hint.get("body") if isinstance(hint, dict) else None
        if not isinstance(body, dict):
            continue
        hint_topic = str(body.get("topic") or "").strip()
        if not hint_topic:
            continue
        similarity = _topic_similarity(topic, hint_topic)
        if similarity < 0.28:
            continue
        used_hints.append(
            {
                "accepted": bool(body.get("accepted")),
                "similarity": similarity,
                "topic": hint_topic,
                "score": int(body.get("score") or 0),
            }
        )

    if not used_hints:
        return {
            "hint_count": 0,
            "accepted_hint_count": 0,
            "rejected_hint_count": 0,
            "score_delta": 0,
            "strongest_similarity": 0.0,
            "reasons": [],
        }

    strongest_similarity = max(item["similarity"] for item in used_hints)
    accepted_hint_count = sum(1 for item in used_hints if item["accepted"])
    rejected_hint_count = sum(1 for item in used_hints if not item["accepted"])

    score_delta = 0
    if rejected_hint_count:
        score_delta -= min(18, rejected_hint_count * 4 + round(strongest_similarity * 8))
    if accepted_hint_count:
        score_delta += min(12, accepted_hint_count * 3 + round(strongest_similarity * 4))

    reasons: list[str] = []
    if rejected_hint_count > accepted_hint_count:
        reasons.append(
            f"AIOS memory 命中了 {rejected_hint_count} 条相近题材的历史拒绝记录，降低本次接受分。"
        )
    elif accepted_hint_count > rejected_hint_count:
        reasons.append(
            f"AIOS memory 命中了 {accepted_hint_count} 条相近题材的历史通过记录，提升本次接受分。"
        )
    elif accepted_hint_count and rejected_hint_count:
        reasons.append("AIOS memory 命中了相互矛盾的历史记录，本次只做轻度调整。")

    if rejected_hint_count and strongest_similarity >= 0.8:
        reasons.append("当前主题与历史拒稿高度相似，需要更强信源或更明确的新闻性。")

    return {
        "hint_count": len(used_hints),
        "accepted_hint_count": accepted_hint_count,
        "rejected_hint_count": rejected_hint_count,
        "score_delta": score_delta,
        "strongest_similarity": round(strongest_similarity, 4),
        "reasons": reasons,
    }


def _normalize_domain(link: str) -> str:
    try:
        domain = urlparse(link).netloc.lower().strip()
    except ValueError:
        return ""
    if domain.startswith("www."):
        domain = domain[4:]
    return domain


def _normalize_story_text(value: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", (value or "").lower())


def _topic_similarity(left: str, right: str) -> float:
    left_normalized = _normalize_story_text(left)
    right_normalized = _normalize_story_text(right)
    if not left_normalized or not right_normalized:
        return 0.0

    sequence_score = SequenceMatcher(None, left_normalized, right_normalized).ratio()
    left_tokens = set(re.findall(r"[\w\u4e00-\u9fff]{2,}", left_normalized))
    right_tokens = set(re.findall(r"[\w\u4e00-\u9fff]{2,}", right_normalized))
    token_score = 0.0
    if left_tokens and right_tokens:
        token_score = len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
    substring_score = 1.0 if left_normalized in right_normalized or right_normalized in left_normalized else 0.0
    return max(sequence_score, token_score, substring_score)
