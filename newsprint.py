"""Render article photographs as colored, slightly faded newspaper prints."""
import base64
import io
import logging
import math

import requests
from PIL import Image, ImageChops, ImageEnhance, ImageFilter, ImageOps

MAX_DOWNLOAD_BYTES = 8 * 1024 * 1024
MAX_IMAGE_PIXELS = 20_000_000
MAX_OUTPUT_SIZE = (1000, 1000)
SCREEN_CELL = 8


def _screen_thresholds():
    center = (SCREEN_CELL - 1) / 2
    order = sorted(
        range(SCREEN_CELL * SCREEN_CELL),
        key=lambda n: ((n % SCREEN_CELL - center) ** 2
                       + (n // SCREEN_CELL - center) ** 2, n),
    )
    thresholds = [0] * len(order)
    for rank, index in enumerate(order):
        thresholds[index] = (rank + 0.5) * 255 / len(order)
    return thresholds


_THRESHOLDS = _screen_thresholds()


def _screen_ink(ink, angle, offset):
    high = ink.resize((ink.width * 2, ink.height * 2), Image.Resampling.LANCZOS)
    cosine, sine = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    x_cosine = [x * cosine for x in range(high.width)]
    x_sine = [x * sine for x in range(high.width)]
    raw = high.tobytes()
    rows = []
    for y in range(high.height):
        y_sine, y_cosine = y * sine, y * cosine
        row = raw[y * high.width:(y + 1) * high.width]
        rows.append(bytes(
            255 if tone > _THRESHOLDS[
                (int(x_sine[x] + y_cosine) % SCREEN_CELL) * SCREEN_CELL
                + int(x_cosine[x] - y_sine) % SCREEN_CELL
            ] else 0
            for x, tone in enumerate(row)
        ))
    dots = Image.frombytes('L', high.size, b''.join(rows)).resize(ink.size, Image.Resampling.LANCZOS)
    # Keep photographic detail between dots and offset each ink plate slightly.
    plate = Image.blend(dots, ink, 0.45)
    return plate.transform(
        plate.size, Image.Transform.AFFINE,
        (1, 0, offset[0], 0, 1, offset[1]),
        resample=Image.Resampling.BICUBIC, fillcolor=0,
    )


def image_to_newsprint_data_url(data):
    with Image.open(io.BytesIO(data)) as source:
        if source.width * source.height > MAX_IMAGE_PIXELS:
            raise ValueError('image is too large')
        source = ImageOps.exif_transpose(source).convert('RGBA')
        source.thumbnail(MAX_OUTPUT_SIZE, Image.Resampling.LANCZOS)
        source = Image.alpha_composite(Image.new('RGBA', source.size, 'white'), source).convert('RGB')

    source = ImageEnhance.Color(source).enhance(0.72)
    source = ImageEnhance.Contrast(source).enhance(0.94)
    source = source.filter(ImageFilter.GaussianBlur(0.18))
    c, m, y = [ImageOps.invert(channel) for channel in source.split()]
    k = ImageChops.darker(ImageChops.darker(c, m), y).point(lambda v: round(v * 0.35))
    c, m, y = [ImageChops.subtract(channel, k) for channel in (c, m, y)]
    plates = [
        _screen_ink(ink, angle, shift)
        for ink, angle, shift in [
            (c, 15, (0.65, -0.25)), (m, 75, (-0.55, 0.25)),
            (y, 0, (0.15, 0.45)), (k, 45, (0, 0)),
        ]
    ]
    printed = Image.merge('CMYK', plates).convert('RGB')
    printed = Image.blend(printed, source, 0.25)
    printed = ImageChops.multiply(printed, Image.new('RGB', printed.size, '#f7efdb'))
    printed = Image.blend(printed, Image.new('RGB', printed.size, '#eee7d5'), 0.045)
    grain = Image.effect_noise(printed.size, 3).convert('RGB')
    printed = ImageChops.add(printed, grain, offset=-128)
    buffer = io.BytesIO()
    printed.save(buffer, format='JPEG', quality=82, optimize=True)
    return 'data:image/jpeg;base64,' + base64.b64encode(buffer.getvalue()).decode('ascii')


def convert_image_url(url, session=requests):
    try:
        with session.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'}, stream=True) as response:
            response.raise_for_status()
            chunks = []
            size = 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > MAX_DOWNLOAD_BYTES:
                    raise ValueError('image download is too large')
                chunks.append(chunk)
        return image_to_newsprint_data_url(b''.join(chunks))
    except (requests.exceptions.RequestException, OSError, ValueError,
            SyntaxError, Image.DecompressionBombError) as exc:
        logging.warning('Newspaper photo conversion failed for %s: %s', url, exc)
        return url
