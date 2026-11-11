"""Bounded public-channel / HN collection and optional Apify X collection."""
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests
from bs4 import BeautifulSoup

PLATFORMS = ('Telegram 热门', 'X 热门', 'Hacker News 热门')


def get(url, **kwargs):
    response = requests.get(url, timeout=25, **kwargs)
    response.raise_for_status()
    return response


def timestamp(value):
    try:
        if isinstance(value, (float, int)):
            return datetime.fromtimestamp(value, timezone.utc)
        try:
            result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        except ValueError:
            result = parsedate_to_datetime(value)
        return result if result.tzinfo else None
    except (ValueError, TypeError, OverflowError, AttributeError):
        return None


def recent(value, now):
    date = timestamp(value)
    return date is not None and now - timedelta(hours=24) <= date <= now


def count(value):
    text = str(value or 0).replace(',', '').strip().upper()
    match = re.fullmatch(r'(\d+(?:\.\d+)?)\s*([KM]?)', text)
    return int(float(match[1]) * {'': 1, 'K': 1000, 'M': 1000000}[match[2]]) if match else 0


def item(text, link, date, score, source, canonical=None):
    text = BeautifulSoup(text, 'html.parser').get_text(' ', strip=True)
    return dict(title=text[:120], summary=text[:800], link=link,
                canonical_url=canonical or link, published=str(date), score=score,
                source=source, image='', _text_is_plain=True)


def telegram(html, channel, now):
    soup = BeautifulSoup(html, 'html.parser')
    messages = soup.select('.tgme_widget_message[data-post]')
    if not messages:
        raise ValueError('public preview has no readable posts')
    results = []
    for message in messages:
        date = message.select_one('time[datetime]')
        text = message.select_one('.tgme_widget_message_text')
        if not date or not text or not recent(date['datetime'], now):
            continue
        post = message['data-post']
        if not re.fullmatch(r'[A-Za-z0-9_]+/\d+', post):
            continue
        views = message.select_one('.tgme_widget_message_views')
        links = [a['href'] for a in text.select('a[href]')
                 if a['href'].startswith(('https://', 'http://'))
                 and not re.match(r'https?://(?:t.me|telegram.me)/', a['href'])]
        results.append(item(str(text), f'https://t.me/{post}', date['datetime'],
                            count(views.get_text() if views else 0), channel,
                            links[0] if links else None))
    return results


def hackernews(config, now):
    ids = get('https://hacker-news.firebaseio.com/v0/topstories.json').json()
    failures = []
    def fetch(story_id):
        try:
            story = get(f'https://hacker-news.firebaseio.com/v0/item/{story_id}.json').json()
            if not story or story.get('deleted') or story.get('dead') or story.get('type') != 'story':
                return None
            if not recent(story.get('time'), now):
                return None
            link = f'https://news.ycombinator.com/item?id={story_id}'
            result = item(story['title'], link, story['time'], count(story.get('score')), 'Hacker News', story.get('url'))
            result['summary'] = f"{result['title']} · {story.get('score', 0)} points · {story.get('descendants', 0)} comments"
            return result
        except (requests.RequestException, ValueError, KeyError):
            failures.append(str(story_id))
    with ThreadPoolExecutor(max_workers=8) as pool:
        items = [i for i in pool.map(fetch, ids[:min(500, config.get('hn_candidates', 150))]) if i]
    if ids and len(failures) == min(len(ids), config.get('hn_candidates', 150), 500):
        raise ValueError('all story requests failed')
    return items, failures


def twitter(config, now):
    token = os.environ.get('APIFY_TOKEN')
    if not token:
        raise ValueError('未配置 APIFY_TOKEN，X 抓取尚未启用')
    response = requests.post(
        f"https://api.apify.com/v2/acts/{config['x_actor'].replace('/', '~')}/run-sync-get-dataset-items",
        headers={'Authorization': f'Bearer {token}'},
        params={'timeout': 120, 'memory': 512}, timeout=135,
        json={'source_mode': 'profiles', 'profile_urls': config['x_users'], 'search_sort': 'Latest', 'max_items': 100})
    response.raise_for_status()
    rows = response.json()
    if not isinstance(rows, list):
        raise ValueError('unexpected X dataset')
    results = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        date = row.get('created_at') or row.get('createdAt')
        text = row.get('full_text') or row.get('text')
        link = row.get('tweet_url') or row.get('url') or row.get('twitterUrl')
        if not link:
            user = row.get('user') or {}
            handle = row.get('handle') or user.get('handle') or user.get('screen_name') or user.get('username') or row.get('username')
            post_id = str(row.get('id_str') or row.get('id') or '').removeprefix('tweet-')
            if handle and post_id.isdigit():
                link = f'https://x.com/{handle}/status/{post_id}'
        if not text or not link or not recent(date, now):
            continue
        if not re.match(r'https://(?:www\.)?(?:x|twitter)\.com/\w+/status/\d+', link):
            continue
        score = count(row.get('favorite_count', row.get('like_count', row.get('likeCount')))) + 2 * count(row.get('retweet_count', row.get('retweetCount'))) + count(row.get('reply_count', row.get('replyCount')))
        results.append(item(text, link, date, score, 'X'))
    return results


def collect(now=None):
    now = now or datetime.now(timezone.utc)
    config = json.loads(Path(__file__).with_name('platform_sources.json').read_text(encoding='utf-8'))
    news = {name: [] for name in PLATFORMS}
    status = {}
    failures = []
    for channel in config['telegram_channels']:
        try:
            if not re.fullmatch(r'[A-Za-z0-9_]+', channel):
                raise ValueError('invalid channel name')
            news[PLATFORMS[0]].extend(telegram(get(f'https://t.me/s/{channel}').text, channel, now))
        except (requests.RequestException, ValueError):
            failures.append(channel)
    status[PLATFORMS[0]] = '部分频道不可用：' + ', '.join(failures) if failures else '正常'
    for name, fetcher in [(PLATFORMS[1], twitter), (PLATFORMS[2], hackernews)]:
        try:
            result = fetcher(config, now)
            if isinstance(result, tuple):
                news[name], errors = result
                status[name] = f'部分帖子获取失败：{len(errors)} 条' if errors else '正常'
            else:
                news[name], status[name] = result, '正常'
        except (requests.RequestException, ValueError, KeyError):
            status[name] = ('未配置 APIFY_TOKEN，X 抓取尚未启用' if name == PLATFORMS[1] and not os.environ.get('APIFY_TOKEN')
                            else '抓取失败，请查看来源配置及服务可用性')
    for name in news:
        news[name].sort(key=lambda row: (-row['score'], row['link']))
    return news, status
