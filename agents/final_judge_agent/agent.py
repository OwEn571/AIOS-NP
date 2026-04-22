import os
import json
import sys
sys.path.append('/data/llm/AIOS-NP')

from cerebrum.llm.apis import llm_chat
from cerebrum.config.config_manager import config

aios_kernel_url = config.get_kernel_url()

class FinalJudgeAgent:
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
        
        请返回JSON格式的检查结果：
        {{
            "meets_requirements": true/false,
            "quality_score": 0-100,
            "issues": ["问题1", "问题2", ...],
            "feedback": "详细的反馈意见",
            "recommendation": "具体的修改建议"
        }}
        
        注意：
        - 如果字数不在300-500字范围内，meets_requirements应为false
        - 如果包含注释、说明或think标签，meets_requirements应为false
        - 如果结构不完整（缺少标题、摘要、内容任一部分），meets_requirements应为false
        - 只返回JSON，不要包含任何其他文字
        """
        
        self.messages = [{"role": "user", "content": prompt}]
        response = llm_chat(
            agent_name=self.agent_name,
            messages=self.messages,
            base_url=aios_kernel_url
        )
        
        return response
    
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

def main():
    agent = FinalJudgeAgent("final_judge_agent")
    # 测试用的新闻内容
    test_news = """
    标题: 测试新闻标题
    
    摘要: 这是一条测试新闻的摘要，用于验证质量检查功能是否正常工作。
    
    内容: 这是一条测试新闻的内容部分。内容应该包含足够的信息来满足字数要求，同时保持客观中立的立场。新闻内容应该结构清晰，表达流畅，不包含任何注释或说明性文字。这条测试新闻的目的是验证final_judge_agent的功能是否正常。
    """
    
    result = agent.run(test_news)
    print(f"检查结果: {result}")

if __name__ == "__main__":
    main()