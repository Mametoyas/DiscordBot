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
GROQ_API_BASE = "https://api.groq.com/openai/v1/chat/completions"

# Models served by Groq (OpenAI-compatible API) instead of Gemini.
GROQ_MODELS = {"openai/gpt-oss-120b", "openai/gpt-oss-20b",
               "allam-2-7b", "qwen/qwen3.8-27b"}

_groq_key: str = ""

_client: "GeminiRotator | None" = None
_default_system: str = (
    "You are a helpful Discord AI assistant. Reply concisely in the user's language (default Thai)."
)


def configure(keys: list[str], model: str = "gemini-2.0-flash", system_prompt: str | None = None):
    global _client, _default_system, _groq_key
    if system_prompt:
        _default_system = system_prompt
    _client = GeminiRotator(keys, model)


def get_client() -> "GeminiRotator":
    if _client is None:
        raise RuntimeError("llm not configured — bot.py must call llm.configure() first")
    return _client


def set_groq_key(key: str):
    """Groq key can be set/rotated at runtime (env GROQ_API_KEY at boot)."""
    global _groq_key
    _groq_key = (key or "").strip()
    log.info("Groq key %s", "set" if _groq_key else "cleared")


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
        self.usage: dict[str, dict] = {}  # model -> {requests, ok, errors, in/out tokens, last_error}
        self.key_stats: list[dict] = [{"requests": 0, "ok": 0, "errors": 0} for _ in keys]

    def _record(self, model: str, idx: int | None, ok: bool,
                in_t: int = 0, out_t: int = 0, err: str | None = None):
        u = self.usage.setdefault(
            model, {"requests": 0, "ok": 0, "errors": 0,
                    "in_tokens": 0, "out_tokens": 0, "last_error": None})
        u["requests"] += 1
        u["in_tokens"] += in_t
        u["out_tokens"] += out_t
        if ok:
            u["ok"] += 1
        else:
            u["errors"] += 1
            u["last_error"] = (err or "?")[:200]
        if idx is not None and 0 <= idx < len(self.key_stats):
            k = self.key_stats[idx]
            k["requests"] += 1
            k["ok" if ok else "errors"] += 1

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
                self.key_stats.append({"requests": 0, "ok": 0, "errors": 0})
                added += 1
        if added:
            self._cycle = itertools.cycle(range(len(self._keys)))
        return added

    async def _groq_generate(self, messages: list[dict], timeout: float, *,
                               system: str | None, temperature: float,
                               max_tokens: int) -> str:
        """OpenAI-compatible chat via Groq (single key, no rotation)."""
        if not _groq_key:
            raise RuntimeError("GROQ_API_KEY not set — add it in .env or ENV, then restart")
        payload = {
            "model": self.model,
            "messages": ([{"role": "system", "content": system or _default_system}]
                         + [{"role": ("assistant" if m["role"] == "model" else "user"),
                             "content": m["text"]} for m in messages]),
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        async with httpx.AsyncClient(timeout=timeout) as client:
            try:
                r = await client.post(
                    GROQ_API_BASE, json=payload,
                    headers={"Authorization": f"Bearer {_groq_key}"})
            except httpx.HTTPError as e:
                self._record(self.model, None, False, err=str(e))
                raise RuntimeError(f"Groq request failed: {e}")
        if r.status_code != 200:
            self._record(self.model, None, False, err=f"HTTP {r.status_code}")
            raise RuntimeError(f"Groq error HTTP {r.status_code}: {r.text[:300]}")
        try:
            data = r.json()
            text = data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError):
            self._record(self.model, None, False, err="bad response")
            raise RuntimeError(f"Groq ตอบแปลก: {r.text[:300]}")
        usage = data.get("usage", {}) or {}
        self._record(self.model, None, True,
                     usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
        return text

    def status(self) -> dict:
        import time as _t

        now = _t.time()
        resting = sum(1 for t in self._dead.values() if t > now)
        provider = "groq" if self.model in GROQ_MODELS else "gemini"
        return {"model": self.model, "provider": provider,
                "keys": len(self._keys), "cooling_down": resting,
                "groq_key": bool(_groq_key),
                "usage": self.usage, "key_usage": self.key_stats}

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
        if self.model in GROQ_MODELS:
            return await self._groq_generate(messages, timeout,
                                             system=system, temperature=temperature,
                                             max_tokens=max_tokens)
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
                            text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
                        except (KeyError, IndexError):
                            last_err = f"Gemini ตอบแปลก: {data}"
                            self._record(self.model, idx, False, err=last_err)
                            continue
                        um = data.get("usageMetadata", {}) or {}
                        self._record(self.model, idx, True,
                                     um.get("promptTokenCount", 0),
                                     um.get("candidatesTokenCount", 0))
                        return text
                    elif r.status_code in (429, 403, 500, 503):
                        # 429 / quota exceeded / overloaded -> สลับคีย์
                        self.mark_dead(idx)
                        last_err = f"HTTP {r.status_code}: {r.text[:300]}"
                        self._record(self.model, idx, False, err=last_err)
                        continue
                    else:
                        last_err = f"HTTP {r.status_code}: {r.text[:300]}"
                        self._record(self.model, idx, False, err=last_err)
                        # error ที่ไม่ใช่ quota (เช่น 400 prompt ผิด) ไม่ต้องสลับคีย์
                        break
                except httpx.HTTPError as e:
                    last_err = str(e)
                    self._record(self.model, idx, False, err=last_err)
                    break
        raise RuntimeError(f"Gemini ทุกคีย์ใช้ไม่ได้: {last_err}")
