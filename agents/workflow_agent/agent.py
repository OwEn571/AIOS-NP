import os
import json
import sys
import re
import time
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
AGENTS_ROOT = PROJECT_ROOT / "agents"

sys.path.insert(0, str(PROJECT_ROOT))

from cerebrum.llm.apis import llm_chat_with_json_output, llm_chat
from cerebrum.config.config_manager import config
sys.path.insert(0, str(AGENTS_ROOT))
from descript_agent.agent import DescriptAgent
from ban_agent.agent import BanAgent
from constructure_agent.agent import ConstructureAgent
from fact_check_agent.agent import FactCheckAgent
from final_judge_agent.agent import FinalJudgeAgent
from apps.news_app.news_registry import build_domain_expert_instances

aios_kernel_url = config.get_kernel_url()

class WorkflowAgent:
    def __init__(self, agent_name):
        self.agent_name = agent_name
        self.current_news = ""
        self.workflow_history = []
        self.messages = []
        self.config = self._load_config()
        
        # 时间统计
        self.time_statistics = {}
        self.current_step_start_time = None
        
        # 初始化通用审阅agent
        self.descript_agent = DescriptAgent("descript_agent")
        self.ban_agent = BanAgent("ban_agent")
        self.constructure_agent = ConstructureAgent("constructure_agent")
        self.fact_check_agent = FactCheckAgent("fact_check_agent")
        self.final_judge_agent = FinalJudgeAgent("final_judge_agent")
        
        # 初始化领域专家
        self.domain_experts = build_domain_expert_instances()
        
    def _load_config(self):
        script_path = os.path.abspath(__file__)
        script_dir = os.path.dirname(script_path)
        config_file = os.path.join(script_dir, "config.json")
        with open(config_file, "r", encoding='utf-8') as f:
            config = json.load(f)
        return config
    
    def _start_timing(self, step_name):
        """开始计时"""
        self.current_step_start_time = time.time()
        print(f"⏱️ 开始 {step_name}...")
    
    def _end_timing(self, step_name):
        """结束计时并记录"""
        if self.current_step_start_time:
            duration = time.time() - self.current_step_start_time
            self.time_statistics[step_name] = duration
            print(f"⏱️ {step_name} 完成，耗时: {duration:.2f}秒")
            self.current_step_start_time = None
            return duration
        return 0
    
    def _read_news_file(self, file_path):
        """读取新闻文件内容"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            return content
        except Exception as e:
            print(f"❌ 读取新闻文件失败: {e}")
            return None
    
    def _load_original_news_content(self, news_file_path):
        """加载原始新闻内容（从_news.txt文件）"""
        try:
            return self._read_news_file(news_file_path)
        except Exception as e:
            print(f"❌ 加载原始新闻内容失败: {e}")
            return None
    
    def _get_final_news_content_from_track(self, news_file_path):
        """从track文件获取最终新闻内容"""
        try:
            # 直接返回当前新闻内容，不再依赖track文件
            return self.current_news
        except Exception as e:
            print(f"⚠️ Track文件解析失败，使用原始新闻内容")
            return self._load_original_news_content(news_file_path)
    
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
    
    def call_agent(self, agent_name, instruction):
        """调用指定的agent"""
        try:
            print(f"🔧 调用 {agent_name}...")
            
            # 开始计时
            self._start_timing(f"调用{agent_name}")
            
            # 记录旧内容
            old_content = self.current_news
            
            # 根据agent名称调用相应的处理函数
            if agent_name == "描述优化Agent":
                result = self.descript_agent.run(self.current_news, instruction)
            elif agent_name == "禁用词检测Agent":
                result = self.ban_agent.run(self.current_news, instruction)
            elif agent_name == "结构优化Agent":
                result = self.constructure_agent.run(self.current_news, instruction)
            elif agent_name == "事实核查Agent":
                # 加载搜索数据
                search_data = self._load_search_data()
                result = self.fact_check_agent.run(self.current_news, search_data, instruction)
            else:
                print(f"❌ 未知的agent: {agent_name}")
                return None
            
            # 结束计时
            self._end_timing(f"调用{agent_name}")
            
            if result:
                # 更新当前新闻内容
                self.current_news = result
                return result
            else:
                print(f"❌ {agent_name} 处理失败")
                return None
                
        except Exception as e:
            print(f"❌ 调用 {agent_name} 失败: {e}")
            return None
    
    def call_final_judge_agent(self):
        """调用最终判断agent"""
        try:
            print("⚖️ 开始新闻质量检查...")
            self._start_timing("最终质量检查")
            
            result = self.final_judge_agent.run(self.current_news)
            
            self._end_timing("最终质量检查")
            return result
            
        except Exception as e:
            print(f"❌ 最终判断失败: {e}")
            return None
    
    def _load_search_data(self):
        """加载搜索数据"""
        try:
            # 从当前新闻文件路径推断搜索文件路径
            if hasattr(self, 'current_news_file') and self.current_news_file:
                search_file = self.current_news_file.replace('_news.txt', '_search.txt')
                if os.path.exists(search_file):
                    with open(search_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    print(f"📚 成功加载搜索数据: {search_file}")
                    return content
                else:
                    print(f"⚠️ 搜索文件不存在: {search_file}")
                    return ""
            else:
                print("⚠️ 无法确定搜索文件路径")
                return ""
        except Exception as e:
            print(f"❌ 加载搜索数据失败: {e}")
            return ""
    
    def run_workflow(self, news_file_path):
        """运行工作流"""
        try:
            print(f"🚀 开始新闻审议工作流...")
            print("=" * 50)
            
            # 初始化跟踪系统
            self.time_statistics = {}
            
            # 读取新闻内容
            self.current_news = self._read_news_file(news_file_path)
            if not self.current_news:
                return {"status": "failed", "message": "无法读取新闻文件"}
            
            self.current_news_file = news_file_path
            print(f"📰 新闻内容长度: {len(self.current_news)} 字符")
            
            # 运行工作流
            result = self._run_workflow_iteration(news_file_path)
            
            # 添加时间统计到结果中
            if isinstance(result, dict):
                result["time_statistics"] = self.time_statistics
            
            return result
            
        except Exception as e:
            return {"status": "failed", "message": f"工作流执行失败: {e}"}
    
    def run_workflow_with_domain(self, news_file_path, domain):
        """运行带领域专家的工作流"""
        try:
            print(f"🚀 开始{domain}新闻审议工作流...")
            print("=" * 50)
            
            # 初始化跟踪系统
            self.time_statistics = {}
            
            # 读取新闻内容
            self.current_news = self._read_news_file(news_file_path)
            if not self.current_news:
                return {"status": "failed", "message": "无法读取新闻文件"}
            
            self.current_news_file = news_file_path
            print(f"📰 新闻内容长度: {len(self.current_news)} 字符")
            
            # 使用领域专家进行初步处理
            print(f"🎯 使用{domain}专家进行初步处理...")
            domain_expert = self.domain_experts.get(domain)
            if domain_expert:
                self._start_timing(f"{domain}专家处理")
                domain_result = domain_expert.run(self.current_news, f"对{domain}新闻进行专业优化")
                self._end_timing(f"{domain}专家处理")
                
                # 检查领域专家返回结果
                if domain_result and isinstance(domain_result, dict):
                    if domain_result.get("status") == "success" and "optimized_news" in domain_result:
                        optimized_news = domain_result["optimized_news"]
                        # 更新当前新闻内容
                        self.current_news = optimized_news
                        print(f"✅ {domain}专家处理完成")
                    else:
                        print(f"⚠️ {domain}专家处理失败: {domain_result.get('result', '未知错误')}")
                else:
                    print(f"⚠️ {domain}专家处理失败，继续使用原始内容")
            else:
                print(f"⚠️ 未找到{domain}专家，跳过领域处理")
            
            # 运行工作流
            result = self._run_workflow_iteration(news_file_path)
            
            # 添加时间统计到结果中
            if isinstance(result, dict):
                result["time_statistics"] = self.time_statistics
                
                # 确保包含reviewed_file
                if "reviewed_file" not in result:
                    reviewed_file = news_file_path.replace('_news.txt', '_reviewed.txt')
                    result["reviewed_file"] = reviewed_file
            
            return result
            
        except Exception as e:
            return {"status": "failed", "message": f"工作流执行失败: {e}"}
    
    def _run_workflow_iteration(self, news_file_path):
        """运行工作流迭代"""
        try:
            max_iterations = 5
            action_count = {}
            is_ready_for_judge = False
            
            for iteration in range(max_iterations):
                print(f"\n🔄 第 {iteration + 1} 轮处理...")
                
                # 调用final_judge_agent进行质量检查
                judge_result = self.call_final_judge_agent()
                print(f"📊 质量检查结果: {judge_result}")
                
                # 解析judge结果
                try:
                    if isinstance(judge_result, dict) and "response" in judge_result:
                        response_text = judge_result["response"]["response_message"]
                        print(f"🔍 原始response_text: {response_text[:200]}...")
                        
                        # 移除think标签
                        response_text = re.sub(r'<think>.*?</think>', '', response_text, flags=re.DOTALL)
                        cleaned_result = self._clean_llm_output(response_text)
                        print(f"📝 清理后结果: {cleaned_result[:200]}...")
                        
                        # 解析JSON结果
                        try:
                            judge_data = json.loads(cleaned_result)
                            print(f"✅ 成功解析judge结果: {judge_data}")

                            need_optimization = judge_data.get("need_optimization")
                            if need_optimization is None and "meets_requirements" in judge_data:
                                need_optimization = not bool(judge_data.get("meets_requirements"))
                            
                            # 检查是否需要进一步处理
                            if need_optimization:
                                recommended_agent = judge_data.get("recommended_agent")
                                processing_instruction = judge_data.get("processing_instruction", "")
                                
                                if recommended_agent and recommended_agent != "none":
                                    print(f"🔧 推荐使用 {recommended_agent} 进行优化")
                                    
                                    # 检查是否已经调用过太多次
                                    if action_count.get(recommended_agent, 0) >= 2:
                                        print(f"⚠️ {recommended_agent} 已调用2次，跳过")
                                        continue
                                    
                                    # 调用推荐的agent
                                    optimized_news = self.call_agent(recommended_agent, processing_instruction)
                                    if optimized_news:
                                        action_count[recommended_agent] = action_count.get(recommended_agent, 0) + 1
                                    else:
                                        print(f"❌ {recommended_agent} 处理失败")
                                        break
                                else:
                                    print("✅ 无需进一步处理，准备进入质量检查...")
                                    is_ready_for_judge = True
                                    break
                            else:
                                print("✅ 新闻质量达到要求，准备进入质量检查...")
                                is_ready_for_judge = True
                                break
                                
                        except json.JSONDecodeError as e:
                            print(f"❌ JSON解析失败: {e}")
                            print(f"原始内容: {cleaned_result}")
                            continue
                    else:
                        print("❌ 无法解析judge结果，继续优化...")
                        continue
                        
                except Exception as e:
                    print(f"❌ 解析judge结果失败: {e}")
                    continue
            
            # 如果达到最大迭代次数或准备就绪，进行最终处理
            if is_ready_for_judge or iteration >= max_iterations - 1:
                print("✅ 新闻质量达到要求，进行事实核查...")
                # 先进行事实核查
                print("🔍 强制进行事实核查...")
                
                # 记录事实核查前的新闻内容
                old_content = self.current_news
                
                self._start_timing("事实核查")
                search_data = self._load_search_data()
                
                # 确保使用干净的最终版新闻内容
                final_news_content = self.current_news
                
                fact_checked_news = self.fact_check_agent.run(
                    final_news_content, 
                    search_data,
                    "对比原始资料检查新闻中的事实准确性，去除幻觉内容"
                )
                self._end_timing("事实核查")
                
                if fact_checked_news:
                    # 更新新闻内容
                    self.current_news = fact_checked_news
                else:
                    print("⚠️ 事实核查失败，保持原内容")
                
                print("✅ 事实核查完成，进行最终检查...")
                # 调用final_judge_agent
                judge_result = self.call_final_judge_agent()
                print(f"📊 质量检查结果: {judge_result}")
                
                # 解析judge结果
                try:
                    if isinstance(judge_result, dict) and "response" in judge_result:
                        response_text = judge_result["response"]["response_message"]
                        print(f"🔍 原始response_text: {response_text[:200]}...")
                        
                        # 移除think标签
                        response_text = re.sub(r'<think>.*?</think>', '', response_text, flags=re.DOTALL)
                        cleaned_result = self._clean_llm_output(response_text)
                        print(f"📝 清理后结果: {cleaned_result[:200]}...")
                        
                        # 解析JSON结果
                        try:
                            judge_data = json.loads(cleaned_result)
                            print(f"✅ 成功解析judge结果: {judge_data}")

                            need_optimization = judge_data.get("need_optimization")
                            if need_optimization is None and "meets_requirements" in judge_data:
                                need_optimization = not bool(judge_data.get("meets_requirements"))
                            
                            # 检查最终质量
                            if need_optimization:
                                print("⚠️ 最终质量检查未通过，但已达到最大迭代次数")
                            else:
                                print("✅ 最终质量检查通过")
                                
                        except json.JSONDecodeError as e:
                            print(f"❌ 最终JSON解析失败: {e}")
                            print(f"原始内容: {cleaned_result}")
                    else:
                        print("❌ 无法解析最终judge结果")
                        
                except Exception as e:
                    print(f"❌ 解析最终judge结果失败: {e}")
            
            # 保存最终结果
            final_news = self._clean_llm_output(self.current_news)
            reviewed_file = news_file_path.replace('_news.txt', '_reviewed.txt')
            
            with open(reviewed_file, 'w', encoding='utf-8') as f:
                f.write(final_news)
            
            print(f"✅ 工作流完成，保存到: {reviewed_file}")
            
            return {
                "status": "success",
                "message": "工作流执行成功",
                "reviewed_file": reviewed_file,
                "final_news": final_news
            }
            
        except Exception as e:
            return {"status": "failed", "message": f"工作流迭代失败: {e}"}


if __name__ == "__main__":
    # 测试代码
    agent = WorkflowAgent("workflow_agent")
    result = agent.run_workflow("/data/llm/AIOS-NP/intermediate/争议事件_0_news.txt")
    print(f"结果: {result}")
