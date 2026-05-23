# Investigation 4: Native UI And Async Log Architecture

## Scope

This investigation defines the native log window, log row state model, and async OCR/translation event flow.

The goal is to preserve the current successful async log behavior while removing Eel/browser event coupling.

This investigation does not cover image filter implementation details. That remains investigation 3.

## Executive Decision

Use a PySide6 native log window backed by a pure log model and a thread-safe event bus.

Recommended architecture:

- UI layer:
  - `log_window.py`
  - `log_row_widget.py`
  - `main_window.py` or compact control window
- State layer:
  - `log_model.py`
  - `LogEntry` dataclass
- Backend services:
  - `log_service.py`
  - `ocr_service.py`
  - `translation_service.py`
  - `screen_capture.py`
  - `filter_service.py`
- Async layer:
  - `workers.py`
  - `event_bus.py`

Use `ThreadPoolExecutor` for OCR/translation workers and PySide `Signal` objects for UI updates.

Reason:

- Current source already uses `ThreadPoolExecutor` successfully for async translation.
- Backend services stay plain Python and testable.
- PySide signals safely deliver updates to the UI thread.
- Translation completion can arrive out of order and still update the correct row by `log_id`.

## Current Source Findings

### Current Async Flow

Current flow in `game2text.py`:

1. OCR completes.
2. `log_text()` writes source text immediately.
3. `queue_log_translation(log_id, text)` tries to acquire a queue slot.
4. UI receives pending state through `eel.updateLogDataById()`.
5. Translation runs in `ThreadPoolExecutor(max_workers=5)`.
6. `update_log_text()` persists translated text into the same log row.
7. UI receives done/error state through `eel.updateLogDataById()`.
8. Queue slot is released in `finally`.

Important behavior to preserve:

- Source text appears immediately.
- Translation is not sequentially blocked by earlier slow requests.
- Translation result updates the matching `log_id`.
- Queue full state does not send an extra API request.
- Log file is updated when translation completes.

### Current Web Log UI

Current behavior in `web/logs.js`:

- `currentLogs` stores visible rows.
- `pendingLogUpdates` stores translation updates that arrive before a row is available.
- `updateLogDataById(logId, data)` merges partial updates into an existing row.
- `addLogs()` merges pending updates before rendering a new row.
- `formatTranslationBlock()` renders:
  - translated text
  - loading state
  - error state

Important behavior to preserve:

- Update rows by `log_id`, not by list index.
- Merge partial updates.
- Keep a pending-update buffer for race protection.
- Translation text is displayed below source text with a divider.
- Pending state shows a non-italic loading spinner/text.
- Error state is red.

### Current Log Format

Current log file format:

```text
<log_id>, <source_text>|||TRANSLATION|||<translated_text>
```

Important behavior to preserve:

- `log_id` supports microseconds.
- Old second-level IDs can still be parsed.
- Translation is stored in the same line as source text.

## Native UI Shape

### Recommended Windows

Use two windows:

1. Log Window
2. Compact Control Window or tray/menu window

The user mainly uses logs, so the log window should be the primary visible surface.

The compact control window can hold:

- select region
- show/hide region border
- filter/profile access
- always-on-top toggle
- open config/log folder
- status indicator

Filter UI may later be integrated as a panel or dialog. The log window should not become crowded.

### Log Window Layout

Recommended structure:

```text
LogWindow
  Header/Toolbar
    - Always on top toggle
    - Select region button
    - Show/hide border toggle
    - Filter/profile button
    - Clear/reload logs button
  Scroll Area
    - LogRowWidget[]
```

Recommended widget:

- `QScrollArea` with a vertical layout of custom `LogRowWidget` instances.

Alternative:

- `QListView` with a custom model/delegate.

Decision:

- Start with `QScrollArea` + custom row widgets.

Reason:

- Easier to implement rich row content:
  - source text
  - divider
  - spinner/loading text
  - translated text
  - error text
- Easier to style close to current `logs.html`.
- Enough performance for the configured current-session log size.

If logs later need thousands of rows, switch to `QListView` with a custom delegate.

## Log Row UI States

Each row should support these states:

- source OCR text
- translation pending
- translated text
- translation error
- queue full
- OCR failure

Recommended visual behavior:

### Source Text

- White text on dark theme.
- Selectable text.
- Copy support.
- Optional edit support can be added later, but not required for MVP.

### Pending Translation

- Divider under source text.
- Small circular spinner.
- Text: `Đang dịch...`
- Not italic.

### Translated Text

- Divider under source text.
- Purple/light-purple text like current log UI.
- Italic text, matching current behavior.

### Error / Queue Full

- Divider under source text.
- Red text.
- Queue-full message:

