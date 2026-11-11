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
from calendar import timegm
from datetime import datetime, timedelta, timezone
from openai import OpenAI
import requests
from bs4 import BeautifulSoup
import random
import shutil
from newsprint import convert_image_url
from html import escape
from pathlib import Path
from platform_news import collect as collect_platforms, PLATFORMS
from news_history import load_history, select_news, save_history
from studio_brand import studio_brand_html

# 修复 Windows 控制台编码问题
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# ============= 新闻源配置 =============

BEIJING_TZ = timezone(timedelta(hours=8))
ECONOMY_CATEGORY = '经济与市场'

NEWS_SOURCES = {
    '独立游戏与视觉小说': [
        'https://www.indiegames.com/feed/',
        'https://www.reddit.com/r/visualnovels/.rss',
        'https://blog.renpy.org/feeds/posts/default',
        'https://itch.io/games/newest/tag-visual-novel.rss',
        'https://www.gcores.com/rss',  # 机核
        'https://www.ign.com.cn/feed.xml',  # IGN 中国
        'https://waytoomany.games/feed/',  # WayTooManyGames
    ],

    'AI与科技': [
        'https://www.technologyreview.com/feed/',
        'https://techcrunch.com/feed/',
        'https://www.theverge.com/rss/index.xml',
        'https://simonwillison.net/atom/everything/',
        'https://www.artificialintelligence-news.com/feed/',
    ],

    ECONOMY_CATEGORY: [
        'https://feeds.bbci.co.uk/news/business/rss.xml',
        'https://www.cnbc.com/id/20910258/device/rss/rss.html',  # 全球经济
        'https://www.cnbc.com/id/10000664/device/rss/rss.html',  # 金融市场
        'https://www.theguardian.com/business/economics/rss',
    ],

    '文化艺术': [
        'https://www.artnews.com/feed/',
        'https://hyperallergic.com/feed/',
        'https://www.creativebloq.com/feed',
        'https://variety.com/v/film/feed/',
        'https://www.theguardian.com/film/rss',
    ],

    '社会事件': [
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

def plain_text(value):
    """Remove feed/translation markup before truncating or escaping for HTML."""
    soup = BeautifulSoup(str(value or ''), 'html.parser')
    for element in soup(['script', 'style', 'template']):
        element.decompose()
    return ' '.join(soup.get_text(' ', strip=True).split())


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


def is_recent_economy_entry(entry, now):
    """经济栏目只收录生成时最近24小时发布的新闻，不用旧闻补数。"""
    published = entry.get('published_parsed') or entry.get('updated_parsed')
    if not published:
        return False
    try:
        published_at = datetime.fromtimestamp(timegm(published), timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return False
    return now - timedelta(hours=24) <= published_at <= now


def fetch_news(candidate_limit=5, extract_images=True):
    """抓取所有新闻源；经济新闻按最近24小时筛选并按链接去重。"""
    all_news = {}
    now = datetime.now(BEIJING_TZ)

    for category, feeds in NEWS_SOURCES.items():
        category_news = []
        seen_links = set()

        for feed_url in feeds:
            try:
                feed = feedparser.parse(feed_url)
                accepted = 0
                for entry in feed.entries:
                    if category == ECONOMY_CATEGORY:
                        if not is_recent_economy_entry(entry, now) or entry.get('link') in seen_links:
                            continue
                    if not entry.get('title') or not entry.get('link'):
                        continue
                    news_item = {
                        'title': plain_text(entry.title),
                        'link': entry.link,
                        'summary': plain_text(entry.get('summary', entry.get('description', '')))[:800],
                        '_text_is_plain': True,
                        'published': entry.get('published', entry.get('updated', '')),
                        'source': feed_url,
                        'image': extract_image_from_url(entry.link) if extract_images else '',
                    }
                    category_news.append(news_item)
                    seen_links.add(entry.link)
                    accepted += 1
                    if accepted == candidate_limit:
                        break

                print(f"✓ {category}: {feed_url}（收录 {accepted} 条）")
            except Exception as e:
                print(f"✗ {category}: {feed_url} - {e}")

        all_news[category] = category_news

    return all_news


def get_celebrity_birthday():
    """获取今天生日的名人小故事"""
    today = datetime.now(BEIJING_TZ)
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

    # 智能补全 base_url：如果不以 /v1 结尾，自动补上
    if base_url and not base_url.endswith('/v1'):
        base_url = base_url.rstrip('/') + '/v1'

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
                        "title_cn": plain_text(title_match.group(1)) if title_match else (item['title'] if item.get('_text_is_plain') else plain_text(item['title'])),
                        "summary_cn": plain_text(summary_match.group(1)) if summary_match else (item['summary'] if item.get('_text_is_plain') else plain_text(item['summary']))[:200],
                        "_text_is_plain": True,
                    })

                print(f"[AI] {category} 批次 {batch_start//batch_size + 1} 翻译完成")

            except Exception as e:
                print(f"[WARN] 翻译批次失败: {e}，使用原文")
                # 失败时使用原文
                for i, item in enumerate(batch):
                    translations[category].append({
                        "index": batch_start + i,
                        "title_cn": item['title'] if item.get('_text_is_plain') else plain_text(item['title']),
                        "summary_cn": (item['summary'] if item.get('_text_is_plain') else plain_text(item['summary']))[:200],
                        "_text_is_plain": True,
                    })

    return {
        "top_story": top_story,
        "translations": translations
    }


def generate_html(all_news, ai_result, platform_status=None):
    """生成复古报纸风格的 HTML（使用中文翻译）"""
    today = datetime.now(BEIJING_TZ)
    date_str = today.strftime('%Y年%m月%d日')
    issue_number = (today.date() - datetime(2026, 11, 1).date()).days + 1

    celebrity_name, celebrity_story = get_celebrity_birthday()

    # 读取 HTML 模板
    template_path = os.path.join(os.path.dirname(__file__), 'templates', 'newspaper.html')
    with open(template_path, 'r', encoding='utf-8') as f:
        template = f.read()

    # 读取 CSS 文件并内嵌到 HTML 中
    css_path = os.path.join(os.path.dirname(__file__), 'static', 'css', 'newspaper.css')
    with open(css_path, 'r', encoding='utf-8') as f:
        css_content = f.read()

    # 替换外部 CSS 链接为内嵌 style 标签
    template = template.replace(
        '<link rel="stylesheet" href="../static/css/newspaper.css">',
        f'<style>\n{css_content}\n    </style>'
    )

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
            title_cn = item['title'] if item.get('_text_is_plain') else plain_text(item['title'])

            # 尝试获取中文翻译
            if ai_result and 'translations' in ai_result and category in ai_result['translations']:
                for trans in ai_result['translations'][category]:
                    if trans['index'] == idx:
                        title_cn = trans['title_cn'] if trans.get('_text_is_plain') else plain_text(trans['title_cn'])
                        break

            top_3_titles.append(f'<li>{escape(title_cn[:50])}</li>')

        top_story_html += f'''
        <div class="index-section">
            <h3><a href="#{escape(category_id, quote=True)}">{escape(category)}</a></h3>
            <ul>
                {''.join(top_3_titles)}
            </ul>
        </div>
        '''

    top_story_html += '</div></div>'

    # 准备各板块新闻（使用中文）
    sections_html = ""
    converted_images = {}
    for category, items in all_news.items():
        if not items:
            if platform_status and category in platform_status:
                category_id = category.replace(' ', '-').replace('与', '-')
                message = platform_status[category]
                if message == '正常':
                    message = '最近24小时暂无未刊登的新帖'
                sections_html += f'<div class="section" id="{escape(category_id)}"><h3 class="section-title">{escape(category)}</h3><p>{escape(message)}</p></div>'
            continue

        # 板块锚点ID
        category_id = category.replace(' ', '-').replace('与', '-')

        sections_html += f'<div class="section" id="{escape(category_id, quote=True)}"><h3 class="section-title">{escape(category)}</h3><div class="section-grid">'

        for idx, item in enumerate(items):
            # 使用中文翻译
            title_cn = item['title'] if item.get('_text_is_plain') else plain_text(item['title'])
            summary_cn = (item['summary'] if item.get('_text_is_plain') else plain_text(item['summary']))[:200]

            if ai_result and 'translations' in ai_result and category in ai_result['translations']:
                for trans in ai_result['translations'][category]:
                    if trans['index'] == idx:
                        title_cn = trans['title_cn'] if trans.get('_text_is_plain') else plain_text(trans['title_cn'])
                        summary_cn = trans['summary_cn'] if trans.get('_text_is_plain') else plain_text(trans['summary_cn'])
                        break

            image_url = item['image']
            if image_url and image_url not in converted_images:
                converted_images[image_url] = convert_image_url(image_url)
            image_src = converted_images.get(image_url, '')
            image_class = ' class="newsprint-photo"' if image_src.startswith('data:image/jpeg;base64,') else ''
            image_html = f'<img{image_class} src="{escape(image_src, quote=True)}" alt="{escape(title_cn, quote=True)}">' if image_src else ''
            source_html = ''
            if category in PLATFORMS:
                metric = {'Telegram 热门': '浏览', 'X 热门': '互动热度', 'Hacker News 热门': '积分'}[category]
                source_html = f'<p class="news-meta">{escape(item.get("source", category))} · {metric} {int(item.get("score", 0))}</p>'

            sections_html += f"""
            <div class="news-item">
                {image_html}
                <div class="news-content">
                    <h4>{escape(title_cn)}</h4>
                    {source_html}
                    <p>{escape(summary_cn)}</p>
                    <a href="{escape(item['link'], quote=True)}" target="_blank" rel="noopener noreferrer">详细阅读 →</a>
                </div>
            </div>
            """

        sections_html += '</div></div>'

    if platform_status:
        notes = '；'.join(f'{name}：{message}' for name, message in platform_status.items())
        sections_html += f'<p class="source-status">平台采集状态 · {escape(notes)}</p>'

    # 替换模板变量
    html = template.replace('{{DATE}}', date_str)
    html = html.replace('{{STUDIO_BRAND}}', studio_brand_html())
    html = html.replace('{{ISSUE_NUMBER}}', str(issue_number))
    html = html.replace('{{TOP_STORY}}', top_story_html)
    html = html.replace('{{SECTIONS}}', sections_html)
    html = html.replace('{{CELEBRITY_NAME}}', celebrity_name)
    html = html.replace('{{CELEBRITY_STORY}}', celebrity_story)

    return html


def save_html(html_content):
    """保存 HTML 文件"""
    today = datetime.now(BEIJING_TZ).strftime('%Y-%m-%d')
    output_dir = os.path.join(os.path.dirname(__file__), 'digests')
    os.makedirs(output_dir, exist_ok=True)

    filename = os.path.join(output_dir, f'{today}.html')
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(html_content)

    # Keep a stable, complete edition for both online reading and download.
    # A backfilled older archive must not replace a newer published issue.
    dated_files = [name for name in os.listdir(output_dir)
                   if re.fullmatch(r'\d{4}-\d{2}-\d{2}\.html', name)]
    latest_archive = os.path.join(output_dir, max(dated_files))
    shutil.copyfile(latest_archive, os.path.join(output_dir, 'latest.html'))

    print(f"[OK] 已保存到: {filename}")
    return filename


def main():
    try:
        print("[START] 视野日报 - 开始生成...")
        print("=" * 50)

        # 1. 抓取新闻
        print("[NEWS] 正在抓取新闻...")
        now = datetime.now(BEIJING_TZ)
        output_dir = Path(__file__).parent / 'digests'
        history = load_history(output_dir, now)
        platform_news, platform_status = collect_platforms(now)
        # Reserve platform sections first; suppress duplicate linked articles in RSS sections.
        candidates = {**platform_news, **fetch_news(candidate_limit=50, extract_images=False)}
        selected = select_news(candidates, history, PLATFORMS)
        all_news = {name: selected[name] for name in list(NEWS_SOURCES) + list(PLATFORMS)}
        for category in NEWS_SOURCES:
            for item in all_news[category]:
                item['image'] = extract_image_from_url(item['link'])

        total_count = sum(len(items) for items in all_news.values())
        print(f"[OK] 共获取 {total_count} 条新闻")

        if total_count == 0:
            print("[ERROR] 未获取到新闻")
            sys.exit(1)

        # 2. AI 翻译和选择头版（简化版）
        print("[AI] AI 分析中（简化模式）...")
        try:
            ai_result = translate_and_select_top_news(all_news)
        except Exception as e:
            print(f"[ERROR] AI 分析失败: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

        # 3. 生成 HTML
        print("[HTML] 生成报纸页面...")
        html_content = generate_html(all_news, ai_result, platform_status)

        # 4. 保存文件
        saved_file = save_html(html_content)
        save_history(output_dir, now, all_news)

        print("=" * 50)
        print("[DONE] 完成！")
        print(f"[FILE] 文件: {saved_file}")

    except Exception as e:
        print(f"[FATAL ERROR] 程序运行出错: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
