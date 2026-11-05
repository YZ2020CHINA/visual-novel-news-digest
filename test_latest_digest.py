"""Latest-edition links must advance with successfully saved newspapers."""
from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

with patch('sys.platform', 'linux'):
    import news_digest


class LatestDigestTests(unittest.TestCase):
    def test_save_creates_archive_and_complete_latest_copy(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.object(news_digest, '__file__', str(Path(root) / 'news_digest.py')):
                with patch.object(news_digest, 'datetime') as clock:
                    clock.now.return_value = datetime(2026, 11, 5)
                    saved = news_digest.save_html('<html>new edition</html>')
            self.assertEqual(Path(saved).read_text(encoding='utf-8'), '<html>new edition</html>')
            self.assertEqual((Path(root) / 'digests/latest.html').read_text(encoding='utf-8'), '<html>new edition</html>')

    def test_latest_advances_and_older_editions_do_not_replace_it(self):
        with tempfile.TemporaryDirectory() as root:
            with patch.object(news_digest, '__file__', str(Path(root) / 'news_digest.py')):
                with patch.object(news_digest, 'datetime') as clock:
                    for day, text in [(4, 'older'), (5, 'newer'), (4, 'backfill')]:
                        clock.now.return_value = datetime(2026, 11, day)
                        news_digest.save_html(text)
            folder = Path(root) / 'digests'
            self.assertEqual((folder / 'latest.html').read_text(encoding='utf-8'), 'newer')
            self.assertEqual((folder / '2026-11-04.html').read_text(encoding='utf-8'), 'backfill')

    def test_reading_and_download_links_use_stable_latest_path(self):
        root = Path(__file__).parent
        readme = (root / 'README.md').read_text(encoding='utf-8')
        index = (root / 'index.html').read_text(encoding='utf-8')
        self.assertIn('https://yz2020china.github.io/visual-novel-news-digest/digests/latest.html', readme)
        self.assertIn('https://github.com/YZ2020CHINA/visual-novel-news-digest/raw/main/digests/latest.html', readme)
        self.assertNotIn('2026-11-04.html', readme)
        self.assertIn('url=./digests/latest.html', index)
        self.assertIn('href="./digests/latest.html"', index)


if __name__ == '__main__':
    unittest.main()