```text
Bạn đã chạm giới hạn queue dịch. Hãy đợi các câu trước dịch xong rồi dịch tiếp.
```

### OCR Failure

- Add a row only if useful for user feedback.
- Red text can say OCR failed or no text detected.
- Do not queue translation.

Decision:

- Keep source text visible even when translation fails.
- Treat queue-full as a row-level translation error, not as an app modal.

## Data Model

Recommended dataclass:

```python
@dataclass
class LogEntry:
    id: str
    folder: str
    source_text: str
    translated_text: str | None = None
    translation_pending: bool = False
    translation_status: str = "idle"
    translation_error: str | None = None
    created_at: datetime | None = None
```

Recommended status values:

```text
idle
pending
done
error
queue_full
ocr_error
```

Recommended UI model:

```python
class LogModel:
    entries_by_id: dict[str, LogEntry]
    order: list[str]
    pending_updates: dict[str, dict]
```

Model behavior:

- `add_entry(entry)` appends a row.
- `update_entry(log_id, patch)` merges partial updates.
- If update arrives before entry exists, store it in `pending_updates`.
- When entry is added, merge and remove pending update.
- Enforce `current_session_max_log_size`.

Decision:

- Keep `pending_updates` in native even if the ideal event order creates row first.

Reason:

- It protects against future races.
- It mirrors the web fix that solved missing translations.
- It costs very little.

## Event Bus

Recommended module:

```text
newsource/native/event_bus.py
```

Recommended PySide signal container:

```python
class AppEventBus(QObject):
    log_entry_created = Signal(object)
    log_entry_updated = Signal(str, dict)
    status_changed = Signal(str)
    capture_failed = Signal(str)
```

Rules:

- Worker threads never mutate widgets directly.
- Worker threads emit events through the event bus.
- UI thread updates `LogModel` and widgets.
- Backend services do not import PySide widgets.

## Async Worker Architecture

Recommended module:

```text
newsource/native/workers.py
```

Use:

```python
capture_executor = ThreadPoolExecutor(max_workers=1)
translation_executor = ThreadPoolExecutor(max_workers=5)
translation_slots = threading.BoundedSemaphore(5)
```

Reason:

- Capture/OCR should not stampede when hotkey is spammed.
- Translation can safely run with bounded concurrency.
- Queue-full behavior remains explicit.

### Why Capture/OCR `max_workers=1`

OCR is CPU-bound and can be expensive.

If the user presses `Ctrl+Q` rapidly:

- Capturing multiple regions is cheap.
- OCR can still become a bottleneck.
- Translation already has API latency.

Recommended MVP behavior:

- One capture/OCR job at a time.
- Translation jobs can run concurrently up to the queue limit.

Optional later behavior:

- OCR queue size of 2.
- Drop duplicate captures if region image is identical.

## Native End-To-End Flow

### Hotkey Capture Flow

```text
Ctrl+Q
  -> hotkey_service emits capture_requested
  -> workers.submit_capture_ocr_job()
  -> hide region border if visible
  -> screen_capture.capture_region()
  -> restore region border if enabled
  -> filter_service.apply_filters()
  -> ocr_service.image_to_text()
  -> log_service.append_source_text()
  -> event_bus.log_entry_created(LogEntry)
  -> workers.queue_translation(log_id, source_text)
```

### Translation Flow

```text
queue_translation(log_id, source_text)
  -> if no queue slot:
       event_bus.log_entry_updated(log_id, queue_full patch)
       return
  -> event_bus.log_entry_updated(log_id, pending patch)
  -> translation_executor.submit(...)
  -> translation_service.translate_text()
  -> log_service.update_translation(log_id, translated_text)
  -> event_bus.log_entry_updated(log_id, done patch)
  -> release queue slot
```

### Error Flow

Capture/OCR error:

```text
event_bus.log_entry_created(LogEntry(status="ocr_error", translation_error=...))
```

Translation error:

```text
event_bus.log_entry_updated(log_id, {
    "translation_pending": False,
    "translation_status": "error",
    "translation_error": error_message,
})
```

Queue full:

```text
event_bus.log_entry_updated(log_id, {
    "translation_pending": False,
    "translation_status": "queue_full",
    "translation_error": queue_full_message,
})
```

## Log Persistence Rules

Source text:

- Persist immediately after OCR succeeds.
- UI row appears immediately after source text is persisted.

Translation:

- Persist only after translation succeeds.
- Store in same log line using `|||TRANSLATION|||`.

Errors:

- Do not write queue-full/API errors into `translated_text` field by default.
- Keep errors as UI state.

Reason:

- Errors are runtime state, not a successful translation.
- Reloading logs should show completed translations from file.
- Queue-full entries can remain untranslated after reload, which is acceptable.

