from __future__ import annotations

import json
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request
from typing import Any

from native.config.service import read_value


REQUEST_TIMEOUT_SECONDS = 45
DEFAULT_MODEL = "gpt-4.1-nano"


def translate_text(text: str) -> str:
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

    system_prompt = _build_system_prompt(source_lang, target_lang)
    normalized_provider = _normalize_provider(provider)

    try:
        if normalized_provider == "openai":
            return _translate_with_openai(api_key, model, text, system_prompt)
        if normalized_provider == "deepseek":
            return _translate_with_deepseek(api_key, model, text, system_prompt)
        if normalized_provider == "claude":
            return _translate_with_claude(api_key, model, text, system_prompt)
        if normalized_provider == "gemini":
            return _translate_with_gemini(api_key, model, text, system_prompt)
        raise RuntimeError(f"Translation provider '{provider}' is not implemented.")
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
        "You are translating game dialogue. Translate the user's text from "
        f"{source_lang} to {target_lang} using natural in-context wording. "
        "You may ignore non-meaningful OCR noise and malformed fragments. "
        "If part of the text is unclear, make the best reasonable guess and continue naturally. "
        "Do not translate word by word. Return only the translation as a single line with no extra commentary."
    )


def _translate_with_openai(api_key: str, model: str, text: str, system_prompt: str) -> str:
    payload = _post_json(
        "https://api.openai.com/v1/chat/completions",
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
