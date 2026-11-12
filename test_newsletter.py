"""Email subscription: masthead link, email rendering and send behaviour (no network)."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock

import newsletter

CONFIG = {'buttondown_username': 'demo', 'site_url': 'https://example.com/site'}
EDITION = '''<header class="masthead"><div class="header-info"><span class="date">2026年11月12日</span>
<span class="issue">第 12 期</span></div><div class="ornament-bottom"></div></header>
<div class="studio-brand"><a class="studio-logo-link" href="https://x.com/johnvauk"></a>
<a class="studio-social" href="https://x.com/johnvauk">@johnvauk</a></div>
<div class="section" id="a"><h3 class="section-title">AI 与科技</h3><div class="section-grid">
<div class="news-item"><img src="data:image/png;base64,AAAA"><div class="news-content"><h4>标题 &lt;一&gt;</h4>
<p class="news-meta">来源 · 积分 5</p><p>摘要内容</p><a href="https://news.example/1?a=1&amp;b=2">详细阅读 →</a></div></div>
<div class="news-item"><div class="news-content"><h4>坏链接</h4><p>x</p><a href="javascript:alert(1)">详细阅读 →</a></div></div>
</div></div>'''


class NewsletterTests(unittest.TestCase):
    def test_subscribe_link_inserted_once_in_masthead(self):
        once = newsletter.add_subscribe_link(EDITION, CONFIG)
        self.assertIn('href="https://buttondown.com/demo"', once)
        self.assertNotIn('subscribe-bar', once)
        self.assertLess(once.index('subscribe-corner'), once.index('studio-social'))
        self.assertEqual(newsletter.add_subscribe_link(once, CONFIG), once)

    def test_email_contains_headlines_escaped_links_and_edition_url(self):
        subject, body = newsletter.build_email(EDITION, '2026-11-12', CONFIG)
        self.assertEqual(subject, '视野日报 · 2026年11月12日 · 第 12 期')
        self.assertIn('https://example.com/site/digests/2026-11-12.html', body)
        self.assertIn('标题 &lt;一&gt;', body)
        self.assertIn('https://news.example/1?a=1&amp;b=2', body)
        self.assertNotIn('javascript:', body)
        self.assertNotIn('data:image', body)
        self.assertNotIn('来源 · 积分', body)

    def test_empty_edition_is_rejected(self):
        with self.assertRaises(ValueError):
            newsletter.build_email('<html></html>', '2026-11-12', CONFIG)

    def _edition_file(self):
        path = Path(tempfile.mkdtemp()) / '2026-11-12.html'
        path.write_text(EDITION, encoding='utf-8')
        return path

    def test_send_posts_to_buttondown_with_key_and_idempotent_slug(self):
        session = MagicMock()
        session.post.return_value = MagicMock(status_code=201)
        result = newsletter.send_edition(self._edition_file(), 'secret', CONFIG, session)
        self.assertEqual(result, 'sent')
        _, kwargs = session.post.call_args
        self.assertEqual(kwargs['headers'], {'Authorization': 'Token secret', 'X-Buttondown-Live-Dangerously': 'true'})
        self.assertEqual(kwargs['json']['slug'], 'daily-2026-11-12')
        self.assertEqual(kwargs['json']['status'], 'about_to_send')

    def test_missing_key_skips_without_network(self):
        session = MagicMock()
        self.assertEqual(newsletter.send_edition(self._edition_file(), '', CONFIG, session), 'skipped')
        session.post.assert_not_called()

    def test_conflict_is_treated_as_already_sent_and_errors_raise(self):
        session = MagicMock()
        session.post.return_value = MagicMock(status_code=409)
        self.assertEqual(newsletter.send_edition(self._edition_file(), 'k', CONFIG, session), 'duplicate')
        failing = MagicMock(status_code=401)
        failing.raise_for_status.side_effect = RuntimeError('401')
        session.post.return_value = failing
        with self.assertRaises(RuntimeError):
            newsletter.send_edition(self._edition_file(), 'k', CONFIG, session)

    def test_default_send_only_targets_todays_edition(self):
        folder = Path(tempfile.mkdtemp())
        today = datetime(2026, 11, 12, 4, 12, tzinfo=timezone(timedelta(hours=8)))
        self.assertIsNone(newsletter.todays_edition(folder, today))
        (folder / '2026-11-11.html').write_text(EDITION, encoding='utf-8')
        self.assertIsNone(newsletter.todays_edition(folder, today))
        (folder / '2026-11-12.html').write_text(EDITION, encoding='utf-8')
        self.assertEqual(newsletter.todays_edition(folder, today).name, '2026-11-12.html')

    def test_backfill_updates_archives_once(self):
        folder = Path(tempfile.mkdtemp())
        (folder / '2026-11-12.html').write_text(EDITION, encoding='utf-8')
        self.assertEqual(newsletter.backfill(folder, CONFIG), ['2026-11-12.html'])
        self.assertEqual(newsletter.backfill(folder, CONFIG), [])

    def test_template_workflow_and_readme_are_wired(self):
        root = Path(__file__).parent
        self.assertNotIn('{{SUBSCRIBE}}', (root / 'templates/newspaper.html').read_text(encoding='utf-8'))
        workflow = (root / '.github/workflows/daily-news.yml').read_text(encoding='utf-8')
        self.assertIn('BUTTONDOWN_API_KEY', workflow)
        self.assertGreater(workflow.index('python newsletter.py send'), workflow.index('git push'))
        readme = (root / 'README.md').read_text(encoding='utf-8')
        self.assertIn(newsletter.subscribe_url(), readme)


if __name__ == '__main__':
    unittest.main()
