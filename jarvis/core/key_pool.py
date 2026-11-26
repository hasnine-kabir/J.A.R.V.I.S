"""Rotate between several Gemini API keys.

When a key hits its quota (HTTP 429) it is benched for a while; when a key is
rejected outright (invalid / no permission) it is benched for the session.
Requests are retried on the next available key.
"""
import time

from jarvis.utils.logger import setup_logger

logger = setup_logger("jarvis.keys")

RATE_LIMIT_COOLDOWN = 60          # per-minute limits reset quickly
DAILY_QUOTA_COOLDOWN = 60 * 60    # per-day quota: try again in an hour
DEAD = float("inf")


def mask(key: str) -> str:
    return f"…{key[-4:]}" if len(key) > 4 else "…"


def classify_error(e: Exception) -> str | None:
    """Return 'quota', 'invalid', or None (not a key problem)."""
    code = getattr(e, "code", None)
    text = str(e)
    if code == 429 or "RESOURCE_EXHAUSTED" in text:
        return "quota"
    if code in (401, 403) or "API_KEY_INVALID" in text or "API key not valid" in text \
            or "PERMISSION_DENIED" in text or "API_KEY_SERVICE_BLOCKED" in text:
        return "invalid"
    return None


class AllKeysExhausted(RuntimeError):
    pass


class KeyPool:
    def __init__(self, keys: list[str], client_factory=None, clock=time.monotonic):
        keys = [k.strip() for k in keys if k and k.strip()]
        self._keys = list(dict.fromkeys(keys))  # dedupe, keep order
        if not self._keys:
            raise ValueError("No Gemini API keys configured")
        self._factory = client_factory or self._default_factory
        self._clock = clock
        self._clients: dict[str, object] = {}
        self._benched_until: dict[str, float] = {}
        self._reasons: dict[str, str] = {}
        self._current = 0

    @staticmethod
    def _default_factory(key: str):
        from google import genai
        from google.genai import types

        # Bounded waits: the SDK's default retries can otherwise stall for minutes.
        return genai.Client(
            api_key=key,
            http_options=types.HttpOptions(
                timeout=45_000, retry_options=types.HttpRetryOptions(attempts=1)
            ),
        )

    def __len__(self) -> int:
        return len(self._keys)

    def _available(self, key: str) -> bool:
        return self._clock() >= self._benched_until.get(key, 0)

    def _client(self, key: str):
        if key not in self._clients:
            self._clients[key] = self._factory(key)
        return self._clients[key]

    def _bench(self, key: str, kind: str, e: Exception) -> None:
        if kind == "invalid":
            self._benched_until[key] = DEAD
            self._reasons[key] = "rejected (invalid or not enabled)"
        else:
            daily = "PerDay" in str(e) or "per day" in str(e).lower()
            wait = DAILY_QUOTA_COOLDOWN if daily else RATE_LIMIT_COOLDOWN
            self._benched_until[key] = self._clock() + wait
            self._reasons[key] = "daily quota used up" if daily else "rate limited"
        logger.warning(f"Gemini key {mask(key)} {self._reasons[key]}; switching key")

    def call(self, fn):
        """Run fn(client), rotating to the next key on quota/invalid-key errors."""
        last_error: Exception | None = None
        n = len(self._keys)
        for offset in range(n):
            idx = (self._current + offset) % n
            key = self._keys[idx]
            if not self._available(key):
                continue
            try:
                result = fn(self._client(key))
            except Exception as e:
                kind = classify_error(e)
                if kind is None:
                    raise
                self._bench(key, kind, e)
                last_error = e
                continue
            self._current = idx  # stick with a working key
            return result
        if last_error is not None:
            raise last_error
        raise AllKeysExhausted(
            f"All {n} Gemini API key(s) are out of quota or rejected. Wait a bit or add another key."
        )

    def add(self, keys: list[str]) -> None:
        for k in keys:
            k = k.strip()
            if k and k not in self._keys:
                self._keys.append(k)

    def status(self) -> list[str]:
        now = self._clock()
        lines = []
        for i, key in enumerate(self._keys):
            until = self._benched_until.get(key, 0)
            if now >= until:
                state = "active" if i == self._current else "ready"
            elif until == DEAD:
                state = self._reasons.get(key, "unavailable")
            else:
                state = f"{self._reasons.get(key, 'benched')}, retry in {int(until - now)}s"
            lines.append(f"key {i + 1} ({mask(key)}): {state}")
        return lines
