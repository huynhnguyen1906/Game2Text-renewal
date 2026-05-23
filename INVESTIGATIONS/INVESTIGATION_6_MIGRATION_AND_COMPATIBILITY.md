# Investigation 6: Migration And Compatibility

## Scope

This investigation defines how the native rewrite should handle existing data from the current modified Game2Text source:

- old text logs
- new async translation logs
- old timestamp IDs
- new microsecond IDs
- `config.ini`
- image filter profiles
- runtime folders
- compatibility with the old Eel/web app

The goal is to avoid losing user data and avoid making old logs/config unreadable unless that is explicitly chosen later.

## Executive Decision

Native app should be backward-compatible for reading old data, but it should write using the newer safer formats.

Final compatibility stance:

- Read old log IDs: `YYYYMMDD-HHMMSS`
- Read new log IDs: `YYYYMMDD-HHMMSS-ffffff`
- Write only new microsecond log IDs
- Preserve text log delimiter: `|||TRANSLATION|||`
- Preserve profile YAML keys
- Preserve existing config sections
- Add native config sections without deleting old sections
- Do not auto-migrate destructively
- Do not auto-translate old untranslated logs

The native app should treat migration as additive and reversible.

## Current Data Findings

### Existing Logs

Current log folder:

```text
logs/text/
```

Observed log file examples:

```text
20260502-050745.txt
20260502-051931-005131.txt
20260502-052222-628887.txt
```

This means the repo currently contains both:

- old session filenames with second-level IDs
- new session filenames with microsecond IDs

Observed old line format:

```text
20260502-051008, aa + In the top 10 high scores...|||TRANSLATION|||Trong top 10 điểm...
```

Observed new line format:

```text
20260502-052239-415530, & In the top 10 high scores...|||TRANSLATION|||Trong top 10 điểm...
```

### Duplicate Old IDs

Old logs can contain duplicated IDs when multiple OCR triggers happen within the same second:

```text
20260502-051018, ...
20260502-051018, ...
20260502-051025, ...
20260502-051025, ...
20260502-051025, ...
```

This caused web UI update bugs because rows were keyed by duplicate DOM/log IDs.

Decision:

- Native parser must read old duplicate IDs.
- Native writer must never generate duplicate second-level IDs.
- Native UI model should create a stable internal key for old duplicate rows if necessary.

## Log Format Decision

Keep the existing text log format:

```text
<log_id>, <source_text>|||TRANSLATION|||<translated_text>
```

For untranslated rows:

```text
<log_id>, <source_text>
```

Reasons:

- Existing logs remain readable.
- Current web app can still read native-created translated lines if it accepts microsecond IDs.
- The format is simple and already works with async translation.

## Log ID Compatibility

Accepted ID patterns:

```text
YYYYMMDD-HHMMSS
YYYYMMDD-HHMMSS-fff
YYYYMMDD-HHMMSS-ffffff
```

Equivalent regex:

```python
LOG_ID_PATTERN = re.compile(r"^\d{8}-\d{6}(?:-\d{3,6})?$")
```

Native generated IDs:

```python
datetime.now().strftime("%Y%m%d-%H%M%S-%f")
```

Rules:

- New native log rows always use microseconds.
- Parser uses the first 15 chars for display time.
- Old IDs are accepted.
- Old duplicate IDs are allowed during load, but not during write.

## Internal Row Key For Old Duplicate IDs

Problem:

- Old logs may contain duplicate `log_id`.
- Native UI must update rows by stable key.
- New native rows can use `log_id` directly because microsecond IDs should be unique.

Recommended native model:

```python
@dataclass
class LogEntry:
    id: str
    row_key: str
    folder: str
    source_text: str
    translated_text: str | None = None
```

For new native rows:

```text
row_key = id
```

For loaded old logs:

```text
row_key = f"{folder}:{line_number}:{id}"
```

Rules:

- UI uses `row_key`.
- File update for newly created current-session rows uses `id`.
- Old duplicate rows should be viewable.
- Editing/updating old duplicate rows by `id` alone is unsafe.

Decision:

- MVP native should not try to update old duplicate historical rows automatically.
- Current-session native rows are unique and safe to update.

## Log Parser Requirements

Native `log_service.py` should:

- Read latest session log.
- Optionally read recent session logs later.
- Skip invalid/short lines.
- Split only on the first `", "`.
- Split translation only on the first `|||TRANSLATION|||`.
- Preserve commas inside OCR text.
- Preserve Vietnamese translation text.
- Strip trailing newlines.
- Avoid creating fake error log entries for parse failures.

