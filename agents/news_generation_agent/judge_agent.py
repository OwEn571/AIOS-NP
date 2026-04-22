#!/usr/bin/env python3
"""
新闻质量评审代理
"""

import json
import re
from typing import Dict, List, Tuple

from cerebrum.config.config_manager import config
from cerebrum.llm.apis import llm_chat
from project_paths import INTERMEDIATE_DIR
from runtime_support.artifacts import get_artifact_store

aios_kernel_url = config.get_kernel_url()

class JudgeAgent:
    """新闻质量评审代理"""

    TITLE_LENGTH_RANGE = (10, 24)
    SUMMARY_LENGTH_RANGE = (60, 160)
    CONTENT_LENGTH_RANGE = (260, 650)
    
    def __init__(self, agent_name: str = "judge_agent"):
        self.agent_name = agent_name
        self.store = get_artifact_store()

    def _range_text(self, bounds: tuple[int, int]) -> str:
        return f"{bounds[0]}-{bounds[1]}字"

    def _within_range(self, text: str, bounds: tuple[int, int]) -> bool:
        return bounds[0] <= len(text) <= bounds[1]

    def judge_news_parts(self, title: str, summary: str, content: str, topic: str) -> Dict[str, any]:
        """
        评审新闻的各个部分
        
        :param title: 新闻标题
        :param summary: 新闻摘要
        :param content: 新闻内容
        :param topic: 新闻主题
        :return: 评审结果字典，包含各部分是否通过和反馈意见
        """
        print(f"=== {self.agent_name} 开始评审新闻各部分 ===")
        print(f"主题: {topic}")
        
        prompt = f"""请对以下新闻内容进行质量评审：

标题：{title}
摘要：{summary}
内容：{content}
主题：{topic}

评审标准：
1. 标题：{self._range_text(self.TITLE_LENGTH_RANGE)}，有吸引力，包含核心信息
2. 摘要：{self._range_text(self.SUMMARY_LENGTH_RANGE)}，简洁明了，包含关键信息
3. 内容：{self._range_text(self.CONTENT_LENGTH_RANGE)}，逻辑清晰，客观准确
4. 整体：标题、摘要、内容要协调一致
5. 风格：专业、客观、准确
6. 语言：必须使用简体中文，不得出现繁体字、英文或其他语言

请返回JSON格式的评审结果，包含以下字段：
- title_pass: 标题是否通过 (true/false)
- summary_pass: 摘要是否通过 (true/false)
- content_pass: 内容是否通过 (true/false)
- title_feedback: 标题的反馈意见（如果不通过）
- summary_feedback: 摘要的反馈意见（如果不通过）
- content_feedback: 内容的反馈意见（如果不通过）
- overall_score: 整体评分 (1-10分)

请直接返回JSON格式，不要包含任何思考过程、解释或说明。"""

        try:
            response = llm_chat(
                agent_name=self.agent_name,
                messages=[{"role": "user", "content": prompt}],
                base_url=aios_kernel_url,
            )
            
            if response and "response" in response and response["response"]:
                response_text = response["response"]["response_message"].strip()
                
                # 清理think标签
                if "</think>" in response_text:
                    response_text = response_text.split("</think>")[-1].strip()
                elif "<think>" in response_text:
                    response_text = response_text.split("<think>")[-1].strip()
                
                # 尝试解析JSON
                try:
                    result = json.loads(response_text)
                    print(f"✅ 评审完成 - 标题: {'通过' if result.get('title_pass', False) else '不通过'}, "
                          f"摘要: {'通过' if result.get('summary_pass', False) else '不通过'}, "
                          f"内容: {'通过' if result.get('content_pass', False) else '不通过'}")
                    return result
                except json.JSONDecodeError:
                    print("❌ JSON解析失败，使用默认评审结果")
                    return self._default_judgment(title, summary, content)
            else:
                print("❌ LLM响应为空或格式错误")
                return self._default_judgment(title, summary, content)
        except Exception as e:
            print(f"❌ 评审失败: {e}")
            return self._default_judgment(title, summary, content)

    def _default_judgment(self, title: str, summary: str, content: str) -> Dict[str, any]:
        """默认评审结果"""
        return {
            "title_pass": self._within_range(title, self.TITLE_LENGTH_RANGE),
            "summary_pass": self._within_range(summary, self.SUMMARY_LENGTH_RANGE),
            "content_pass": self._within_range(content, self.CONTENT_LENGTH_RANGE),
            "title_feedback": (
                f"标题长度不符合要求，应控制在{self._range_text(self.TITLE_LENGTH_RANGE)}"
                if not self._within_range(title, self.TITLE_LENGTH_RANGE)
                else ""
            ),
            "summary_feedback": (
                f"摘要长度不符合要求，应控制在{self._range_text(self.SUMMARY_LENGTH_RANGE)}"
                if not self._within_range(summary, self.SUMMARY_LENGTH_RANGE)
                else ""
            ),
            "content_feedback": (
                f"内容长度不符合要求，应控制在{self._range_text(self.CONTENT_LENGTH_RANGE)}"
                if not self._within_range(content, self.CONTENT_LENGTH_RANGE)
                else ""
            ),
            "overall_score": 7
        }

    def judge_single_part(self, part_type: str, part_content: str, topic: str) -> Tuple[bool, str]:
        """
        评审单个部分
        
        :param part_type: 部分类型 (title/summary/content)
        :param part_content: 部分内容
        :param topic: 新闻主题
        :return: (是否通过, 反馈意见)
        """
        print(f"=== {self.agent_name} 开始评审{part_type} ===")
        
        if part_type == "title":
            bounds = self.TITLE_LENGTH_RANGE
            criteria = f"{self._range_text(bounds)}，有吸引力，包含核心信息"
        elif part_type == "summary":
            bounds = self.SUMMARY_LENGTH_RANGE
            criteria = f"{self._range_text(bounds)}，简洁明了，包含关键信息"
        elif part_type == "content":
            bounds = self.CONTENT_LENGTH_RANGE
            criteria = f"{self._range_text(bounds)}，逻辑清晰，客观准确"
        else:
            return False, "未知的部分类型"
        
        prompt = f"""请对以下新闻{part_type}进行质量评审：

{part_type}：{part_content}
主题：{topic}

评审标准：{criteria}
语言要求：必须使用简体中文，不得出现繁体字、英文或其他语言

请返回JSON格式的评审结果，包含以下字段：
- pass: 是否通过 (true/false)
- feedback: 反馈意见（如果不通过，请提供具体的改进建议）

注意：
1. 只做基本格式和长度检查，不要对内容进行大幅修改建议
2. 如果基本符合要求，应该通过
3. 如果不通过，提供保守的修改建议，只调整长度，不要改变内容含义
4. 记住你没有原始资料，只能做基本检查，修改建议要保守
5. 必须检查语言统一性，繁体字内容必须标记为不通过

请直接返回JSON格式，不要包含任何思考过程、解释或说明。"""

        try:
            response = llm_chat(
                agent_name=self.agent_name,
                messages=[{"role": "user", "content": prompt}],
                base_url=aios_kernel_url,
            )
            
            if response and "response" in response and response["response"]:
                response_text = response["response"]["response_message"].strip()
                
                # 清理think标签
                if "</think>" in response_text:
                    response_text = response_text.split("</think>")[-1].strip()
                elif "<think>" in response_text:
                    response_text = response_text.split("<think>")[-1].strip()
                
                # 尝试解析JSON
                try:
                    # 清理响应文本，提取JSON部分
                    response_text = self._extract_json_from_response(response_text)
                    result = json.loads(response_text)
                    pass_status = result.get('pass', False)
                    feedback = result.get('feedback', '')
                    print(f"✅ {part_type}评审完成: {'通过' if pass_status else '不通过'}")
                    return pass_status, feedback
                except json.JSONDecodeError:
                    print(f"❌ {part_type}评审JSON解析失败，使用默认评审")
                    return self._default_single_judgment(part_type, part_content)
            else:
                print(f"❌ {part_type}评审LLM响应为空")
                return self._default_single_judgment(part_type, part_content)
        except Exception as e:
            print(f"❌ {part_type}评审失败: {e}")
            return self._default_single_judgment(part_type, part_content)

    def _extract_json_from_response(self, response_text: str) -> str:
        """从响应文本中提取JSON部分"""
        # 查找JSON开始和结束位置
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}')
        
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            return response_text[start_idx:end_idx + 1]
        
        # 如果没有找到完整的JSON，尝试查找其他格式
        if '"pass"' in response_text and '"feedback"' in response_text:
            # 尝试提取包含pass和feedback的部分
            lines = response_text.split('\n')
            for line in lines:
                if '"pass"' in line and '"feedback"' in line:
                    return line.strip()
        
        return response_text

    def _default_single_judgment(self, part_type: str, part_content: str) -> Tuple[bool, str]:
        """默认单个部分评审结果 - 放宽字数窗口后仍保持保守修改意见"""
        if part_type == "title":
            length_ok = self._within_range(part_content, self.TITLE_LENGTH_RANGE)
            return length_ok, (
                f"标题长度不符合要求，应控制在{self._range_text(self.TITLE_LENGTH_RANGE)}"
                if not length_ok else ""
            )
        elif part_type == "summary":
            length_ok = self._within_range(part_content, self.SUMMARY_LENGTH_RANGE)
            return length_ok, (
                f"摘要长度不符合要求，应控制在{self._range_text(self.SUMMARY_LENGTH_RANGE)}"
                if not length_ok else ""
            )
        elif part_type == "content":
            length_ok = self._within_range(part_content, self.CONTENT_LENGTH_RANGE)
            return length_ok, (
                f"内容长度不符合要求，应控制在{self._range_text(self.CONTENT_LENGTH_RANGE)}"
                if not length_ok else ""
            )
        else:
            return False, "未知的部分类型"

    def analyze_source_relevance(self, search_data: str, topic: str) -> Dict:
        """
        分析搜索资料中各个链接的相关度，用于新闻生成
        
        :param search_data: 搜索原始数据
        :param topic: 新闻主题
        :return: 信源相关度分析结果
        """
        print(f"=== {self.agent_name} 开始分析信源相关度 ===")
        
        prompt = f"""请分析以下搜索原始资料中各个结果与新闻主题的相关度：

新闻主题：{topic}

搜索原始资料：
{search_data}

要求：
1. 分析每个搜索结果与新闻主题的相关度（0-100分）
2. 提取每个搜索结果的标题和链接
3. 计算相关度分数，考虑内容匹配度、信息价值等
4. 为后续新闻生成提供信源权重参考

请返回JSON格式，包含以下字段：
- topic: 新闻主题
- sources: 信源列表，每个信源包含：
  - title: 搜索结果标题
  - link: 搜索结果链接
  - relevance_score: 相关度分数(0-100)
  - relevance_reason: 相关度原因说明
  - key_info: 该信源的关键信息摘要

注意：
1. 只返回JSON格式，不要包含任何其他文字
2. 相关度分数要客观准确，基于内容质量而非个人偏好
3. 确保所有搜索结果都被分析"""

        try:
            response = llm_chat(
                agent_name=self.agent_name,
                messages=[{"role": "user", "content": prompt}],
                base_url=aios_kernel_url,
            )
            
            if response and "response" in response and response["response"]:
                response_text = response["response"]["response_message"].strip()
                
                # 清理think标签
                import re
                response_text = re.sub(r'<think>.*?</think>', '', response_text, flags=re.DOTALL)
                response_text = re.sub(r'^```(?:json)?\s*', '', response_text)
                response_text = re.sub(r'\s*```$', '', response_text)
                json_match = re.search(r'(\{.*\})', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)
                
                # 解析JSON
                try:
                    result = json.loads(response_text)
                    print(f"✅ 信源相关度分析完成")
                    return result
                except json.JSONDecodeError as e:
                    print(f"⚠️ JSON解析失败: {e}")
                    return self._fallback_source_analysis(search_data, topic)
            else:
                print(f"⚠️ 信源相关度分析失败: 无响应")
                return self._fallback_source_analysis(search_data, topic)
                
        except Exception as e:
            print(f"❌ 信源相关度分析异常: {e}")
            return self._fallback_source_analysis(search_data, topic)

    def _fallback_source_analysis(self, search_data: str, topic: str) -> Dict:
        import re

        sources = []
        pattern = re.compile(
            r"标题:\s*(?P<title>.+?)\n链接:\s*(?P<link>.+?)(?:\n|$)",
            re.MULTILINE,
        )
        for match in pattern.finditer(search_data):
            title = match.group("title").strip()
            link = match.group("link").strip()
            if not title:
                continue
            score = self._fallback_source_score(topic, title)
            sources.append(
                {
                    "title": title,
                    "link": link,
                    "relevance_score": score,
                    "relevance_reason": self._fallback_source_reason(score),
                    "key_info": "",
                }
            )

        return {"topic": topic, "sources": sources[:5]}

    def _fallback_source_score(self, topic: str, title: str) -> int:
        normalized_topic = re.sub(r"[^\w\u4e00-\u9fff]+", "", topic.lower())
        normalized_title = re.sub(r"[^\w\u4e00-\u9fff]+", "", title.lower())

        if normalized_topic and normalized_topic in normalized_title:
            return 85
        if normalized_title and normalized_title in normalized_topic:
            return 85

        shared_chars = set(normalized_topic) & set(normalized_title)
        if len(shared_chars) >= 4:
            return 70
        if len(shared_chars) >= 2:
            return 45
        return 25

    def _fallback_source_reason(self, score: int) -> str:
        if score >= 80:
            return "标题与主题高度贴合，可作为核心参考信源。"
        if score >= 60:
            return "标题与主题基本相关，可作为补充参考信源。"
        if score >= 35:
            return "标题与主题存在一定关联，适合作为延伸参考。"
        return "与主题关联度较弱，不建议作为主要信源。"

    def save_news_to_file(self, title: str, summary: str, content: str, topic: str, search_data: str = "") -> str:
        """
        保存新闻到文件，并生成信源相关度JSON
        
        :param title: 新闻标题
        :param summary: 新闻摘要
        :param content: 新闻内容
        :param topic: 新闻主题
        :param search_data: 搜索原始数据（用于分析信源相关度）
        :return: 保存的文件路径
        """
        try:
            # 从topic中提取领域和索引信息
            # topic格式应该是 "领域名新闻索引"，如 "社会热点与公共事务新闻0"
            if "新闻" in topic:
                parts = topic.split("新闻")
                domain = parts[0]
                index = parts[1] if len(parts) > 1 else "0"
            else:
                domain = topic
                index = "0"
            
            # 构建文件路径
            filepath = str(INTERMEDIATE_DIR / f"{domain}_{index}_news.txt")
            json_filepath = str(INTERMEDIATE_DIR / f"{domain}_{index}_sources.json")
            
            # 清理摘要中的字数统计
            import re
            cleaned_summary = re.sub(r'（\d+字）', '', summary)
            
            # 组合新闻内容，只包含标题、摘要、内容，不包含其他信息
            news_content = f"标题: {title}\n\n摘要: {cleaned_summary}\n\n内容: {content}"
            
            print(f"💾 正在保存新闻到: {filepath}")
            
            # 创建文件
            self.store.write_text(filepath, news_content)
            
            # 分析信源相关度并保存JSON；如果搜索资料为空，也保留一个结构化占位文件
            if search_data:
                print(f"📊 正在分析信源相关度...")
                source_analysis = self.analyze_source_relevance(search_data, topic)
            else:
                print(f"⚠️ 搜索原始数据为空，写入空信源JSON: {json_filepath}")
                source_analysis = {
                    "topic": topic,
                    "sources": [],
                    "note": "search_data_missing",
                }

            # 添加新闻标题到分析结果中
            source_analysis["news_title"] = title

            # 保存信源相关度JSON
            self.store.write_json(json_filepath, source_analysis)
            print(f"✅ 信源相关度JSON保存成功: {json_filepath}")
            
            print(f"✅ 新闻保存成功: {filepath}")
            return filepath
            
        except Exception as e:
            print(f"❌ 新闻保存失败: {e}")
            return ""
