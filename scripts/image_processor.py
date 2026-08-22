# -*- coding: utf-8 -*-
"""图片文字提取工具：使用 pytesseract + PIL 从图片中提取文字（默认语言 chi_sim+eng）。

依赖：pip install pillow pytesseract，并安装 Tesseract OCR（含简体中文语言包）。
若依赖缺失，脚本会输出清晰的中文安装提示，而不会崩溃。
脚本会自动探测 Tesseract 的常见安装位置，无需手动配置 PATH。
"""
import argparse
import os
import shutil
import sys

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import pytesseract
except ImportError:
    pytesseract = None

# Tesseract 常见安装位置（Windows / macOS / Linux）
_TESSERACT_CANDIDATES = [
    "C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
    "C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe",
    "C:\\Users\\{}\\AppData\\Local\\Programs\\Tesseract-OCR\\tesseract.exe",
    "/usr/bin/tesseract",
    "/usr/local/bin/tesseract",
]


def _find_tesseract_cmd():
    """探测 tesseract 可执行文件路径；找不到返回 None。"""
    cmd = shutil.which("tesseract")
    if cmd:
        return cmd
    username = os.environ.get("USERNAME", "")
    for candidate in _TESSERACT_CANDIDATES:
        candidate = candidate.format(username)
        if os.path.exists(candidate):
            return candidate
    return None


def _preprocess(image):
    """OCR 前预处理：灰度 → 放大（小图 2 倍）→ 自动对比度 → 增强对比度，提升识别率。"""
    try:
        from PIL import ImageOps, ImageEnhance
        gray = image.convert("L")
        w, h = gray.size
        if min(w, h) < 1200:
            gray = gray.resize((w * 2, h * 2), Image.LANCZOS)
        gray = ImageOps.autocontrast(gray, cutoff=1)
        gray = ImageEnhance.Contrast(gray).enhance(1.5)
        return gray
    except Exception:
        return image


def extract_text(image_path, lang="chi_sim+eng"):
    """从图片提取文字。返回 (text, error) 元组，error 为空字符串表示成功。"""
    if not os.path.exists(image_path):
        return "", "[错误] 图片文件不存在：{}".format(image_path)
    if Image is None or pytesseract is None:
        msg = (
            "[错误] 缺少 OCR 依赖库。\n"
            "请先安装 Python 依赖：\n"
            "    pip install pillow pytesseract\n"
            "并安装 Tesseract OCR 及简体中文（chi_sim）语言包：\n"
            "    https://github.com/tesseract-ocr/tessdata\n"
        )
        return "", msg
    tesseract_cmd = _find_tesseract_cmd()
    if not tesseract_cmd:
        msg = (
            "[错误] 未找到 Tesseract OCR 引擎。\n"
            "请安装 Tesseract OCR（Windows 推荐：winget install UB-Mannheim.TesseractOCR），\n"
            "并确保包含简体中文语言包 chi_sim.traineddata。\n"
            "装好后重新运行本脚本。"
        )
        return "", msg
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    try:
        image = Image.open(image_path)
        image = _preprocess(image)
        text = pytesseract.image_to_string(image, lang=lang)
        return text.strip(), ""
    except Exception as e:
        return "", "[错误] OCR 处理失败：{}".format(e)


def main():
    parser = argparse.ArgumentParser(description="从图片中提取文字（OCR）")
    parser.add_argument("image", help="图片文件路径")
    parser.add_argument("--lang", default="chi_sim+eng", help="OCR 语言，默认 chi_sim+eng")
    args = parser.parse_args()

    text, error = extract_text(args.image, args.lang)
    print("=" * 50)
    print("OCR 文字提取结果")
    print("=" * 50)
    if error:
        print(error)
        return 1
    if not text:
        print("未提取到文字内容（图片可能不包含清晰文本）。")
        return 0
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
