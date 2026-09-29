"""Shared LLM layer: multi-key Gemini rotation + JSON extraction.

bot.py configures the singleton at startup via configure();
agent/* modules call generate_text() — no import cycles (agent never imports bot).
"""

import asyncio
import itertools
import logging
import time

import httpx

from src.utils.json_helper import extract_json  # noqa: F401 (re-exported for agent/*)

log = logging.getLogger("gemini-bot")

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

_client: "GeminiRotator | None" = None
_default_system: str = (
    "You are a helpful Discord AI assistant. Reply concisely in the user's language (default Thai)."
)


def configure(keys: list[str], model: str = "gemini-2.0-flash", system_prompt: str | None = None):
    global _client, _default_system
    if system_prompt:
        _default_system = system_prompt
    _client = GeminiRotator(keys, model)


def get_client() -> "GeminiRotator":
    if _client is None:
        raise RuntimeError("llm not configured — bot.py must call llm.configure() first")
    return _client


async def generate_text(
    prompt: str,
    *,
    system: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 2048,
    timeout: float = 60.0,
) -> str:
    """Single-turn call (planner / summarizer)."""
    return await get_client().generate(
        [{"role": "user", "text": prompt}],
        timeout=timeout,
        system=system,
        temperature=temperature,
        max_tokens=max_tokens,
    )


class GeminiRotator:
    """วน API key หลายตัว เมื่อโดน 429/quota จะข้ามไปตัวถัดไปอัตโนมัติ"""

    def __init__(self, keys: list[str], model: str = "gemini-2.0-flash"):
        if not keys:
            raise ValueError("GEMINI_KEYS ว่าง — ใส่คีย์อย่างน้อย 1 ตัวใน .env")
        self._keys = keys
        self.model = model
        self._cycle = itertools.cycle(range(len(keys)))
        self._lock = asyncio.Lock()
        self._dead: dict[int, float] = {}  # index -> unix time ที่กลับมาใช้ได้

    @property
    def key_count(self) -> int:
        return len(self._keys)

    async def _next_key(self) -> tuple[int, str]:
        async with self._lock:
            for _ in range(len(self._keys)):
                i = next(self._cycle)
                if self._dead.get(i, 0) < time.time():
                    return i, self._keys[i]
            # ทุกตัวโดน cooldown หมด -> ล้างแล้วลองใหม่
            self._dead.clear()
            i = next(self._cycle)
            return i, self._keys[i]

    def mark_dead(self, idx: int, cooldown_sec: int = 60):
        self._dead[idx] = time.time() + cooldown_sec
        log.warning(f"Gemini key #{idx + 1} โดน limit -> พัก {cooldown_sec}s แล้วสลับตัวถัดไป")

    def set_model(self, model: str):
        """Switch backbone at runtime (e.g. via /model). Clears key cooldowns."""
        self.model = model.strip()
        self._dead.clear()
        log.info(f"LLM backbone switched to {self.model}")

    def add_keys(self, new_keys: list[str]) -> int:
        """Append keys at runtime (e.g. via /addkey). Returns # actually added."""
        added = 0
        for k in new_keys:
            k = k.strip()
            if k and k not in self._keys:
                self._keys.append(k)
                added += 1
        if added:
            self._cycle = itertools.cycle(range(len(self._keys)))
        return added

    def status(self) -> dict:
        import time as _t

        now = _t.time()
        resting = sum(1 for t in self._dead.values() if t > now)
        return {"model": self.model, "keys": len(self._keys), "cooling_down": resting}

    async def generate(
        self,
        messages: list[dict],
        timeout: float = 60.0,
        *,
        system: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 1500,
    ) -> str:
        """messages = [{'role': 'user'|'model', 'text': str}]"""
        contents = [
            {"role": ("model" if m["role"] == "model" else "user"),
             "parts": [{"text": m["text"]}]} for m in messages
        ]
        payload = {
            "system_instruction": {"parts": [{"text": system or _default_system}]},
            "contents": contents,
            "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens},
        }
        last_err = None
        async with httpx.AsyncClient(timeout=timeout) as client:
            for _ in range(len(self._keys)):
                idx, key = await self._next_key()
                url = f"{GEMINI_API_BASE}/{self.model}:generateContent?key={key}"
                try:
                    r = await client.post(url, json=payload)
                    if r.status_code == 200:
                        data = r.json()
                        try:
                            return data["candidates"][0]["content"]["parts"][0]["text"].strip()
                        except (KeyError, IndexError):
                            last_err = f"Gemini ตอบแปลก: {data}"
                            continue
                    elif r.status_code in (429, 403, 500, 503):
                        # 429 / quota exceeded / overloaded -> สลับคีย์
                        self.mark_dead(idx)
                        last_err = f"HTTP {r.status_code}: {r.text[:300]}"
                        continue
                    else:
                        last_err = f"HTTP {r.status_code}: {r.text[:300]}"
                        # error ที่ไม่ใช่ quota (เช่น 400 prompt ผิด) ไม่ต้องสลับคีย์
                        break
                except httpx.HTTPError as e:
                    last_err = str(e)
                    break
        raise RuntimeError(f"Gemini ทุกคีย์ใช้ไม่ได้: {last_err}")
