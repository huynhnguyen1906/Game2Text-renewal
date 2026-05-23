from __future__ import annotations

import re
import pytesseract
from PIL import Image

from native.config.service import read_value
from native.core import paths


HORIZONTAL_TEXT_DETECTION = 6
VERTICAL_TEXT_DETECTION = 5
MIN_ENGLISH_WORD_CONFIDENCE = 35

CJK_REGEX = re.compile(r'[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uff66-\uff9f]+')
CONTROL_REGEX = re.compile(r'[\x00-\x1f\x7f-\x9f]+')
SPACE_REGEX = re.compile(r'\s+')
ASCII_LETTER_REGEX = re.compile(r'[A-Za-z]')
OCR_UPSCALE_FACTOR = 2


def is_english_language(language: str) -> bool:
    return language.lower().split('+')[0] == 'eng'


def clean_ocr_text(text: str, language: str) -> str:
    if not text:
        return text
    text = text.replace('\f', ' ')
    text = text.replace('“', '"').replace('”', '"').replace('’', "'").replace('‘', "'")
    text = text.replace('…', '...')

    if is_english_language(language):
        text = CJK_REGEX.sub(' ', text)
        text = ''.join(char if 32 <= ord(char) <= 126 else ' ' for char in text)
    else:
        text = CONTROL_REGEX.sub(' ', text)

    text = SPACE_REGEX.sub(' ', text).strip()
    return text.strip(' |\\/`~_-')


def should_keep_low_confidence_english_token(text: str) -> bool:
    letters = ASCII_LETTER_REGEX.findall(text)
    if len(letters) < 4:
        return False
    return len(letters) / max(len(text), 1) >= 0.6


def upscale_image_for_ocr(image: Image.Image, language: str) -> Image.Image:
    if not is_english_language(language):
        return image
    width, height = image.size
    if width <= 0 or height <= 0:
        return image
    upscaled_size = (width * OCR_UPSCALE_FACTOR, height * OCR_UPSCALE_FACTOR)
    return image.resize(upscaled_size, Image.Resampling.LANCZOS)


def tesseract_data_to_text(image: Image.Image, language: str, custom_config: str) -> tuple[str, str]:
    data = pytesseract.image_to_data(
        image,
        config=custom_config,
        lang=language,
        output_type=pytesseract.Output.DICT
    )
    raw_tokens = []
    lines = []
    current_line = []
    current_line_id = None

    texts = data.get('text', [])
    confs = data.get('conf', [])
    block_nums = data.get('block_num', [])
    par_nums = data.get('par_num', [])
    line_nums = data.get('line_num', [])

    for i, raw_text in enumerate(texts):
        raw_text = (raw_text or "").strip()
        if raw_text:
            raw_tokens.append(raw_text)

        text = clean_ocr_text(raw_text, language)
        if not text:
            continue

        try:
            confidence = float(confs[i])
        except (ValueError, TypeError):
            confidence = -1

        if confidence < MIN_ENGLISH_WORD_CONFIDENCE and not should_keep_low_confidence_english_token(text):
            continue

        line_id = (block_nums[i], par_nums[i], line_nums[i])
        if current_line_id is not None and line_id != current_line_id and current_line:
            lines.append(' '.join(current_line))
            current_line = []

        current_line_id = line_id
        current_line.append(text)

    if current_line:
        lines.append(' '.join(current_line))

    return ' '.join(raw_tokens), ' '.join(lines)


def image_to_text(image: Image.Image, text_orientation: str = "horizontal") -> str:
    """Run Tesseract OCR on a PIL Image.
    Reads tesseract config from config.ini via config_service.
    """
    tesseract_cmd = str(paths.tesseract_exe_path())
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    language = read_value("OCRCONFIG", "tesseract_language", "eng")
    oem = read_value("OCRCONFIG", "oem", "1")
    extra_options = read_value("OCRCONFIG", "extra_options", "").strip('"')

    psm = HORIZONTAL_TEXT_DETECTION
    is_legacy_tesseract = oem == '0'
    if is_legacy_tesseract:
        language += '+eng'
        
    if text_orientation == 'vertical':
        psm = VERTICAL_TEXT_DETECTION
        language += "_vert"
        
    tessdata_dir = str(paths.tessdata_dir())
    custom_config = f'--tessdata-dir "{tessdata_dir}" --oem {oem} --psm {psm} -c preserve_interword_spaces=1 {extra_options}'
    ocr_image = upscale_image_for_ocr(image, language)
    
    if is_english_language(language):
        _raw_data_text, cleaned_data_text = tesseract_data_to_text(ocr_image, language, custom_config)
        if cleaned_data_text:
            return cleaned_data_text

    result = pytesseract.image_to_string(ocr_image, config=custom_config, lang=language)
    return clean_ocr_text(result, language)
