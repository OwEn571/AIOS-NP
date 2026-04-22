import os
import json
import sys
sys.path.append('/data/llm/AIOS-NP')

from cerebrum.llm.apis import llm_chat
from cerebrum.config.config_manager import config

aios_kernel_url = config.get_kernel_url()

class FactCheckAgent:
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
    
    def check_facts(self, news_content, search_data, processing_instruction=""):
        """对比原始资料检查新闻中的事实准确性"""
        prompt = f"""请对比原始资料检查以下新闻中的事实准确性：

新闻内容：
{news_content}

原始搜索资料：
{search_data}

要求：
1. 对比新闻内容与原始资料，识别并修正任何不准确的信息
2. 检查是否有幻觉内容（虚构的时间、地点、数据等）
3. 确保所有事实、数据、引用都来源于原始资料
4. 保持新闻的客观性和可读性
5. 允许根据原始资料进行小的补充和拓展

请返回修正后的新闻内容，格式为：
标题: [标题]

摘要: [摘要]

内容: [内容]

注意：
1. 内容部分控制在300-500字之间
2. 不要添加任何注释、说明或think标签
3. 只返回纯新闻内容，确保格式正确"""
        
        self.messages = [{"role": "user", "content": prompt}]
        response = llm_chat(
            agent_name=self.agent_name,
            messages=self.messages,
            base_url=aios_kernel_url,
        )
        
        # 处理响应格式
        if "response" in response and "response_message" in response["response"]:
            response_message = response["response"]["response_message"]
        elif "response_message" in response:
            response_message = response["response_message"]
        else:
            print(f"⚠️ 响应格式异常: {response}")
            response_message = str(response)
        
        # 清理输出
        cleaned_response = self._clean_llm_output(response_message)
        final_response = self._clean_analysis_result(cleaned_response)
        
        return final_response
    
    def run(self, news_content, search_data, processing_instruction=""):
        """运行事实核查流程"""
        print("🔍 开始事实核查...")
        
        # 进行事实核查
        checked_news = self.check_facts(news_content, search_data, processing_instruction)
        print("✅ 事实核查完成")
        
        return checked_news
    
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
    
    def _extract_search_results(self, search_data):
        """提取每个搜索结果的前2000字"""
        import re
        
        # 按【结果 x】分割搜索数据
        results = re.split(r'【结果 \d+】', search_data)
        
        processed_results = []
        for i, result in enumerate(results):
            if i == 0:  # 第一个分割结果通常是标题或前言
                continue
            
            # 清理结果，去除多余空白
            cleaned_result = result.strip()
            if cleaned_result:
                # 取前2000字
                if len(cleaned_result) > 2000:
                    cleaned_result = cleaned_result[:2000] + "...[已截取前2000字]"
                
                processed_results.append(f"【结果 {i}】\n{cleaned_result}")
        
        return "\n\n".join(processed_results)

def main():
    agent = FactCheckAgent("fact_check_agent")
    
    # 测试新闻内容
    test_news = """标题: 张雪峰5000万捐款引争议

摘要: 张雪峰承诺若台海战争爆发将捐5000万元引发争议。支持者认为其表态体现爱国立场，批评者质疑其时机动机，认为应优先支持民生救灾等实际需求。该事件折射出公众对"算计式爱国"的反感，凸显和平统一政策与舆论场中爱国叙事的复杂博弈。

内容: 张雪峰近期因承诺"若台海发生战争，将捐出5000万元支持祖国统一"引发广泛争议。这一言论迅速在社交媒体上激起讨论，部分网友认为其言论时机敏感，存在"借爱国谋流量"的嫌疑，而另一部分人则赞赏其爱国情怀，认为此举体现了对国家统一的支持。"""
    
    # 测试搜索数据
    test_search = "张雪峰，教育从业者，近期在社交媒体上承诺若台海发生战争将捐出5000万元支持祖国统一，引发争议。"
    
    result = agent.run(test_news, test_search, "检查新闻中的事实准确性")
    print("\n🎯 处理完成!")
    print(f"📊 核查结果: {result}")

if __name__ == "__main__":
    main()