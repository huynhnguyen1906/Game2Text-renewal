from __future__ import annotations

from native.config.service import read_value


def translate_text(text: str) -> str:
    """Translate OCR text using OpenAI.
    
    Reads mapping from TRANSLATIONCONFIG for compatibility.
    Raises ValueError if API key is missing.
    Raises RuntimeError on other translation failures.
    """
    if not text or not text.strip():
        return ""

    service = read_value("TRANSLATIONCONFIG", "translation_service", "Google Translate")
    api_key = read_value("TRANSLATIONCONFIG", "openai_api_key", "").strip()
    model = read_value("TRANSLATIONCONFIG", "openai_model", "gpt-4.1-nano").strip() or "gpt-4.1-nano"

    # Preserve old behavior: "Google Translate" is mapped to OpenAI in recent updates.
    if service != "Google Translate":
        # MVP only guarantees the current OpenAI-backed translation path.
        service = "Google Translate"

    if not api_key:
        raise ValueError("OpenAI API key is missing in config.")

    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        system_content = (
            "Đây là các đoạn thoại của game. Hãy dịch văn bản từ tiếng Anh sang tiếng Việt theo ngữ cảnh game. Bạn hoàn toàn có thể bỏ qua các ký tự không phải tiếng anh và không rõ nghĩa và Nếu có từ nào không rõ ràng, hãy cố gắng dự đoán và tiếp tục phần dịch, đừng dịch word by word hãy tự phán đoán nghĩa 1 cách mềm mại. Chỉ cần trả ra mỗi bản dịch không cần nói gì thêm và trả ra trên 1 dòng không cần xuống dòng. "
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
