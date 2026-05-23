from __future__ import annotations

from native.config.service import read_value


def translate_text(text: str) -> str:
    """Translate OCR text using OpenAI.

    Raises ValueError if API key is missing.
    Raises RuntimeError on other translation failures.
    """
    if not text or not text.strip():
        return ""

    api_key = read_value("TRANSLATIONCONFIG", "openai_api_key", "").strip()
    model = read_value("TRANSLATIONCONFIG", "openai_model", "gpt-4.1-nano").strip() or "gpt-4.1-nano"
    source_lang = read_value("TRANSLATIONCONFIG", "source_lang", "en").strip() or "en"
    target_lang = read_value("TRANSLATIONCONFIG", "target_lang", "vi").strip() or "vi"

    if not api_key:
        raise ValueError("OpenAI API key is missing in config.")

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        system_content = (
            "You are translating game dialogue. Translate the user's text from "
            f"{source_lang} to {target_lang} using natural in-context wording. "
            "You may ignore non-meaningful OCR noise and malformed fragments. "
            "If part of the text is unclear, make the best reasonable guess and continue naturally. "
            "Do not translate word by word. Return only the translation as a single line with no extra commentary."
        )
        
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_content},
                {"role": "user", "content": text}
            ],
            temperature=0.3
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        raise RuntimeError(f"Translation Error: {str(e)}")
