from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from native.config.service import read_value


class WorkerPool:
    def __init__(self) -> None:
        self.capture_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="CaptureWorker")
        
        queue_limit_str = read_value("NATIVEAPP", "translation_queue_limit", "5")
        try:
            queue_limit = int(queue_limit_str)
        except ValueError:
            queue_limit = 5
            
        self.translation_executor = ThreadPoolExecutor(max_workers=queue_limit, thread_name_prefix="TranslationWorker")
        self.translation_slots = threading.BoundedSemaphore(queue_limit)

    def shutdown(self) -> None:
        self.capture_executor.shutdown(wait=False)
        self.translation_executor.shutdown(wait=False)


global_workers = WorkerPool()
