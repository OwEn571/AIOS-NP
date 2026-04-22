"""News workflow application built on top of the AIOS kernel."""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "AgentRegistryManager",
    "AgentRegistryStore",
    "NewsAppConfig",
    "NewsEcosystemSettings",
    "NewsMetricsBuilder",
    "NEWS_DOMAINS",
    "NewsRunManager",
    "NewsScheduler",
    "NewsDomain",
    "NewsWorkflowApp",
    "NewsWorkflowStateBuilder",
    "build_domain_expert_instances",
    "load_news_app_config",
    "news_category_definitions",
    "news_category_file_map",
    "news_category_names",
    "news_category_output_template",
]

_EXPORT_MAP = {
    "AgentRegistryManager": (".agent_registry", "AgentRegistryManager"),
    "AgentRegistryStore": (".agent_registry", "AgentRegistryStore"),
    "NEWS_DOMAINS": (".news_registry", "NEWS_DOMAINS"),
    "NewsAppConfig": (".config", "NewsAppConfig"),
    "NewsDomain": (".news_registry", "NewsDomain"),
    "NewsEcosystemSettings": (".ecosystem", "NewsEcosystemSettings"),
    "NewsMetricsBuilder": (".metrics", "NewsMetricsBuilder"),
    "NewsRunManager": (".ecosystem", "NewsRunManager"),
    "NewsScheduler": (".ecosystem", "NewsScheduler"),
    "NewsWorkflowApp": (".pipeline", "NewsWorkflowApp"),
    "NewsWorkflowStateBuilder": (".state", "NewsWorkflowStateBuilder"),
    "build_domain_expert_instances": (".news_registry", "build_domain_expert_instances"),
    "load_news_app_config": (".config", "load_news_app_config"),
    "news_category_definitions": (".news_registry", "news_category_definitions"),
    "news_category_file_map": (".news_registry", "news_category_file_map"),
    "news_category_names": (".news_registry", "news_category_names"),
    "news_category_output_template": (".news_registry", "news_category_output_template"),
}


def __getattr__(name: str) -> Any:
    target = _EXPORT_MAP.get(name)
    if not target:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attr_name = target
    module = import_module(module_name, __name__)
    value = getattr(module, attr_name)
    globals()[name] = value
    return value
