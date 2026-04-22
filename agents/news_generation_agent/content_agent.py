#!/usr/bin/env python3
"""
新闻内容生成代理
"""

from cerebrum.llm.apis import llm_chat
from cerebrum.config.config_manager import config
aios_kernel_url = config.get_kernel_url()
import re

class ContentAgent:
    """新闻内容生成代理"""
    
    def __init__(self, agent_name: str = "content_agent"):
        self.agent_name = agent_name

    def generate_content(self, search_result: str, topic: str) -> str:
        """
        生成新闻内容
        
        :param search_result: 搜索结果内容
        :param topic: 新闻主题
        :return: 生成的内容
        """
        print(f"=== {self.agent_name} 开始生成内容 ===")
        print(f"主题: {topic}")
        
        prompt = f"""请基于以下搜索结果生成300-500字数的专业新闻正文内容：

主题：{topic}
搜索结果：{search_result}

要求：
1. 长度在300-500字之间
2. 基于搜索结果中的核心事实进行展开、解释、补充细节、提供背景、引述观点和描述影响
3. 条理要清晰，逻辑要顺畅、客观准确
4. 避免使用引号或其他符号包裹新闻内容
5. 使用搜索结果中的具体数据和事实
6. 只输出新闻正文内容，不要包含标题、副标题或其他格式标记
7. 直接以正文内容开始，不要添加"内容："、"正文："等前缀

请直接输出新闻正文内容，不要包含任何思考过程、解释或说明。"""

        try:
            response = llm_chat(
                agent_name=self.agent_name,
                messages=[{"role": "user", "content": prompt}],
                base_url=aios_kernel_url,
            )
            content = self._extract_content_text(response)
            if content:
                print(f"✅ 内容生成完成: {len(content)} 字符")
                return content
            print("❌ LLM未返回可用正文")
            return ""
        except Exception as e:
            print(f"❌ 内容生成失败: {e}")
            return ""

    def regenerate_content(self, search_result: str, topic: str, feedback: str) -> str:
        """
        根据反馈重新生成内容
        
        :param search_result: 搜索结果内容
        :param topic: 新闻主题
        :param feedback: 评审反馈意见
        :return: 重新生成的内容
        """
        print(f"=== {self.agent_name} 根据反馈重新生成内容 ===")
        print(f"反馈意见: {feedback}")
        
        prompt = f"""请根据以下反馈意见重新生成新闻正文内容：

主题：{topic}
搜索结果：{search_result}
反馈意见：{feedback}

要求：
1. 长度在300-500字之间
2. 基于搜索结果中的核心事实进行展开、解释、补充细节、提供背景、引述观点和描述影响
3. 条理要清晰，逻辑要顺畅、客观准确
4. 避免使用引号或其他符号包裹新闻内容
5. 根据反馈意见进行改进
6. 使用搜索结果中的具体数据和事实
7. 只输出新闻正文内容，不要包含标题、副标题或其他格式标记
8. 直接以正文内容开始，不要添加"内容："、"正文："等前缀

请直接输出新闻正文内容，不要包含任何思考过程、解释或说明。"""

        try:
            response = llm_chat(
                agent_name=self.agent_name,
                messages=[{"role": "user", "content": prompt}],
                base_url=aios_kernel_url,
            )
            content = self._extract_content_text(response)
            if content:
                print(f"✅ 内容重新生成完成: {len(content)} 字符")
                return content
            print("❌ LLM未返回可用正文")
            return ""
        except Exception as e:
            print(f"❌ 内容重新生成失败: {e}")
            return ""

    def _extract_content_text(self, response: dict) -> str:
        payload = (response or {}).get("response") or {}
        content = payload.get("response_message")
        if not isinstance(content, str) or not content.strip():
            error = payload.get("error")
            if error:
                print(f"⚠️ 正文生成上游错误: {error}")
            return ""

        content = content.strip()
        if "</think>" in content:
            content = content.split("</think>")[-1].strip()
        elif "<think>" in content:
            content = content.split("<think>")[-1].strip()

        content = re.sub(r'\n+', ' ', content).strip()
        content = re.sub(r'\s+', ' ', content).strip()
        return content
