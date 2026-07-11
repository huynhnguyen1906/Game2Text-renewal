from __future__ import annotations

import os
import gc
import sys
import threading
import time
from datetime import datetime
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

    _log_cuda_memory("before_pre_ocr_empty_cache")
    _empty_cuda_cache()
    _log_cuda_memory("after_pre_ocr_empty_cache")
    _log_cuda_memory("before_convert")
    convert_started_at = time.perf_counter()
    image_array = np.array(image.convert("RGB"))
    convert_seconds = time.perf_counter() - convert_started_at
    _reset_timing_state(ocr)
    _log_cuda_memory("before_ocr")
    started_at = time.perf_counter()
    result: Any = None
    try:
        result = ocr.ocr(image_array)
        total_seconds = time.perf_counter() - started_at
        _log_cuda_memory("after_ocr")
        _print_timing_if_enabled(ocr, total_seconds, image.size, convert_seconds)
        texts = _extract_texts(result)
        return " ".join(part for part in texts if part).strip()
    except Exception:
        _log_cuda_memory("ocr_exception_before_cleanup")
        raise
    finally:
        result = None
        image_array = None
        gc.collect()
        _log_cuda_memory("after_gc_before_empty_cache")
        _empty_cuda_cache()
        _log_cuda_memory("after_empty_cache")


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
            text_recognition_batch_size=2,
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
    # Best-effort 3.5GB cap for inference. Paddle's GPU memory limit flags are not perfectly strict
    # in every inference path, but this gives OCR enough headroom for heavy recognition spikes.
    os.environ["FLAGS_allocator_strategy"] = "auto_growth"
    os.environ["FLAGS_gpu_memory_limit_mb"] = "3584"
    os.environ["FLAGS_initial_gpu_memory_in_mb"] = "3584"
    os.environ.pop("FLAGS_reallocate_gpu_memory_in_mb", None)
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
            _log_recognizer_inputs(ocr, args, kwargs)
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


def _log_recognizer_inputs(ocr: Any, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
    if not read_bool("OCRCONFIG", "paddle_log_timing", True):
        return
    try:
        batch_data = args[0] if args else kwargs.get("batch_data")
        raw_instances = getattr(batch_data, "instances", None)
        instances = list(raw_instances) if raw_instances is not None else []
        state = getattr(ocr, "_codex_timing_state", None)
        call_index = int(state.get("recognizer_calls", 0)) + 1 if isinstance(state, dict) else 1
        crop_details: list[str] = []
        for index, crop in enumerate(instances):
            shape = getattr(crop, "shape", ())
            if len(shape) < 2:
                crop_details.append(f"crop[{index}]=shape:{shape!r}")
                continue
            height = int(shape[0])
            width = int(shape[1])
            ratio = width / float(height) if height > 0 else float("inf")
            projected_width = min(3200, int(48 * max(320 / 48, ratio))) if height > 0 else 3200
            crop_details.append(
                f"crop[{index}]={width}x{height} ratio={ratio:.3f} projected_rec_width={projected_width}"
            )
        details = " ".join(crop_details) if crop_details else "no_crops"
        _write_paddle_perf_log(
            f"[PADDLE REC INPUT] call={call_index} crops={len(instances)} {details}"
        )
    except Exception as exc:
        _write_paddle_perf_log(f"[PADDLE REC INPUT] logging_failed={exc!r}")


def _reset_timing_state(ocr: Any) -> None:
    state = getattr(ocr, "_codex_timing_state", None)
    if isinstance(state, dict):
        state["detector_seconds"] = 0.0
        state["recognizer_seconds"] = 0.0
        state["detector_calls"] = 0
        state["recognizer_calls"] = 0


def _print_timing_if_enabled(
    ocr: Any,
    total_seconds: float,
    image_size: tuple[int, int],
    convert_seconds: float,
) -> None:
    if not read_bool("OCRCONFIG", "paddle_log_timing", True):
        return
    state = getattr(ocr, "_codex_timing_state", None)
    width, height = image_size
    if not isinstance(state, dict):
        message = (
            "[PADDLE OCR TIMING] "
            f"size={width}x{height} "
            f"convert={convert_seconds:.3f}s "
            f"total={total_seconds:.3f}s"
        )
        print(message)
        _write_paddle_perf_log(message)
        return
    detector_seconds = float(state.get("detector_seconds", 0.0))
    recognizer_seconds = float(state.get("recognizer_seconds", 0.0))
    detector_calls = int(state.get("detector_calls", 0))
    recognizer_calls = int(state.get("recognizer_calls", 0))
    message = (
        "[PADDLE OCR TIMING] "
        f"size={width}x{height} "
        f"convert={convert_seconds:.3f}s "
        f"total={total_seconds:.3f}s "
        f"detector={detector_seconds:.3f}s(calls={detector_calls}) "
        f"recognizer={recognizer_seconds:.3f}s(calls={recognizer_calls})"
    )
    print(message)
    _write_paddle_perf_log(message)


def _write_paddle_perf_log(message: str) -> None:
    try:
        logs_dir = paths.text_logs_dir()
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_path = logs_dir / "ocr_perf.txt"
        timestamp = datetime.now().isoformat(timespec="seconds")
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass


def _log_cuda_memory(stage: str) -> None:
    if not read_bool("OCRCONFIG", "paddle_log_timing", True):
        return
    try:
        import paddle

        cuda = paddle.device.cuda
        allocated = int(cuda.memory_allocated("gpu:0"))
        reserved = int(cuda.memory_reserved("gpu:0"))
        max_allocated = int(cuda.max_memory_allocated("gpu:0"))
        max_reserved = int(cuda.max_memory_reserved("gpu:0"))
        idle_reserved = max(0, reserved - allocated)
        message = (
            "[PADDLE CUDA MEMORY] "
            f"stage={stage} "
            f"allocated={_format_bytes(allocated)} "
            f"reserved={_format_bytes(reserved)} "
            f"idle_reserved={_format_bytes(idle_reserved)} "
            f"max_allocated={_format_bytes(max_allocated)} "
            f"max_reserved={_format_bytes(max_reserved)}"
        )
        print(message)
        _write_paddle_perf_log(message)
    except Exception as exc:
        _write_paddle_perf_log(f"[PADDLE CUDA MEMORY] stage={stage} unavailable={exc!r}")


def _empty_cuda_cache() -> None:
    try:
        import paddle

        paddle.device.cuda.empty_cache()
    except Exception as exc:
        _write_paddle_perf_log(f"[PADDLE CUDA MEMORY] empty_cache_failed={exc!r}")


def _format_bytes(value: int) -> str:
    mib = value / (1024 * 1024)
    gib = value / (1024 * 1024 * 1024)
    if gib >= 1:
        return f"{gib:.3f}GiB/{mib:.1f}MiB"
    return f"{mib:.1f}MiB"


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
