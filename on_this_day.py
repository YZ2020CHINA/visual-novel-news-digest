"""Date-matched, source-linked history of human dignity and civilization.

Reviewed primary-source entries take precedence over the daily Wikipedia index.
Remote text is excerpted, never expanded by an LLM into unsupported claims.
"""
import json
import re
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from urllib.parse import quote, urlsplit

import requests
from bs4 import BeautifulSoup

BEIJING_TZ = timezone(timedelta(hours=8))
CURATED_PATH = Path(__file__).with_name('on_this_day_events.json')
API_URL = 'https://zh.wikipedia.org/w/api.php'
USER_AGENT = 'VisionDaily/1.0 (+https://github.com/YZ2020CHINA/visual-novel-news-digest)'
MAX_EVENTS = 3
TOPICS = {
    '关爱与社会福利': (
        r'社会福利|社会保障|社会保险|社会救助|医疗保险|养老保险|慈善|救济|红十字|红新月|儿童基金会|扶贫|无障碍|残疾人权益|劳动保护|最低工资|八小时工作',
        r'成立|建立|创立|通过|颁布|实施|生效|签署|启动|开办|提供|救援|救助|废除|实行|设立',
    ),
    '医疗与公共卫生': (
        r'疫苗|抗生素|青霉素|胰岛素|麻醉|器官移植|心脏移植|试管婴儿|公共卫生|世界卫生组织|医院|医疗|医学|免疫|根除天花|消灭天花',
        r'首次|第一|发现|发明|成功|批准|研制|成立|建立|启用|通过|生效|问世|开放|根除|消灭|治愈',
    ),
    '教育与知识普及': (
        r'义务教育|免费教育|扫盲|受教育权|女子学校|女子大学|大学|图书馆|开放教育|教育权|学校',
        r'成立|建立|创办|创立|开放|开办|通过|颁布|实施|生效|启用|入学|落成',
    ),
    '自由、平等与人权': (
        r'人权|民权|平等|博爱|妇女参政|女性参政|选举权|投票权|奴隶制|奴隶制度|种族隔离|种族歧视|妇女权利|儿童权利|宪法|言论自由|新闻自由|宗教自由|同性婚姻|同性结婚|残疾人权利',
        r'通过|颁布|签署|生效|废除|取消|成立|宣布|发表|宣言|保障|承认|赋予|争取|运动|抗议|裁定|判决',
    ),
    '科技与生活改善': (
        r'互联网|万维网|计算机|电脑|电报|电话|广播|电力|发电站|自来水|污水处理|铁路|铁路桥|地铁|有轨|印刷|盲文|卫星|探测器|望远镜|航天|太空|火星|月球|天文|脉冲星|科学|物理|化学',
        r'首次|第一|发明|发现|成功|建成|启用|开通|通车|发布|问世|诞生|成立|发射|着陆|登陆|公开|开放',
    ),
    '文化艺术与文明': (
        r'电影|小说|诗集|诗歌|(?<![天人])文学|戏剧|歌剧|交响曲|乐曲|音乐|绘画|画作|雕塑|博物馆|美术馆|文化遗产|考古|古籍|文物|壁画|舞剧|芭蕾|艺术|著作',
        r'首映|首播|首演|上映|播映|公映|出版|发表|完成|创作|开幕|落成|成立|建成|揭幕|演出|问世|发现|开放|出土|列入',
    ),
}
JUDICIAL_ACTION = re.compile(r'审判|宣判|判处|判决|定罪|裁定|开庭|起诉|受审|审理|法庭.{0,12}成立|法庭.{0,12}设立')
HUMAN_RIGHTS_CRIME = re.compile(r'战争罪|战犯|反人类罪|危害人类罪|种族灭绝|大屠杀|纳粹|酷刑|强迫失踪|种族隔离|人权侵害|侵犯人权')
ADVERSE_EVENT = re.compile(r'屠杀|惨案|枪击|空袭|轰炸|恐怖袭击|恐怖攻击|遇刺|遇袭|坠毁|爆炸|政变|发动.{0,8}(?:战争|进攻)|核试验|导弹|洲际|弹道|驱逐|禁止|镇压|迫害|剥夺|撤销|废止')
RIGHTS_ADVANCE = re.compile(r'废除.{0,12}(?:奴隶|隔离|歧视)|取消.{0,12}(?:隔离|歧视)|解除.{0,12}禁令')


def beijing_time(now=None):
    now = now or datetime.now(BEIJING_TZ)
    return now.replace(tzinfo=BEIJING_TZ) if now.tzinfo is None else now.astimezone(BEIJING_TZ)


def safe_url(value):
    value = str(value or '')
    try:
        parsed = urlsplit(value)
    except ValueError:
        return ''
    return value if parsed.scheme in ('https', 'http') and parsed.netloc else ''


def classify_event(text):
    """Conservative editorial rules; a court action alone is not a conviction."""
    if JUDICIAL_ACTION.search(text) and HUMAN_RIGHTS_CRIME.search(text):
        return '正义、审判与追责'
    if ADVERSE_EVENT.search(text) and not RIGHTS_ADVANCE.search(text):
        return None
    for topic, (subject, action) in TOPICS.items():
        if re.search(subject, text) and re.search(action, text):
            return topic
    return None


