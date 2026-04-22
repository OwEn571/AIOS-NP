import os
import json
import sys
sys.path.append('/data/llm/AIOS-NP')

from cerebrum.llm.apis import llm_chat
from cerebrum.config.config_manager import config

aios_kernel_url = config.get_kernel_url()

class JudgeAgent:
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
    
    def judge_quality(self, news_content):
        """严格检查新闻质量"""
        # 先计算实际字数
        content_start = news_content.find("内容: ")
        if content_start != -1:
            content_text = news_content[content_start + 3:]  # 去掉"内容: "
            actual_word_count = len(content_text.strip())
        else:
            actual_word_count = len(news_content.strip())
        
        prompt = f"""
        作为严格的新闻质量检查专家，请检查以下新闻是否符合要求：
        
        新闻内容：
        {news_content}
        
        实际字数统计：{actual_word_count}字符
        
        检查标准：
        1. 字数是否合适（300-500字）- 当前{actual_word_count}字符
        2. 结构是否清晰（标题、摘要、内容三段式）
        3. 内容是否客观中立
        4. 表达是否流畅自然
        5. 是否包含注释或说明（不允许）
        6. 是否包含think标签（不允许）
        
        重要：如果字数超过500字或少于300字，必须设置meets_requirements为false
        重要：如果新闻包含think标签、优化说明、注释等非新闻内容，必须设置meets_requirements为false
        
        请严格按照以下JSON格式返回检查结果：
        {{
            "quality_score": 8.5,
            "meets_requirements": true,
            "issues": ["问题1", "问题2"],
            "recommendation": "建议内容",
            "feedback": "详细反馈意见"
        }}
        
        注意：
        - quality_score必须是数字
        - meets_requirements必须是true或false
        - issues必须是字符串数组
        - 所有字符串不要包含换行符
        - 确保JSON格式正确
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
    
    def run(self, news_content):
        """运行质量检查流程"""
        print("⚖️ 开始新闻质量检查...")
        
        # 进行质量检查
        judge_result = self.judge_quality(news_content)
        print("✅ 质量检查完成")
        
        return judge_result
    
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
    agent = JudgeAgent("judge_agent")
    
    # 测试新闻内容
    test_news = """标题: 张雪峰5000万捐款引争议

摘要: 张雪峰承诺若台海战争爆发将捐5000万元引发争议。支持者认为其表态体现爱国立场，批评者质疑其时机动机，认为应优先支持民生救灾等实际需求。该事件折射出公众对"算计式爱国"的反感，凸显和平统一政策与舆论场中爱国叙事的复杂博弈。

内容: 张雪峰近期因承诺"若台海发生战争，将捐出5000万元支持祖国统一"引发广泛争议。这一言论迅速在社交媒体上激起讨论，部分网友认为其言论时机敏感，存在"借爱国谋流量"的嫌疑，而另一部分人则赞赏其爱国情怀，认为此举体现了对国家统一的支持。"""
    
    result = agent.run(test_news)
    print("\n🎯 检查完成!")
    print(f"📊 检查结果: {result}")

if __name__ == "__main__":
    main()