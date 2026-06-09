from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image

from native.core import paths
from native.config.service import read_bool, read_value


_OCR_INSTANCES: dict[tuple[str, bool], Any] = {}
_OCR_LOCK = threading.Lock()

LANGUAGE_ALIASES = {
    "eng": "en",
    "en": "en",
    "vi": "vi",
    "vie": "vi",
    "jpn": "japan",
    "jp": "japan",
    "ja": "japan",
    "japanese": "japan",
    "zh": "ch",
    "chi_sim": "ch",
    "ch": "ch",
    "ko": "korean",
    "kor": "korean",
    "th": "th",
    "de": "german",
    "fr": "fr",
    "ru": "ru",
    "es": "es",
    "it": "it",
    "pt": "pt",
}


def image_to_text(image: Image.Image, text_orientation: str = "horizontal") -> str:
    """Run PaddleOCR on a PIL image and return flattened text output."""
    language = _resolve_paddle_language()
    use_angle_cls = text_orientation != "vertical"
    ocr = _get_ocr_instance(language, use_angle_cls)

    image_array = np.array(image.convert("RGB"))
    _reset_timing_state(ocr)
    started_at = time.perf_counter()
    result = ocr.ocr(image_array)
    total_seconds = time.perf_counter() - started_at
    _print_timing_if_enabled(ocr, total_seconds)
    texts = _extract_texts(result)
    return " ".join(part for part in texts if part).strip()


def _resolve_paddle_language() -> str:
    configured = read_value("OCRCONFIG", "paddle_language", "").strip().lower()
    if configured:
        return LANGUAGE_ALIASES.get(configured, configured)

    fallback = read_value("OCRCONFIG", "tesseract_language", "eng").strip().lower()
    return LANGUAGE_ALIASES.get(fallback, fallback or "en")


def _build_instance_key(language: str, use_angle_cls: bool) -> tuple[Any, ...]:
    runtime_engine = read_value("OCRCONFIG", "paddle_runtime_engine", "paddle_dynamic").strip() or "paddle_dynamic"
    cache_dir = _resolve_paddle_cache_dir()
    disable_source_check = read_bool("OCRCONFIG", "paddle_disable_model_source_check", True)
    device = _resolve_paddle_device()
    enable_hpi = read_bool("OCRCONFIG", "paddle_enable_hpi", False)
    use_tensorrt = read_bool("OCRCONFIG", "paddle_use_tensorrt", False)
    precision = read_value("OCRCONFIG", "paddle_precision", "fp32").strip() or "fp32"
    use_doc_orientation_classify = read_bool("OCRCONFIG", "paddle_use_doc_orientation_classify", False)
    use_doc_unwarping = read_bool("OCRCONFIG", "paddle_use_doc_unwarping", False)
    use_textline_orientation = read_bool("OCRCONFIG", "paddle_use_textline_orientation", False)
    if use_angle_cls and not use_textline_orientation:
        use_textline_orientation = False
    text_detection_model_name = _optional_config_value("paddle_text_detection_model_name")
    text_recognition_model_name = _optional_config_value("paddle_text_recognition_model_name")
    if text_recognition_model_name is None:
        text_recognition_model_name = _default_text_recognition_model_name(language)
    return (
        language,
        use_angle_cls,
        runtime_engine,
        cache_dir,
        disable_source_check,
        device,
        enable_hpi,
        use_tensorrt,
        precision,
        use_doc_orientation_classify,
        use_doc_unwarping,
        use_textline_orientation,
        text_detection_model_name,
        text_recognition_model_name,
    )