def curated_events(now):
    """Keep only reviewed entries for this month/day in a strictly earlier year."""
    rows = json.loads(CURATED_PATH.read_text(encoding='utf-8'))
    return [dict(row, source_kind='primary') for row in rows
            if (row['month'], row['day']) == (now.month, now.day) and row['year'] < now.year]


def parse_day_page(html, now):
    """Read 大事记 only, excluding TOC, birthdays, deaths and observances."""
    soup = BeautifulSoup(html, 'html.parser')
    events, active = [], False
    date_url = 'https://zh.wikipedia.org/wiki/' + quote(f'{now.month}月{now.day}日')
    for tag in soup.find_all(['h2', 'li']):
        if tag.name == 'h2':
            heading = tag.get_text('', strip=True).replace('[编辑]', '').strip()
            active = heading == '大事记'
            continue
        if not active or tag.find_parent('li'):
            continue
        # Remove reference markers and language links, keeping the actual event text.
        for extra in tag.select('sup, .mw-editsection, .noprint, ul, ol'):
            extra.decompose()
        text = tag.get_text('', strip=True)
        match = re.match(r'^(\d{1,4})年[：:]\s*(.+)$', text)
        if not match:
            continue
        year, summary = int(match[1]), match[2]
        if not 1 <= year < now.year:
            continue
        topic = classify_event(summary)
        if not topic:
            continue
        events.append(dict(year=year, month=now.month, day=now.day, topic=topic,
                           summary=summary[:360] + ('…' if len(summary) > 360 else ''),
                           source_name='维基百科·当日大事记（自动筛选）', source_url=date_url + '#大事记',
                           source_kind='index'))
    return events


def select_events(reviewed, discovered, limit=MAX_EVENTS):
    """Prefer reviewed sources and vary topics without filling with unrelated items."""
    candidates = list(reviewed)
    for event in discovered:
        if any(event['year'] == row['year'] and any(term in event['summary'] for term in row.get('match_terms', []))
               for row in reviewed):
            continue
        candidates.append(event)
    chosen, topics, seen = [], set(), set()
    # A diverse first pass; a second pass allows multiple events on the same theme.
    for diverse in (True, False):
        for event in candidates:
            key = (event['year'], event['summary'])
            if key in seen or (diverse and event['topic'] in topics):
                continue
            chosen.append(event)
            seen.add(key)
            topics.add(event['topic'])
            if len(chosen) >= limit:
                return chosen
    return chosen


def get_on_this_day(now=None, *, fetch_remote=True, session=requests):
    now = beijing_time(now)
    reviewed = curated_events(now)
    discovered, status = [], 'local'
    if fetch_remote:
        try:
            response = session.get(API_URL, params={
                'action': 'parse', 'page': f'{now.month}月{now.day}日', 'prop': 'text',
                'format': 'json', 'formatversion': 2, 'variant': 'zh-cn', 'redirects': 1,
            }, headers={'User-Agent': USER_AGENT}, timeout=20)
            response.raise_for_status()
            html = response.json()['parse']['text']
            if not isinstance(html, str):
                raise ValueError('Invalid day-page text')
            discovered = parse_day_page(html, now)
            status = 'ok'
        except (requests.RequestException, ValueError, KeyError, TypeError):
            # Never substitute a different date or ask an LLM to invent a history item.
            status = 'unavailable'
    return {'date': now.date().isoformat(), 'events': select_events(reviewed, discovered), 'status': status}


def render_history(result):
    parts = []
    for event in result['events']:
        date_iso = f'{event["year"]:04d}-{event["month"]:02d}-{event["day"]:02d}'
        date_label = f'{event["year"]}年{event["month"]}月{event["day"]}日'
        url = safe_url(event.get('source_url'))
        source = escape(event.get('source_name', '来源'))
        source_html = (f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{source} →</a>'
                       if url else source)
        parts.append(f'<article class="history-event"><h4><time datetime="{date_iso}">{date_label}</time>'
                     f'<span class="history-topic">{escape(event["topic"])}</span></h4>'
                     f'<p class="history-story">{escape(event["summary"])}</p>'
                     f'<p class="history-source">来源：{source_html}</p></article>')
    if not parts:
        notice = ('今日历史资料暂时无法获取，暂缺可核对的同日主题事件。'
                  if result['status'] == 'unavailable' else '今天暂未检索到符合主题的同日历史事件。')
        parts.append(f'<p class="history-empty">{notice}</p>')
    elif result['status'] == 'unavailable':
        parts.append('<p class="history-note">在线历史检索暂不可用，本期采用已核对来源的同日记录。</p>')
    if any(e.get('source_kind') == 'index' for e in result['events']):
        parts.append('<p class="history-note">含维基百科当日大事记的自动筛选摘录；日期与表述仍可能存在资料误差，详见来源。'
                     '相关文字依 CC BY-SA 4.0 使用。</p>')
    return '\n'.join(parts)
