import os
import json
import sys
sys.path.append('/data/llm/AIOS-NP')

from cerebrum.llm.apis import llm_chat
from cerebrum.config.config_manager import config

aios_kernel_url = config.get_kernel_url()

class TechInnovationExpert:
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
    
    def analyze_tech_innovation(self, news_content, processing_instruction=""):
        """分析科技与创新新闻"""
        prompt = f"""
        作为科技与创新专家，请分析以下新闻：
        
        新闻内容：
        {news_content}
        
        处理指令：{processing_instruction}
        
        分析要求：
        1. 识别新闻中的技术要素和创新点
        2. 分析技术影响和应用前景
        3. 评估创新价值和突破性
        4. 识别技术趋势和发展方向
        5. 提供专业的科技创新处理建议
        
        请严格按照以下JSON格式返回分析结果：
        {{
            "tech_elements": ["技术要素1", "技术要素2"],
            "innovation_points": ["创新点1", "创新点2"],
            "tech_impact": "技术影响分析",
            "application_prospects": "应用前景评估",
            "innovation_value": "创新价值评估",
            "tech_trends": "技术趋势分析",
            "recommendations": ["建议1", "建议2"],
            "expert_opinion": "专家意见和处理建议"
        }}
        """
        
        response = llm_chat(
            agent_name=self.agent_name,
            messages=[
                {"role": "system", "content": "你是一个专业的科技与创新专家，擅长分析技术现象和创新价值。"},
                {"role": "user", "content": prompt}
            ],
            base_url=aios_kernel_url,
        )["response"]
        
        return response["response_message"]
    
    def optimize_tech_news(self, news_content, analysis_result, processing_instruction=""):
        """优化科技与创新新闻"""
        prompt = f"""
        作为科技与创新专家，请优化以下新闻：
        
        原始新闻：
        {news_content}
        
        分析结果：
        {analysis_result}
        
        处理指令：{processing_instruction}
        
        优化要求：
        1. 突出技术价值和创新意义
        2. 确保技术表述准确和专业
        3. 增强可读性和理解性
        4. 突出应用前景和影响
        5. 平衡技术深度和通俗性
        6. 保持原始事实和观点不变，仅做风格调整
        
        请直接输出优化后的新闻内容，不要包含任何解释或额外文字。
        """
        
        response = llm_chat(
            agent_name=self.agent_name,
            messages=[
                {"role": "system", "content": "你是一个专业的科技与创新专家，擅长优化新闻表达。"},
                {"role": "user", "content": prompt}
            ],
            base_url=aios_kernel_url,
        )["response"]
        
        return response["response_message"]
    
    def run(self, news_content, processing_instruction=""):
        """运行科技与创新专家分析"""
        try:
            # 分析新闻
            analysis_result = self.analyze_tech_innovation(news_content, processing_instruction)
            
            # 优化新闻
            optimized_news = self.optimize_tech_news(news_content, analysis_result, processing_instruction)
            
            return {
                "agent_name": self.agent_name,
                "status": "success",
                "result": "科技与创新分析完成",
                "analysis": analysis_result,
                "optimized_news": optimized_news
            }
            
        except Exception as e:
            return {
                "agent_name": self.agent_name,
                "status": "failed",
                "result": f"科技与创新分析失败: {e}"
            }