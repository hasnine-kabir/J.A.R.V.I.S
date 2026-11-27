"""Import heavy modules on first use instead of at startup."""
import importlib


class LazyModule:
    """Stands in for a module; the real import happens on first attribute access.

    Attributes set on the proxy (e.g. by `unittest.mock.patch`) take precedence.
    """

    def __init__(self, name: str):
        self.__dict__["_lazy_name"] = name

    def __getattr__(self, attr):
        return getattr(importlib.import_module(self._lazy_name), attr)

    def __repr__(self) -> str:
        return f"<lazy module {self._lazy_name!r}>"
