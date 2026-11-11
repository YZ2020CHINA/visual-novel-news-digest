"""Deduplicate against published editions; no history is written during collection."""
import hashlib
import json
import re
import unicodedata
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup


def canonical_url(url):
    try:
        parts = urlsplit(url)
        host = (parts.hostname or '').lower().removeprefix('www.')
        host = {'twitter.com': 'x.com', 'telegram.me': 't.me', 'telegram.dog': 't.me'}.get(host, host)
        query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                 if not k.lower().startswith('utm_') and k.lower() not in {'fbclid', 'gclid', 'mc_cid', 'mc_eid'}]
        return urlunsplit(('https', host, parts.path.rstrip('/'), urlencode(sorted(query)), ''))
    except (ValueError, TypeError):
        return str(url)


def keys(item):
    result = {'url:' + canonical_url(item[field]) for field in ('link', 'canonical_url') if item.get(field)}
    title = unicodedata.normalize('NFKC', item.get('title', '')).casefold()
    title = re.sub(r'[^\w]', '', title)
    if len(title) >= 16:
        result.add('title:' + hashlib.sha256(title.encode()).hexdigest())
    return result


def load_history(directory, now, days=30):
    seen = set()
    directory = Path(directory)
    for offset in range(days + 1):
        date = (now.date() - timedelta(days=offset)).isoformat()
        record = directory / f'{date}.news.json'
        if record.exists():
            # A corrupt history is a publication error, not permission to reprint old news.
            seen.update(json.loads(record.read_text(encoding='utf-8'))['keys'])
        archive = directory / f'{date}.html'
        if archive.exists():
            soup = BeautifulSoup(archive.read_text(encoding='utf-8'), 'html.parser')
            for card in soup.select('.news-item'):
                link, title = card.select_one('a[href]'), card.select_one('h4')
                if link:
                    seen.update(keys({'link': link['href'], 'title': title.get_text() if title else ''}))
    return seen


def select_news(news, seen, platform_names=()):
    seen = set(seen)
    selected = {}
    for category, items in news.items():
        selected[category] = []
        source_counts = {}
        for item in items:
            identity = keys(item)
            if identity & seen:
                continue
            source = item.get('source', category)
            if category not in platform_names and source_counts.get(source, 0) >= 5:
                continue
            selected[category].append(item)
            seen.update(identity)
            source_counts[source] = source_counts.get(source, 0) + 1
            if category in platform_names and len(selected[category]) >= 5:
                break
    return selected


def save_history(directory, now, news):
    path = Path(directory) / f'{now.date().isoformat()}.news.json'
    previous = set(json.loads(path.read_text(encoding='utf-8'))['keys']) if path.exists() else set()
    for items in news.values():
        for item in items:
            previous.update(keys(item))
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps({'keys': sorted(previous)}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)
