import json
import os
import re
import subprocess
import sys
from typing import Dict, Any
from cerebrum.tool.base import BaseTool

class WebSearch(BaseTool):
    def __init__(self):
        super().__init__()
        self.search_timeout = int(os.getenv("TAVILY_SEARCH_TIMEOUT", "35"))
        self.max_clean_input_chars = int(
            os.getenv("TAVILY_MAX_CLEAN_INPUT_CHARS", "120000")
        )
    
    def _clean_html_content(self, html_content: str) -> str:
        """清理HTML内容，提取核心文章内容，保留正文中的图片"""
        if not html_content:
            return ""

        if len(html_content) > self.max_clean_input_chars:
            html_content = html_content[: self.max_clean_input_chars]
        
        # 使用优化的内容提取方法
        cleaned_content = self._extract_clean_article(html_content)
        
        return cleaned_content
    
    def _extract_clean_article(self, html_content: str) -> str:
        """提取干净的文章内容，保留正文和图片"""
        if not html_content:
            return ""
        
        # 第一步：移除所有无用的HTML标签和内容
        html_content = self._remove_all_junk(html_content)
        
        # 第二步：提取文章主体
        main_content = self._extract_main_article(html_content)
        
        if main_content:
            # 第三步：清理并格式化内容
            return self._format_clean_content(main_content)
        
        return ""
    
    def _remove_all_junk(self, html_content: str) -> str:
        """移除所有无用的HTML内容"""
        # 移除script、style、注释
        html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        html_content = re.sub(r'<!--.*?-->', '', html_content, flags=re.DOTALL)
        
        # 移除导航、头部、底部、侧边栏等
        junk_patterns = [
            r'<nav[^>]*>.*?</nav>',
            r'<header[^>]*>.*?</header>',
            r'<footer[^>]*>.*?</footer>',
            r'<aside[^>]*>.*?</aside>',
            # 移除包含特定class或id的div
            r'<div[^>]*(?:class|id)="[^"]*(?:nav|menu|header|footer|sidebar|ad|banner|advertisement|related|hot|comment|share|author|time|tag|copyright|social|follow|subscribe|login|register|search|form|button|link|breadcrumb)[^"]*"[^>]*>.*?</div>',
            # 移除包含特定class或id的section
            r'<section[^>]*(?:class|id)="[^"]*(?:nav|menu|header|footer|sidebar|ad|banner|advertisement|related|hot|comment|share|author|time|tag|copyright|social|follow|subscribe|login|register|search|form|button|link|breadcrumb)[^"]*"[^>]*>.*?</section>',
            # 移除包含特定class或id的article
            r'<article[^>]*(?:class|id)="[^"]*(?:nav|menu|header|footer|sidebar|ad|banner|advertisement|related|hot|comment|share|author|time|tag|copyright|social|follow|subscribe|login|register|search|form|button|link|breadcrumb)[^"]*"[^>]*>.*?</article>',
            # 移除包含特定class或id的ul/ol
            r'<ul[^>]*(?:class|id)="[^"]*(?:nav|menu|header|footer|sidebar|ad|banner|advertisement|related|hot|comment|share|author|time|tag|copyright|social|follow|subscribe|login|register|search|form|button|link|breadcrumb)[^"]*"[^>]*>.*?</ul>',
            r'<ol[^>]*(?:class|id)="[^"]*(?:nav|menu|header|footer|sidebar|ad|banner|advertisement|related|hot|comment|share|author|time|tag|copyright|social|follow|subscribe|login|register|search|form|button|link|breadcrumb)[^"]*"[^>]*>.*?</ol>',
        ]
        
        for pattern in junk_patterns:
            html_content = re.sub(pattern, '', html_content, flags=re.DOTALL | re.IGNORECASE)
        
        return html_content
    
    def _extract_main_article(self, html_content: str) -> str:
        """提取文章主体内容"""
        # 策略1：寻找article标签
        article_match = re.search(r'<article[^>]*>(.*?)</article>', html_content, re.DOTALL | re.IGNORECASE)
        if article_match:
            return article_match.group(1)
        
        # 策略2：寻找main标签
        main_match = re.search(r'<main[^>]*>(.*?)</main>', html_content, re.DOTALL | re.IGNORECASE)
        if main_match:
            return main_match.group(1)
        
        # 策略3：寻找包含大量中文文本的段落
        chinese_text_patterns = [
            r'<p[^>]*>.*?[\u4e00-\u9fff].*?[\u4e00-\u9fff].*?[\u4e00-\u9fff].*?[\u4e00-\u9fff].*?</p>',
            r'<div[^>]*>.*?[\u4e00-\u9fff].*?[\u4e00-\u9fff].*?[\u4e00-\u9fff].*?[\u4e00-\u9fff].*?</div>',
        ]
        
        for pattern in chinese_text_patterns:
            matches = re.findall(pattern, html_content, re.DOTALL | re.IGNORECASE)
            if matches:
                # 选择最长的匹配内容
                main_content = max(matches, key=len)
                if len(main_content) > 500:  # 确保内容足够长
                    return main_content
        
        # 策略4：如果都找不到，返回整个内容
        return html_content
    
    def _format_clean_content(self, content: str) -> str:
        """极端清理：只保留大段中文内容，图片保存到后面"""
        # 先提取所有可能的图片链接
        img_patterns = [
            r'<img[^>]+src=["\']([^"\']+)["\'][^>]*>',
            r'https?://[^\s<>"\']+\.(?:jpg|jpeg|png|gif|webp|bmp|svg)',
            r'https?://[^\s<>"\']*image[^\s<>"\']*',
            r'https?://[^\s<>"\']*img[^\s<>"\']*',
            r'https?://[^\s<>"\']*photo[^\s<>"\']*',
            r'https?://[^\s<>"\']*pic[^\s<>"\']*'
        ]
        
        all_images = []
        for pattern in img_patterns:
            matches = re.findall(pattern, content, re.IGNORECASE)
            all_images.extend(matches)
        
        # 过滤有效图片（排除明显的广告图标）
        valid_images = []
        for img_url in all_images:
            if not any(skip in img_url.lower() for skip in [
                'ad', 'banner', 'icon', 'logo', 'button', 'arrow', 
                'spacer', 'pixel', 'tracking', 'analytics', 'ads',
                'avatar', 'profile', 'menu', 'nav', 'header', 'footer', 
                'sidebar', 'social', 'share', 'comment', 'like', 'follow', 
                'subscribe', 'facebook', 'twitter', 'weibo', 'qq', 'wechat',
                'scorecard', 'udn', 'static', 'beian', 'police', 'report'
            ]):
                if any(img_type in img_url.lower() for img_type in [
                    '.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg', 'image'
                ]):
                    valid_images.append(img_url)
        
        # 移除所有HTML标签
        content = re.sub(r'<[^>]+>', '', content)
        
        # 按段落分割内容
        paragraphs = content.split('\n')
        chinese_paragraphs = []
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
                
            # 计算中文字符比例
            chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', para))
            total_chars = len(para)
            
            if total_chars > 0:
                chinese_ratio = chinese_chars / total_chars
                
                # 只保留中文字符比例大于50%且长度大于20的段落
                if chinese_ratio > 0.5 and total_chars > 20:
                    # 进一步清理段落内容
                    para = self._clean_paragraph(para)
                    if para:  # 如果清理后还有内容
                        chinese_paragraphs.append(para)
        
        # 合并段落
        result = '\n\n'.join(chinese_paragraphs)
        
        # 如果有有效图片，添加到内容末尾
        if valid_images:
            result += "\n\n🖼️ 相关图片:\n"
            for i, img_url in enumerate(valid_images[:5], 1):  # 最多保留5张图片
                result += f"{i}. {img_url}\n"
        
        return result
    
    def _clean_paragraph(self, para: str) -> str:
        """清理单个段落"""
        # 移除明显的无用内容
        useless_patterns = [
            r'点击.*?查看.*?',
            r'阅读.*?更多.*?',
            r'相关.*?推荐.*?',
            r'热门.*?文章.*?',
            r'热文.*?排行.*?',
            r'点击.*?排行.*?',
            r'广告.*?投放.*?',
            r'版权.*?所有.*?',
            r'未经.*?许可.*?',
            r'违者.*?必究.*?',
            r'读者.*?热线.*?',
            r'特别.*?提醒.*?',
            r'如需.*?转载.*?',
            r'联系我们.*?',
            r'意见反馈.*?',
            r'网站.*?声明.*?',
            r'隐私.*?政策.*?',
            r'服务.*?条款.*?',
            r'关于.*?我们.*?',
            r'加入.*?我们.*?',
            r'友情.*?链接.*?',
            r'关注.*?我们.*?',
            r'分享.*?好友.*?',
            r'生成.*?海报.*?',
            r'保存.*?图片.*?',
            r'下载.*?APP.*?',
            r'扫码.*?关注.*?',
            r'微信.*?公众号.*?',
            r'微博.*?关注.*?',
            r'QQ.*?空间.*?',
            r'新浪.*?微博.*?',
            r'腾讯.*?微博.*?',
            r'人人.*?网.*?',
            r'开心.*?网.*?',
            r'豆瓣.*?网.*?',
            r'知乎.*?网.*?',
            r'贴吧.*?网.*?',
            r'论坛.*?网.*?',
            r'社区.*?网.*?',
            r'博客.*?网.*?',
            r'空间.*?网.*?',
            r'相册.*?网.*?',
            r'视频.*?网.*?',
            r'音乐.*?网.*?',
            r'游戏.*?网.*?',
            r'购物.*?网.*?',
            r'团购.*?网.*?',
            r'优惠.*?券.*?',
            r'折扣.*?信息.*?',
            r'促销.*?活动.*?',
            r'限时.*?特价.*?',
            r'秒杀.*?活动.*?',
            r'抢购.*?活动.*?',
            r'免费.*?试用.*?',
            r'免费.*?体验.*?',
            r'免费.*?领取.*?',
            r'免费.*?下载.*?',
            r'免费.*?注册.*?',
            r'免费.*?开通.*?',
            r'免费.*?申请.*?',
            r'免费.*?预约.*?',
            r'免费.*?咨询.*?',
            r'免费.*?服务.*?',
            r'免费.*?支持.*?',
            r'免费.*?帮助.*?',
            r'免费.*?指导.*?',
            r'免费.*?培训.*?',
            r'免费.*?学习.*?',
            r'免费.*?教育.*?',
            r'免费.*?课程.*?',
            r'免费.*?讲座.*?',
            r'免费.*?会议.*?',
            r'免费.*?活动.*?',
            r'免费.*?参与.*?',
            r'免费.*?加入.*?',
            r'免费.*?成为.*?',
            r'免费.*?获得.*?',
            r'免费.*?得到.*?',
            r'免费.*?享受.*?',
            r'免费.*?使用.*?',
            r'热文.*?精选.*?',
            r'精彩.*?用户.*?评论.*?',
            r'黑子网.*?',
            r'吃瓜.*?网.*?',
            r'51.*?吃瓜.*?',
            r'51.*?黑料.*?',
            r'同城.*?热聊.*?',
            r'夜色.*?派对.*?',
            r'电子.*?游戏.*?',
            r'娱乐.*?城.*?',
            r'直播.*?平台.*?',
            r'澳门.*?娱乐.*?',
            r'PG.*?电子.*?',
            r'开元.*?棋牌.*?',
            r'金沙.*?直播.*?',
            r'AI.*?直播.*?',
            r'抖阴.*?直播.*?',
            r'免费.*?看片.*?',
            r'免费.*?色漫.*?',
            r'免费.*?萝莉.*?',
            r'免费.*?黄片.*?',
            r'成人.*?福利.*?',
            r'性福.*?管家.*?',
            r'约炮.*?交友.*?',
            r'换妻.*?交友.*?',
            r'男男.*?视频.*?',
            r'猎奇.*?重口.*?',
            r'萝莉.*?呦呦.*?',
            r'幼幼.*?白虎.*?',
            r'海角.*?乱伦.*?',
            r'18AV.*?',
            r'Xvideos.*?破解.*?',
            r'91.*?视频.*?',
            r'JVID.*?大陆.*?',
            r'爱威奶.*?破解.*?',
            r'永利.*?皇宫.*?',
            r'抖阴.*?破解.*?',
            r'杏吧.*?app.*?',
            r'外网.*?天堂.*?',
            r'免费.*?VPN.*?',
            r'免费.*?AV.*?',
            r'免费.*?微密圈.*?',
            r'51.*?萝莉.*?',
            r'51.*?约妹.*?',
            r'51.*?选妃.*?',
            r'51.*?免费.*?破解.*?',
            r'彩虹.*?星球.*?',
            r'好色.*?先生.*?',
            r'抖音.*?Max.*?',
            r'Pornhub.*?',
            r'成人.*?版.*?快手.*?',
            r'TikTok.*?成人.*?版.*?',
            r'91.*?破解.*?版.*?',
            r'小马.*?拉大车.*?',
            r'茶馆.*?约妹儿.*?',
            r'51.*?污漫.*?',
            r'AI.*?脱衣.*?换脸.*?',
            r'暗网.*?禁区.*?',
            r'草榴.*?app.*?',
            r'91.*?全能.*?版.*?',
            r'YouTube.*?成人.*?版.*?',
            r'缅北.*?禁地.*?',
            r'创作.*?不易.*?',
            r'麻烦.*?多多.*?分享.*?',
            r'您的.*?支持.*?是.*?前进.*?动力.*?',
            r'发邮件.*?获取.*?最新.*?地址.*?',
            r'长按.*?复制.*?',
            r'欢迎.*?加入.*?.*?讨论.*?群.*?',
            r'关注.*?邮箱.*?回家.*?不迷路.*?',
            r'扫描.*?二维码.*?获取.*?最新.*?链接.*?',
            r'该文章.*?由.*?发布.*?',
            r'转载请注明.*?来源.*?',
            r'任何.*?媒体.*?网站.*?或个人.*?未经.*?授权.*?不得.*?复制.*?转载.*?摘编.*?或以.*?其他.*?方式.*?使用.*?',
            r'否则.*?将.*?依法.*?追究.*?其.*?法律.*?责任.*?',
            r'重磅.*?热瓜.*?',
            r'顶流.*?女星.*?',
            r'温馨提示.*?',
            r'请.*?广大.*?瓜友.*?复制.*?保存.*?官方.*?地址.*?',
            r'牢记.*?并.*?添加.*?收藏夹.*?',
            r'谨防.*?假冒.*?',
            r'随时.*?欢迎.*?您.*?回家.*?',
            r'点击.*?下载.*?.*?回家的路.*?PDF.*?',
            r'免费.*?吃瓜.*?每日.*?更新.*?',
            r'51.*?福利.*?导航.*?',
            r'重要.*?提示.*?',
            r'复制.*?网址.*?用.*?浏览器.*?打开.*?',
            r'商务.*?合作.*?',
            r'往期.*?内容.*?',
            r'常见.*?问题.*?',
            r'投稿.*?方式.*?',
            r'回家的路.*?',
            r'51.*?吃瓜.*?一直.*?致力于.*?免费.*?为.*?广大.*?瓜友.*?提供.*?最.*?优质.*?的.*?吃瓜.*?内容.*?',
            r'欢迎.*?分享.*?给.*?你的.*?小伙伴.*?们.*?',
            r'51.*?吃瓜.*?网.*?永久.*?地址.*?',
            r'需.*?翻墙.*?访问.*?',
            r'Copyright.*?.*?保留.*?所有.*?权利.*?',
            r'Powered.*?by.*?',
            r'All.*?Rights.*?Reserved.*?',
            r'京ICP.*?备.*?',
            r'京公网.*?安备.*?',
            r'18\+.*?',
            r'新闻.*?时间线.*?',
            r'新闻.*?时间线.*?快报.*?',
            r'即时.*?新闻.*?',
            r'更多.*?',
            r'阅读.*?下一篇.*?',
            r'下一篇.*?已.*?是.*?最新.*?一.*?篇.*?文章.*?',
            r'热文.*?排行榜.*?',
            r'三天.*?',
            r'一周.*?',
            r'立即.*?注册.*?.*?网.*?每日.*?新闻.*?简报.*?',
            r'查看更多.*?',
            r'您.*?查看.*?的.*?内容.*?可能.*?不完整.*?',
            r'部分.*?内容.*?和.*?推荐.*?被.*?拦截.*?',
            r'请.*?对.*?本站.*?关闭.*?广告.*?拦截.*?和.*?阅读.*?模式.*?',
            r'或.*?使用.*?自带.*?浏览器.*?后.*?恢复.*?正常.*?',
            r'热度.*?加载中.*?',
            r'更多.*?内容.*?访问.*?',
            r'专栏.*?',
            r'您.*?可能.*?还.*?喜欢.*?',
            r'相关.*?文章.*?',
            r'推荐.*?阅读.*?',
            r'热门.*?推荐.*?',
            r'最新.*?推荐.*?',
            r'编辑.*?推荐.*?',
            r'小编.*?推荐.*?',
            r'精彩.*?推荐.*?',
            r'必读.*?推荐.*?',
            r'精选.*?推荐.*?',
            r'热门.*?话题.*?',
            r'最新.*?话题.*?',
            r'热门.*?标签.*?',
            r'最新.*?标签.*?',
            r'相关.*?标签.*?',
            r'热门.*?搜索.*?',
            r'最新.*?搜索.*?',
            r'搜索.*?历史.*?',
            r'搜索.*?建议.*?',
            r'搜索.*?推荐.*?',
            r'搜索.*?热门.*?',
            r'搜索.*?排行.*?',
            r'搜索.*?榜单.*?',
            r'搜索.*?趋势.*?',
            r'搜索.*?统计.*?',
            r'搜索.*?分析.*?',
            r'搜索.*?报告.*?',
            r'搜索.*?数据.*?',
            r'搜索.*?结果.*?',
            r'搜索.*?排名.*?',
            r'搜索.*?优化.*?',
            r'搜索.*?推广.*?',
            r'搜索.*?营销.*?',
            r'搜索.*?广告.*?',
            r'搜索.*?竞价.*?',
            r'搜索.*?投放.*?',
            r'搜索.*?策略.*?',
            r'搜索.*?方案.*?',
            r'搜索.*?计划.*?',
            r'搜索.*?预算.*?',
            r'搜索.*?成本.*?',
            r'搜索.*?效果.*?',
            r'搜索.*?转化.*?',
            r'搜索.*?ROI.*?',
            r'搜索.*?KPI.*?',
            r'搜索.*?指标.*?',
            r'搜索.*?监控.*?',
            r'搜索.*?跟踪.*?',
            r'搜索.*?统计.*?',
            r'搜索.*?分析.*?',
            r'搜索.*?报告.*?',
            r'搜索.*?数据.*?',
            r'搜索.*?洞察.*?',
            r'搜索.*?趋势.*?',
            r'搜索.*?预测.*?',
            r'搜索.*?建议.*?',
            r'搜索.*?优化.*?',
            r'搜索.*?改进.*?',
            r'搜索.*?提升.*?',
            r'搜索.*?增强.*?',
            r'搜索.*?升级.*?',
            r'搜索.*?更新.*?',
            r'搜索.*?维护.*?',
            r'搜索.*?管理.*?',
            r'搜索.*?运营.*?',
            r'搜索.*?执行.*?',
            r'搜索.*?实施.*?',
            r'搜索.*?部署.*?',
            r'搜索.*?配置.*?',
            r'搜索.*?设置.*?',
            r'搜索.*?参数.*?',
            r'搜索.*?选项.*?',
            r'搜索.*?功能.*?',
            r'搜索.*?特性.*?',
            r'搜索.*?优势.*?',
            r'搜索.*?亮点.*?',
            r'搜索.*?特色.*?',
            r'搜索.*?卖点.*?',
            r'搜索.*?价值.*?',
            r'搜索.*?收益.*?',
            r'搜索.*?利润.*?',
            r'搜索.*?回报.*?',
            r'搜索.*?效益.*?',
            r'搜索.*?效果.*?',
            r'搜索.*?成果.*?',
            r'搜索.*?成就.*?',
            r'搜索.*?成功.*?',
            r'搜索.*?胜利.*?',
            r'搜索.*?获胜.*?',
            r'搜索.*?赢得.*?',
            r'搜索.*?获得.*?',
            r'搜索.*?取得.*?',
            r'搜索.*?实现.*?',
            r'搜索.*?达成.*?',
            r'搜索.*?完成.*?',
            r'搜索.*?结束.*?',
            r'搜索.*?终止.*?',
            r'搜索.*?停止.*?',
            r'搜索.*?暂停.*?',
            r'搜索.*?中断.*?',
            r'搜索.*?取消.*?',
            r'搜索.*?撤销.*?',
            r'搜索.*?回退.*?',
            r'搜索.*?恢复.*?',
            r'搜索.*?重启.*?',
            r'搜索.*?重新.*?开始.*?',
            r'搜索.*?重新.*?启动.*?',
            r'搜索.*?重新.*?运行.*?',
            r'搜索.*?重新.*?执行.*?',
            r'搜索.*?重新.*?实施.*?',
            r'搜索.*?重新.*?部署.*?',
            r'搜索.*?重新.*?配置.*?',
            r'搜索.*?重新.*?设置.*?',
            r'搜索.*?重新.*?调整.*?',
            r'搜索.*?重新.*?优化.*?',
            r'搜索.*?重新.*?改进.*?',
            r'搜索.*?重新.*?提升.*?',
            r'搜索.*?重新.*?增强.*?',
            r'搜索.*?重新.*?升级.*?',
            r'搜索.*?重新.*?更新.*?',
            r'搜索.*?重新.*?维护.*?',
            r'搜索.*?重新.*?管理.*?',
            r'搜索.*?重新.*?运营.*?',
            r'搜索.*?重新.*?执行.*?',
            r'搜索.*?重新.*?实施.*?',
            r'搜索.*?重新.*?部署.*?',
            r'搜索.*?重新.*?配置.*?',
            r'搜索.*?重新.*?设置.*?',
            r'搜索.*?重新.*?调整.*?',
            r'搜索.*?重新.*?优化.*?',
            r'搜索.*?重新.*?改进.*?',
            r'搜索.*?重新.*?提升.*?',
            r'搜索.*?重新.*?增强.*?',
            r'搜索.*?重新.*?升级.*?',
            r'搜索.*?重新.*?更新.*?',
            r'搜索.*?重新.*?维护.*?',
            r'搜索.*?重新.*?管理.*?',
            r'搜索.*?重新.*?运营.*?',
        ]
        
        for pattern in useless_patterns:
            para = re.sub(pattern, '', para, flags=re.IGNORECASE)
        
        # 清理多余的空白字符
        para = re.sub(r'\s+', ' ', para)
        para = para.strip()
        
        return para
    
    def _extract_article_content(self, html_content: str) -> str:
        """智能提取文章核心内容，移除所有无用信息"""
        if not html_content:
            return ""
        
        # 第一步：移除所有明显的无用内容
        html_content = self._remove_junk_content(html_content)
        
        # 第二步：直接提取所有段落内容
        paragraphs = re.findall(r'<p[^>]*>(.*?)</p>', html_content, re.DOTALL | re.IGNORECASE)
        
        if paragraphs:
            # 合并所有段落
            all_content = '\n\n'.join(paragraphs)
            # 清理内容
            cleaned_content = self._clean_main_content(all_content)
            return cleaned_content
        
        # 如果没有段落，尝试提取div内容
        divs = re.findall(r'<div[^>]*>(.*?)</div>', html_content, re.DOTALL | re.IGNORECASE)
        if divs:
            # 选择最长的div内容
            main_div = max(divs, key=len)
            if len(main_div) > 200:
                cleaned_content = self._clean_main_content(main_div)
                return cleaned_content
        
        # 如果都找不到，使用基础清理
        return self._basic_clean(html_content)
    
    def _remove_junk_content(self, html_content: str) -> str:
        """移除所有无用的HTML内容"""
        # 移除script、style、注释
        html_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        html_content = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        html_content = re.sub(r'<!--.*?-->', '', html_content, flags=re.DOTALL)
        
        # 移除导航、头部、底部、侧边栏
        junk_patterns = [
            r'<nav[^>]*>.*?</nav>',
            r'<header[^>]*>.*?</header>',
            r'<footer[^>]*>.*?</footer>',
            r'<aside[^>]*>.*?</aside>',
            # 移除包含特定class或id的div
            r'<div[^>]*(?:class|id)="[^"]*(?:nav|menu|header|footer|sidebar|ad|banner|advertisement|related|hot|comment|share|author|time|tag|copyright|social|follow|subscribe)[^"]*"[^>]*>.*?</div>',
            # 移除包含特定class或id的section
            r'<section[^>]*(?:class|id)="[^"]*(?:nav|menu|header|footer|sidebar|ad|banner|advertisement|related|hot|comment|share|author|time|tag|copyright|social|follow|subscribe)[^"]*"[^>]*>.*?</section>',
            # 移除包含特定class或id的article
            r'<article[^>]*(?:class|id)="[^"]*(?:nav|menu|header|footer|sidebar|ad|banner|advertisement|related|hot|comment|share|author|time|tag|copyright|social|follow|subscribe)[^"]*"[^>]*>.*?</article>',
        ]
        
        for pattern in junk_patterns:
            html_content = re.sub(pattern, '', html_content, flags=re.DOTALL | re.IGNORECASE)
        
        return html_content
    
    def _find_main_content_area(self, html_content: str) -> str:
        """找到文章的主要内容区域"""
        # 尝试多种策略找到主要内容
        
        # 策略1：寻找包含文章标题的区域
        title_patterns = [
            r'<h1[^>]*>(.*?)</h1>',
            r'<h2[^>]*>(.*?)</h2>',
            r'<title[^>]*>(.*?)</title>',
        ]
        
        for pattern in title_patterns:
            matches = re.findall(pattern, html_content, re.DOTALL | re.IGNORECASE)
            if matches:
                title = matches[0].strip()
                clean_title = re.sub(r'<[^>]+>', '', title)
                clean_title = re.sub(r'\s+', ' ', clean_title).strip()
                
                if len(clean_title) > 10:  # 确保标题有意义
                    # 寻找包含标题的段落
                    title_context_pattern = rf'<p[^>]*>.*?{re.escape(clean_title[:20])}.*?</p>'
                    title_context = re.search(title_context_pattern, html_content, re.DOTALL | re.IGNORECASE)
                    if title_context:
                        start_pos = title_context.start()
                        return html_content[start_pos:]
        
        # 策略2：寻找包含大量中文文本的段落
        chinese_text_patterns = [
            r'<p[^>]*>.*?[\u4e00-\u9fff].*?[\u4e00-\u9fff].*?[\u4e00-\u9fff].*?[\u4e00-\u9fff].*?</p>',
            r'<div[^>]*>.*?[\u4e00-\u9fff].*?[\u4e00-\u9fff].*?[\u4e00-\u9fff].*?[\u4e00-\u9fff].*?</div>',
        ]
        
        for pattern in chinese_text_patterns:
            matches = re.findall(pattern, html_content, re.DOTALL | re.IGNORECASE)
            if matches:
                # 选择最长的匹配内容
                main_content = max(matches, key=len)
                if len(main_content) > 500:  # 确保内容足够长
                    return main_content
        
        # 策略3：寻找article标签
        article_match = re.search(r'<article[^>]*>(.*?)</article>', html_content, re.DOTALL | re.IGNORECASE)
        if article_match:
            return article_match.group(1)
        
        # 策略4：寻找main标签
        main_match = re.search(r'<main[^>]*>(.*?)</main>', html_content, re.DOTALL | re.IGNORECASE)
        if main_match:
            return main_match.group(1)
        
        return ""
    
    def _clean_main_content(self, content: str) -> str:
        """清理主要内容，提取纯文本"""
        # 移除所有HTML标签
        content = re.sub(r'<[^>]+>', '', content)
        
        # 清理多余的空白字符
        content = re.sub(r'\s+', ' ', content)
        content = re.sub(r'\n\s*\n', '\n\n', content)
        
        # 移除明显的无用文本（更精确的匹配）
        useless_patterns = [
            r'点击.*?查看.*?',
            r'阅读.*?更多.*?',
            r'相关.*?推荐.*?',
            r'热门.*?文章.*?',
            r'广告.*?投放.*?',
            r'版权.*?所有.*?',
            r'未经.*?许可.*?',
            r'违者.*?必究.*?',
            r'读者.*?热线.*?',
            r'特别.*?提醒.*?',
            r'如需.*?转载.*?',
            r'联系我们.*?',
            r'意见反馈.*?',
            r'网站.*?声明.*?',
            r'隐私.*?政策.*?',
            r'服务.*?条款.*?',
            r'关于.*?我们.*?',
            r'加入.*?我们.*?',
            r'友情.*?链接.*?',
            r'关注.*?我们.*?',
            r'分享.*?好友.*?',
            r'生成.*?海报.*?',
            r'保存.*?图片.*?',
            r'下载.*?APP.*?',
            r'扫码.*?关注.*?',
            r'微信.*?公众号.*?',
            r'微博.*?关注.*?',
            r'QQ.*?空间.*?',
            r'新浪.*?微博.*?',
            r'腾讯.*?微博.*?',
            r'人人.*?网.*?',
            r'开心.*?网.*?',
            r'豆瓣.*?网.*?',
            r'知乎.*?网.*?',
            r'贴吧.*?网.*?',
            r'论坛.*?网.*?',
            r'社区.*?网.*?',
            r'博客.*?网.*?',
            r'空间.*?网.*?',
            r'相册.*?网.*?',
            r'视频.*?网.*?',
            r'音乐.*?网.*?',
            r'游戏.*?网.*?',
            r'购物.*?网.*?',
            r'团购.*?网.*?',
            r'优惠.*?券.*?',
            r'折扣.*?信息.*?',
            r'促销.*?活动.*?',
            r'限时.*?特价.*?',
            r'秒杀.*?活动.*?',
            r'抢购.*?活动.*?',
            r'免费.*?试用.*?',
            r'免费.*?体验.*?',
            r'免费.*?领取.*?',
            r'免费.*?下载.*?',
            r'免费.*?注册.*?',
            r'免费.*?开通.*?',
            r'免费.*?申请.*?',
            r'免费.*?预约.*?',
            r'免费.*?咨询.*?',
            r'免费.*?服务.*?',
            r'免费.*?支持.*?',
            r'免费.*?帮助.*?',
            r'免费.*?指导.*?',
            r'免费.*?培训.*?',
            r'免费.*?学习.*?',
            r'免费.*?教育.*?',
            r'免费.*?课程.*?',
            r'免费.*?讲座.*?',
            r'免费.*?会议.*?',
            r'免费.*?活动.*?',
            r'免费.*?参与.*?',
            r'免费.*?加入.*?',
            r'免费.*?成为.*?',
            r'免费.*?获得.*?',
            r'免费.*?得到.*?',
            r'免费.*?享受.*?',
            r'免费.*?使用.*?',
        ]
        
        for pattern in useless_patterns:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE)
        
        # 清理多余的空白字符
        content = re.sub(r'\s+', ' ', content)
        content = content.strip()
        
        return content
    
    def _filter_relevant_results(self, query: str, results: list) -> list:
        """过滤相关性搜索结果"""
        if not results:
            return []
        
        # 提取查询关键词
        query_keywords = self._extract_keywords(query)
        filtered_results = []
        
        for result in results:
            title = result.get('title', '')
            content = result.get('content', '')
            
            # 计算相关性得分
            relevance_score = self._calculate_relevance_score(query_keywords, title, content)
            
            # 只保留相关性得分大于阈值的结果
            if relevance_score > 0.1:  # 降低阈值，保留更多相关结果
                filtered_results.append(result)
        
        # 按相关性得分排序
        filtered_results.sort(key=lambda x: self._calculate_relevance_score(
            query_keywords, 
            x.get('title', ''), 
            x.get('content', '')
        ), reverse=True)
        
        return filtered_results
    
    def _extract_keywords(self, query: str) -> list:
        """提取查询关键词"""
        # 移除标点符号，分割成词汇
        import re
        words = re.findall(r'[\u4e00-\u9fff\w]+', query.lower())
        
        # 过滤掉常见的停用词
        stop_words = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'}
        keywords = [word for word in words if word not in stop_words and len(word) > 1]
        
        return keywords
    
    def _calculate_relevance_score(self, query_keywords: list, title: str, content: str) -> float:
        """计算相关性得分"""
        if not query_keywords:
            return 0.0
        
        title_lower = title.lower()
        content_lower = content.lower()
        
        score = 0.0
        
        for keyword in query_keywords:
            # 标题匹配权重更高
            if keyword in title_lower:
                score += 2.0
            # 内容匹配权重较低
            if keyword in content_lower:
                score += 1.0
        
        # 归一化得分
        max_possible_score = len(query_keywords) * 3.0  # 标题2分 + 内容1分
        if max_possible_score > 0:
            score = score / max_possible_score
        
        return score
    
    def _basic_clean(self, html_content: str) -> str:
        """基础HTML清理"""
        # 移除常见的无用标签和内容
        patterns_to_remove = [
            # 移除script标签
            r'<script[^>]*>.*?</script>',
            # 移除style标签
            r'<style[^>]*>.*?</style>',
            # 移除注释
            r'<!--.*?-->',
            # 移除导航相关
            r'<nav[^>]*>.*?</nav>',
            # 移除header标签
            r'<header[^>]*>.*?</header>',
            # 移除footer标签
            r'<footer[^>]*>.*?</footer>',
            # 移除aside标签
            r'<aside[^>]*>.*?</aside>',
            # 移除广告相关
            r'<div[^>]*class="[^"]*ad[^"]*"[^>]*>.*?</div>',
            r'<div[^>]*id="[^"]*ad[^"]*"[^>]*>.*?</div>',
            # 移除侧边栏
            r'<div[^>]*class="[^"]*sidebar[^"]*"[^>]*>.*?</div>',
            r'<div[^>]*id="[^"]*sidebar[^"]*"[^>]*>.*?</div>',
            # 移除导航菜单
            r'<div[^>]*class="[^"]*nav[^"]*"[^>]*>.*?</div>',
            r'<div[^>]*id="[^"]*nav[^"]*"[^>]*>.*?</div>',
            # 移除页脚相关
            r'<div[^>]*class="[^"]*footer[^"]*"[^>]*>.*?</div>',
            r'<div[^>]*id="[^"]*footer[^"]*"[^>]*>.*?</div>',
            # 移除版权信息
            r'<div[^>]*class="[^"]*copyright[^"]*"[^>]*>.*?</div>',
            r'<div[^>]*id="[^"]*copyright[^"]*"[^>]*>.*?</div>',
            # 移除相关文章推荐
            r'<div[^>]*class="[^"]*related[^"]*"[^>]*>.*?</div>',
            r'<div[^>]*id="[^"]*related[^"]*"[^>]*>.*?</div>',
            # 移除热门文章
            r'<div[^>]*class="[^"]*hot[^"]*"[^>]*>.*?</div>',
            r'<div[^>]*id="[^"]*hot[^"]*"[^>]*>.*?</div>',
            # 移除评论区域
            r'<div[^>]*class="[^"]*comment[^"]*"[^>]*>.*?</div>',
            r'<div[^>]*id="[^"]*comment[^"]*"[^>]*>.*?</div>',
            # 移除分享按钮
            r'<div[^>]*class="[^"]*share[^"]*"[^>]*>.*?</div>',
            r'<div[^>]*id="[^"]*share[^"]*"[^>]*>.*?</div>',
            # 移除作者信息
            r'<div[^>]*class="[^"]*author[^"]*"[^>]*>.*?</div>',
            r'<div[^>]*id="[^"]*author[^"]*"[^>]*>.*?</div>',
            # 移除时间信息
            r'<div[^>]*class="[^"]*time[^"]*"[^>]*>.*?</div>',
            r'<div[^>]*id="[^"]*time[^"]*"[^>]*>.*?</div>',
            # 移除标签信息
            r'<div[^>]*class="[^"]*tag[^"]*"[^>]*>.*?</div>',
            r'<div[^>]*id="[^"]*tag[^"]*"[^>]*>.*?</div>',
        ]
        
        cleaned_content = html_content
        for pattern in patterns_to_remove:
            cleaned_content = re.sub(pattern, '', cleaned_content, flags=re.DOTALL | re.IGNORECASE)
        
        # 移除多余的空白行
        cleaned_content = re.sub(r'\n\s*\n', '\n\n', cleaned_content)
        
        # 移除HTML标签，保留文本内容
        cleaned_content = re.sub(r'<[^>]+>', '', cleaned_content)
        
        # 清理多余的空白字符
        cleaned_content = re.sub(r'\s+', ' ', cleaned_content)
        cleaned_content = cleaned_content.strip()
        
        return cleaned_content
        
    def _get_conda_env_var(self, var_name: str) -> str:
        """获取conda环境变量"""
        try:
            # 方法1: 直接从当前环境获取
            env_var = os.getenv(var_name)
            if env_var:
                return env_var
            
            # 方法2: 通过conda命令获取当前环境的变量
            result = subprocess.run(
                ['conda', 'env', 'config', 'vars', 'list'],
                capture_output=True,
                text=True,
                shell=True
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if '=' in line:
                        key, value = line.split('=', 1)
                        if key.strip() == var_name:
                            return value.strip()
            
            # 方法3: 尝试从conda info获取环境路径
            result = subprocess.run(
                ['conda', 'info', '--envs'],
                capture_output=True,
                text=True,
                shell=True
            )
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if '*' in line and 'AIOS2' in line:
                        # 找到当前激活的环境
                        env_path = line.split()[-1]
                        env_file = os.path.join(env_path, 'etc', 'conda', 'env_vars.sh')
                        if os.path.exists(env_file):
                            with open(env_file, 'r') as f:
                                for env_line in f:
                                    if env_line.startswith(f'export {var_name}='):
                                        return env_line.split('=', 1)[1].strip().strip('"')
            
            return None
            
        except Exception as e:
            print(f"获取conda环境变量失败: {e}")
            return None
        
    def run(self, params: Dict[str, Any]) -> str:
        """运行web搜索工具，使用Tavily API进行搜索"""
        try:
            # 获取API密钥 - 优先从环境变量获取，然后尝试conda环境变量
            api_key = os.getenv('TAVILY_API_KEY')
            if not api_key:
                api_key = self._get_conda_env_var('TAVILY_API_KEY')
            
            if not api_key:
                return "错误：未设置TAVILY_API_KEY环境变量，请先设置环境变量"
            
            # 获取搜索参数
            query = params.get('query', '')
            max_results = params.get('max_results', 5)
            
            # 添加时间戳来绕过缓存
            import time
            query_with_timestamp = f"{query} {int(time.time())}"
            
            if not query:
                return "错误：请提供搜索查询内容"
            
            response = self._perform_tavily_search(
                api_key=api_key,
                query=query_with_timestamp,
                max_results=max_results,
            )
            if isinstance(response, str):
                return response
            
            # 格式化搜索结果
            results = []
            results.append(f"🔍 搜索查询: {query}")
            
            # 添加知识图谱答案（如果有）
            if response.get('answer'):
                results.append(f"\n💡 知识图谱答案:\n{response['answer']}")
            
            # 暂时禁用相关性过滤，先测试内容清理效果
            if response.get('results'):
                # filtered_results = self._filter_relevant_results(query, response['results'])
                # results.append(f"📊 返回结果数量: {len(response['results'])} (过滤后: {len(filtered_results)})")
                results.append(f"📊 返回结果数量: {len(response['results'])}")
                
                # 添加搜索结果
                results.append(f"\n📋 搜索结果:")
                for i, result in enumerate(response['results'][:max_results], 1):
                    title = result.get('title', '无标题')
                    url = result.get('url', '无链接')
                    content = result.get('content', '无内容')
                    raw_content = result.get('raw_content', '')  # 获取原始完整内容
                    
                    results.append(f"\n【结果 {i}】")
                    results.append(f"标题: {title}")
                    results.append(f"链接: {url}")
                    results.append(f"内容摘要: {content}")
                    
                    # 如果有原始完整内容，清理后显示
                    if raw_content and raw_content != content:
                        cleaned_content = self._clean_html_content(raw_content)
                        results.append(f"\n📄 清理后的核心内容:")
                        results.append(f"{cleaned_content}")
                    else:
                        # 如果没有raw_content，清理content后显示
                        cleaned_content = self._clean_html_content(content)
                        results.append(f"\n📄 清理后的内容:")
                        results.append(f"{cleaned_content}")
            else:
                results.append("\n❌ 未找到相关搜索结果")
            
            return "\n".join(results)
            
        except Exception as e:
            return f"搜索失败: {str(e)}"

    def _perform_tavily_search(
        self,
        *,
        api_key: str,
        query: str,
        max_results: int,
    ) -> Dict[str, Any] | str:
        """在独立子进程中执行 Tavily 调用，避免单条 query 无限阻塞整轮 workflow。"""
        script = """
import json
import os
from tavily import TavilyClient

client = TavilyClient(os.environ["TAVILY_API_KEY"])
response = client.search(
    query=os.environ["TAVILY_QUERY"],
    max_results=int(os.environ["TAVILY_MAX_RESULTS"]),
    include_answer=True,
    include_raw_content=True,
    search_depth="advanced",
    include_domains=[],
    exclude_domains=[],
    include_images=True,
)
print(json.dumps(response, ensure_ascii=False))
"""
        env = os.environ.copy()
        env["TAVILY_API_KEY"] = api_key
        env["TAVILY_QUERY"] = query
        env["TAVILY_MAX_RESULTS"] = str(max_results)

        try:
            result = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                text=True,
                env=env,
                timeout=self.search_timeout,
            )
        except subprocess.TimeoutExpired:
            return f"错误：Tavily 搜索超时（>{self.search_timeout}秒），已跳过该热点"

        if result.returncode != 0:
            stderr = (result.stderr or "").strip()
            if "No module named 'tavily'" in stderr:
                return "错误：未安装tavily库，请先运行: pip install tavily-python"
            return f"错误：Tavily 搜索失败: {stderr or '未知错误'}"

        stdout = (result.stdout or "").strip()
        if not stdout:
            return "错误：Tavily 搜索返回为空"

        try:
            return json.loads(stdout)
        except json.JSONDecodeError:
            return f"错误：Tavily 返回解析失败: {stdout[:200]}"

    def get_tool_call_format(self):
        tool_call_format = {
            "type": "function",
            "function": {
                "name": "owen/web_search",
                "description": "使用Tavily API进行网络搜索，传入API密钥和搜索查询，返回搜索结果",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "要搜索的查询内容"
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "最大返回结果数量，默认5",
                            "default": 5,
                            "minimum": 1,
                            "maximum": 10
                        }
                    },
                    "required": [
                        "query"
                    ]
                }
            }
        }
        return tool_call_format 
