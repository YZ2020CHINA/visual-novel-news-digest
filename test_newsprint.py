"""Offline tests for colored newspaper photos and daily HTML integration."""
import base64
import io
import struct
import threading
import unittest
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import Mock, patch

import requests
from PIL import Image, ImageStat

from newsprint import image_to_newsprint_data_url, convert_image_url


def png_bytes(image):
    stream = io.BytesIO()
    image.save(stream, format='PNG')
    return stream.getvalue()


def decoded_image(data_url):
    return Image.open(io.BytesIO(base64.b64decode(data_url.split(',', 1)[1])))


def malformed_png():
    raw = png_bytes(Image.new('RGB', (12, 8), 'navy'))
    payload = b'Note\x00\x01invalid'
    chunk = (struct.pack('>I', len(payload)) + b'zTXt' + payload
             + struct.pack('>I', zlib.crc32(b'zTXt' + payload)))
    return raw[:-12] + chunk + raw[-12:]


class ImageHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/fail':
            self.send_error(403)
            return
        self.send_response(200)
        self.end_headers()
        if self.path == '/invalid':
            self.wfile.write(b'not an image')
        elif self.path == '/metadata':
            self.wfile.write(malformed_png())
        else:
            self.wfile.write(png_bytes(Image.new('RGB', (120, 80), 'navy')))

    def log_message(self, *args):
        pass


class NewsprintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), ImageHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()

    def test_embeds_colored_photo_with_print_texture(self):
        result = image_to_newsprint_data_url(png_bytes(Image.new('RGB', (120, 80), (220, 60, 30))))
        self.assertTrue(result.startswith('data:image/jpeg;base64,'))
        output = decoded_image(result)
        self.assertEqual(output.size, (120, 80))
        self.assertEqual(output.mode, 'RGB')
        means = ImageStat.Stat(output).mean
        self.assertGreater(means[0], means[1] + 30)
        self.assertGreater(len(output.getcolors(output.width * output.height)), 20)

    def test_preserves_light_and_dark_photographic_tones(self):
        source = Image.new('RGB', (120, 80), 'white')
        source.paste((20, 20, 20), (0, 0, 60, 80))
        output = decoded_image(image_to_newsprint_data_url(png_bytes(source)))
        dark = ImageStat.Stat(output.crop((5, 5, 55, 75)).convert('L')).mean[0]
        light = ImageStat.Stat(output.crop((65, 5, 115, 75)).convert('L')).mean[0]
        self.assertGreater(light - dark, 100)

    def test_downloads_and_converts_actual_http_image(self):
        result = convert_image_url(self.base_url + '/image')
        self.assertTrue(result.startswith('data:image/jpeg;base64,'))
        self.assertEqual(decoded_image(result).format, 'JPEG')

    def test_failed_download_preserves_original_url(self):
        session = Mock()
        session.get.side_effect = OSError('offline')
        self.assertEqual(convert_image_url('https://example.org/a.png', session), 'https://example.org/a.png')

    def test_http_failure_falls_back(self):
        url = self.base_url + '/fail'
        self.assertEqual(convert_image_url(url), url)

    def test_invalid_image_falls_back(self):
        url = self.base_url + '/invalid'
        self.assertEqual(convert_image_url(url), url)

    def test_corrupt_png_metadata_falls_back(self):
        # This valid image with broken ancillary metadata used to abort a digest.
        with self.assertRaises(SyntaxError):
            Image.open(io.BytesIO(malformed_png())).load()
        url = self.base_url + '/metadata'
        self.assertEqual(convert_image_url(url), url)

    def test_download_limit_falls_back(self):
        url = self.base_url + '/image'
        with patch('newsprint.MAX_DOWNLOAD_BYTES', 10):
            self.assertEqual(convert_image_url(url), url)

    def test_timeout_falls_back(self):
        session = Mock()
        session.get.side_effect = requests.exceptions.Timeout('timeout')
        self.assertEqual(convert_image_url('https://example.org/slow', session), 'https://example.org/slow')

    def test_preserves_aspect_ratio(self):
        source = Image.new('RGB', (1200, 600), 'navy')
        output = decoded_image(image_to_newsprint_data_url(png_bytes(source)))
        self.assertEqual(output.size, (1000, 500))

    def test_transparent_pixels_leave_light_paper(self):
        output = decoded_image(image_to_newsprint_data_url(png_bytes(Image.new('RGBA', (100, 100), (0, 0, 0, 0)))))
        self.assertGreater(min(ImageStat.Stat(output).mean), 200)

    def test_extreme_portrait_is_bounded(self):
        output = decoded_image(image_to_newsprint_data_url(png_bytes(Image.new('RGB', (2, 20000), 'navy'))))
        self.assertLessEqual(max(output.size), 1000)

    def test_pixel_limit_rejects_before_rendering(self):
        with patch('newsprint.MAX_IMAGE_PIXELS', 100):
            with self.assertRaises(ValueError):
                image_to_newsprint_data_url(png_bytes(Image.new('RGB', (20, 20))))

    def test_respects_camera_orientation(self):
        stream = io.BytesIO()
        exif = Image.Exif()
        exif[274] = 6
        Image.new('RGB', (120, 60), 'navy').save(stream, format='JPEG', exif=exif)
        output = decoded_image(image_to_newsprint_data_url(stream.getvalue()))
        self.assertEqual(output.size, (60, 120))


class DigestIntegrationTests(unittest.TestCase):
    def setUp(self):
        # Match Linux production without replacing unittest's Windows streams.
        with patch('sys.platform', 'linux'):
            import news_digest
        self.news_digest = news_digest
        self.sample = {
            'title': 'A "quoted" headline', 'summary': 'Sample summary',
            'link': 'https://example.org/story', 'image': 'https://example.org/image.png',
        }

    def test_digest_embeds_photos_and_reuses_converted_images(self):
        data_url = image_to_newsprint_data_url(png_bytes(Image.new('RGB', (100, 60), 'navy')))
        with patch('news_digest.convert_image_url', return_value=data_url) as convert:
            html = self.news_digest.generate_html({'AI与科技': [self.sample, dict(self.sample)]}, None)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        images = soup.select('.news-item img')
        self.assertEqual(len(images), 2)
        self.assertEqual(images[0]['src'], data_url)
        self.assertEqual(images[0]['alt'], self.sample['title'])
        self.assertIn('newsprint-photo', images[0].get('class', []))
        self.assertIn('object-fit: contain', html)
        self.assertNotIn('{{', html)
        convert.assert_called_once_with(self.sample['image'])

    def test_digest_survives_failed_image_conversion(self):
        with patch('newsprint.requests.get', side_effect=requests.exceptions.Timeout('offline')):
            html = self.news_digest.generate_html({'AI与科技': [self.sample]}, None)
        from bs4 import BeautifulSoup
        image = BeautifulSoup(html, 'html.parser').select_one('.news-item img')
        self.assertEqual(image['src'], self.sample['image'])
        self.assertNotIn('newsprint-photo', image.get('class', []))


if __name__ == '__main__':
    unittest.main()
