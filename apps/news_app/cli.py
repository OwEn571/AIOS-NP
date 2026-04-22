from __future__ import annotations

import argparse
from typing import Sequence

from .pipeline import MODE_LABELS, NewsWorkflowApp


def build_arg_parser(default_mode: str | None = None) -> argparse.ArgumentParser:
    description = "运行 AIOS-NP 新闻应用工作流"
    parser = argparse.ArgumentParser(description=description)

    if default_mode is None:
        parser.add_argument(
            "--mode",
            choices=tuple(MODE_LABELS.keys()),
            default="parallel",
            help="工作流模式",
        )
    else:
        parser.set_defaults(mode=default_mode)

    parser.add_argument("--config", type=str, help="工作流配置文件路径")
    parser.add_argument("--zh-api-key", dest="zh_api_key", type=str, help="云析 API 密钥")
    parser.add_argument("--tavily-api-key", dest="tavily_api_key", type=str, help="Tavily API 密钥")
    return parser


def execute_from_args(args: argparse.Namespace) -> int:
    app = NewsWorkflowApp(
        mode=args.mode,
        config_path=args.config,
        zh_api_key=args.zh_api_key,
        tavily_api_key=args.tavily_api_key,
    )
    result = app.run()
    return 0 if result.get("status") == "success" else 1


def main(argv: Sequence[str] | None = None, default_mode: str | None = None) -> int:
    parser = build_arg_parser(default_mode=default_mode)
    args = parser.parse_args(list(argv) if argv is not None else None)
    return execute_from_args(args)
