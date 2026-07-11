from __future__ import annotations

import sys
import time
import traceback
from datetime import datetime

from native.app.event_bus import global_bus
from native.app.workers import global_workers
from native.config.service import load_filter_config
from native.core import paths
from native.filters.service import apply_filters
from native.ocr.service import image_to_text
from native.ocr.models import OcrResult
from native.logs.service import default_log_service
from native.translation.service import translate_text
from native.core.models import LogEntry


class AppController:
    def __init__(self) -> None:
        self.bus = global_bus
        self.workers = global_workers

    def queue_translation(
        self,
        log_id: str,
        source_text: str,
        context_labels: tuple[str, ...] = (),
    ) -> None:
        # Avoid unlimited API backlog:
        acquired = self.workers.translation_slots.acquire(blocking=False)
        if not acquired:
            queue_full_message = "Translation queue limit reached. Wait for earlier items to finish before translating more."
            self.bus.log_entry_updated.emit(log_id, {
                "translation_pending": False,
                "translation_status": "queue_full",
                "translation_error": queue_full_message,
            })
            return

        self.bus.log_entry_updated.emit(log_id, {
            "translation_pending": True,
            "translation_status": "pending",
            "translation_error": None,
        })

        def _translate_task() -> None:
            try:
                translated = translate_text(source_text, context_labels=context_labels)
                default_log_service.update_translation(log_id, translated)
                self.bus.overlay_text_updated.emit(translated)
                self.bus.log_entry_updated.emit(log_id, {
                    "translation_pending": False,
                    "translation_status": "done",
                    "translated_text": translated,
                    "translation_error": None,
                })
            except Exception as e:
                self.bus.log_entry_updated.emit(log_id, {
                    "translation_pending": False,
                    "translation_status": "error",
                    "translation_error": str(e),
                })
            finally:
                self.workers.translation_slots.release()

        self.workers.translation_executor.submit(_translate_task)

    def process_ocr_result(self, result: OcrResult) -> None:
        text = result.text
        if not text or not text.strip():
            # Generate fake log_id and fire row update without queue translation
            fake_id = default_log_service.generate_log_id()
            entry = LogEntry(
                id=fake_id,
                row_key=fake_id,
                folder="error",
                source_text="No text detected.",
                translation_status="ocr_error",
                translation_error="No text detected.",
                created_at=datetime.now()
            )
            self.bus.log_entry_created.emit(entry)
            return

        # Normal valid OCR
        entry = default_log_service.append_source_text(text)
        self.bus.log_entry_created.emit(entry)
        self.queue_translation(entry.id, entry.source_text, context_labels=result.context_labels)

    def process_captured_image(self, image, region_id: str = "1") -> None:
        def _ocr_task() -> None:
            try:
                self.bus.status_changed.emit("Running OCR...")
                filter_started_at = time.perf_counter()
                filter_config = load_filter_config()
                filtered_image = apply_filters(image.copy(), filter_config)
                filter_seconds = time.perf_counter() - filter_started_at
                ocr_started_at = time.perf_counter()
                result = image_to_text(filtered_image)
                ocr_seconds = time.perf_counter() - ocr_started_at
                self._write_ocr_perf_log(
                    f"region_id={region_id} image={image.width}x{image.height} "
                    f"filter={filter_seconds:.3f}s ocr={ocr_seconds:.3f}s"
                )
                self.process_ocr_result(result)
                self.bus.status_changed.emit("Ready")
            except Exception as e:
                self._write_ocr_error_log(e)
                if not getattr(sys, "frozen", False):
                    print("[OCR ERROR]", repr(e), file=sys.stderr)
                    traceback.print_exc()
                self.bus.capture_failed.emit(str(e))
                self.bus.status_changed.emit("OCR failed")

        self.workers.capture_executor.submit(_ocr_task)

    def _write_ocr_error_log(self, error: Exception) -> None:
        try:
            logs_dir = paths.text_logs_dir()
            logs_dir.mkdir(parents=True, exist_ok=True)
            log_path = logs_dir / "ocr_errors.txt"
            timestamp = datetime.now().isoformat(timespec="seconds")
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(f"[{timestamp}] {repr(error)}\n")
                handle.write(traceback.format_exc())
                if not traceback.format_exc().endswith("\n"):
                    handle.write("\n")
                handle.write("\n")
        except Exception:
            pass

    def _write_ocr_perf_log(self, message: str) -> None:
        try:
            logs_dir = paths.text_logs_dir()
            logs_dir.mkdir(parents=True, exist_ok=True)
            log_path = logs_dir / "ocr_perf.txt"
            timestamp = datetime.now().isoformat(timespec="seconds")
            with log_path.open("a", encoding="utf-8") as handle:
                handle.write(f"[{timestamp}] {message}\n")
            if not getattr(sys, "frozen", False):
                print(f"[OCR PERF] {message}")
        except Exception:
            pass


global_controller = AppController()
