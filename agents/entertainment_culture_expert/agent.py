import os
import json
import sys
sys.path.append('/data/llm/AIOS-NP')

from cerebrum.llm.apis import llm_chat
from cerebrum.config.config_manager import config

aios_kernel_url = config.get_kernel_url()

class EntertainmentCultureExpert:
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
    
    def analyze_entertainment_culture(self, news_content, processing_instruction=""):
        """分析娱乐与文化新闻"""
        prompt = f"""
        作为娱乐与文化专家，请分析以下新闻：
        
        新闻内容：
        {news_content}
        
        处理指令：{processing_instruction}
        
        分析要求：
        1. 识别新闻中的娱乐元素和文化价值
        2. 分析文化影响和艺术价值
        3. 评估娱乐性和观赏性
        4. 识别文化传承和创新要素
        5. 提供专业的娱乐文化处理建议
        
        请严格按照以下JSON格式返回分析结果：
        {{
            "entertainment_elements": ["娱乐元素1", "娱乐元素2"],
            "cultural_value": "文化价值分析",
            "artistic_merit": "艺术价值评估",
            "entertainment_value": "娱乐价值评估",
            "cultural_heritage": "文化传承要素",
            "innovation_aspects": "创新要素",
            "recommendations": ["建议1", "建议2"],
            "expert_opinion": "专家意见和处理建议"
        }}
        """
        
        response = llm_chat(
            agent_name=self.agent_name,
            messages=[
                {"role": "system", "content": "你是一个专业的娱乐与文化专家，擅长分析娱乐现象和文化价值。"},
                {"role": "user", "content": prompt}
            ],
            base_url=aios_kernel_url,
        )["response"]
        
        return response["response_message"]
    
    def optimize_entertainment_news(self, news_content, analysis_result, processing_instruction=""):
        """优化娱乐与文化新闻"""
        prompt = f"""
        作为娱乐与文化专家，请优化以下新闻：
        
        原始新闻：
        {news_content}
        
        分析结果：
        {analysis_result}
        
        处理指令：{processing_instruction}
        
        优化要求：
        1. 增强娱乐性和趣味性
        2. 突出文化价值和艺术性
        3. 保持内容的生动性和吸引力
        4. 确保文化表述准确
        5. 平衡娱乐与教育价值
        6. 保持原始事实和观点不变，仅做风格调整
        
        请直接输出优化后的新闻内容，不要包含任何解释或额外文字。
        """
        
        response = llm_chat(
            agent_name=self.agent_name,
            messages=[
                {"role": "system", "content": "你是一个专业的娱乐与文化专家，擅长优化新闻表达。"},
                {"role": "user", "content": prompt}
            ],
            base_url=aios_kernel_url,
        )["response"]
        
        return response["response_message"]
    
    def run(self, news_content, processing_instruction=""):
        """运行娱乐与文化专家分析"""
        try:
            # 分析新闻
            analysis_result = self.analyze_entertainment_culture(news_content, processing_instruction)
            
            # 优化新闻
            optimized_news = self.optimize_entertainment_news(news_content, analysis_result, processing_instruction)
            
            return {
                "agent_name": self.agent_name,
                "status": "success",
                "result": "娱乐与文化分析完成",
                "analysis": analysis_result,
                "optimized_news": optimized_news
            }
            
        except Exception as e:
            return {
                "agent_name": self.agent_name,
                "status": "failed",
                "result": f"娱乐与文化分析失败: {e}"
            }