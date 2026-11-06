"""News freshness, section rendering, and Beijing dates at the UTC boundary."""
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup
from feedparser import FeedParserDict

with patch('sys.platform', 'linux'):
    import news_digest


def entry(title, published=None, link=None):
    item = FeedParserDict(title=title, link=link or f'https://example.org/{title}',
                          summary=f'<p>{title} summary</p>')
    if published:
        item['published_parsed'] = published.utctimetuple()
        item['published'] = format_datetime(published)
    return item


class NewsSourcesTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 7, 4, 12, tzinfo=news_digest.BEIJING_TZ)

    def test_economy_24_hour_boundaries_and_missing_dates(self):
        cases = [(self.now, True), (self.now - timedelta(hours=24), True),
                 (self.now - timedelta(hours=24, seconds=1), False),
                 (self.now + timedelta(seconds=1), False), (None, False)]
        for published, expected in cases:
            with self.subTest(published=published):
                self.assertEqual(news_digest.is_recent_economy_entry(
                    entry('story', published), self.now), expected)

    def test_economy_accepts_atom_updated_timestamp(self):
        item = entry('atom')
        item['updated_parsed'] = (self.now - timedelta(hours=1)).utctimetuple()
        self.assertTrue(news_digest.is_recent_economy_entry(item, self.now))

    def test_filter_before_limit_and_deduplicate_across_economy_feeds(self):
        old = [entry(f'old{i}', self.now - timedelta(days=3)) for i in range(6)]
        recent = [entry(f'new{i}', self.now - timedelta(hours=1)) for i in range(7)]
        feeds = [FeedParserDict(entries=old + recent),
                 FeedParserDict(entries=[recent[0], entry('other', self.now)])]
        sources = {news_digest.ECONOMY_CATEGORY: ['feed-one', 'feed-two']}
        with patch.dict(news_digest.NEWS_SOURCES, sources, clear=True), \
                patch.object(news_digest, 'datetime', wraps=datetime) as clock, \
                patch.object(news_digest.feedparser, 'parse', side_effect=feeds), \
                patch.object(news_digest, 'extract_image_from_url', return_value='photo') as image:
            clock.now.return_value = self.now
            items = news_digest.fetch_news()[news_digest.ECONOMY_CATEGORY]
        self.assertEqual([item['title'] for item in items],
                         ['new0', 'new1', 'new2', 'new3', 'new4', 'other'])
        self.assertEqual(image.call_count, 6)

    def test_other_sections_keep_undated_items_and_handle_source_failures(self):
        sources = {'文化艺术': ['broken', 'working']}
        with patch.dict(news_digest.NEWS_SOURCES, sources, clear=True), \
                patch.object(news_digest.feedparser, 'parse', side_effect=[
                    RuntimeError('unavailable'), FeedParserDict(entries=[entry('film')])]), \
                patch.object(news_digest, 'extract_image_from_url', return_value='photo'):
            self.assertEqual(news_digest.fetch_news()['文化艺术'][0]['title'], 'film')

    def test_all_six_sections_and_links_render_without_nested_cards(self):
        news = {category: [dict(entry(f'story{i}'), image='photo')]
                for i, category in enumerate(news_digest.NEWS_SOURCES)}
        with patch.object(news_digest, 'convert_image_url', return_value='photo'):
            soup = BeautifulSoup(news_digest.generate_html(news, None), 'html.parser')
        self.assertEqual(len(soup.select('main > .section')), 6)
        self.assertEqual(len(soup.select('.index-section')), 6)
        self.assertEqual(len(soup.select('.news-item .news-item')), 0)
        self.assertIn('经济与市场', [h.get_text() for h in soup.select('.section-title')])
        self.assertIn('社会事件', [h.get_text() for h in soup.select('.section-title')])
        self.assertNotIn('社会与文化', soup.get_text())
        for link in soup.select('.index-section h3 a'):
            self.assertIsNotNone(soup.find(id=link['href'][1:]))

    def test_early_morning_edition_uses_beijing_date_for_header_and_archive(self):
        # On the UTC runner it is still Nov 6; the Beijing edition must be Nov 7.
        utc_now = self.now.astimezone(timezone.utc)
        with tempfile.TemporaryDirectory() as root:
            with patch.object(news_digest, 'datetime', wraps=datetime) as clock:
                clock.now.side_effect = lambda tz=None: (
                    utc_now.astimezone(tz) if tz else utc_now.replace(tzinfo=None))
                page = news_digest.generate_html({}, None)
                with patch.object(news_digest, '__file__', str(Path(root) / 'news_digest.py')):
                    saved = news_digest.save_html(page)
            self.assertEqual(Path(saved).name, '2026-11-07.html')
            self.assertIn('2026年11月07日', page)
            self.assertIn('第 7 期', page)
            self.assertEqual((Path(root) / 'digests/latest.html').read_text(encoding='utf-8'), page)


if __name__ == '__main__':
    unittest.main()
