import os
import json
import sys
sys.path.append('/data/llm/AIOS-NP')

from cerebrum.llm.apis import llm_chat
from cerebrum.config.config_manager import config

aios_kernel_url = config.get_kernel_url()

class ConstructureAgent:
    def __init__(self, agent_name):
        self.agent_name = agent_name
        self.messages = []
        self.config = self._load_config()
        
    def _load_config(self):
        script_path = os.path.abspath(__file__)
        script_dir = os.path.dirname(script_path)
        config_file = os.path.join(script_dir, "config.json")
        with open(config_file, "r", encoding='utf-8') as f:
            config = json.load(f)
        return config
    
    def analyze_structure(self, news_content, processing_instruction=""):
        """分析新闻结构"""
        prompt = f"""
        作为新闻结构优化专家，请分析以下新闻的结构：
        
        新闻内容：
        {news_content}
        
        处理指令：{processing_instruction}
        
        分析要求：
        1. 评估新闻标题的吸引力和准确性
        2. 分析摘要的完整性和概括性
        3. 检查正文的段落结构和逻辑性
        4. 评估叙述节奏和表达流畅性
        5. 识别结构上的问题和改进空间
        
        请严格按照以下JSON格式返回分析结果：
        {{
            "title_analysis": "标题分析",
            "summary_analysis": "摘要分析",
            "content_structure": "正文结构分析",
            "narrative_rhythm": "叙述节奏分析",
            "logical_flow": "逻辑连贯性分析",
            "improvement_suggestions": ["建议1", "建议2"],
            "structure_score": 8.5
        }}
        
        注意：
        - 确保JSON格式正确
        - 所有字符串不要包含换行符
        - 基于新闻结构标准进行分析
        """
        
        self.messages = [{"role": "user", "content": prompt}]
        response = llm_chat(
            agent_name=self.agent_name,
            messages=self.messages,
            base_url=aios_kernel_url,
        )["response"]
        
        # 清理输出
        cleaned_response = self._clean_llm_output(response["response_message"])
        final_response = self._clean_analysis_result(cleaned_response)
        
        return final_response
    
    def optimize_structure(self, news_content, structure_analysis, processing_instruction=""):
        """优化新闻结构"""
        prompt = f"""
        作为新闻结构优化专家，请根据结构分析结果优化以下新闻：
        
        原始新闻：
        {news_content}
        
        结构分析：
        {structure_analysis}
        
        处理指令：{processing_instruction}
        
        优化要求：
        1. 保持原始格式：标题、摘要、内容三个部分
        2. 内容部分严格控制在300-500字之间
        3. 优化标题结构，提高吸引力
        4. 完善摘要内容，确保准确概括
        5. 调整正文段落结构，提高可读性
        6. 优化叙述节奏，使表达更加自然
        7. 确保逻辑连贯，层次分明
        8. 不要添加任何注释、说明或think标签
        9. 重要：保持原始新闻的所有关键信息和具体细节，不要删除或简化重要内容
        10. 重要：只对结构和表达进行微调，不要大幅修改内容
        11. 重要：保持原始新闻的所有事实、数据、引用和具体观点，只调整结构组织
        12. 重要：不要改变新闻的核心信息和逻辑结构，只优化段落组织和表达节奏
        13. 重要：必须完整保留所有书名号、引号、政策文件名称等格式标记
        14. 重要：不要将书名号内容替换为星号或其他符号
        15. 重要：保持所有引用和引用的完整性
        
        结构优化重点：
        - 标题：简洁有力，突出要点
        - 摘要：准确概括，信息完整
        - 正文：结构清晰，逻辑连贯
        - 节奏：自然流畅，易于阅读
        - 层次：重点突出，层次分明
        
        请返回优化后的新闻内容，格式为：
        标题: [标题]
        
        摘要: [摘要]
        
        内容: [内容]
        
        注意：内容部分必须控制在300-500字之间，不要添加任何括号标注、注释、说明或think标签。
        """
        
        self.messages = [{"role": "user", "content": prompt}]
        response = llm_chat(
            agent_name=self.agent_name,
            messages=self.messages,
            base_url=aios_kernel_url,
        )["response"]
        
        # 清理输出
        cleaned_response = self._clean_llm_output(response["response_message"])
        final_response = self._clean_analysis_result(cleaned_response)
        
        return final_response
    
    def run(self, news_content, processing_instruction=""):
        """运行结构优化流程"""
        print("🏗️ 开始新闻结构优化...")
        
        # 1. 分析结构
        print("🔍 分析新闻结构...")
        structure_analysis = self.analyze_structure(news_content, processing_instruction)
        print("✅ 结构分析完成")
        
        # 2. 优化结构
        print("🎯 优化新闻结构...")
        optimized_news = self.optimize_structure(news_content, structure_analysis, processing_instruction)
        print("✅ 结构优化完成")
        
        return optimized_news
    
    def _clean_llm_output(self, text):
        """清理LLM输出，移除think标签和优化说明"""
        import re
        # 移除think标签
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        # 移除其他标签
        text = re.sub(r'<[^>]+>', '', text)
        # 移除优化说明
        text = re.sub(r'（优化说明：.*?）', '', text, flags=re.DOTALL)
        text = re.sub(r'\(优化说明：.*?\)', '', text, flags=re.DOTALL)
        text = re.sub(r'（注：.*?）', '', text, flags=re.DOTALL)
        text = re.sub(r'\(注：.*?\)', '', text, flags=re.DOTALL)
        # 清理多余换行
        text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)
        return text.strip()
    
    def _clean_analysis_result(self, text):
        """清理分析结果，提取有效内容"""
        import re
        # 移除think标签
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        # 移除其他标签
        text = re.sub(r'<[^>]+>', '', text)
        # 尝试提取JSON
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json_match.group(0)
        return text.strip()

def main():
    agent = ConstructureAgent("constructure_agent")
    
    # 测试新闻内容
    test_news = """标题: 张雪峰5000万捐款引争议

摘要: 张雪峰承诺若台海战争爆发将捐5000万元引发争议。支持者认为其表态体现爱国立场，批评者质疑其时机动机，认为应优先支持民生救灾等实际需求。该事件折射出公众对"算计式爱国"的反感，凸显和平统一政策与舆论场中爱国叙事的复杂博弈。

内容: 张雪峰近期因承诺"若台海发生战争，将捐出5000万元支持祖国统一"引发广泛争议。这一言论迅速在社交媒体上激起讨论，部分网友认为其言论时机敏感，存在"借爱国谋流量"的嫌疑，而另一部分人则赞赏其爱国情怀，认为此举体现了对国家统一的支持。"""
    
    result = agent.run(test_news, "优化新闻结构")
    print("\n🎯 处理完成!")
    print(f"📊 优化结果: {result}")

if __name__ == "__main__":
    main()