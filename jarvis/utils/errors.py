"""Turn provider/network exceptions into one-line, actionable messages."""


def friendly_error(e: Exception, model: str = "") -> str:
    text = str(e)
    if "API_KEY_INVALID" in text or "API key not valid" in text:
        return ("Your Gemini API key(s) were rejected. Fix GEMINI_API_KEYS in the .env file, "
                "or add a working key with /addkey.")
    if "PERMISSION_DENIED" in text:
        return "Gemini refused the request (permission denied). Check that your API key is enabled for the Gemini API."
    if "NOT_FOUND" in text or " 404" in text:
        return (f"The model '{model}' isn't available to your key. "
                "Change llm.model in config.yaml (e.g. gemini-3.5-flash).")
    if "RESOURCE_EXHAUSTED" in text or " 429" in text or "out of quota" in text:
        return ("All your Gemini API keys are out of quota right now. Wait a minute, "
                "or add another key with /addkey (or: python -m jarvis --add-key).")
    if "UNAVAILABLE" in text or " 503" in text or "overloaded" in text.lower():
        return "Gemini is temporarily overloaded. Try again in a moment."
    if any(s in text for s in ("ConnectError", "getaddrinfo", "Name or service not known", "timed out")):
        return "Can't reach Gemini. Check your internet connection."
    return f"Error: {text[:300]}"
