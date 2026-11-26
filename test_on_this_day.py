"""No-network regression coverage for the daily history feature and delivery."""
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import requests
from bs4 import BeautifulSoup

import on_this_day as history
import newsletter
with patch('sys.platform', 'linux'):
    import news_digest

DAY_PAGE = '''<h2>目录</h2><li>1999年：虚假图书馆开放</li>
<h2><span>大事记</span><span class="mw-editsection">[编辑]</span></h2><h3>20世纪</h3>
<ul><li>1949年：印度制宪会议通过宪法。<sup>[1]</sup></li>
<li>1942年：电影《卡萨布兰卡》在纽约首映。</li>
<li>1980年：首家公共图书馆开放。</li>
<li>2026年：公共图书馆开放。</li><li>2030年：公共图书馆开放。</li>
<li>1940年：战争中轰炸医院。</li><li>1950年：第一个政党成立。</li>
<li>1960年：博物馆开放。<ul><li>1961年：假事件图书馆开放。</li></ul></li></ul>
<h2>出生</h2><ul><li>1900年：某位大学创办人出生。</li></ul>
<h2>逝世</h2><ul><li>1901年：某位人权运动领袖逝世。</li></ul>'''


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.today = datetime(2026, 11, 26, 6, tzinfo=history.BEIJING_TZ)

    def test_beijing_date_handles_utc_yesterday_and_leap_day(self):
        now = datetime(2026, 11, 25, 18, tzinfo=timezone.utc)
        result = history.get_on_this_day(now, fetch_remote=False)
        self.assertEqual(result['date'], '2026-11-26')
        self.assertTrue(all((e['month'], e['day']) == (11, 26) for e in result['events']))
        session = Mock()
        session.get.return_value.json.return_value = {'parse': {'text': '<h2>大事记</h2><ul><li>2000年：公共图书馆开放。</li></ul>'}}
        leap = history.get_on_this_day(datetime(2024, 2, 29), session=session)
        self.assertEqual(leap['date'], '2024-02-29')
        self.assertEqual(session.get.call_args.kwargs['params']['page'], '2月29日')
        self.assertEqual(leap['events'][0]['day'], 29)

    def test_parse_only_events_earlier_years_without_birthdays_or_deaths(self):
        rows = history.parse_day_page(DAY_PAGE, self.today)
        self.assertEqual([e['year'] for e in rows], [1949, 1942, 1980, 1960])
        self.assertNotIn('[1]', rows[0]['summary'])
        self.assertTrue(all(e['source_kind'] == 'index' and e['source_url'].startswith('https://') for e in rows))

    def test_topics_include_welfare_science_education_rights_justice_and_art(self):
        for text, topic in [
            ('联合国儿童基金会成立。', '关爱与社会福利'),
            ('首次成功进行心脏移植。', '医疗与公共卫生'),
            ('免费义务教育法通过。', '教育与知识普及'),
            ('废除奴隶制的法案通过。', '自由、平等与人权'),
            ('妇女获得平等投票权的法案生效。', '自由、平等与人权'),
            ('世界上第一条公共铁路开通。', '科技与生活改善'),
            ('电影首次上映。', '文化艺术与文明'),
            ('英国天文学家发现首颗脉冲星。', '科技与生活改善'),
            ('纽伦堡法庭开始审判纳粹战犯。', '正义、审判与追责'),
            ('国际法庭裁定种族灭绝罪成立。', '正义、审判与追责'),
        ]:
            with self.subTest(text=text):
                self.assertEqual(history.classify_event(text), topic)
        for text in ['轰炸医院，造成大量伤亡。', '首枚洲际弹道导弹发射成功。',
                     '宣布剥夺公民投票权。', '宣布禁止自由选举。', '某政党成立。', '名人出生。']:
            with self.subTest(text=text):
                self.assertIsNone(history.classify_event(text))

    def test_reviewed_sources_first_deduplicate_and_keep_topic_diversity(self):
        local = history.curated_events(self.today)
        selected = history.select_events(local, history.parse_day_page(DAY_PAGE, self.today))
        self.assertEqual(len(selected), 3)
        self.assertEqual(len({e['topic'] for e in selected}), 3)
        self.assertTrue(all(e['source_kind'] == 'primary' for e in selected))
        self.assertEqual(sum(e['year'] == 1949 for e in selected), 1)

    def test_november_20_justice_preserves_trial_stage(self):
        result = history.get_on_this_day(datetime(2026, 11, 20), fetch_remote=False)
        event = next(e for e in result['events'] if e['topic'] == '正义、审判与追责')
        self.assertEqual(event['year'], 1945)
        self.assertIn('开庭', event['summary'])

    def test_failed_or_malformed_lookup_keeps_local_or_explicit_notice(self):
        for failure in [requests.Timeout('offline'), requests.HTTPError('429'), KeyError('parse')]:
            with self.subTest(failure=failure):
                session = Mock()
                session.get.side_effect = failure
                result = history.get_on_this_day(self.today, session=session)
                self.assertEqual(result['status'], 'unavailable')
                self.assertEqual(len(result['events']), 3)
                self.assertIn('在线历史检索暂不可用', history.render_history(result))
        session = Mock()
        session.get.return_value.json.return_value = {'error': {'info': 'missing'}}
        result = history.get_on_this_day(datetime(2026, 2, 1), session=session)
        self.assertFalse(result['events'])
        self.assertIn('暂缺', history.render_history(result))

    def test_renderer_escapes_content_and_rejects_unsafe_source_urls(self):
        event = dict(year=2000, month=11, day=26, topic='<tag>', summary='<script>alert(1)</script>',
                     source_url='javascript:alert(1)', source_name='<img>', source_kind='index')
        html = history.render_history(dict(events=[event], status='ok'))
        soup = BeautifulSoup(html, 'html.parser')
        self.assertIsNone(soup.find('script'))
        self.assertIsNone(soup.find('a'))
        self.assertEqual(soup.select_one('time')['datetime'], '2000-11-26')
        self.assertIn('CC BY-SA', html)

    def test_html_and_email_share_footer_and_sources_after_news(self):
        result = history.get_on_this_day(self.today, fetch_remote=False)
        item = dict(title='测试新闻', summary='正文', link='https://example.org/news', image='')
        page = news_digest.generate_html({'AI与科技': [item]}, None,
                                        history_result=result, edition_time=self.today)
        soup = BeautifulSoup(page, 'html.parser')
        self.assertEqual(len(soup.select('footer .history-on-this-day .history-event')), 3)
        self.assertNotIn('今日诞辰', page)
        self.assertNotIn('{{', page)
        self.assertEqual(len(soup.select('main > .section')), 1)
        _, mail = newsletter.build_email(page, '2026-11-26', {'site_url': 'https://example.org'})
        self.assertLess(mail.index('测试新闻'), mail.index('历史上的今天'))
        self.assertIn('1949年11月26日', mail)
        self.assertIn('mygov.in', mail)
        self.assertNotIn('data:image', mail)

    def test_empty_history_section_is_always_present_in_html_and_email(self):
        result = dict(date='2026-02-01', events=[], status='unavailable')
        item = dict(title='新闻', summary='正文', link='https://example.org', image='')
        page = news_digest.generate_html({'AI': [item]}, None, history_result=result)
        _, mail = newsletter.build_email(page, '2026-02-01', {'site_url': 'https://example.org'})
        self.assertIn('历史上的今天', page)
        self.assertIn('历史上的今天', mail)
        self.assertIn('暂缺', mail)

    def test_curated_data_has_valid_dates_sources_and_known_topics(self):
        rows = json.loads(history.CURATED_PATH.read_text(encoding='utf-8'))
        for row in rows:
            datetime(row['year'], row['month'], row['day'])
            self.assertEqual(history.safe_url(row['source_url']), row['source_url'])
            self.assertIn(row['topic'], set(history.TOPICS) | {'正义、审判与追责'})
            self.assertTrue(row['match_terms'])

    def test_production_main_fetches_history_once_and_passes_one_edition_date(self):
        item = dict(title='新闻', summary='正文', link='https://example.org', image='')
        candidates = {name: [dict(item)] for name in list(news_digest.NEWS_SOURCES) + list(news_digest.PLATFORMS)}
        with patch.object(news_digest, 'load_history', return_value=set()), \
             patch.object(news_digest, 'collect_platforms', return_value=({}, {})), \
             patch.object(news_digest, 'fetch_news', return_value=candidates), \
             patch.object(news_digest, 'select_news', return_value=candidates), \
             patch.object(news_digest, 'extract_image_from_url', return_value=''), \
             patch.object(news_digest, 'translate_and_select_top_news', return_value={}), \
             patch.object(news_digest, 'get_on_this_day', return_value={'date': 'test', 'events': [], 'status': 'ok'}) as fetch, \
             patch.object(news_digest, 'generate_html', return_value='html') as render, \
             patch.object(news_digest, 'save_html') as save, \
             patch.object(news_digest, 'save_history'):
            news_digest.main()
        fetch.assert_called_once()
        self.assertEqual(render.call_args.kwargs['edition_time'], fetch.call_args.args[0])
        self.assertEqual(save.call_args.kwargs['edition_time'], fetch.call_args.args[0])


if __name__ == '__main__':
    unittest.main()
