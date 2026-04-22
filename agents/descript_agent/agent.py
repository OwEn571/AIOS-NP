import os
import json
import sys
sys.path.append('/data/llm/AIOS-NP')

from cerebrum.llm.apis import llm_chat
from cerebrum.config.config_manager import config

aios_kernel_url = config.get_kernel_url()

class DescriptAgent:
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
    
    def optimize_expression(self, news_content, processing_instruction=""):
        """优化新闻表达，使其更具新闻化特色"""
        prompt = f"""
        作为新闻表达优化专家，请优化以下新闻的表达方式：
        
        新闻内容：
        {news_content}
        
        处理指令：{processing_instruction}
        
        优化要求：
        1. 保持原始格式：标题、摘要、内容三个部分
        2. 内容部分严格控制在300-500字之间
        3. 优化标题，使其更具吸引力和新闻性
        4. 改进摘要表达，提高概括性和准确性
        5. 优化正文表达，增强可读性和生动性
        6. 使用专业的新闻语言和表达方式
        7. 确保语言精炼，避免冗余表达
        8. 不要添加任何注释、说明或think标签
        9. 重要：保持原始新闻的所有关键信息和具体细节，不要删除或简化重要内容
        10. 重要：只对表达方式进行微调，不要大幅修改内容
        11. 重要：保持原始新闻的所有事实、数据、引用和具体观点，只调整表达风格
        12. 重要：不要改变新闻的核心信息和逻辑结构，只优化语言表达
        13. 重要：必须完整保留所有书名号、引号、政策文件名称等格式标记
        14. 重要：不要将书名号内容替换为星号或其他符号
        15. 重要：保持所有引用和引用的完整性
        
        优化重点：
        - 标题：简洁有力，突出新闻要点
        - 摘要：准确概括，突出核心信息
        - 正文：表达生动，逻辑清晰
        - 语言：专业准确，易于理解
        - 风格：符合新闻标准，具有传播力
        
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
        """运行表达优化流程"""
        print("📝 开始新闻表达优化...")
        
        # 优化表达
        optimized_news = self.optimize_expression(news_content, processing_instruction)
        print("✅ 表达优化完成")
        
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
        return text.strip()

def main():
    agent = DescriptAgent("descript_agent")
    
    # 测试新闻内容
    test_news = """标题: 张雪峰5000万捐款引争议

摘要: 张雪峰承诺若台海战争爆发将捐5000万元引发争议。支持者认为其表态体现爱国立场，批评者质疑其时机动机，认为应优先支持民生救灾等实际需求。该事件折射出公众对"算计式爱国"的反感，凸显和平统一政策与舆论场中爱国叙事的复杂博弈。

内容: 张雪峰近期因承诺"若台海发生战争，将捐出5000万元支持祖国统一"引发广泛争议。这一言论迅速在社交媒体上激起讨论，部分网友认为其言论时机敏感，存在"借爱国谋流量"的嫌疑，而另一部分人则赞赏其爱国情怀，认为此举体现了对国家统一的支持。"""
    
    result = agent.run(test_news, "优化新闻表达，使其更有新闻化")
    print("\n🎯 处理完成!")
    print(f"📊 优化结果: {result}")

if __name__ == "__main__":
    main()