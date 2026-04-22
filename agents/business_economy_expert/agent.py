import os
import json
import sys
sys.path.append('/data/llm/AIOS-NP')

from cerebrum.llm.apis import llm_chat
from cerebrum.config.config_manager import config

aios_kernel_url = config.get_kernel_url()

class BusinessEconomyExpert:
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
    
    def analyze_business_economy(self, news_content, processing_instruction=""):
        """分析商业与经济新闻"""
        prompt = f"""
        作为商业与经济专家，请分析以下新闻：
        
        新闻内容：
        {news_content}
        
        处理指令：{processing_instruction}
        
        分析要求：
        1. 识别新闻中的商业要素和经济指标
        2. 分析市场影响和投资价值
        3. 评估经济政策和商业环境
        4. 识别行业趋势和发展前景
        5. 提供专业的商业经济处理建议
        
        请严格按照以下JSON格式返回分析结果：
        {{
            "business_elements": ["商业要素1", "商业要素2"],
            "economic_indicators": ["经济指标1", "经济指标2"],
            "market_impact": "市场影响分析",
            "investment_value": "投资价值评估",
            "policy_impact": "政策影响分析",
            "industry_trends": "行业趋势分析",
            "recommendations": ["建议1", "建议2"],
            "expert_opinion": "专家意见和处理建议"
        }}
        """
        
        response = llm_chat(
            agent_name=self.agent_name,
            messages=[
                {"role": "system", "content": "你是一个专业的商业与经济专家，擅长分析商业现象和经济趋势。"},
                {"role": "user", "content": prompt}
            ],
            base_url=aios_kernel_url,
        )["response"]
        
        return response["response_message"]
    
    def optimize_business_news(self, news_content, analysis_result, processing_instruction=""):
        """优化商业与经济新闻"""
        prompt = f"""
        作为商业与经济专家，请优化以下新闻：
        
        原始新闻：
        {news_content}
        
        分析结果：
        {analysis_result}
        
        处理指令：{processing_instruction}
        
        优化要求：
        1. 突出商业价值和经济意义
        2. 确保数据准确性和专业性
        3. 增强可读性和理解性
        4. 平衡各方利益观点
        5. 突出市场影响和投资价值
        6. 保持原始事实和观点不变，仅做风格调整
        
        请直接输出优化后的新闻内容，不要包含任何解释或额外文字。
        """
        
        response = llm_chat(
            agent_name=self.agent_name,
            messages=[
                {"role": "system", "content": "你是一个专业的商业与经济专家，擅长优化新闻表达。"},
                {"role": "user", "content": prompt}
            ],
            base_url=aios_kernel_url,
        )["response"]
        
        return response["response_message"]
    
    def run(self, news_content, processing_instruction=""):
        """运行商业与经济专家分析"""
        try:
            # 分析新闻
            analysis_result = self.analyze_business_economy(news_content, processing_instruction)
            
            # 优化新闻
            optimized_news = self.optimize_business_news(news_content, analysis_result, processing_instruction)
            
            return {
                "agent_name": self.agent_name,
                "status": "success",
                "result": "商业与经济分析完成",
                "analysis": analysis_result,
                "optimized_news": optimized_news
            }
            
        except Exception as e:
            return {
                "agent_name": self.agent_name,
                "status": "failed",
                "result": f"商业与经济分析失败: {e}"
            }