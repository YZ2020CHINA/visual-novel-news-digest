"""Email subscription: subscribe link in the masthead and daily delivery through Buttondown.

Buttondown hosts the sign-up page, double opt-in confirmation, subscriber list and the
unsubscribe link it appends to every email, so no subscriber data is stored in this repository.
"""
import json
import os
import re
import sys
from html import escape
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

import requests
from bs4 import BeautifulSoup

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        stream.reconfigure(encoding='utf-8', errors='replace')

API_URL = 'https://api.buttondown.com/v1/emails'
CONFIG_PATH = Path(__file__).parent / 'newsletter.json'
LEGACY_BAR = re.compile(r'\s*<div class="subscribe-bar".*?</div></div>', re.S)
CORNER_MARKER = 'class="subscribe-corner"'
CORNER_ANCHOR = '<a class="studio-social"'
MAX_SUMMARY = 120
MAX_ITEMS_PER_SECTION = 5


def load_config():
    return json.loads(CONFIG_PATH.read_text(encoding='utf-8'))


def subscribe_url(config=None):
    config = config or load_config()
    return f"https://buttondown.com/{config['buttondown_username']}"


CORNER_STYLE = (
    '<style>'
    '.subscribe-corner{margin-left:auto;margin-right:18px;flex-shrink:0;white-space:nowrap;padding:6px 14px;'
    'border:2px solid #2b2b2b;color:#2b2b2b;text-decoration:none;font-weight:700;letter-spacing:0.1em;font-size:0.85rem}'
    '.subscribe-corner:hover{background:#2b2b2b;color:#f4f0e6}'
    '@media (max-width:600px){'
    '.studio-brand .studio-logo-link{flex-basis:96px}'
    '.studio-brand .studio-social-label{display:none}'
    '.studio-brand .studio-handle{font-size:0.78rem}'
    '.subscribe-corner{margin-right:0;padding:5px 8px;font-size:0.74rem;letter-spacing:0.03em}}'
    '</style>'
)


def subscribe_corner_html(config=None):
    return (
        f'{CORNER_STYLE}<a {CORNER_MARKER} href="{escape(subscribe_url(config), quote=True)}" target="_blank" '
        'rel="noopener noreferrer">✉ 订阅日报</a>'
    )

def add_subscribe_link(html, config=None):
    """Insert the corner button beside the studio link and drop the retired block under the date; safe to repeat."""
    html = LEGACY_BAR.sub('', html)
    if CORNER_MARKER not in html:
        index = html.find(CORNER_ANCHOR)
        if index >= 0:
            html = html[:index] + subscribe_corner_html(config) + '\n                ' + html[index:]
    return html


def safe_link(url):
    return url if urlsplit(url).scheme in ('http', 'https') else ''


def parse_edition(html):
    soup = BeautifulSoup(html, 'html.parser')
    date = soup.select_one('.header-info .date')
    issue = soup.select_one('.header-info .issue')
    sections = []
    for section in soup.select('.section'):
        title = section.select_one('.section-title')
        items = []
        for card in section.select('.news-item'):
            heading = card.select_one('h4')
            link = card.select_one('a[href]')
            paragraphs = [p for p in card.select('.news-content p') if 'news-meta' not in (p.get('class') or [])]
            if not heading:
                continue
            summary = paragraphs[0].get_text(' ', strip=True) if paragraphs else ''
            items.append({
                'title': heading.get_text(' ', strip=True),
                'summary': summary[:MAX_SUMMARY] + ('…' if len(summary) > MAX_SUMMARY else ''),
                'link': safe_link(link['href']) if link else '',
            })
        if title and items:
            sections.append({'title': title.get_text(strip=True), 'items': items[:MAX_ITEMS_PER_SECTION]})
    return {
        'date': date.get_text(strip=True) if date else '',
        'issue': issue.get_text(strip=True) if issue else '',
        'sections': sections,
    }


def edition_url(date_iso, config=None):
    config = config or load_config()
    return f"{config['site_url'].rstrip('/')}/digests/{date_iso}.html"


def build_email(html, date_iso, config=None):
    """Return (subject, body). The body is a lightweight headline digest without embedded images."""
    edition = parse_edition(html)
    if not edition['sections']:
        raise ValueError('日报中没有可发送的新闻')
    url = escape(edition_url(date_iso, config), quote=True)
    parts = ['<!-- buttondown-editor-mode: fancy -->',
             f'<h1>视野日报 · {escape(edition["date"])}</h1>',
             f'<p>{escape(edition["issue"])} · <a href="{url}">在线阅读完整报纸（含配图）</a></p>']
    for section in edition['sections']:
        parts.append(f'<h2>{escape(section["title"])}</h2><ul>')
        for item in section['items']:
            title = escape(item['title'])
            if item['link']:
                title = f'<a href="{escape(item["link"], quote=True)}">{title}</a>'
            summary = f'<br>{escape(item["summary"])}' if item['summary'] else ''
            parts.append(f'<li><strong>{title}</strong>{summary}</li>')
        parts.append('</ul>')
    parts.append(f'<p><a href="{url}">阅读完整一期 →</a></p>')
    subject = f'视野日报 · {edition["date"]}'
    if edition['issue']:
        subject += f' · {edition["issue"]}'
    return subject, '\n'.join(parts)


def send_edition(path, api_key=None, config=None, session=requests):
    """Send one saved edition. Returns 'sent', 'duplicate' or 'skipped'."""
    api_key = api_key if api_key is not None else os.environ.get('BUTTONDOWN_API_KEY', '')
    if not api_key:
        print('[MAIL] 未配置 BUTTONDOWN_API_KEY，跳过邮件发送')
        return 'skipped'
    path = Path(path)
    date_iso = path.stem
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', date_iso):
        raise ValueError(f'不是日期命名的日报文件: {path.name}')
    subject, body = build_email(path.read_text(encoding='utf-8'), date_iso, config)
    response = session.post(
        API_URL,
        headers={'Authorization': f'Token {api_key}', 'X-Buttondown-Live-Dangerously': 'true'},
        json={'subject': subject, 'body': body, 'slug': f'daily-{date_iso}', 'status': 'about_to_send'},
        timeout=30,
    )
    if response.status_code == 409:
        print(f'[MAIL] {date_iso} 已发送过，跳过')
        return 'duplicate'
    response.raise_for_status()
    print(f'[MAIL] 已提交发送: {subject}')
    return 'sent'


def todays_edition(directory, now=None):
    """Today's (Beijing time) edition, or None so a failed run never re-sends an old issue."""
    now = now or datetime.now(timezone(timedelta(hours=8)))
    path = Path(directory) / f'{now.date().isoformat()}.html'
    return path if path.exists() else None


def backfill(directory, config=None):
    changed = []
    for path in sorted(Path(directory).glob('*.html')):
        original = path.read_text(encoding='utf-8')
        updated = add_subscribe_link(original, config)
        if updated != original:
            path.write_text(updated, encoding='utf-8')
            changed.append(path.name)
    return changed


def main(argv):
    digests = Path(__file__).parent / 'digests'
    command = argv[1] if len(argv) > 1 else 'send'
    if command == 'send':
        target = Path(argv[2]) if len(argv) > 2 else todays_edition(digests)
        if target is None:
            print('[MAIL] 今天没有新生成的日报，不发送邮件')
            return 0
        send_edition(target)
    elif command == 'backfill':
        print('已更新:', ', '.join(backfill(digests)) or '无')
    else:
        print('用法: python newsletter.py [send [文件] | backfill]')
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
