"""Regression tests for RSS markup breaking the newspaper grid."""
import unittest
from unittest.mock import patch

from bs4 import BeautifulSoup
from feedparser import FeedParserDict

with patch('sys.platform', 'linux'):
    import news_digest


class LayoutTests(unittest.TestCase):
    def test_translation_parser_accepts_spacing_markdown_and_fullwidth_colon(self):
        batch = [{'title': 'Original title', 'summary': 'Original summary'}]
        parsed = news_digest.parse_translation_pairs(
            '**标题 1：** 中文标题\n- 摘要 1：中文摘要', 0, batch)
        self.assertEqual(parsed[0]['title_cn'], '中文标题')
        self.assertEqual(parsed[0]['summary_cn'], '中文摘要')

    def test_translation_parser_accepts_english_labels(self):
        batch = [{'title': 'Original title', 'summary': 'Original summary'}]
        parsed = news_digest.parse_translation_pairs(
            'Title 1: 中文标题\nSummary 1: 中文摘要', 0, batch)
        self.assertEqual(parsed[0]['title_cn'], '中文标题')
        self.assertEqual(parsed[0]['summary_cn'], '中文摘要')

    def test_translation_parser_keeps_missing_pairs_explicit_for_fallback(self):
        batch = [
            {'title': 'First title', 'summary': 'First summary'},
            {'title': 'Second title', 'summary': 'Second summary'},
        ]
        parsed = news_digest.parse_translation_pairs(
            '标题1: 第一条\n摘要1: 第一条摘要', 0, batch)
        self.assertEqual(parsed[0]['title_cn'], '第一条')
        self.assertIsNone(parsed[1]['title_cn'])

    def test_unclosed_summary_cannot_nest_cards_or_sections(self):
        item = {'title': 'First', 'summary': '<!-- SC_OFF --><div class="md"><p>Readable <b>news</b><table><tr><td>tail',
                'link': 'https://example.org/story', 'image': 'https://example.org/photo'}
        with patch('news_digest.convert_image_url', side_effect=lambda url: url):
            page = news_digest.generate_html({'Games': [item, dict(item)], 'Culture': [dict(item)]}, None)
        soup = BeautifulSoup(page, 'html.parser')
        self.assertEqual(len(soup.select('main > .section')), 2)
        self.assertEqual(len(soup.select('.section > .section-grid > .news-item')), 3)
        self.assertEqual(len(soup.select('.news-item .news-item')), 0)
        for summary in soup.select('.news-content > p'):
            self.assertEqual(summary.get_text(), 'Readable news tail')
            self.assertEqual(summary.find_all(), [])

    def test_translated_markup_and_quotes_remain_readable_text(self):
        item = {'title': 'Original', 'summary': 'Original',
                'link': 'https://example.org/?q="news"&page=2', 'image': 'https://example.org/photo'}
        translations = {'translations': {'AI': [{'index': 0, 'title_cn': '<b>标题</b> & 新闻',
                         'summary_cn': '<p>数值 2 < 3 &amp; 5 > 4</p><img src="bad"><script>bad()</script>'}]}}
        with patch('news_digest.convert_image_url', side_effect=lambda url: url):
            page = news_digest.generate_html({'AI': [item]}, translations)
        soup = BeautifulSoup(page, 'html.parser')
        self.assertEqual(soup.select_one('.news-content h4').get_text(), '标题 & 新闻')
        self.assertEqual(soup.select_one('.index-section li').get_text(), '标题 & 新闻')
        self.assertEqual(soup.select_one('.news-content > p').get_text(), '数值 2 < 3 & 5 > 4')
        self.assertEqual(soup.select_one('.news-content > a')['href'], item['link'])
        self.assertEqual(len(soup.select('.news-item img')), 1)
        self.assertIsNone(soup.find('script'))

    def test_feed_summary_is_cleaned_before_truncation(self):
        entry = FeedParserDict(title='Headline', link='https://example.org/story',
                               summary='<div data-long="' + 'x' * 900 + '"><p>Actual news</p></div>')
        with patch.dict(news_digest.NEWS_SOURCES, {'AI': ['https://example.org/feed']}, clear=True), \
                patch('news_digest.feedparser.parse', return_value=FeedParserDict(entries=[entry])), \
                patch('news_digest.extract_image_from_url', return_value='photo'):
            result = news_digest.fetch_news()
        self.assertEqual(result['AI'][0]['summary'], 'Actual news')

    def test_literal_html_examples_survive_feed_to_render(self):
        entry = FeedParserDict(title='Use &lt;div&gt; in HTML', link='https://example.org/story',
                               summary='<p>Use <code>&lt;div&gt;content&lt;/div&gt;</code> in HTML.</p>')
        with patch.dict(news_digest.NEWS_SOURCES, {'AI': ['https://example.org/feed']}, clear=True), \
                patch('news_digest.feedparser.parse', return_value=FeedParserDict(entries=[entry])), \
                patch('news_digest.extract_image_from_url', return_value='photo'), \
                patch('news_digest.convert_image_url', side_effect=lambda url: url):
            news = news_digest.fetch_news()
            page = news_digest.generate_html(news, None)
        soup = BeautifulSoup(page, 'html.parser')
        self.assertEqual(soup.select_one('.news-content > p').get_text(), 'Use <div>content</div> in HTML.')
        self.assertEqual(soup.select_one('.news-content h4').get_text(), 'Use <div> in HTML')
        self.assertEqual(soup.select_one('.index-section li').get_text(), 'Use <div> in HTML')
        self.assertEqual(soup.select_one('.news-content > p').find_all(), [])

    def test_failed_translation_keeps_literal_code_examples(self):
        from unittest.mock import Mock
        item = {'title': 'Use <div> in HTML', 'summary': 'Use <div>content</div> in HTML.',
                '_text_is_plain': True, 'link': 'https://example.org/story', 'image': 'photo'}
        client = Mock()
        client.chat.completions.create.side_effect = RuntimeError('offline')
        with patch('news_digest.OpenAI', return_value=client), \
                patch('news_digest.convert_image_url', side_effect=lambda url: url):
            news = {'AI': [item]}
            result = news_digest.translate_and_select_top_news(news)
            page = news_digest.generate_html(news, result)
        soup = BeautifulSoup(page, 'html.parser')
        self.assertEqual(soup.select_one('.news-content > p').get_text(), 'Use <div>content</div> in HTML.')
        self.assertEqual(soup.select_one('.news-content h4').get_text(), 'Use <div> in HTML')


if __name__ == '__main__':
    unittest.main()
