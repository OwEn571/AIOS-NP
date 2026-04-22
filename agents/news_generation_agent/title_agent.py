#!/usr/bin/env python3
"""
新闻标题生成代理
"""

from cerebrum.llm.apis import llm_chat
from cerebrum.config.config_manager import config
aios_kernel_url = config.get_kernel_url()
import re

class TitleAgent:
    """新闻标题生成代理"""
    
    def __init__(self, agent_name: str = "title_agent"):
        self.agent_name = agent_name

    def generate_title(self, search_result: str, topic: str) -> str:
        """
        生成新闻标题
        
        :param search_result: 搜索结果内容
        :param topic: 新闻主题
        :return: 生成的标题
        """
        print(f"=== {self.agent_name} 开始生成标题 ===")
        print(f"主题: {topic}")
        
        prompt = f"""请基于以下搜索结果生成1个新闻标题：

主题：{topic}
搜索结果：{search_result}

要求：
1. 长度在12-18字之间
2. 使用吸引眼球的词汇
3. 包含冲突/悬念/数字等元素
4. 符合专业风格要求
5. 避免使用引号或其他符号包裹标题
6. 基于搜索结果中的核心信息生成

请直接输出标题文本，不要包含任何思考过程、解释或说明。不要使用<think>标签，不要描述你的思考过程。"""

        try:
            response = llm_chat(
                agent_name=self.agent_name,
                messages=[{"role": "user", "content": prompt}],
                base_url=aios_kernel_url,
            )
            title = self._extract_title_text(response)
            if title:
                print(f"✅ 标题生成完成: {title}")
                return title
            print("❌ LLM未返回可用标题")
            return ""
        except Exception as e:
            print(f"❌ 标题生成失败: {e}")
            return ""

    def regenerate_title(self, search_result: str, topic: str, feedback: str) -> str:
        """
        根据反馈重新生成标题
        
        :param search_result: 搜索结果内容
        :param topic: 新闻主题
        :param feedback: 评审反馈意见
        :return: 重新生成的标题
        """
        print(f"=== {self.agent_name} 根据反馈重新生成标题 ===")
        print(f"反馈意见: {feedback}")
        
        prompt = f"""请根据以下反馈意见重新生成新闻标题：

主题：{topic}
搜索结果：{search_result}
反馈意见：{feedback}

要求：
1. 长度在12-18字之间
2. 使用吸引眼球的词汇
3. 包含冲突/悬念/数字等元素
4. 符合专业风格要求
5. 避免使用引号或其他符号包裹标题
6. 根据反馈意见进行改进
7. 基于搜索结果中的核心信息生成

请直接输出标题文本，不要包含任何思考过程、解释或说明。不要使用<think>标签，不要描述你的思考过程。"""

        try:
            response = llm_chat(
                agent_name=self.agent_name,
                messages=[{"role": "user", "content": prompt}],
                base_url=aios_kernel_url,
            )
            title = self._extract_title_text(response)
            if title:
                print(f"✅ 标题重新生成完成: {title}")
                return title
            print("❌ LLM未返回可用标题")
            return ""
        except Exception as e:
            print(f"❌ 标题重新生成失败: {e}")
            return ""

    def _extract_title_text(self, response: dict) -> str:
        payload = (response or {}).get("response") or {}
        title = payload.get("response_message")
        if not isinstance(title, str) or not title.strip():
            error = payload.get("error")
            if error:
                print(f"⚠️ 标题生成上游错误: {error}")
            return ""

        title = title.strip()
        if "</think>" in title:
            title = title.split("</think>")[-1].strip()
        elif "<think>" in title:
            title = title.split("<think>")[-1].strip()

        title = re.sub(r'\n+', ' ', title).strip()
        title = re.sub(r'\s+', ' ', title).strip()
        return title
