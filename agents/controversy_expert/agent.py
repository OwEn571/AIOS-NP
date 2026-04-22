import os
import json
import sys
sys.path.append('/data/llm/AIOS-NP')

from cerebrum.llm.apis import llm_chat
from cerebrum.config.config_manager import config

aios_kernel_url = config.get_kernel_url()

class ControversyExpert:
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
    
    def analyze_controversy(self, news_content, processing_instruction=""):
        """分析新闻中的争议点和敏感话题"""
        prompt = f"""
        作为争议事件专家，请分析以下新闻中的争议点和敏感话题：
        
        新闻内容：
        {news_content}
        
        处理指令：{processing_instruction}
        
        分析要求：
        1. 识别新闻中的争议点、敏感话题和潜在风险
        2. 分析各方观点的平衡性
        3. 识别可能引发不当争议的表述
        4. 评估新闻的社会影响和公众反应
        5. 提供专业的争议事件处理建议
        
        请严格按照以下JSON格式返回分析结果：
        {{
            "controversy_points": ["争议点1", "争议点2"],
            "sensitive_topics": ["敏感话题1", "敏感话题2"],
            "risk_assessment": "风险等级评估",
            "balance_analysis": "观点平衡性分析",
            "social_impact": "社会影响评估",
            "recommendations": ["建议1", "建议2"],
            "expert_opinion": "专家意见和处理建议"
        }}
        
        注意：
        - 确保JSON格式正确
        - 所有字符串不要包含换行符
        - 基于争议事件专业经验进行分析
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
    
    def optimize_controversy_news(self, news_content, controversy_analysis, processing_instruction=""):
        """优化争议事件新闻"""
        prompt = f"""
        作为争议事件专家，请根据分析结果优化以下争议事件新闻：
        
        原始新闻：
        {news_content}
        
        争议分析：
        {controversy_analysis}
        
        处理指令：{processing_instruction}
        
        优化要求：
        1. 保持原始格式：标题、摘要、内容三个部分
        2. 内容部分严格控制在300-500字之间
        3. 确保争议各方观点得到公平呈现
        4. 去除可能引发不当争议的表述
        5. 保持客观中立的立场
        6. 优化争议事件的表达方式
        7. 确保新闻符合争议事件报道的专业标准
        8. 不要添加任何注释、说明或think标签
        9. 重要：必须完整保留原始新闻中的所有具体事实、数据、引用、政策文件名称等关键信息
        10. 重要：必须完整保留原始新闻中的所有观点和论述，不要删除或简化任何内容
        11. 重要：只对表述方式进行微调，不要大幅修改内容结构
        12. 重要：保持原始新闻的丰富性和完整性，确保所有细节都得到保留
        13. 重要：不要改变新闻的核心信息和逻辑结构，只优化语言表达
        14. 重要：争议事件专家应该专注于风格调整，保持内容的完整性和丰富性
        15. 重要：不要因为字数限制而删除重要观点，应该通过优化表达来压缩
        
        专业处理重点：
        - 平衡各方观点，避免偏向任何一方
        - 使用客观中立的表述
        - 避免情绪化或煽动性语言
        - 确保事实准确，避免主观判断
        - 考虑社会影响和公众利益
        
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
        """运行争议事件专家处理流程"""
        print("⚖️ 开始争议事件专家处理...")
        
        # 1. 分析争议点
        print("🔍 分析争议点和敏感话题...")
        controversy_analysis = self.analyze_controversy(news_content, processing_instruction)
        print("✅ 争议分析完成")
        
        # 2. 优化新闻
        print("🎯 优化争议事件新闻...")
        optimized_news = self.optimize_controversy_news(news_content, controversy_analysis, processing_instruction)
        print("✅ 争议事件优化完成")
        
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
    expert = ControversyExpert("controversy_expert")
    
    # 测试新闻内容
    test_news = """标题: 张雪峰5000万捐款引争议

摘要: 张雪峰承诺若台海战争爆发将捐5000万元引发争议。支持者认为其表态体现爱国立场，批评者质疑其时机动机，认为应优先支持民生救灾等实际需求。该事件折射出公众对"算计式爱国"的反感，凸显和平统一政策与舆论场中爱国叙事的复杂博弈。

内容: 张雪峰近期因承诺"若台海发生战争，将捐出5000万元支持祖国统一"引发广泛争议。这一言论迅速在社交媒体上激起讨论，部分网友认为其言论时机敏感，存在"借爱国谋流量"的嫌疑，而另一部分人则赞赏其爱国情怀，认为此举体现了对国家统一的支持。"""
    
    result = expert.run(test_news, "对争议事件进行专业处理，确保中立性和客观性")
    print("\n🎯 处理完成!")
    print(f"📊 优化结果: {result}")

if __name__ == "__main__":
    main()