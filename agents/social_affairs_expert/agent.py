import os
import json
import sys
sys.path.append('/data/llm/AIOS-NP')

from cerebrum.llm.apis import llm_chat
from cerebrum.config.config_manager import config

aios_kernel_url = config.get_kernel_url()

class SocialAffairsExpert:
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
    
    def analyze_social_affairs(self, news_content, processing_instruction=""):
        """分析社会热点与公共事务新闻"""
        prompt = f"""
        作为社会热点与公共事务专家，请分析以下新闻：
        
        新闻内容：
        {news_content}
        
        处理指令：{processing_instruction}
        
        分析要求：
        1. 识别新闻中的社会热点和公共事务要素
        2. 分析政策影响和公众关注度
        3. 评估新闻的公共价值和意义
        4. 识别可能的社会影响和舆论反应
        5. 提供专业的公共事务处理建议
        
        请严格按照以下JSON格式返回分析结果：
        {{
            "social_hotspots": ["社会热点1", "社会热点2"],
            "public_affairs": ["公共事务1", "公共事务2"],
            "policy_impact": "政策影响分析",
            "public_attention": "公众关注度评估",
            "social_value": "公共价值评估",
            "potential_impact": "潜在社会影响",
            "recommendations": ["建议1", "建议2"],
            "expert_opinion": "专家意见和处理建议"
        }}
        """
        
        response = llm_chat(
            agent_name=self.agent_name,
            messages=[
                {"role": "system", "content": "你是一个专业的社会热点与公共事务专家，擅长分析社会现象和公共政策。"},
                {"role": "user", "content": prompt}
            ],
            base_url=aios_kernel_url,
        )["response"]
        
        return response["response_message"]
    
    def optimize_social_news(self, news_content, analysis_result, processing_instruction=""):
        """优化社会热点与公共事务新闻"""
        prompt = f"""
        作为社会热点与公共事务专家，请优化以下新闻：
        
        原始新闻：
        {news_content}
        
        分析结果：
        {analysis_result}
        
        处理指令：{processing_instruction}
        
        优化要求：
        1. 保持新闻的客观性和公正性
        2. 突出社会价值和公共意义
        3. 确保政策表述准确
        4. 平衡各方观点
        5. 增强新闻的可读性和影响力
        6. 保持原始事实和观点不变，仅做风格调整
        
        请直接输出优化后的新闻内容，不要包含任何解释或额外文字。
        """
        
        response = llm_chat(
            agent_name=self.agent_name,
            messages=[
                {"role": "system", "content": "你是一个专业的社会热点与公共事务专家，擅长优化新闻表达。"},
                {"role": "user", "content": prompt}
            ],
            base_url=aios_kernel_url,
        )["response"]
        
        return response["response_message"]
    
    def run(self, news_content, processing_instruction=""):
        """运行社会热点与公共事务专家分析"""
        try:
            # 分析新闻
            analysis_result = self.analyze_social_affairs(news_content, processing_instruction)
            
            # 优化新闻
            optimized_news = self.optimize_social_news(news_content, analysis_result, processing_instruction)
            
            return {
                "agent_name": self.agent_name,
                "status": "success",
                "result": "社会热点与公共事务分析完成",
                "analysis": analysis_result,
                "optimized_news": optimized_news
            }
            
        except Exception as e:
            return {
                "agent_name": self.agent_name,
                "status": "failed",
                "result": f"社会热点与公共事务分析失败: {e}"
            }