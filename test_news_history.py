import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from news_history import canonical_url, load_history, save_history, select_news


class HistoryTests(unittest.TestCase):
    def test_tracking_and_platform_aliases(self):
        self.assertEqual(canonical_url('http://www.twitter.com/a/status/1?utm_source=r#x'),
                         canonical_url('https://x.com/a/status/1'))
        self.assertNotEqual(canonical_url('https://news.ycombinator.com/item?id=1'),
                            canonical_url('https://news.ycombinator.com/item?id=2'))

    def test_global_dedup_and_backfill_after_history(self):
        rows = [dict(title=f'Unique headline number {i}', link=f'https://a.test/{i}') for i in range(10)]
        result = select_news({'X': rows, 'RSS': [rows[3]]}, {'url:https://a.test/0'}, ['X'])
        self.assertEqual([row['link'] for row in result['X']], [f'https://a.test/{i}' for i in range(1, 6)])
        self.assertEqual(result['RSS'], [])

    def test_titles_and_canonical_article_dedup(self):
        rows = [dict(title='A sufficiently long identical headline!', link='https://a/1'),
                dict(title='A sufficiently long identical headline', link='https://b/2'),
                dict(title='Other title', link='https://c/3', canonical_url='https://a/1')]
        self.assertEqual(len(select_news({'test': rows}, set())['test']), 1)

    def test_archive_bootstrap_and_same_day_history_union(self):
        now = datetime(2026, 11, 11, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / '2026-11-10.html').write_text('<div class="news-item"><h4>Old</h4><a href="https://a/old?utm_source=r">read</a></div>')
            self.assertIn('url:https://a/old', load_history(path, now))
            save_history(path, now, {'X': [dict(title='one', link='https://a/1')]})
            save_history(path, now, {'X': [dict(title='two', link='https://a/2')]})
            self.assertTrue({'url:https://a/1', 'url:https://a/2'} <= load_history(path, now))
            self.assertEqual(len(json.loads((path / '2026-11-11.news.json').read_text())['keys']), 2)

    def test_old_archives_expire_and_short_titles_do_not_collide(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / '2025-01-01.html').write_text('<div class="news-item"><a href="https://a/1">x</a></div>')
            self.assertEqual(load_history(directory, datetime(2026, 11, 11)), set())
        rows = [dict(title='News', link=f'https://a/{i}') for i in range(2)]
        self.assertEqual(len(select_news({'a': rows}, set())['a']), 2)
