#!/usr/bin/env python3
"""
新闻摘要生成代理
"""

from cerebrum.llm.apis import llm_chat
from cerebrum.config.config_manager import config
aios_kernel_url = config.get_kernel_url()
import re

class SummaryAgent:
    """新闻摘要生成代理"""
    
    def __init__(self, agent_name: str = "summary_agent"):
        self.agent_name = agent_name

    def generate_summary(self, search_result: str, topic: str) -> str:
        """
        生成新闻摘要
        
        :param search_result: 搜索结果内容
        :param topic: 新闻主题
        :return: 生成的摘要
        """
        print(f"=== {self.agent_name} 开始生成摘要 ===")
        print(f"主题: {topic}")
        
        prompt = f"""请基于以下搜索结果生成1个专业风格的新闻摘要：

主题：{topic}
搜索结果：{search_result}

要求：
1. 长度在80-120字之间
2. 保留搜索结果中的核心信息和关键数据
3. 语言简洁流畅，逻辑清晰
4. 避免添加额外解释或个人观点
5. 基于搜索结果中的最新、最重要的信息
6. 不要包含字数统计，如"(119字)"等

请直接输出摘要文本，不要包含任何思考过程、解释或说明。不要使用<think>标签，不要描述你的思考过程。"""

        try:
            response = llm_chat(
                agent_name=self.agent_name,
                messages=[{"role": "user", "content": prompt}],
                base_url=aios_kernel_url,
            )
            summary = self._extract_summary_text(response)
            if summary:
                print(f"✅ 摘要生成完成: {len(summary)} 字符")
                return summary
            print("❌ LLM未返回可用摘要")
            return ""
        except Exception as e:
            print(f"❌ 摘要生成失败: {e}")
            return ""

    def regenerate_summary(self, search_result: str, topic: str, feedback: str) -> str:
        """
        根据反馈重新生成摘要
        
        :param search_result: 搜索结果内容
        :param topic: 新闻主题
        :param feedback: 评审反馈意见
        :return: 重新生成的摘要
        """
        print(f"=== {self.agent_name} 根据反馈重新生成摘要 ===")
        print(f"反馈意见: {feedback}")
        
        prompt = f"""请根据以下反馈意见重新生成新闻摘要：

主题：{topic}
搜索结果：{search_result}
反馈意见：{feedback}

要求：
1. 长度在80-120字之间
2. 保留搜索结果中的核心信息和关键数据
3. 语言简洁流畅，逻辑清晰
4. 避免添加额外解释或个人观点
5. 根据反馈意见进行改进
6. 基于搜索结果中的最新、最重要的信息
7. 不要包含字数统计，如"(119字)"等

请直接输出摘要文本，不要包含任何思考过程、解释或说明。不要使用<think>标签，不要描述你的思考过程。"""

        try:
            response = llm_chat(
                agent_name=self.agent_name,
                messages=[{"role": "user", "content": prompt}],
                base_url=aios_kernel_url,
            )
            summary = self._extract_summary_text(response)
            if summary:
                print(f"✅ 摘要重新生成完成: {len(summary)} 字符")
                return summary
            print("❌ LLM未返回可用摘要")
            return ""
        except Exception as e:
            print(f"❌ 摘要重新生成失败: {e}")
            return ""

    def _extract_summary_text(self, response: dict) -> str:
        payload = (response or {}).get("response") or {}
        summary = payload.get("response_message")
        if not isinstance(summary, str) or not summary.strip():
            error = payload.get("error")
            if error:
                print(f"⚠️ 摘要生成上游错误: {error}")
            return ""

        summary = summary.strip()
        if "</think>" in summary:
            summary = summary.split("</think>")[-1].strip()
        elif "<think>" in summary:
            summary = summary.split("<think>")[-1].strip()

        summary = re.sub(r'\n+', ' ', summary).strip()
        summary = re.sub(r'\s+', ' ', summary).strip()
        return summary