Recommended parser shape:

```python
def parse_log_line(line: str, folder: str, line_number: int) -> LogEntry | None:
    log_id, content = split_log_line(line)
    if not log_id:
        return None
    source, translated = split_translation(content)
    return LogEntry(
        id=log_id,
        row_key=f"{folder}:{line_number}:{log_id}",
        folder=folder,
        source_text=source,
        translated_text=translated,
    )
```

## Log Writer Requirements

Native `log_service.py` should:

- Use a file lock.
- Write UTF-8.
- Write one log entry per line.
- Remove newlines from source/translation before writing, matching current behavior.
- Append source text immediately.
- Rewrite the matching current-session row after successful translation.
- Use atomic-ish temp file replacement for update.

Recommended update behavior:

- For current-session native rows, update by exact `log_id`.
- If multiple lines match the same `log_id`, update only the intended line if line number is known.
- Since native-generated IDs are unique, normal current-session updates are safe.

## Translation Error Persistence

Decision:

- Do not write queue-full/API errors into `|||TRANSLATION|||`.

Reason:

- `translated_text` should mean successful translation.
- Runtime errors should be UI state.
- Reloading logs should not show a queue-full warning as if it were a translation.

Optional later:

- Add sidecar metadata if persistent errors matter:

```text
logs/meta/<session>.json
```

Not required for MVP.

## Config Compatibility

Current config sections:

```ini
[APPEARANCE]
[APPCONFIG]
[ANKICONFIG]
[OCRCONFIG]
[TRANSLATIONCONFIG]
[LOGCONFIG]
[SCRIPTMATCHCONFIG]
[TEXTHOOKERCONFIG]
[WINDOWS_HOTKEYS]
[MAC_HOTKEYS]
[LINUX_HOTKEYS]
[PATHS]
```

Native should preserve existing sections and add:

```ini
[REGIONCONFIG]
[NATIVEAPP]
[FILTERCONFIG]
```

Rules:

- Do not delete old sections.
- Do not rename old sections in-place.
- Read OpenAI key from existing `[TRANSLATIONCONFIG]`.
- Read OCR language/OEM/options from existing `[OCRCONFIG]` where possible.
- Read current session log sizes from `[LOGCONFIG]` if native-specific values are missing.
- Write native-specific keys only to native sections.
- Repair missing native sections on startup.

Important current source issue:

- `config.py` reads with an absolute `config_file`, but `w_config()` writes `"config.ini"` relative to cwd.

Native decision:

- `config_service.py` must use an explicit runtime config path for both read and write.

## Translation Provider Compatibility

Current user-facing config says:

```ini
translation_service = Google Translate
```

But current modified code uses OpenAI inside the Google Translate branch.

Native compatibility decision:

- Preserve this value when reading old config.
- Internally map `"Google Translate"` to the OpenAI translation provider for this project, or introduce a clearer native key without breaking old config.

Recommended native behavior:

```text
If translation_service == "Google Translate":
    use OpenAI provider for compatibility with current modified app
```

Optional later:

```ini
[TRANSLATIONCONFIG]
translation_service = OpenAI
openai_model = gpt-4.1-nano
```

But do not force this migration in MVP.

## Profile Compatibility

Existing profile path:

```text
profiles/
```

Existing YAML keys:

```yaml
invertColor: true
dilate: true
blurImageRadius: 0
binarizeThreshold: 19
```

Rules:

- Native reads old YAML profiles.
- Native exports profiles old app can read.
- Native keeps same key casing.
- Native keeps `binarizeThreshold` omission behavior when binarize is disabled.
- Native loads display name from file stem.

Decision:

- No profile migration is needed.
- Runtime `profiles/` remains the shared compatibility folder.

## Runtime Folder Compatibility

Current folders:

```text
logs/text/
logs/images/
logs/audio/
profiles/
resources/bin/win/tesseract/
```

Native MVP uses:

```text
logs/text/
profiles/
resources/bin/win/tesseract/
```

Native should not require:

- `logs/audio/`
- old image log folders
- Anki files
- dictionary resources
- Textractor resources

Decision:

- Keep `logs/images/` untouched if it exists.
- Do not delete or migrate old image/audio logs.
- Native may ignore old image/audio references in MVP.

## Sharing Data With Old Web App

