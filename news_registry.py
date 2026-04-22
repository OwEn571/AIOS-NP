"""Compatibility shim for the news domain registry.

The implementation now lives under ``apps.news_app.news_registry`` so the
business-specific registry stays inside the news application package. Keep
re-exporting the public symbols here for older imports and scripts.
"""

from apps.news_app.news_registry import (
    NEWS_DOMAINS,
    NewsDomain,
    build_domain_expert_instances,
    news_category_definitions,
    news_category_file_map,
    news_category_names,
    news_category_output_template,
)

__all__ = [
    "NEWS_DOMAINS",
    "NewsDomain",
    "build_domain_expert_instances",
    "news_category_definitions",
    "news_category_file_map",
    "news_category_names",
    "news_category_output_template",
]
