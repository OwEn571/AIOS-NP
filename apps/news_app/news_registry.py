from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NewsDomain:
    name: str
    description: str
    category_file: str
    expert_module: str
    expert_class: str
    expert_agent_name: str


NEWS_DOMAINS: tuple[NewsDomain, ...] = (
    NewsDomain(
        name="社会热点与公共事务",
        description="政治、社会事件、公共政策等",
        category_file="社会热点与公共事务_api.txt",
        expert_module="agents.social_affairs_expert.agent",
        expert_class="SocialAffairsExpert",
        expert_agent_name="social_affairs_expert",
    ),
    NewsDomain(
        name="娱乐与文化",
        description="明星、影视、音乐、文化等",
        category_file="娱乐与文化_api.txt",
        expert_module="agents.entertainment_culture_expert.agent",
        expert_class="EntertainmentCultureExpert",
        expert_agent_name="entertainment_culture_expert",
    ),
    NewsDomain(
        name="商业与经济",
        description="企业、经济、金融、市场等",
        category_file="商业与经济_api.txt",
        expert_module="agents.business_economy_expert.agent",
        expert_class="BusinessEconomyExpert",
        expert_agent_name="business_economy_expert",
    ),
    NewsDomain(
        name="科技与创新",
        description="科技产品、创新技术、互联网等",
        category_file="科技与创新_api.txt",
        expert_module="agents.tech_innovation_expert.agent",
        expert_class="TechInnovationExpert",
        expert_agent_name="tech_innovation_expert",
    ),
    NewsDomain(
        name="民生与健康",
        description="生活、健康、教育、民生等",
        category_file="民生与健康_api.txt",
        expert_module="agents.livelihood_health_expert.agent",
        expert_class="LivelihoodHealthExpert",
        expert_agent_name="livelihood_health_expert",
    ),
    NewsDomain(
        name="争议事件",
        description="有争议、敏感或负面的事件",
        category_file="争议事件_api.txt",
        expert_module="agents.controversy_expert.agent",
        expert_class="ControversyExpert",
        expert_agent_name="controversy_expert",
    ),
)


def news_category_names() -> tuple[str, ...]:
    return tuple(domain.name for domain in NEWS_DOMAINS)


def news_category_file_map() -> dict[str, str]:
    return {domain.name: domain.category_file for domain in NEWS_DOMAINS}


def news_category_definitions() -> str:
    return "\n".join(
        f"{index}. {domain.name} - {domain.description}"
        for index, domain in enumerate(NEWS_DOMAINS, start=1)
    )


def news_category_output_template() -> str:
    return "\n\n".join(f"{domain.name}:\n- 热点内容" for domain in NEWS_DOMAINS)


def build_domain_expert_instances() -> dict[str, Any]:
    import importlib

    instances: dict[str, Any] = {}
    for domain in NEWS_DOMAINS:
        module = importlib.import_module(domain.expert_module)
        expert_class = getattr(module, domain.expert_class)
        instances[domain.name] = expert_class(domain.expert_agent_name)
    return instances
