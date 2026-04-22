#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AIOS-NP 并行流水线兼容入口。

真实的业务编排逻辑已经迁移到 apps/news_app。
"""

from apps.news_app.cli import main as run_news_app_cli
from apps.news_app.pipeline import NewsWorkflowApp


class ParallelAiosPipeline(NewsWorkflowApp):
    """兼容旧接口，内部转发到统一的 NewsWorkflowApp。"""

    def __init__(self, zh_api_key: str | None = None, tavily_api_key: str | None = None):
        super().__init__(
            mode="parallel",
            zh_api_key=zh_api_key,
            tavily_api_key=tavily_api_key,
        )

    def run_parallel_pipeline(self):
        return self.run()


def main() -> int:
    return run_news_app_cli(default_mode="parallel")


if __name__ == "__main__":
    raise SystemExit(main())
