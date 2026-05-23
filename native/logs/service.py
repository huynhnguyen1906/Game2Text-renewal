from __future__ import annotations

import os
import threading
from datetime import datetime
from pathlib import Path

from native.core import models
from native.core import paths


class LogService:
    def __init__(self) -> None:
        self.session_id: str | None = None
        self._lock = threading.Lock()

    def _ensure_session(self) -> str:
        if self.session_id is None:
            now = datetime.now()
            self.session_id = now.strftime("%Y%m%d-%H%M%S%f")
        return self.session_id

    def _get_log_file_path(self) -> Path:
        session_id = self._ensure_session()
        logs_dir = paths.text_logs_dir()
        logs_dir.mkdir(parents=True, exist_ok=True)
        # Old format relies on the filename being YYYYMMDD-HHMMSS.txt or YYYYMMDD-HHMMSSmmmuuu.txt
        # If we want microsecond in session file, we can just use the session_id
        return logs_dir / f"{session_id}.txt"

    def generate_log_id(self) -> str:
        with self._lock:
            # To ensure unique IDs in case of rapid calls, we can append a counter or just use microsecond precision
            # Current legacy logs use: time.time()*1000 or similar
            # In native phase, logging uses microsecond
            now = datetime.now()
            return now.strftime("%Y%m%d-%H%M%S%f")

    def append_source_text(self, source_text: str) -> models.LogEntry:
        # Clean text
        cleaned_text = " ".join(source_text.splitlines()).strip()
        log_id = self.generate_log_id()
        session_id = self._ensure_session()
        
        entry = models.LogEntry(
            id=log_id,
            row_key=log_id,
            folder=session_id,
            source_text=cleaned_text,
            created_at=datetime.now()
        )

        with self._lock:
            log_file = self._get_log_file_path()
            with open(log_file, "a", encoding="utf-8") as f:
                # Add line only containing source text first
                f.write(f"{log_id}, {cleaned_text}\n")

        return entry

    def update_translation(self, log_id: str, translated_text: str) -> None:
        cleaned_translated_text = " ".join(translated_text.splitlines()).strip()
        with self._lock:
            log_file = self._get_log_file_path()
            if not log_file.exists():
                return
            
            # Read all lines
            lines: list[str] = []
            with open(log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()

            # Find matching log id and modify it in place
            modified = False
            for i, line in enumerate(lines):
                if line.startswith(f"{log_id}, "):
                    # Existing translated text?
                    if "|||TRANSLATION|||" in line:
                        parts = line.split("|||TRANSLATION|||")
                        source = parts[0].strip()
                        lines[i] = f"{source}|||TRANSLATION|||{cleaned_translated_text}\n"
                    else:
                        source = line.strip()
                        lines[i] = f"{source}|||TRANSLATION|||{cleaned_translated_text}\n"
                    modified = True
                    break
            
            if modified:
                with open(log_file, "w", encoding="utf-8") as f:
                    f.writelines(lines)

    def parse_log_line(self, line: str, folder_name: str) -> models.LogEntry | None:
        line = line.strip()
        if not line:
            return None
        
        parts = line.split(", ", 1)
        if len(parts) < 2:
            return None
            
        log_id = parts[0]
        content = parts[1]
        
        source_text = content
        translated_text = None
        translation_status = "idle"
        
        if "|||TRANSLATION|||" in content:
            content_parts = content.split("|||TRANSLATION|||", 1)
            source_text = content_parts[0]
            translated_text = content_parts[1]
            translation_status = "done"
            
        return models.LogEntry(
            id=log_id,
            row_key=log_id,
            folder=folder_name,
            source_text=source_text,
            translated_text=translated_text,
            translation_status=translation_status
        )

    def get_logs(self, limit: int | None = None) -> list[models.LogEntry]:
        logs_dir = paths.text_logs_dir()
        if not logs_dir.exists():
            return []
            
        # Get all txt files, sort by name descending (newest first)
        log_files = sorted(logs_dir.glob("*.txt"), reverse=True)
        
        results: list[models.LogEntry] = []
        for file_path in log_files:
            folder_name = file_path.stem
            
            with self._lock:
                with open(file_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
            
            # Process lines in reverse order (newest first within the file)
            for line in reversed(lines):
                entry = self.parse_log_line(line, folder_name)
                if entry:
                    results.append(entry)
                    if limit and len(results) >= limit:
                        # Return in chronological order (oldest -> newest) for display
                        return list(reversed(results))
        
        return list(reversed(results))

default_log_service = LogService()
