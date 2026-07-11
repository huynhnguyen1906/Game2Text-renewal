from __future__ import annotations

from collections import deque
import json
import threading
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request
from typing import Any

from native.config.service import read_value


REQUEST_TIMEOUT_SECONDS = 45
DEFAULT_MODEL = "gpt-5.4-nano"
HISTORY_LIMIT = 5

_translation_history: deque[tuple[str, str]] = deque(maxlen=HISTORY_LIMIT)
_history_lock = threading.Lock()
_history_context_key: tuple[str, str, str, str] | None = None


def translate_text(text: str, context_labels: tuple[str, ...] = ()) -> str:
    """Translate OCR text using the configured provider."""
    if not text or not text.strip():
        return ""

    provider = read_value("TRANSLATIONCONFIG", "translation_service", "openai").strip().lower() or "openai"
    api_key = read_value("TRANSLATIONCONFIG", "api_key", "").strip()
    model = read_value("TRANSLATIONCONFIG", "model", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    source_lang = read_value("TRANSLATIONCONFIG", "source_lang", "en").strip() or "en"
    target_lang = read_value("TRANSLATIONCONFIG", "target_lang", "vi").strip() or "vi"

    if not api_key:
        raise ValueError("API key is missing in config.")

    normalized_provider = _normalize_provider(provider)
    history_key = (normalized_provider, model, source_lang, target_lang)
    history = _get_history_snapshot(history_key)
    system_prompt = _build_system_prompt(source_lang, target_lang)
    user_prompt = _build_user_prompt(text, history, context_labels=context_labels)

    try:
        if normalized_provider == "openai":
            translated = _translate_with_openai(api_key, model, user_prompt, system_prompt)
        elif normalized_provider == "deepseek":
            translated = _translate_with_deepseek(api_key, model, user_prompt, system_prompt)
        elif normalized_provider == "claude":
            translated = _translate_with_claude(api_key, model, user_prompt, system_prompt)
        elif normalized_provider == "gemini":
            translated = _translate_with_gemini(api_key, model, user_prompt, system_prompt)
        else:
            raise RuntimeError(f"Translation provider '{provider}' is not implemented.")
        _append_translation_history(history_key, text, translated)
        return translated
    except urllib_error.URLError as exc:
        raise RuntimeError(f"Translation request failed: {exc}") from exc
    except Exception as exc:
        if isinstance(exc, (ValueError, RuntimeError)):
            raise
        raise RuntimeError(f"Translation error: {exc}") from exc


def _normalize_provider(provider: str) -> str:
    normalized = provider.strip().lower()
    if normalized in {"anthropic", "claude"}:
        return "claude"
    return normalized


def _build_system_prompt(source_lang: str, target_lang: str) -> str:
    return (
        f"You translate game dialogue from {source_lang} to {target_lang} using natural, context-aware wording. "
        "The user may provide up to five previous source/translation pairs as context. "
        "Use them only to preserve terminology, proper names, pronouns, tone, and consistent translation choices. "
        "Preserve proper names and established terms unless the context clearly provides a translated form. "
        "An optional OCR context label may identify a speaker or provide a name reading; use it only as context and do not output it. "
        "Translate only the current source and never output or retranslate the previous context. "
        "If previous context conflicts with the current source, prioritize the current source. "
        "Ignore meaningless OCR noise and make the best reasonable guess for unclear fragments. "
        "Do not translate word by word. Return only the translation with no commentary."
    )


def _build_user_prompt(
    text: str,
    history: list[tuple[str, str]],
    context_labels: tuple[str, ...] = (),
) -> str:
    sections: list[str] = []
    if history:
        context_lines = ["<previous_context>"]
        for index, (source_text, translated_text) in enumerate(history, start=1):
            context_lines.extend(
                (
                    f"[{index}]",
                    f"Source: {source_text}",
                    f"Translation: {translated_text}",
                    "",
                )
            )
        context_lines.append("</previous_context>")
        sections.append("\n".join(context_lines))
    cleaned_labels = [label.strip() for label in context_labels if label and label.strip()]
    if cleaned_labels:
        sections.append(
            "<ocr_context_labels>\n"
            + "\n".join(cleaned_labels)
            + "\n</ocr_context_labels>"
        )
    sections.append(f"<current_source>\n{text.strip()}\n</current_source>")
    return "\n\n".join(sections)


def _get_history_snapshot(context_key: tuple[str, str, str, str]) -> list[tuple[str, str]]:
    global _history_context_key
    with _history_lock:
        if _history_context_key != context_key:
            _translation_history.clear()
            _history_context_key = context_key
        return list(_translation_history)


def _append_translation_history(
    context_key: tuple[str, str, str, str],
    source_text: str,
    translated_text: str,
) -> None:
    normalized_source = " ".join(source_text.splitlines()).strip()
    normalized_translation = " ".join(translated_text.splitlines()).strip()
    if not normalized_source or not normalized_translation:
        return
    with _history_lock:
        if _history_context_key != context_key:
            return
        if _translation_history and _translation_history[-1][0] == normalized_source:
            _translation_history[-1] = (normalized_source, normalized_translation)
            return
        _translation_history.append((normalized_source, normalized_translation))


def clear_translation_history() -> None:
    global _history_context_key
    with _history_lock:
        _translation_history.clear()
        _history_context_key = None


def _translate_with_openai(api_key: str, model: str, text: str, system_prompt: str) -> str:
    request_payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text},
        ],
    }
    reasoning_effort = _openai_reasoning_effort(model)
    if reasoning_effort is not None:
        request_payload["reasoning_effort"] = reasoning_effort
    elif not model.strip().lower().startswith("gpt-5"):
        request_payload["temperature"] = 0.3

    payload = _post_json(
        "https://api.openai.com/v1/chat/completions",
        {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        request_payload,
    )
    return _extract_openai_style_text(payload)


def _openai_reasoning_effort(model: str) -> str | None:
    normalized = model.strip().lower()
    if normalized.startswith(("gpt-5.1", "gpt-5.2", "gpt-5.4", "gpt-5.5")):
        return "none"
    if normalized == "gpt-5" or normalized.startswith(
        ("gpt-5-2025", "gpt-5-mini", "gpt-5-nano")
    ):
        return "minimal"
    return None


def _translate_with_deepseek(api_key: str, model: str, text: str, system_prompt: str) -> str:
    payload = _post_json(
        "https://api.deepseek.com/chat/completions",
        {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            "temperature": 0.3,
        },
    )
    return _extract_openai_style_text(payload)


def _translate_with_claude(api_key: str, model: str, text: str, system_prompt: str) -> str:
    payload = _post_json(
        "https://api.anthropic.com/v1/messages",
        {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        {
            "model": model,
            "max_tokens": 1024,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": text},
            ],
        },
    )
    return _extract_claude_text(payload)


def _translate_with_gemini(api_key: str, model: str, text: str, system_prompt: str) -> str:
    normalized_model = model.removeprefix("models/")
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{normalized_model}:generateContent"
        f"?{urllib_parse.urlencode({'key': api_key})}"
    )
    payload = _post_json(
        url,
        {
            "Content-Type": "application/json",
        },
        {
            "systemInstruction": {
                "parts": [
                    {"text": system_prompt},
                ]
            },
            "contents": [
                {
                    "parts": [
                        {"text": text},
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.3,
            },
        },
    )
    return _extract_gemini_text(payload)


def _post_json(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib_request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib_request.urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            raw_body = response.read().decode("utf-8")
    except urllib_error.HTTPError as exc:
        response_text = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Provider HTTP {exc.code}: {response_text}") from exc

    try:
        parsed = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Provider returned invalid JSON: {raw_body}") from exc

    if not isinstance(parsed, dict):
        raise RuntimeError("Provider returned an unexpected JSON payload.")
    return parsed


def _extract_openai_style_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices") or []
    if not choices:
        raise RuntimeError("Provider returned no choices.")
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    raise RuntimeError("Provider returned an unexpected response shape.")


def _extract_claude_text(payload: dict[str, Any]) -> str:
    blocks = payload.get("content") or []
    parts: list[str] = []
    for block in blocks:
        if block.get("type") == "text":
            block_text = str(block.get("text", "")).strip()
            if block_text:
                parts.append(block_text)
    result = " ".join(parts).strip()
    if not result:
        raise RuntimeError("Provider returned no text content.")
    return result


def _extract_gemini_text(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates") or []
    if not candidates:
        raise RuntimeError("Provider returned no candidates.")
    content = (candidates[0] or {}).get("content") or {}
    parts = content.get("parts") or []
    texts: list[str] = []
    for part in parts:
        part_text = part.get("text")
        if isinstance(part_text, str) and part_text.strip():
            texts.append(part_text.strip())
    result = " ".join(texts).strip()
    if not result:
        raise RuntimeError("Provider returned no text content.")
    return result
