import os
import json
import sys
sys.path.append('/data/llm/AIOS-NP')

from cerebrum.llm.apis import llm_chat
from cerebrum.config.config_manager import config

aios_kernel_url = config.get_kernel_url()

class BanAgent:
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
    
    def check_content_safety(self, news_content, processing_instruction=""):
        """检查新闻内容的安全性"""
        prompt = f"""
        作为内容安全审查专家，请检查以下新闻内容的安全性：
        
        新闻内容：
        {news_content}
        
        处理指令：{processing_instruction}
        
        检查要求：
        1. 识别新闻中的敏感词汇和表述
        2. 检查是否存在歧视性、侮辱性或不当表达
        3. 评估内容的政治敏感性和社会影响
        4. 识别可能引发问题的内容
        5. 提供安全的内容替代方案
        
        请严格按照以下JSON格式返回检查结果：
        {{
            "sensitive_words": ["敏感词1", "敏感词2"],
            "inappropriate_expressions": ["不当表达1", "不当表达2"],
            "risk_level": "风险等级",
            "safety_assessment": "安全性评估",
            "recommendations": ["建议1", "建议2"],
            "replacement_suggestions": ["替代方案1", "替代方案2"]
        }}
        
        注意：
        - 确保JSON格式正确
        - 所有字符串不要包含换行符
        - 基于内容安全标准进行检查
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
    
    def optimize_content_safety(self, news_content, safety_analysis, processing_instruction=""):
        """优化新闻内容的安全性"""
        prompt = f"""
        作为内容安全审查专家，请根据安全检查结果优化以下新闻内容：
        
        原始新闻：
        {news_content}
        
        安全检查结果：
        {safety_analysis}
        
        处理指令：{processing_instruction}
        
        优化要求：
        1. 保持原始格式：标题、摘要、内容三个部分
        2. 内容部分严格控制在300-500字之间
        3. 移除或替换敏感词汇和不当表达
        4. 确保内容符合安全标准
        5. 保持新闻的客观性和可读性
        6. 维护社会和谐和正面影响
        7. 不要添加任何注释、说明或think标签
        8. 重要：保持原始新闻的所有关键信息和具体细节，不要删除或简化重要内容
        9. 重要：只对敏感词汇进行替换，不要大幅修改内容结构
        10. 重要：保持原始新闻的所有事实、数据、引用和具体观点，只替换敏感词汇
        11. 重要：不要改变新闻的核心信息和逻辑结构，只进行必要的敏感词替换
        
        安全优化重点：
        - 替换敏感词汇为中性表达
        - 修正不当表述
        - 确保内容合规
        - 维护社会和谐
        - 保持新闻价值
        
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
        """运行内容安全检查流程"""
        print("🛡️ 开始内容安全检查...")
        
        # 1. 检查内容安全性
        print("🔍 检查敏感词和不当表达...")
        safety_analysis = self.check_content_safety(news_content, processing_instruction)
        print("✅ 安全检查完成")
        
        # 2. 优化内容安全性
        print("🎯 优化内容安全性...")
        optimized_news = self.optimize_content_safety(news_content, safety_analysis, processing_instruction)
        print("✅ 内容安全优化完成")
        
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
    agent = BanAgent("ban_agent")
    
    # 测试新闻内容
    test_news = """标题: 张雪峰5000万捐款引争议

摘要: 张雪峰承诺若台海战争爆发将捐5000万元引发争议。支持者认为其表态体现爱国立场，批评者质疑其时机动机，认为应优先支持民生救灾等实际需求。该事件折射出公众对"算计式爱国"的反感，凸显和平统一政策与舆论场中爱国叙事的复杂博弈。

内容: 张雪峰近期因承诺"若台海发生战争，将捐出5000万元支持祖国统一"引发广泛争议。这一言论迅速在社交媒体上激起讨论，部分网友认为其言论时机敏感，存在"借爱国谋流量"的嫌疑，而另一部分人则赞赏其爱国情怀，认为此举体现了对国家统一的支持。"""
    
    result = agent.run(test_news, "检查敏感词和不良表达")
    print("\n🎯 处理完成!")
    print(f"📊 优化结果: {result}")

if __name__ == "__main__":
    main()