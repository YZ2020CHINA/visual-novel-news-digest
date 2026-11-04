#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视野日报 - 每日新闻自动生成系统
生成复古报纸风格的 HTML 页面
"""

import sys
import io
import feedparser
import os
import re
from datetime import datetime
from openai import OpenAI
import requests
from bs4 import BeautifulSoup
import random

# 修复 Windows 控制台编码问题
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ============= 新闻源配置 =============

NEWS_SOURCES = {
    '独立游戏与视觉小说': [
        'https://www.indiegames.com/feed/',
        'https://www.reddit.com/r/visualnovels/.rss',
        'https://blog.renpy.org/feeds/posts/default',
        'https://itch.io/games/newest/tag-visual-novel.rss',
    ],

    'AI与科技': [
        'https://www.technologyreview.com/feed/',
        'https://techcrunch.com/feed/',
        'https://www.theverge.com/rss/index.xml',
        'https://simonwillison.net/atom/everything/',
        'https://www.artificialintelligence-news.com/feed/',
    ],

    '文化艺术': [
        'https://www.artnews.com/feed/',
        'https://hyperallergic.com/feed/',
        'https://www.creativebloq.com/feed',
    ],

    '社会与文化': [
        'https://cn.nytimes.com/rss.html',
        'https://www.bbc.com/zhongwen/simp/index.xml',
    ],

    '宗教与意识形态': [
        'https://www.csmonitor.com/feeds/all',
        'https://aeon.co/feed.rss',
        'https://philosophynow.org/rss',
    ],
}


# ============= 工具函数 =============

def extract_image_from_url(url):
    """从网页中提取主图"""
    try:
        response = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        soup = BeautifulSoup(response.content, 'html.parser')

        # 尝试多种方式提取图片
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            return og_image['content']

        twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
        if twitter_image and twitter_image.get('content'):
            return twitter_image['content']

        # 找第一个大尺寸图片
        images = soup.find_all('img')
        for img in images:
            src = img.get('src', '')
            if src and any(x in src.lower() for x in ['.jpg', '.jpeg', '.png', '.webp']):
                if 'http' not in src:
                    src = requests.compat.urljoin(url, src)
                return src
    except:
        pass

    # 返回占位图
    return 'https://via.placeholder.com/800x600/f4f1eb/333333?text=视野日报'


def fetch_news():
    """抓取所有新闻源"""
    all_news = {}

    for category, feeds in NEWS_SOURCES.items():
        category_news = []

        for feed_url in feeds:
            try:
                feed = feedparser.parse(feed_url)
                for entry in feed.entries[:5]:  # 每个源取 5 条
                    news_item = {
                        'title': entry.title,
                        'link': entry.link,
                        'summary': entry.get('summary', entry.get('description', ''))[:800],  # 增加摘要长度
                        'published': entry.get('published', ''),
                        'image': extract_image_from_url(entry.link),  # 提取图片
                    }
                    category_news.append(news_item)

                print(f"✓ {category}: {feed_url}")
            except Exception as e:
                print(f"✗ {category}: {feed_url} - {e}")

        all_news[category] = category_news

    return all_news


def get_celebrity_birthday():
    """获取今天生日的名人小故事"""
    today = datetime.now()
    month = today.month
    day = today.day

    # 这里简化处理，实际可以调用 API 或维护数据库
    # 暂时用一个示例
    celebrities = {
        (11, 4): ("巴拉克·奥巴马（虚拟示例）", "美国第44任总统，首位非裔总统，以\"Yes We Can\"的口号激励了一代人。"),
    }

    return celebrities.get((month, day), ("未知名人", "今天没有找到特别的名人生日记录。"))


def translate_and_select_top_news(all_news):
    """简化版：只选择头版新闻 + 翻译标题和摘要为中文"""
    # 尝试从 config.py 读取配置
    try:
        from config import OPENAI_API_KEY, OPENAI_BASE_URL
        api_key = OPENAI_API_KEY
        base_url = OPENAI_BASE_URL
    except ImportError:
        api_key = os.getenv('OPENAI_API_KEY')
        base_url = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')

    client = OpenAI(
        api_key=api_key,
        base_url=base_url
    )

    # 准备简化的新闻列表（只包含标题）
    news_list = []
    for category, items in all_news.items():
        for i, item in enumerate(items):
            news_list.append({
                "category": category,
                "index": i,
                "title": item['title']
            })

    # 第一步：选择头版新闻（简化prompt，减少token）
    news_titles = "\n".join([f"{idx+1}. [{n['category']}] {n['title']}" for idx, n in enumerate(news_list[:20])])  # 只看前20条

    prompt1 = f"""从以下新闻标题中选择1条最重要的作为今日头版新闻。只需返回序号。

