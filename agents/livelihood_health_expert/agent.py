import os
import json
import sys
sys.path.append('/data/llm/AIOS-NP')

from cerebrum.llm.apis import llm_chat
from cerebrum.config.config_manager import config

aios_kernel_url = config.get_kernel_url()

class LivelihoodHealthExpert:
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
    
    def analyze_livelihood_health(self, news_content, processing_instruction=""):
        """分析民生与健康新闻"""
        prompt = f"""
        作为民生与健康专家，请分析以下新闻：
        
        新闻内容：
        {news_content}
        
        处理指令：{processing_instruction}
        
        分析要求：
        1. 识别新闻中的民生要素和健康信息
        2. 分析对民众生活的影响
        3. 评估健康风险和安全问题
        4. 识别社会关注度和民生价值
        5. 提供专业的民生健康处理建议
        
        请严格按照以下JSON格式返回分析结果：
        {{
            "livelihood_elements": ["民生要素1", "民生要素2"],
            "health_information": ["健康信息1", "健康信息2"],
            "life_impact": "生活影响分析",
            "health_risks": "健康风险评估",
            "social_concern": "社会关注度评估",
            "livelihood_value": "民生价值评估",
            "recommendations": ["建议1", "建议2"],
            "expert_opinion": "专家意见和处理建议"
        }}
        """
        
        response = llm_chat(
            agent_name=self.agent_name,
            messages=[
                {"role": "system", "content": "你是一个专业的民生与健康专家，擅长分析民生现象和健康问题。"},
                {"role": "user", "content": prompt}
            ],
            base_url=aios_kernel_url,
        )["response"]
        
        return response["response_message"]
    
    def optimize_livelihood_news(self, news_content, analysis_result, processing_instruction=""):
        """优化民生与健康新闻"""
        prompt = f"""
        作为民生与健康专家，请优化以下新闻：
        
        原始新闻：
        {news_content}
        
        分析结果：
        {analysis_result}
        
        处理指令：{processing_instruction}
        
        优化要求：
        1. 突出民生价值和健康意义
        2. 确保健康信息准确和专业
        3. 增强贴近性和实用性
        4. 突出对民众生活的影响
        5. 平衡专业性和通俗性
        6. 保持原始事实和观点不变，仅做风格调整
        
        请直接输出优化后的新闻内容，不要包含任何解释或额外文字。
        """
        
        response = llm_chat(
            agent_name=self.agent_name,
            messages=[
                {"role": "system", "content": "你是一个专业的民生与健康专家，擅长优化新闻表达。"},
                {"role": "user", "content": prompt}
            ],
            base_url=aios_kernel_url,
        )["response"]
        
        return response["response_message"]
    
    def run(self, news_content, processing_instruction=""):
        """运行民生与健康专家分析"""
        try:
            # 分析新闻
            analysis_result = self.analyze_livelihood_health(news_content, processing_instruction)
            
            # 优化新闻
            optimized_news = self.optimize_livelihood_news(news_content, analysis_result, processing_instruction)
            
            return {
                "agent_name": self.agent_name,
                "status": "success",
                "result": "民生与健康分析完成",
                "analysis": analysis_result,
                "optimized_news": optimized_news
            }
            
        except Exception as e:
            return {
                "agent_name": self.agent_name,
                "status": "failed",
                "result": f"民生与健康分析失败: {e}"
            }