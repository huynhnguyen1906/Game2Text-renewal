from __future__ import annotations

from datetime import datetime

from native.app.event_bus import global_bus
from native.app.workers import global_workers
from native.config.service import load_filter_config
from native.filters.service import apply_filters
from native.ocr.service import image_to_text
from native.logs.service import default_log_service
from native.translation.service import translate_text
from native.core.models import LogEntry


class AppController:
    def __init__(self) -> None:
        self.bus = global_bus
        self.workers = global_workers

    def queue_translation(self, log_id: str, source_text: str) -> None:
        # Avoid unlimited API backlog:
        acquired = self.workers.translation_slots.acquire(blocking=False)
        if not acquired:
            queue_full_message = "Bạn đã chạm giới hạn queue dịch. Hãy đợi các câu trước dịch xong rồi dịch tiếp."
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
                translated = translate_text(source_text)
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

    def process_ocr_result(self, text: str) -> None:
        if not text or not text.strip():
            # Generate fake log_id and fire row update without queue translation
            fake_id = default_log_service.generate_log_id()
            entry = LogEntry(
                id=fake_id,
                row_key=fake_id,
                folder="error",
                source_text="Không nhận diện được text.",
                translation_status="ocr_error",
                translation_error="Không nhận diện được text.",
                created_at=datetime.now()
            )
            self.bus.log_entry_created.emit(entry)
            return

        # Normal valid OCR
        entry = default_log_service.append_source_text(text)
        self.bus.log_entry_created.emit(entry)
        self.queue_translation(entry.id, entry.source_text)

    def process_captured_image(self, image, region_id: str = "1") -> None:
        def _ocr_task() -> None:
            try:
                self.bus.status_changed.emit("Đang OCR...")
                filter_config = load_filter_config()
                filtered_image = apply_filters(image.copy(), filter_config)
                text = image_to_text(filtered_image)
                self.process_ocr_result(text)
                self.bus.status_changed.emit("Sẵn sàng")
            except Exception as e:
                self.bus.capture_failed.emit(str(e))
                self.bus.status_changed.emit("OCR thất bại")

        self.workers.capture_executor.submit(_ocr_task)


global_controller = AppController()