{news_titles}

返回格式：只返回数字，如：5"""

    try:
        response1 = client.chat.completions.create(
            model="gpt-6.1-terra",
            messages=[
                {"role": "user", "content": prompt1}
            ],
            temperature=0.3,
            max_tokens=10
        )

        top_index = int(response1.choices[0].message.content.strip()) - 1
        top_story = news_list[top_index]
        print(f"[AI] 头版新闻已选择: {top_story['title'][:50]}...")

    except Exception as e:
        print(f"[WARN] AI 选择头版失败: {e}，使用第一条新闻")
        top_story = news_list[0]

    # 第二步：翻译所有新闻标题和摘要为中文（分批处理，每批10条）
    translations = {}

    for category, items in all_news.items():
        translations[category] = []

        # 分批处理，每批10条
        batch_size = 10
        for batch_start in range(0, len(items), batch_size):
            batch = items[batch_start:batch_start + batch_size]

            # 准备批量翻译的文本
            texts_to_translate = []
            for i, item in enumerate(batch):
                texts_to_translate.append(f"===新闻{batch_start+i+1}===\n标题: {item['title']}\n摘要: {item['summary'][:150]}\n")

            prompt2 = f"""将以下英文新闻翻译成中文。每条新闻独立翻译，保持简洁专业。

{chr(10).join(texts_to_translate)}

