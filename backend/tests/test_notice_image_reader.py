import struct
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.core.config import Settings
from app.core.errors import AppError
from app.domains.tasks.notice_image_reader import image_dimensions, ScreenshotReader


def png(width=100, height=100):
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", width, height) + b"\0" * 9


@pytest.mark.parametrize("data,mime,status", [(b"x", "image/png", 422), (png(0), "image/png", 422),
    (png(4097), "image/png", 422), (png(4000, 4000), "image/png", 422),
    (b"x" * (2 * 1024 * 1024 + 1), "image/png", 413), (b"%PDF", "application/pdf", 415)],
    ids=["bad-header", "zero-size", "wide-image", "too-many-pixels", "oversized-file", "unsupported-pdf"])
def test_bounded_image_input(data, mime, status):
    with pytest.raises(AppError) as result:
        image_dimensions(data, mime)
    assert result.value.status_code == status


def test_jpeg_dimensions_without_trusting_filename():
    jpeg = b"\xff\xd8\xff\xc0" + struct.pack(">H", 8) + b"\x08" + struct.pack(">HH", 200, 300) + b"\x01\xff\xd9"
    assert image_dimensions(jpeg, "image/jpeg") == (300, 200)


def test_disabled_engine_does_not_start_a_process():
    with patch("subprocess.run") as run:
        with pytest.raises(AppError) as result:
            ScreenshotReader(Settings(_env_file=None)).read(png(), "image/png")
        assert result.value.status_code == 503
        run.assert_not_called()
