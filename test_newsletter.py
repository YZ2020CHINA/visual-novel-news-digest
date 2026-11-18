"""Email subscription: masthead link, email rendering and send behaviour (no network)."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

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
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / '2026-11-12.html'
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

    def test_early_edition_schedules_0800_beijing_even_if_now_is_utc_yesterday(self):
        session = MagicMock()
        session.post.return_value.status_code = 201
        now = datetime(2026, 11, 11, 20, 12, tzinfo=timezone.utc)
        result = newsletter.send_edition(self._edition_file(), 'k', CONFIG, session, schedule=True, now=now)
        payload = session.post.call_args.kwargs['json']
        self.assertEqual(result, 'scheduled')
        self.assertEqual(payload['slug'], 'daily-2026-11-12')
        self.assertEqual(payload['status'], 'scheduled')
        self.assertEqual(payload['publish_date'], '2026-11-12T00:00:00+00:00')

    def test_due_or_late_edition_is_queued_for_immediate_delivery(self):
        session = MagicMock()
        session.post.return_value.status_code = 201
        for hour in (8, 11):
            with self.subTest(hour=hour):
                now = datetime(2026, 11, 12, hour, tzinfo=newsletter.BEIJING_TZ)
                result = newsletter.send_edition(self._edition_file(), 'k', CONFIG, session, schedule=True, now=now)
                payload = session.post.call_args.kwargs['json']
                self.assertEqual(result, 'sent')
                self.assertEqual(payload['status'], 'about_to_send')
                self.assertNotIn('publish_date', payload)

    def test_schedule_rejects_a_stale_edition_without_sending(self):
        session = MagicMock()
        now = datetime(2026, 11, 13, 4, tzinfo=newsletter.BEIJING_TZ)
        with self.assertRaisesRegex(ValueError, '当天'):
            newsletter.send_edition(self._edition_file(), 'k', CONFIG, session, schedule=True, now=now)
        session.post.assert_not_called()

    def test_duplicate_schedule_and_late_retry_use_the_same_slug(self):
        session = MagicMock()
        session.post.return_value.status_code = 409
        path = self._edition_file()
        for hour in (4, 11):
            now = datetime(2026, 11, 12, hour, tzinfo=newsletter.BEIJING_TZ)
            self.assertEqual(newsletter.send_edition(path, 'k', CONFIG, session, schedule=True, now=now), 'duplicate')
        self.assertEqual([call.kwargs['json']['slug'] for call in session.post.call_args_list], ['daily-2026-11-12'] * 2)

    def test_automatic_cli_reports_missing_edition_or_key(self):
        with patch('newsletter.todays_edition', return_value=None), patch('newsletter.send_edition') as send:
            self.assertEqual(newsletter.main(['newsletter.py', 'schedule']), 1)
            send.assert_not_called()
        path = self._edition_file()
        with patch('newsletter.todays_edition', return_value=path), patch('newsletter.send_edition', return_value='skipped') as send:
            self.assertEqual(newsletter.main(['newsletter.py', 'schedule']), 1)
            self.assertEqual(send.call_args.args, (path,))
            self.assertTrue(send.call_args.kwargs['schedule'])

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
        self.assertGreater(workflow.index('python newsletter.py schedule'), workflow.index('git push'))
        delivery = workflow.split('- name: 预约 08:00 邮件推送或当天补发', 1)[1]
        self.assertNotIn('steps.guard.outputs.skip', delivery)
        self.assertIn('github.event.repository.default_branch', delivery)
        readme = (root / 'README.md').read_text(encoding='utf-8')
        self.assertIn(newsletter.subscribe_url(), readme)


if __name__ == '__main__':
    unittest.main()