def _get_ocr_instance(language: str, use_angle_cls: bool) -> Any:
    key = _build_instance_key(language, use_angle_cls)
    with _OCR_LOCK:
        cached = _OCR_INSTANCES.get(key)
        if cached is not None:
            return cached

        cache_dir = str(key[3])
        disable_source_check = bool(key[4])
        device = str(key[5])
        runtime_engine = str(key[2])
        enable_hpi = bool(key[6])
        use_tensorrt = bool(key[7])
        precision = str(key[8])
        use_doc_orientation_classify = bool(key[9])
        use_doc_unwarping = bool(key[10])
        use_textline_orientation = bool(key[11])
        text_detection_model_name = key[12]
        text_recognition_model_name = key[13]

        _configure_paddle_environment(cache_dir, disable_source_check)

        try:
            from paddleocr import PaddleOCR
        except ImportError as exc:
            raise RuntimeError(
                "PaddleOCR backend is not installed. Install both 'paddlepaddle' and 'paddleocr' to use OCRCONFIG.engine = paddleocr."
            ) from exc

        instance = PaddleOCR(
            device=device,
            engine=runtime_engine,
            enable_hpi=enable_hpi,
            use_tensorrt=use_tensorrt,
            precision=precision,
            lang=language,
            use_doc_orientation_classify=use_doc_orientation_classify,
            use_doc_unwarping=use_doc_unwarping,
            use_textline_orientation=use_textline_orientation,
            text_detection_model_name=text_detection_model_name,
            text_recognition_model_name=text_recognition_model_name,
        )
        _attach_timing_hooks(instance)
        _OCR_INSTANCES[key] = instance
        return instance


def _resolve_paddle_cache_dir() -> str:
    configured = read_value("OCRCONFIG", "paddle_cache_dir", "").strip()
    if configured:
        return configured
    return str(paths.paddle_cache_dir())


def _configure_paddle_environment(cache_dir: str, disable_source_check: bool) -> None:
    cache_path = Path(cache_dir).expanduser()
    cache_path.mkdir(parents=True, exist_ok=True)
    os.environ["PADDLE_PDX_CACHE_HOME"] = str(cache_path)
    os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True" if disable_source_check else "False"
    if read_bool("OCRCONFIG", "paddle_use_gpu", False):
        _configure_windows_gpu_dll_paths()


def _configure_windows_gpu_dll_paths() -> None:
    if os.name != "nt":
        return

    candidate_dirs = [
        paths.app_root() / "nvidia" / "cu13" / "bin" / "x86_64",
        paths.app_root() / "nvidia" / "cudnn" / "bin",
        paths.bundle_root() / "nvidia" / "cu13" / "bin" / "x86_64",
        paths.bundle_root() / "nvidia" / "cudnn" / "bin",
        Path(sys.prefix) / "Lib" / "site-packages" / "nvidia" / "cu13" / "bin" / "x86_64",
        Path(sys.prefix) / "Lib" / "site-packages" / "nvidia" / "cudnn" / "bin",
    ]

    existing_dirs = [str(path) for path in candidate_dirs if path.is_dir()]
    if not existing_dirs:
        return

    current_path_entries = os.environ.get("PATH", "").split(os.pathsep)
    normalized_existing = {entry.lower() for entry in current_path_entries if entry}
    prepended_entries: list[str] = []
    for entry in existing_dirs:
        if entry.lower() not in normalized_existing:
            prepended_entries.append(entry)
            normalized_existing.add(entry.lower())
            if hasattr(os, "add_dll_directory"):
                try:
                    os.add_dll_directory(entry)
                except OSError:
                    pass

    if prepended_entries:
        os.environ["PATH"] = os.pathsep.join(prepended_entries + current_path_entries)


def _optional_config_value(key: str) -> str | None:
    value = read_value("OCRCONFIG", key, "").strip()
    return value or None


def _resolve_paddle_device() -> str:
    if read_bool("OCRCONFIG", "paddle_use_gpu", False):
        return read_value("OCRCONFIG", "paddle_gpu_device", "gpu:0").strip() or "gpu:0"
    return "cpu"


def _default_text_recognition_model_name(language: str) -> str:
    if language == "en":
        return "en_PP-OCRv5_mobile_rec"
    if language == "ch":
        return "PP-OCRv5_mobile_rec"
    if language == "japan":
        return "japan_PP-OCRv3_mobile_rec"
    if language == "korean":
        return "korean_PP-OCRv5_mobile_rec"
    if language == "th":
        return "th_PP-OCRv5_mobile_rec"
    if language in {"fr", "de", "es", "it", "pt", "vi"}:
        return "latin_PP-OCRv5_mobile_rec"
    if language == "ru":
        return "cyrillic_PP-OCRv5_mobile_rec"
    return "en_PP-OCRv5_mobile_rec"


