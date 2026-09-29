"""Language guidance — mirrors discord-bot-agents/src/agent/language.js.

Match the user's language; English only when ambiguous. Thai detection added
for this bot's audience.
"""

import re

NAMES = {
    "en": "ENGLISH", "id": "INDONESIAN", "th": "THAI", "ar": "ARABIC",
    "ja": "JAPANESE", "ru": "RUSSIAN", "de": "GERMAN", "es": "SPANISH",
    "fr": "FRENCH", "zh": "CHINESE", "ko": "KOREAN", "pt": "PORTUGUESE",
}

_FORCED = [
    ("en", r"in english|reply in english"),
    ("id", r"in indonesian|bahasa indonesia|reply in indonesian"),
    ("th", r"in thai|ภาษาไทย|ตอบเป็นไทย"),
    ("ar", r"in arabic|bahasa arab"),
    ("ja", r"in japanese|bahasa jepang"),
    ("ru", r"in russian|bahasa rusia"),
    ("de", r"in german|bahasa jerman"),
    ("es", r"in spanish|bahasa spanyol"),
    ("fr", r"in french|bahasa prancis"),
    ("zh", r"in chinese|bahasa mandarin"),
    ("ko", r"in korean|bahasa korea"),
    ("pt", r"in portuguese|bahasa portugis"),
]

_ID_WORDS = (r"\b(buatlah|buatkan|tolong|hapus|hapuskan|tampilkan|berikan|carikan|"
             r"kirimkan|kamu|siapa|daftar|tambah|ganti|bisukan|keluarkan|selamanya|"
             r"dalam|anggota|beri|list)\b|^(hei+|hai+|halo+|pagi|siang|sore|malam)\b")
_EN_WORDS = (r"^(how|what|why|when|where|who|tell|create|make|change|list|give|show|"
             r"timeout|is|are|can|do|did|will|would|could|rename|deafen|unmute|snipe|"
             r"search|kick|ban|mute|block|unblock|hi|hey|hello)\b")
_TH_WORDS = r"(ครับ|ค่ะ|อะไร|ยังไง|อย่างไร|ช่วย|สร้าง|ลบ|แสดง|รายการ|เชิญ|สวัสดี|ขอ|หน่อย|ให้)"


def detect_language(msg: str) -> dict:
    text = (msg or "").strip()
    for lang, pat in _FORCED:
        if re.search(pat, text, re.IGNORECASE):
            return {"lang": lang, "name": NAMES[lang], "mode": "forced"}
    if re.search(r"[\u3040-\u30ff]", text):
        return {"lang": "ja", "name": NAMES["ja"], "mode": "detected"}
    if re.search(r"[\u3400-\u9fff]", text):
        return {"lang": "zh", "name": NAMES["zh"], "mode": "detected"}
    if re.search(r"[\u0600-\u06ff]", text):
        return {"lang": "ar", "name": NAMES["ar"], "mode": "detected"}
    if re.search(r"[\u0400-\u04ff]", text):
        return {"lang": "ru", "name": NAMES["ru"], "mode": "detected"}
    if re.search(r"[\uac00-\ud7af]", text):
        return {"lang": "ko", "name": NAMES["ko"], "mode": "detected"}
    if re.search(r"[\u0e00-\u0e7f]", text) or re.search(_TH_WORDS, text):
        return {"lang": "th", "name": NAMES["th"], "mode": "detected"}
    if re.search(_ID_WORDS, text, re.IGNORECASE):
        return {"lang": "id", "name": NAMES["id"], "mode": "detected"}
    if re.search(_EN_WORDS, text, re.IGNORECASE):
        return {"lang": "en", "name": NAMES["en"], "mode": "detected"}
    return {"lang": "en", "name": NAMES["en"], "mode": "default"}


def language_instruction(detected: dict, phase: str) -> str:
    if phase == "plan":
        return 'Write "reasoning" in English. Understand the user request in ANY language.'
    if detected.get("mode") in ("forced", "detected"):
        return f'Your "reply" MUST be 100% in {detected["name"]}.'
    return 'Your "reply" MUST match the user\'s language. If ambiguous, use ENGLISH.'