Optional later:

- Write error metadata to a separate sidecar log if needed.

## Startup Log Loading

On app start:

1. `log_service.get_logs(limit=...)`.
2. Convert old log objects into `LogEntry`.
3. Add rows to `LogModel`.
4. Do not re-queue translation for old untranslated logs automatically.

Decision:

- Avoid automatic backfill translation on startup.

Reason:

- Prevent surprise API cost.
- User-triggered capture should be the only automatic translation path.

Optional later:

- Add a manual `Translate missing` action.

## Window Persistence

Use `config.ini`:

```ini
[NATIVEAPP]
log_window_x = 1200
log_window_y = 120
log_window_width = 700
log_window_height = 900
always_on_top = true
dark_theme = true
current_session_max_log_size = 30
translation_queue_limit = 5
```

Persist:

- window position
- window size
- always-on-top
- dark theme
- current session max log size
- translation queue limit

Existing `LOGCONFIG.currentsessionmaxlogsize` can be reused for log count if sharing config is preferred.

## UI Styling Decision

Keep the current log visual language:

- dark theme by default
- source text above
- divider
- translated text below
- purple italic translation
- red errors
- non-italic loading text/spinner

Native Qt styling can be done with QSS.

Recommended row widgets:

- `QLabel` or `QTextEdit` for source text.
- `QFrame` horizontal divider.
- `QLabel` for translated/error text.
- `QMovie`/custom spinner or small indeterminate progress indicator for loading.

Text should be selectable. If using `QLabel`, enable:

```python
label.setTextInteractionFlags(Qt.TextSelectableByMouse)
```

## Avoiding Double Translation Requests

Important rule:

- Only the log async path should call `translation_service.translate_text()` automatically.

Native app should not have an index-style single-output translation path unless explicitly added later.

Recommended service boundary:

- Capture/OCR creates a log entry.
- Log entry creation queues translation.
- There is no separate automatic "main output translation".

This preserves the cost-control fix from the current source.

## Queue Policy

Default:

```text
translation_queue_limit = 5
```

Behavior:

- If fewer than 5 translations are running, accept.
- If 5 are running, mark current row as queue full.
- Do not block UI.
- Do not send another API request.

Important nuance:

- `BoundedSemaphore(5)` limits active translations.
- It does not maintain an infinite waiting queue.
- This is the desired behavior because the user wanted queue-full feedback instead of unlimited API backlog.

## Files To Add Later

Recommended native modules:

```text
newsource/native/event_bus.py
newsource/native/log_model.py
newsource/native/log_window.py
newsource/native/log_row_widget.py
newsource/native/workers.py
newsource/native/hotkey_service.py
```

Related modules from other investigations:

```text
newsource/native/config_service.py
newsource/native/log_service.py
newsource/native/screen_capture.py
newsource/native/filter_service.py
newsource/native/ocr_service.py
newsource/native/translation_service.py
newsource/native/region_border.py
```

## Prototype Checklist

Before full implementation, verify:

- Log window opens without web/Eel.
- App can append a source-text row.
- Translation pending state appears below the correct source text.
- Five concurrent translation slots work.
- Sixth rapid request shows queue-full red error and sends no API request.
- Translation completion updates the correct row even when completions are out of order.
- UI remains responsive during OCR and translation.
- Reloading logs displays existing translated entries from file.
- Old second-level IDs and new microsecond IDs both load.
- Window position/size restore after restart.
- Always-on-top works for log window.

## Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Worker thread touches Qt widget directly | Crashes or random UI bugs | Only update UI through PySide signals. |
| Translation finishes before row exists | Missing translation display | Keep `pending_updates` in `LogModel`. |
| OCR jobs pile up when hotkey is spammed | App slows badly | Use single capture/OCR worker or bounded OCR queue. |
| Unlimited translation backlog | API cost and delayed UI | Use bounded semaphore queue limit of 5. |
| Writing logs from multiple threads corrupts file | Broken logs | Keep file lock in `log_service`. |
| Errors look like successful translations | Confusing logs | Separate `translated_text` from `translation_error`. |
| Reload triggers API calls | Surprise cost | Do not auto-translate old logs on startup. |

## Investigation 4 Result

Native UI should use a PySide log window with row widgets keyed by `log_id`.

Final decisions:

- Use `ThreadPoolExecutor` workers plus PySide signals.
- Keep async translation queue limit at 5.
- Use one capture/OCR worker initially.
- Persist source text immediately.
- Persist translation only after successful translation.
- Keep row-level states: pending, done, error, queue full, OCR error.
- Keep `pending_updates` race protection from the web fix.
- Do not add any second automatic translation path that could double API cost.

This preserves the useful behavior of the current async log system while making it native and easier to reason about.
