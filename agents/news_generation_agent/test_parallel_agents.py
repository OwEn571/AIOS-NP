#!/usr/bin/env python3
"""
并行新闻生成主流程。
"""

import threading
from typing import Dict
from concurrent.futures import ThreadPoolExecutor, as_completed

from title_agent import TitleAgent
from summary_agent import SummaryAgent
from content_agent import ContentAgent
from judge_agent import JudgeAgent


class ParallelNewsTest:
    """并行生成标题、摘要和正文，并在局部评审后输出新闻结果。"""

    def __init__(self):
        self.title_agent = TitleAgent()
        self.summary_agent = SummaryAgent()
        self.content_agent = ContentAgent()
        self.judge_agent = JudgeAgent()
        self.lock = threading.Lock()
        self.max_retries = 3

    def generate_news(self, search_result: str, topic: str, category: str) -> Dict[str, str]:
        """
        并行生成新闻内容，完成后立即评审
        
        :param search_result: 搜索结果内容
        :param topic: 新闻主题
        :param category: 新闻分类
        :return: 包含标题、摘要、内容的字典
        """
        print(f"=== 并行新闻生成开始 ===")
        print(f"主题: {topic}")
        print(f"分类: {category}")
        print(f"搜索结果长度: {len(search_result)} 字符")
        
        # 搜索结果在搜索阶段已经处理了长度问题
        truncated_search_result = self._auto_truncate_search_result(search_result, topic)
        
        # 为每个新闻创建独立的结果存储
        news_results = {
            'title': None,
            'summary': None,
            'content': None
        }
        
        news_judgments = {
            'title': {'pass': False, 'feedback': '', 'retry_count': 0},
            'summary': {'pass': False, 'feedback': '', 'retry_count': 0},
            'content': {'pass': False, 'feedback': '', 'retry_count': 0}
        }
        
        
        # 启动三个生成任务，传递独立的结果存储
        with ThreadPoolExecutor(max_workers=3) as executor:
            # 提交任务
            title_future = executor.submit(self._generate_title_with_judge, truncated_search_result, topic, news_results, news_judgments)
            summary_future = executor.submit(self._generate_summary_with_judge, truncated_search_result, topic, news_results, news_judgments)
            content_future = executor.submit(self._generate_content_with_judge, truncated_search_result, topic, news_results, news_judgments)
            
        # 等待所有任务完成
        futures = [title_future, summary_future, content_future]
        for future in as_completed(futures):
            try:
                future.result()
            except Exception as e:
                print(f"❌ 任务执行失败: {e}")
        
        # 检查是否所有部分都通过评审
        all_passed = all(news_judgments[part]['pass'] for part in ['title', 'summary', 'content'])
        
        if all_passed:
            print("🎉 所有部分都通过评审！开始保存新闻文件...")
            # 保存新闻到文件，并传递搜索数据用于信源相关度分析
            saved_file = self.judge_agent.save_news_to_file(
                news_results['title'],
                news_results['summary'], 
                news_results['content'],
                topic,
                truncated_search_result  # 传递截断后的搜索数据用于信源相关度分析
            )
            if saved_file:
                print(f"📰 新闻已保存到: {saved_file}")
        else:
            error_message = self._build_failure_message(news_judgments)
            print(f"⚠️ 新闻生成未通过评审: {error_message}")
            return {
                'title': '',
                'summary': '',
                'content': '',
                'error': error_message,
                'judgments': {
                    part: dict(news_judgments.get(part) or {})
                    for part in ['title', 'summary', 'content']
                },
                'category': category,
                'topic': topic,
            }

        # 组装最终结果
        final_result = {
            'title': news_results['title'] or '',
            'summary': news_results['summary'] or '',
            'content': news_results['content'] or ''
        }
        
        print(f"=== 并行新闻生成完成 ===")
        return final_result

    def _auto_truncate_search_result(self, search_result: str, topic: str) -> str:
        """
        简单的搜索结果截断，在搜索阶段已经处理了长度问题
        """
        # 搜索阶段已经处理了长度截断，这里直接返回
        return search_result

    def _build_failure_message(self, news_judgments: dict) -> str:
        failed_parts = []
        for part in ['title', 'summary', 'content']:
            judgment = news_judgments.get(part, {})
            if judgment.get('pass'):
                continue
            feedback = judgment.get('feedback') or '未通过评审'
            failed_parts.append(f"{part}: {feedback}")
        return "; ".join(failed_parts) if failed_parts else "生成结果为空"



    def _generate_title_with_judge(self, search_result: str, topic: str, news_results: dict, news_judgments: dict):
        """生成标题并进行评审"""
        print("🚀 启动标题生成...")
        
        retry_count = 0
        while retry_count < self.max_retries:
            try:
                # 生成标题
                if retry_count == 0:
                    title = self.title_agent.generate_title(search_result, topic)
                else:
                    feedback = news_judgments['title']['feedback']
                    title = self.title_agent.regenerate_title(search_result, topic, feedback)
                
                # 立即评审
                print("⚖️ 立即评审标题...")
                pass_status, feedback = self.judge_agent.judge_single_part("title", title, topic)
                
                with self.lock:
                    news_results['title'] = title
                    news_judgments['title'] = {
                        'pass': pass_status,
                        'feedback': feedback,
                        'retry_count': retry_count
                    }
                
                if pass_status:
                    print("✅ 标题通过评审！")
                    return
                else:
                    print(f"❌ 标题未通过评审: {feedback}")
                    retry_count += 1
                    
            except Exception as e:
                print(f"❌ 标题生成失败: {e}")
                retry_count += 1
        
        print(f"⚠️ 标题达到最大重试次数 {self.max_retries}")

    def _generate_summary_with_judge(self, search_result: str, topic: str, news_results: dict, news_judgments: dict):
        """生成摘要并进行评审"""
        print("🚀 启动摘要生成...")
        
        retry_count = 0
        while retry_count < self.max_retries:
            try:
                # 生成摘要
                if retry_count == 0:
                    summary = self.summary_agent.generate_summary(search_result, topic)
                else:
                    feedback = news_judgments['summary']['feedback']
                    summary = self.summary_agent.regenerate_summary(search_result, topic, feedback)
                
                # 立即评审
                print("⚖️ 立即评审摘要...")
                pass_status, feedback = self.judge_agent.judge_single_part("summary", summary, topic)
                
                with self.lock:
                    news_results['summary'] = summary
                    news_judgments['summary'] = {
                        'pass': pass_status,
                        'feedback': feedback,
                        'retry_count': retry_count
                    }
                
                if pass_status:
                    print("✅ 摘要通过评审！")
                    return
                else:
                    print(f"❌ 摘要未通过评审: {feedback}")
                    retry_count += 1
                    
            except Exception as e:
                print(f"❌ 摘要生成失败: {e}")
                retry_count += 1
        
        print(f"⚠️ 摘要达到最大重试次数 {self.max_retries}")

    def _generate_content_with_judge(self, search_result: str, topic: str, news_results: dict, news_judgments: dict):
        """生成内容并进行评审"""
        print("🚀 启动内容生成...")
        
        retry_count = 0
        while retry_count < self.max_retries:
            try:
                # 生成内容
                if retry_count == 0:
                    content = self.content_agent.generate_content(search_result, topic)
                else:
                    feedback = news_judgments['content']['feedback']
                    content = self.content_agent.regenerate_content(search_result, topic, feedback)
                
                # 立即评审
                print("⚖️ 立即评审内容...")
                pass_status, feedback = self.judge_agent.judge_single_part("content", content, topic)
                
                with self.lock:
                    news_results['content'] = content
                    news_judgments['content'] = {
                        'pass': pass_status,
                        'feedback': feedback,
                        'retry_count': retry_count
                    }
                
                if pass_status:
                    print("✅ 内容通过评审！")
                    return
                else:
                    print(f"❌ 内容未通过评审: {feedback}")
                    retry_count += 1
                    
            except Exception as e:
                print(f"❌ 内容生成失败: {e}")
                retry_count += 1
        
        print(f"⚠️ 内容达到最大重试次数 {self.max_retries}")
