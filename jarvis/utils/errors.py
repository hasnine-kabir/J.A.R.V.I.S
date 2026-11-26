"""Turn provider/network exceptions into one-line, actionable messages."""


def friendly_error(e: Exception, model: str = "") -> str:
    text = str(e)
    if "API_KEY_INVALID" in text or "API key not valid" in text:
        return ("Your Gemini API key was rejected. Fix GEMINI_API_KEY in the .env file "
                "(or delete that line and restart Jarvis to be asked again).")
    if "PERMISSION_DENIED" in text:
        return "Gemini refused the request (permission denied). Check that your API key is enabled for the Gemini API."
    if "NOT_FOUND" in text or " 404" in text:
        return (f"The model '{model}' isn't available to your key. "
                "Change llm.model in config.yaml (e.g. gemini-2.5-flash).")
    if "RESOURCE_EXHAUSTED" in text or " 429" in text:
        return "Gemini rate limit or quota reached. Wait a minute and try again."
    if "UNAVAILABLE" in text or " 503" in text or "overloaded" in text.lower():
        return "Gemini is temporarily overloaded. Try again in a moment."
    if any(s in text for s in ("ConnectError", "getaddrinfo", "Name or service not known", "timed out")):
        return "Can't reach Gemini. Check your internet connection."
    return f"Error: {text[:300]}"
