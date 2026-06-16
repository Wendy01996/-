#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TRINX 千里达 新闻爬虫脚本
自动收集全球新闻和 RSS 源信息
"""

import os
import json
import smtplib
import re
from datetime import datetime, timezone, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict
import feedparser
import requests
from urllib.parse import urlencode

# ============ 配置 ============

# 搜索关键词
KEYWORDS = ["TRINX", "千里达"]

# QQ 邮箱配置
QQ_EMAIL = "872366072@qq.com"
QQ_SMTP_SERVER = "smtp.qq.com"
QQ_SMTP_PORT = 587

# Google News API (免费 RSS)
GOOGLE_NEWS_BASE = "https://news.google.com/rss/search"

# RSS 源列表（常见摩托车/赛车新闻源）
RSS_SOURCES = [
    {
        "name": "BBC News",
        "url": "http://feeds.bbc.co.uk/news/rss.xml"
    },
    {
        "name": "Reuters",
        "url": "https://www.reutersagency.com/feed/?taxonomy=best-topics&output=rss"
    },
    {
        "name": "Motor Sports News",
        "url": "https://www.motorsport.com/rss/feed/all/"
    },
    {
        "name": "Cycling News",
        "url": "https://www.cyclingnews.com/news/feed/"
    }
]

# 需要过滤的敏感词
BLOCKED_KEYWORDS = ["virus", "crack", "hack", "malware", "porn", "sex"]


class TrinxScraper:
    """TRINX 千里达 信息爬虫"""
    
    def __init__(self):
        self.articles = []
        self.error_log = []
    
    def clean_text(self, text: str) -> str:
        """清理和规范化文本"""
        if not text:
            return ""
        
        # 移除 HTML 标签
        text = re.sub(r'<[^>]+>', '', text)
        # 移除特殊字符和控制符
        text = re.sub(r'[\x00-\x08\x0B-\x0C\x0E-\x1F\x7F]', '', text)
        # 规范化空格
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    
    def is_safe_content(self, title: str, summary: str) -> bool:
        """检查内容是否安全（不包含敏感词）"""
        content = (title + " " + summary).lower()
        for keyword in BLOCKED_KEYWORDS:
            if keyword in content:
                return False
        return True
        
    def scrape_google_news(self) -> List[Dict]:
        """从 Google News 爬取数据"""
        print("[Google News] 开始爬取...")
        articles = []
        
        for keyword in KEYWORDS:
            try:
                # Google News RSS 搜索
                params = {"q": keyword, "hl": "zh-CN", "gl": "CN"}
                url = f"{GOOGLE_NEWS_BASE}?{urlencode(params)}"
                
                print(f"  搜索关键词: {keyword}")
                print(f"  URL: {url}")
                
                response = requests.get(url, timeout=10)
                response.encoding = 'utf-8'
                
                feed = feedparser.parse(response.content)
                
                if feed.entries:
                    print(f"  找到 {len(feed.entries)} 条结果")
                    for entry in feed.entries[:10]:  # 限制每个关键词 10 条
                        title = self.clean_text(entry.get("title", "无标题"))
                        summary = self.clean_text(entry.get("summary", "")[:200])
                        
                        # 检查内容安全性
                        if not self.is_safe_content(title, summary):
                            continue
                        
                        article = {
                            "title": title,
                            "link": entry.get("link", ""),
                            "source": "Google News",
                            "keyword": keyword,
                            "published": entry.get("published", ""),
                            "summary": summary
                        }
                        articles.append(article)
                else:
                    print(f"  未找到结果")
                    
            except Exception as e:
                error_msg = f"Google News 爬取失败 ({keyword}): {str(e)}"
                print(f"  ❌ {error_msg}")
                self.error_log.append(error_msg)
        
        print(f"[Google News] 完成，共 {len(articles)} 条\n")
        return articles
    
    def scrape_rss_feeds(self) -> List[Dict]:
        """从 RSS 源爬取数据"""
        print("[RSS Feeds] 开始爬取...")
        articles = []
        
        for source in RSS_SOURCES:
            try:
                print(f"  爬取: {source['name']}")
                response = requests.get(source['url'], timeout=10)
                feed = feedparser.parse(response.content)
                
                if feed.entries:
                    for entry in feed.entries[:5]:  # 每个源限制 5 条
                        # 检查是否包含关键词
                        title = self.clean_text(entry.get("title", "").lower())
                        summary = self.clean_text(entry.get("summary", "").lower())
                        
                        # 检查内容安全性
                        if not self.is_safe_content(title, summary):
                            continue
                        
                        if any(kw.lower() in title or kw.lower() in summary for kw in KEYWORDS):
                            article = {
                                "title": self.clean_text(entry.get("title", "无标题")),
                                "link": entry.get("link", ""),
                                "source": source['name'],
                                "keyword": next((kw for kw in KEYWORDS if kw.lower() in title or kw.lower() in summary), ""),
                                "published": entry.get("published", ""),
                                "summary": self.clean_text(entry.get("summary", "")[:200])
                            }
                            articles.append(article)
                            print(f"    ✓ {article['title'][:60]}")
                
            except Exception as e:
                error_msg = f"RSS 爬取失败 ({source['name']}): {str(e)}"
                print(f"    ❌ {error_msg}")
                self.error_log.append(error_msg)
        
        print(f"[RSS Feeds] 完成，共 {len(articles)} 条\n")
        return articles
    
    def run(self) -> List[Dict]:
        """运行所有爬虫"""
        print("=" * 60)
        print("TRINX 千里达 新闻爬虫")
        print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60 + "\n")
        
        # 爬取数据
        google_articles = self.scrape_google_news()
        rss_articles = self.scrape_rss_feeds()
        
        # 合并并去重
        all_articles = google_articles + rss_articles
        self.articles = self.deduplicate(all_articles)
        
        print(f"总计收集: {len(self.articles)} 条独特新闻\n")
        
        return self.articles
    
    @staticmethod
    def deduplicate(articles: List[Dict]) -> List[Dict]:
        """去重"""
        seen_titles = set()
        unique = []
        for article in articles:
            title_hash = article["title"].lower()
            if title_hash not in seen_titles:
                seen_titles.add(title_hash)
                unique.append(article)
        return unique


class EmailSender:
    """邮件发送器"""
    
    def __init__(self, sender_email: str, app_password: str):
        self.sender_email = sender_email
        self.app_password = app_password
    
    def generate_html_email(self, articles: List[Dict], error_log: List[str]) -> str:
        """生成 HTML 邮件内容"""
        
        html = f"""
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: 'Microsoft YaHei', Arial, sans-serif; color: #333; }}
                .container {{ max-width: 800px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                           color: white; padding: 20px; border-radius: 10px; text-align: center; }}
                .header h1 {{ margin: 0; font-size: 24px; }}
                .date {{ font-size: 14px; opacity: 0.9; }}
                .article {{ background: #f9f9f9; border-left: 4px solid #667eea; 
                           padding: 15px; margin: 15px 0; border-radius: 5px; }}
                .article-title {{ font-size: 16px; font-weight: bold; color: #333; margin: 0 0 10px 0; }}
                .article-meta {{ font-size: 12px; color: #999; margin: 5px 0; }}
                .article-source {{ display: inline-block; background: #667eea; color: white; 
                                 padding: 2px 8px; border-radius: 3px; font-size: 12px; }}
                .article-link {{ color: #667eea; text-decoration: none; }}
                .article-summary {{ font-size: 14px; color: #666; margin-top: 10px; line-height: 1.6; }}
                .empty {{ text-align: center; color: #999; padding: 20px; }}
                .error-section {{ background: #ffe6e6; border-left: 4px solid #ff6b6b; 
                                padding: 15px; margin: 20px 0; border-radius: 5px; }}
                .error-title {{ color: #ff6b6b; font-weight: bold; margin: 0 0 10px 0; }}
                .footer {{ text-align: center; font-size: 12px; color: #999; 
                         margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🏍️ TRINX 千里达 日报</h1>
                    <div class="date">{datetime.now(timezone.utc).strftime('%Y年%m月%d日')}</div>
                </div>
                
                <div style="margin: 20px 0;">
                    <p>早上好！📰 这是您今天的 TRINX 千里达 新闻精选。</p>
                </div>
        """
        
        if articles:
            for i, article in enumerate(articles, 1):
                html += f"""
                <div class="article">
                    <div class="article-title">{i}. {article.get('title', '无标题')}</div>
                    <div class="article-meta">
                        <span class="article-source">{article.get('source', '未知源')}</span>
                        <span style="margin-left: 10px; color: #999;">📅 {article.get('published', '时间未知')}</span>
                    </div>
                    <div class="article-summary">{article.get('summary', '')}</div>
                    <div style="margin-top: 10px;">
                        <a href="{article.get('link', '#')}" class="article-link">👉 阅读全文 →</a>
                    </div>
                </div>
                """
        else:
            html += '<div class="empty">暂无相关新闻 😴</div>'
        
        # 错误日志
        if error_log:
            html += '<div class="error-section"><div class="error-title">⚠️ 爬取错误日志</div>'
            for error in error_log:
                html += f'<div style="font-size: 12px; color: #d32f2f; margin: 5px 0;">{error}</div>'
            html += '</div>'
        
        html += f"""
                <div class="footer">
                    <p>此邮件由自动化脚本生成 | TRINX 千里达 新闻监测系统</p>
                    <p>下次更新: 明天 10:00 (UTC+8)</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def send_email(self, recipient_email: str, articles: List[Dict], error_log: List[str]) -> bool:
        """发送邮件"""
        try:
            print("[邮件] 正在准备邮件内容...")
            
            # 创建邮件
            message = MIMEMultipart("alternative")
            message["Subject"] = f"TRINX 千里达 日报 - {datetime.now().strftime('%Y年%m月%d日')}"
            message["From"] = self.sender_email
            message["To"] = recipient_email
            
            # HTML 内容
            html_content = self.generate_html_email(articles, error_log)
            html_part = MIMEText(html_content, "html", "utf-8")
            message.attach(html_part)
            
            # 发送邮件
            print(f"[邮件] 正在连接 SMTP 服务器...")
            with smtplib.SMTP(QQ_SMTP_SERVER, QQ_SMTP_PORT) as server:
                server.starttls()
                print(f"[邮件] 正在登录...")
                server.login(self.sender_email, self.app_password)
                print(f"[邮件] 正在发送到 {recipient_email}...")
                server.send_message(message)
            
            print(f"[邮件] ✅ 邮件发送成功！\n")
            return True
            
        except Exception as e:
            print(f"[邮件] ❌ 发送失败: {str(e)}\n")
            return False


def main():
    """主函数"""
    
    # 从环境变量获取 QQ 邮箱授权码
    # 需要在 GitHub Secrets 中设置 QQ_APP_PASSWORD
    qq_app_password = os.getenv("QQ_APP_PASSWORD", "")
    recipient_email = os.getenv("RECIPIENT_EMAIL", "872366072@qq.com")
    
    if not qq_app_password:
        print("❌ 错误: 未设置 QQ_APP_PASSWORD 环境变量")
        print("   请在 GitHub Secrets 中添加 QQ_APP_PASSWORD")
        return False
    
    # 运行爬虫
    scraper = TrinxScraper()
    articles = scraper.run()
    
    # 发送邮件
    sender = EmailSender(QQ_EMAIL, qq_app_password)
    success = sender.send_email(recipient_email, articles, scraper.error_log)
    
    if success:
        print("=" * 60)
        print("✅ 任务完成！")
        print("=" * 60)
        return True
    else:
        print("=" * 60)
        print("❌ 任务失败！")
        print("=" * 60)
        return False


if __name__ == "__main__":
    main()
