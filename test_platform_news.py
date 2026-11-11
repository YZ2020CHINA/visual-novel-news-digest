import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import platform_news as platforms
with patch('sys.platform', 'linux'):
    import news_digest
from bs4 import BeautifulSoup


class PlatformTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 11, 11, 4, 12, tzinfo=timezone.utc)

    def test_time_boundaries_and_view_counts(self):
        for hours, expected in [(0, True), (24, True), (25, False), (-1, False)]:
            self.assertEqual(platforms.recent((self.now - timedelta(hours=hours)).isoformat(), self.now), expected)
        self.assertFalse(platforms.recent(None, self.now))
        self.assertFalse(platforms.recent('2026-11-11T01:00:00', self.now))
        self.assertEqual(platforms.count('1.2K'), 1200)
        self.assertEqual(platforms.count('2M'), 2000000)

    def test_telegram_parser_and_login_page(self):
        html = f'<div class="tgme_widget_message" data-post="demo/12"><time datetime="{self.now.isoformat()}"></time><div class="tgme_widget_message_text">Hello <a href="https://example.com/story">story</a></div><span class="tgme_widget_message_views">1.2K</span></div>'
        result = platforms.telegram(html, 'demo', self.now)[0]
        self.assertEqual(result['score'], 1200)
        self.assertEqual(result['canonical_url'], 'https://example.com/story')
        with self.assertRaises(ValueError):
            platforms.telegram('<html>login</html>', 'demo', self.now)

    def test_x_real_actor_fields_and_authorization(self):
        response = Mock()
        response.json.return_value = [dict(id='tweet-123', user={'screen_name': 'demo'}, full_text='Hello', created_at=self.now.isoformat(), favorite_count=10, retweet_count=2, reply_count=3)]
        with patch.dict('os.environ', {'APIFY_TOKEN': 'test-only'}), patch.object(platforms.requests, 'post', return_value=response) as post:
            rows = platforms.twitter({'x_actor': 'altimis/scweet', 'x_users': ['demo']}, self.now)
        self.assertEqual(rows[0]['link'], 'https://x.com/demo/status/123')
        self.assertEqual(rows[0]['score'], 17)
        self.assertEqual(post.call_args.kwargs['json']['profile_urls'], ['demo'])

    def test_x_current_scweet_output_and_handle_fallback(self):
        response = Mock()
        row = dict(id='123', handle='demo', text='Current output',
                   created_at='Wed Nov 11 04:12:00 +0000 2026',
                   favorite_count=10, retweet_count=2, reply_count=3)
        response.json.return_value = [dict(row, tweet_url='https://x.com/demo/status/123'),
                                      dict(row, id='124', user={'handle': 'demo'})]
        with patch.dict('os.environ', {'APIFY_TOKEN': 'test-only'}), patch.object(platforms.requests, 'post', return_value=response):
            rows = platforms.twitter({'x_actor': 'altimis/scweet', 'x_users': ['demo']}, self.now)
        self.assertEqual([r['link'] for r in rows],
                         ['https://x.com/demo/status/123', 'https://x.com/demo/status/124'])
        self.assertEqual(rows[0]['score'], 17)

    def test_hn_deleted_old_and_partial_failure(self):
        def get(url):
            if 'topstories' in url:
                return Mock(json=lambda: [1, 2, 3])
            if '/2.json' in url:
                raise ValueError('bad')
            row = dict(id=1, type='story', title='HN', time=self.now.timestamp(), score=50)
            if '/3.json' in url:
                row['dead'] = True
            return Mock(json=lambda: row)
        with patch.object(platforms, 'get', side_effect=get):
            rows, failures = platforms.hackernews({'hn_candidates': 3}, self.now)
        self.assertEqual(len(rows), 1)
        self.assertEqual(failures, ['2'])

    def test_missing_x_credentials_does_not_stop_other_platforms(self):
        with patch.dict('os.environ', {}, clear=True), patch.object(platforms, 'get', return_value=Mock(text='login')), patch.object(platforms, 'hackernews', return_value=([], [])):
            news, status = platforms.collect(self.now)
        self.assertIn('APIFY_TOKEN', status['X 热门'])
        self.assertEqual(status['Hacker News 热门'], '正常')
        html = news_digest.generate_html(news, None, status)
        soup = BeautifulSoup(html, 'html.parser')
        self.assertEqual(len(soup.select('main > .section')), 3)
        self.assertIn('APIFY_TOKEN', soup.get_text())

    def test_no_fake_images_and_five_items_render(self):
        rows = [platforms.item(f'Post {i}', f'https://x.com/demo/status/{i}', self.now, i, 'demo') for i in range(5)]
        soup = BeautifulSoup(news_digest.generate_html({'X 热门': rows}, None), 'html.parser')
        self.assertEqual(len(soup.select('.news-item')), 5)
        self.assertEqual(len(soup.select('.news-item img')), 0)
        self.assertEqual(len(soup.select('.masthead .studio-brand')), 1)
        self.assertTrue(soup.select_one('.studio-logo')['src'].startswith('data:image/png;base64,'))
        self.assertEqual(soup.select_one('.studio-social')['href'], 'https://x.com/johnvauk')