严格按照以下格式返回（每条新闻3行）：
标题{batch_start+1}: [翻译后的中文标题，不超过30字]
摘要{batch_start+1}: [翻译后的中文摘要，不超过80字]
---
标题{batch_start+2}: [翻译后的中文标题，不超过30字]
摘要{batch_start+2}: [翻译后的中文摘要，不超过80字]
---
..."""

            try:
                response2 = client.chat.completions.create(
                    model="gpt-6.1-terra",
                    messages=[
                        {"role": "user", "content": prompt2}
                    ],
                    temperature=0.3,
                    max_tokens=2000
                )

                result_text = response2.choices[0].message.content

                # 解析翻译结果
                for i, item in enumerate(batch):
                    idx = batch_start + i + 1
                    title_pattern = f"标题{idx}:\\s*(.+)"
                    summary_pattern = f"摘要{idx}:\\s*(.+)"

                    title_match = re.search(title_pattern, result_text)
                    summary_match = re.search(summary_pattern, result_text)

                    translations[category].append({
                        "index": batch_start + i,
                        "title_cn": title_match.group(1).strip() if title_match else item['title'],
                        "summary_cn": summary_match.group(1).strip() if summary_match else item['summary'][:200]
                    })

                print(f"[AI] {category} 批次 {batch_start//batch_size + 1} 翻译完成")

            except Exception as e:
                print(f"[WARN] 翻译批次失败: {e}，使用原文")
                # 失败时使用原文
                for i, item in enumerate(batch):
                    translations[category].append({
                        "index": batch_start + i,
                        "title_cn": item['title'],
                        "summary_cn": item['summary'][:200]
                    })

    return {
        "top_story": top_story,
        "translations": translations
    }


def generate_html(all_news, ai_result):
    """生成复古报纸风格的 HTML（使用中文翻译）"""
    today = datetime.now()
    date_str = today.strftime('%Y年%m月%d日')
    issue_number = (today - datetime(2026, 11, 1)).days + 1

    celebrity_name, celebrity_story = get_celebrity_birthday()

    # 读取 HTML 模板
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'newspaper.html')
    with open(template_path, 'r', encoding='utf-8') as f:
        template = f.read()

    # 准备头版：所有板块的标题目录
    top_story_html = '<div class="top-story-index"><h2>今日要闻</h2><div class="index-grid">'

    for category, items in all_news.items():
        if not items:
            continue

        # 板块锚点ID（用于跳转）
        category_id = category.replace(' ', '-').replace('与', '-')

        # 获取该板块前3条新闻的中文标题
        top_3_titles = []
        for idx in range(min(3, len(items))):
            item = items[idx]
            title_cn = item['title'][:50]  # 限制长度

            # 尝试获取中文翻译
            if ai_result and 'translations' in ai_result and category in ai_result['translations']:
                for trans in ai_result['translations'][category]:
                    if trans['index'] == idx:
                        title_cn = trans['title_cn'][:50]  # 限制长度
                        break

            top_3_titles.append(f'<li>{title_cn}</li>')

        top_story_html += f'''
        <div class="index-section">
            <h3><a href="#{category_id}">{category}</a></h3>
            <ul>
                {''.join(top_3_titles)}
            </ul>
        </div>
        '''

    top_story_html += '</div></div>'

    # 准备各板块新闻（使用中文）
    sections_html = ""
    for category, items in all_news.items():
        if not items:
            continue

        # 板块锚点ID
        category_id = category.replace(' ', '-').replace('与', '-')

        sections_html += f'<div class="section" id="{category_id}"><h3 class="section-title">{category}</h3><div class="section-grid">'

        for idx, item in enumerate(items):
            # 使用中文翻译
            title_cn = item['title']
            summary_cn = item['summary'][:200]

            if ai_result and 'translations' in ai_result and category in ai_result['translations']:
                for trans in ai_result['translations'][category]:
                    if trans['index'] == idx:
                        title_cn = trans['title_cn']
                        summary_cn = trans['summary_cn']
                        break

            sections_html += f"""
            <div class="news-item">
                <img src="{item['image']}" alt="{title_cn}">
                <div class="news-content">
                    <h4>{title_cn}</h4>
                    <p>{summary_cn}</p>
                    <a href="{item['link']}" target="_blank">详细阅读 →</a>
                </div>
            </div>
            """

        sections_html += '</div></div>'

    # 替换模板变量
    html = template.replace('{{DATE}}', date_str)
    html = html.replace('{{ISSUE_NUMBER}}', str(issue_number))
    html = html.replace('{{TOP_STORY}}', top_story_html)
    html = html.replace('{{SECTIONS}}', sections_html)
    html = html.replace('{{CELEBRITY_NAME}}', celebrity_name)
    html = html.replace('{{CELEBRITY_STORY}}', celebrity_story)

    return html


def save_html(html_content):
    """保存 HTML 文件"""
    today = datetime.now().strftime('%Y-%m-%d')
    output_dir = os.path.join(os.path.dirname(__file__), 'digests')
    os.makedirs(output_dir, exist_ok=True)

    filename = os.path.join(output_dir, f'{today}.html')
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"[OK] 已保存到: {filename}")
    return filename


def main():
    print("[START] 视野日报 - 开始生成...")
    print("=" * 50)

    # 1. 抓取新闻
    print("[NEWS] 正在抓取新闻...")
    all_news = fetch_news()

    total_count = sum(len(items) for items in all_news.values())
    print(f"[OK] 共获取 {total_count} 条新闻")

    if total_count == 0:
        print("[ERROR] 未获取到新闻")
        return

    # 2. AI 翻译和选择头版（简化版）
    print("[AI] AI 分析中（简化模式）...")
    ai_result = translate_and_select_top_news(all_news)

    # 3. 生成 HTML
    print("[HTML] 生成报纸页面...")
    html_content = generate_html(all_news, ai_result)

    # 4. 保存文件
    saved_file = save_html(html_content)

    print("=" * 50)
    print("[DONE] 完成！")
    print(f"[FILE] 文件: {saved_file}")


if __name__ == "__main__":
    main()