Can native and old web app share the same `config.ini`, `logs/`, and `profiles/`?

### Profiles

Yes.

Reason:

- YAML format remains compatible.

### Logs

Mostly yes.

Reason:

- Native writes the same text/translation separator format.
- Current old source has already been updated to accept microsecond IDs.

Risk:

- Older unmodified Game2Text builds may not accept microsecond IDs.

Decision:

- Compatibility target is this modified project, not the original upstream clone.

### Config

Partially.

Reason:

- Native adds new sections old app should ignore.
- Old app may preserve unknown sections when writing config if ConfigParser reads/writes whole file.

Risk:

- Current old `w_config()` writes relative to cwd and may rewrite config formatting.
- If old app writes config, it should usually keep unknown sections, but this should be tested.

Decision:

- Native should preserve old sections.
- Avoid relying on old web app to preserve native sections perfectly.
- Keep backups before any automated config migration.

## Migration Strategy

### First Native Run

1. Locate runtime `config.ini`.
2. If missing, create from default.
3. If present, read existing sections.
4. Add missing native sections/keys.
5. Do not remove old sections.
6. Ensure runtime `logs/text/` exists.
7. Ensure runtime `profiles/` exists.
8. Load existing profiles.
9. Load latest logs.

### Backup Rule

Before writing native sections for the first time, optionally create:

```text
config.ini.bak-native-first-run
```

Decision:

- Recommended for implementation.

Reason:

- Config contains the user's OpenAI key and tuned OCR settings.
- Backup makes migration reversible.

### No Destructive Migration

Native should not:

- rename old log files
- rewrite all old logs
- delete old duplicate IDs
- delete old config sections
- move old profiles
- convert old image/audio logs

## Compatibility Tests

Required tests/prototype checks:

- Parse old log file `20260502-050745.txt`.
- Parse new log file `20260502-052222-628887.txt`.
- Load old duplicate IDs without crashing UI.
- Generate new microsecond log ID.
- Append source-only row.
- Update native-generated row with translation.
- Reload and show translated text.
- Load old profile `light-background.yaml`.
- Load old profile `wuwa.yaml`.
- Export native profile and load it in old web app.
- Add native sections to copied `config.ini` without removing old sections.
- Read OpenAI key from `[TRANSLATIONCONFIG]`.
- Read OCR config from `[OCRCONFIG]`.

## Files To Add Later

Recommended native modules:

```text
newsource/native/migration.py
newsource/native/config_service.py
newsource/native/log_service.py
newsource/native/image_profile_service.py
```

Recommended migration helpers:

```python
def ensure_native_config_sections(config_path: Path) -> None:
    ...

def backup_config_once(config_path: Path) -> None:
    ...

def parse_legacy_log_id(log_id: str) -> datetime:
    ...

def make_row_key(folder: str, line_number: int, log_id: str) -> str:
    ...
```

## Risks

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Old duplicate IDs update wrong row | Wrong translation shown or wrong line rewritten | Use microsecond IDs for new rows and `row_key` for loaded old rows. |
| Native rewrites old logs | Data corruption | Append/update current session only; do not bulk-migrate logs. |
| Config migration removes old sections | Old app breaks or user settings lost | Add sections only; create backup before first native write. |
| Old app overwrites native sections | Native settings lost | Keep native settings repairable; consider separate native config later if needed. |
| Error messages saved as translations | Reloaded logs become misleading | Do not persist runtime errors as `translated_text`. |
| Profiles become incompatible | User loses tuned filters | Preserve exact YAML keys and omission behavior. |
| Packaged build overwrites logs/profiles/config | Data loss | Runtime files stay beside exe and build script must not replace them. |

## Investigation 6 Result

Migration should be additive, not destructive.

Final decisions:

- Read both old and new log ID formats.
- Write only microsecond IDs.
- Keep `|||TRANSLATION|||`.
- Use `row_key` internally to handle old duplicate IDs.
- Keep profile YAML format unchanged.
- Add `[REGIONCONFIG]`, `[NATIVEAPP]`, and `[FILTERCONFIG]` without deleting existing config sections.
- Create a config backup before first native migration if practical.
- Do not auto-translate old logs.
- Do not rewrite or clean old logs automatically.
- Preserve compatibility with this modified source, not necessarily every upstream Game2Text version.

This lets the native app reuse the user's current logs/config/profiles while avoiding the duplicate-ID and web-event problems that motivated the rewrite.
