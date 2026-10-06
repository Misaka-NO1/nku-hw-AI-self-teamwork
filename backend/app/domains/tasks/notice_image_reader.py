"""Bounded screenshot OCR adapters; disabled by default, no model/network writes."""
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile

from app.core.errors import AppError

MAX_IMAGE_BYTES = 2 * 1024 * 1024
MAX_PIXELS = 12_000_000


def image_dimensions(data, content_type):
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise AppError(413, "VALIDATION_ERROR", "截图最多2 MiB")
    width = height = 0
    if content_type == "image/png":
        if len(data) < 33 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
            raise AppError(422, "VALIDATION_ERROR", "PNG文件头不合法")
        width, height = struct.unpack(">II", data[16:24])
    elif content_type == "image/jpeg":
        if not data.startswith(b"\xff\xd8") or not data.endswith(b"\xff\xd9"):
            raise AppError(422, "VALIDATION_ERROR", "JPEG文件头不合法")
        at = 2
        while at + 4 <= len(data):
            if data[at] != 255:
                break
            while at < len(data) and data[at] == 255:
                at += 1
            if at >= len(data):
                break
            marker = data[at]
            at += 1
            if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
                continue
            if at + 2 > len(data):
                break
            size = struct.unpack(">H", data[at:at + 2])[0]
            if size < 2 or at + size > len(data):
                break
            if marker in {0xC0, 0xC1, 0xC2} and size >= 8:
                height, width = struct.unpack(">HH", data[at + 3:at + 7])
                break
            at += size
    else:
        raise AppError(415, "VALIDATION_ERROR", "目前只支持PNG/JPEG单张截图，PDF尚不支持")
    if not 1 <= width <= 4096 or not 1 <= height <= 4096 or width * height > MAX_PIXELS:
        raise AppError(422, "VALIDATION_ERROR", "截图尺寸无效、超4096边长或1200万像素")
    return width, height


class ScreenshotReader:
    def __init__(self, settings):
        self.settings = settings

    def read(self, data, content_type):
        width, height = image_dimensions(data, content_type)
        backend = self.settings.notice_ocr_backend
        if backend == "disabled":
            raise AppError(503, "DEPENDENCY_UNAVAILABLE", "截图OCR尚未配置，可先粘贴通知文字", True)
        suffix = ".png" if content_type == "image/png" else ".jpg"
        with tempfile.TemporaryDirectory(prefix="notice-ocr-") as folder:
            image = Path(folder) / ("source" + suffix)
            image.write_bytes(data)
            if backend == "windows":
                if os.name != "nt":
                    raise AppError(503, "DEPENDENCY_UNAVAILABLE", "Windows OCR仅适用于本机Windows", True)
                executable = Path(os.environ.get("WINDIR", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
                script = Path(__file__).with_name("windows_notice_ocr.ps1")
                # Execute our fixed local commands without changing the host's
                # script execution policy. The path is data via a private env
                # variable, never interpolated into PowerShell source code.
                source = "$ImagePath = $env:NOTICE_OCR_INPUT\n" + script.read_text(encoding="utf-8").split("\n", 1)[1]
                command = [str(executable), "-NoProfile", "-NonInteractive", "-Command", source]
            else:
                executable = Path(self.settings.notice_ocr_command)
                if not executable.is_absolute() or not executable.is_file():
                    raise AppError(503, "DEPENDENCY_UNAVAILABLE", "需配置绝对路径的Tesseract OCR程序", True)
                command = [str(executable), str(image), "stdout", "-l", "chi_sim+eng", "--psm", "6"]
            try:
                environment = os.environ.copy()
                environment["NOTICE_OCR_INPUT"] = str(image)
                result = subprocess.run(command, capture_output=True, timeout=25, check=False,
                                        env=environment,
                                        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                if result.returncode != 0 or len(result.stdout) > 131072:
                    raise ValueError("OCR failed")
                text = result.stdout.decode("utf-8-sig").strip()
                if backend == "windows":
                    text = json.loads(text)["text"]
                if not isinstance(text, str) or not text.strip() or len(text) > 20000:
                    raise ValueError("OCR unreadable")
            except (OSError, subprocess.TimeoutExpired, ValueError, KeyError):
                raise AppError(422, "VALIDATION_ERROR", "截图无法可靠读取，请换清晰截图或粘贴文字") from None
        raw_text = text
        # Windows inserts segmentation spaces around Chinese words. Remove
        # only those separators; never join spaced digits or repair numerals.
        text = re.sub(r"(?<=[\u4e00-\u9fff])\s+|\s+(?=[\u4e00-\u9fff])", "", text)
        return {"source_text": text, "raw_ocr_text": raw_text,
                "document_sha256": hashlib.sha256(data).hexdigest(),
                "source_kind": "ocr", "width": width, "height": height,
                "input_coverage": {"total_pages": 1, "processed_pages": [1], "unread_pages": [],
                                   "ocr_accuracy": "unknown"},
                "limitations": ["OCR可能错字或错数字；需核对截图及逐字段确认关键时间", "仅单张截图；PDF未支持"]}


def require_ocr_review(batch):
    for item in batch["items"]:
        needs = item["notice"]["needs_confirmation"]
        required = ["ocr_review", "source_review"] + (["due_time", "estimated_minutes", "earliest_start"]
                    if item["kind"] == "deadline_feasibility" else ["event_time"])
        item["notice"]["needs_confirmation"] = list(dict.fromkeys(needs + required))
    batch["limitations"].append("截图OCR结果须明确核对原图，并补充确认关键字段后才能计算")
    return batch