def _attach_timing_hooks(ocr: Any) -> None:
    if getattr(ocr, "_codex_timing_hooks_installed", False):
        return

    pipe = getattr(getattr(ocr, "paddlex_pipeline", None), "_pipeline", None)
    if pipe is None:
        ocr._codex_timing_hooks_installed = True
        return

    ocr._codex_timing_state = {
        "detector_seconds": 0.0,
        "recognizer_seconds": 0.0,
        "detector_calls": 0,
        "recognizer_calls": 0,
    }

    if hasattr(pipe, "text_det_model"):
        original_det_process = pipe.text_det_model.process

        def timed_det_process(*args: Any, **kwargs: Any) -> Any:
            started_at = time.perf_counter()
            try:
                return original_det_process(*args, **kwargs)
            finally:
                elapsed = time.perf_counter() - started_at
                state = getattr(ocr, "_codex_timing_state", None)
                if isinstance(state, dict):
                    state["detector_seconds"] += elapsed
                    state["detector_calls"] += 1

        pipe.text_det_model.process = timed_det_process

    if hasattr(pipe, "text_rec_model"):
        original_rec_process = pipe.text_rec_model.process

        def timed_rec_process(*args: Any, **kwargs: Any) -> Any:
            started_at = time.perf_counter()
            try:
                return original_rec_process(*args, **kwargs)
            finally:
                elapsed = time.perf_counter() - started_at
                state = getattr(ocr, "_codex_timing_state", None)
                if isinstance(state, dict):
                    state["recognizer_seconds"] += elapsed
                    state["recognizer_calls"] += 1

        pipe.text_rec_model.process = timed_rec_process

    ocr._codex_timing_hooks_installed = True


def _reset_timing_state(ocr: Any) -> None:
    state = getattr(ocr, "_codex_timing_state", None)
    if isinstance(state, dict):
        state["detector_seconds"] = 0.0
        state["recognizer_seconds"] = 0.0
        state["detector_calls"] = 0
        state["recognizer_calls"] = 0


def _print_timing_if_enabled(ocr: Any, total_seconds: float) -> None:
    if not read_bool("OCRCONFIG", "paddle_log_timing", True):
        return
    state = getattr(ocr, "_codex_timing_state", None)
    if not isinstance(state, dict):
        print(f"[PADDLE OCR TIMING] total={total_seconds:.3f}s")
        return
    detector_seconds = float(state.get("detector_seconds", 0.0))
    recognizer_seconds = float(state.get("recognizer_seconds", 0.0))
    detector_calls = int(state.get("detector_calls", 0))
    recognizer_calls = int(state.get("recognizer_calls", 0))
    print(
        "[PADDLE OCR TIMING] "
        f"total={total_seconds:.3f}s "
        f"detector={detector_seconds:.3f}s(calls={detector_calls}) "
        f"recognizer={recognizer_seconds:.3f}s(calls={recognizer_calls})"
    )


def _extract_texts(result: Any) -> list[str]:
    texts: list[str] = []
    _walk_result(result, texts)
    return texts


def _walk_result(node: Any, texts: list[str]) -> None:
    if node is None:
        return

    if isinstance(node, str):
        cleaned = node.strip()
        if cleaned:
            texts.append(cleaned)
        return

    if isinstance(node, dict):
        if "rec_texts" in node and isinstance(node["rec_texts"], list):
            for item in node["rec_texts"]:
                _walk_result(item, texts)
            return
        if "rec_text" in node:
            _walk_result(node["rec_text"], texts)
            return
        if "text" in node:
            _walk_result(node["text"], texts)
            return
        if "res" in node:
            _walk_result(node["res"], texts)
            return
        for value in node.values():
            _walk_result(value, texts)
        return

    if isinstance(node, (list, tuple)):
        if len(node) >= 2 and isinstance(node[1], (list, tuple)):
            second = node[1]
            if second and isinstance(second[0], str):
                _walk_result(second[0], texts)
                return
        for item in node:
            _walk_result(item, texts)
        return
