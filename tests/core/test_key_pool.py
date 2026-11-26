import pytest

from jarvis.core.key_pool import AllKeysExhausted, KeyPool, classify_error


class FakeAPIError(Exception):
    def __init__(self, code, msg):
        super().__init__(f"{code} {msg}")
        self.code = code


QUOTA = FakeAPIError(429, "RESOURCE_EXHAUSTED quota exceeded")
DAILY = FakeAPIError(429, "RESOURCE_EXHAUSTED GenerateRequestsPerDayPerProjectPerModel")
INVALID = FakeAPIError(400, "API_KEY_INVALID API key not valid")


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def make_pool(keys, behaviour, clock=None):
    """behaviour: key -> list of results/exceptions consumed per call."""
    calls = []

    def fn(client):
        calls.append(client)
        outcome = behaviour[client].pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    pool = KeyPool(keys, client_factory=lambda k: k, clock=clock or Clock())
    return pool, fn, calls


def test_classify_error():
    assert classify_error(QUOTA) == "quota"
    assert classify_error(INVALID) == "invalid"
    assert classify_error(FakeAPIError(403, "PERMISSION_DENIED")) == "invalid"
    assert classify_error(FakeAPIError(500, "INTERNAL")) is None


def test_requires_a_key():
    with pytest.raises(ValueError):
        KeyPool(["", "  "])


def test_dedupes_keys():
    assert len(KeyPool(["a", "a", " b "], client_factory=lambda k: k)) == 2


def test_uses_first_key_when_healthy():
    pool, fn, calls = make_pool(["a", "b"], {"a": ["ok", "ok"], "b": []})
    assert pool.call(fn) == "ok"
    assert pool.call(fn) == "ok"
    assert calls == ["a", "a"]


def test_rotates_on_quota_and_sticks_with_new_key():
    pool, fn, calls = make_pool(["a", "b"], {"a": [QUOTA], "b": ["ok", "ok"]})
    assert pool.call(fn) == "ok"
    assert pool.call(fn) == "ok"
    assert calls == ["a", "b", "b"]
    assert "rate limited" in pool.status()[0]
    assert pool.status()[1].endswith("active")


def test_quota_key_comes_back_after_cooldown():
    clock = Clock()
    pool, fn, calls = make_pool(["a", "b"], {"a": [QUOTA, "ok-a"], "b": ["ok-b", QUOTA]}, clock)
    assert pool.call(fn) == "ok-b"
    clock.t += 61
    assert pool.call(fn) == "ok-a"   # b hits quota, a is back
    assert calls == ["a", "b", "b", "a"]


def test_daily_quota_benches_longer():
    clock = Clock()
    pool, fn, _ = make_pool(["a", "b"], {"a": [DAILY], "b": ["ok"]}, clock)
    pool.call(fn)
    assert "daily quota" in pool.status()[0]
    clock.t += 120
    assert "daily quota" in pool.status()[0]  # still benched after 2 minutes


def test_invalid_key_is_skipped_for_the_session():
    clock = Clock()
    pool, fn, calls = make_pool(["bad", "good"], {"bad": [INVALID], "good": ["ok", "ok"]}, clock)
    pool.call(fn)
    clock.t += 10**6
    pool.call(fn)
    assert calls == ["bad", "good", "good"]
    assert "rejected" in pool.status()[0]


def test_all_keys_out_raises_last_error_then_exhausted():
    pool, fn, _ = make_pool(["a", "b"], {"a": [QUOTA], "b": [QUOTA]})
    with pytest.raises(FakeAPIError):
        pool.call(fn)
    with pytest.raises(AllKeysExhausted):
        pool.call(fn)


def test_non_key_errors_are_not_swallowed():
    boom = FakeAPIError(500, "INTERNAL")
    pool, fn, calls = make_pool(["a", "b"], {"a": [boom], "b": ["ok"]})
    with pytest.raises(FakeAPIError):
        pool.call(fn)
    assert calls == ["a"]


def test_add_keys_at_runtime():
    pool, fn, calls = make_pool(["a"], {"a": [QUOTA], "c": ["ok"]})
    pool.add(["c", "a"])
    assert len(pool) == 2
    assert pool.call(fn) == "ok"
    assert calls == ["a", "c"]


def test_status_masks_keys():
    pool = KeyPool(["AIzaSecretKey1234"], client_factory=lambda k: k)
    assert pool.status() == ["key 1 (…1234): active"]
    assert "Secret" not in pool.status()[0]


def test_brain_rotates_keys_end_to_end():
    from types import SimpleNamespace

    from google.genai import types

    from jarvis.core.brain import GeminiBrain, Message

    ok = SimpleNamespace(candidates=[SimpleNamespace(
        content=types.Content(role="model", parts=[types.Part.from_text(text="hi")]))])

    class Client:
        def __init__(self, key):
            self.key = key
            self.models = self

        def generate_content(self, **kw):
            if self.key == "k1":
                raise QUOTA
            return ok

    brain = GeminiBrain(["k1", "k2"], model="m", client_factory=Client)
    assert brain.think([Message("user", "hello")], [], "sys").text == "hi"
    assert brain.keys.status()[1] == "key 2 (…): active"
