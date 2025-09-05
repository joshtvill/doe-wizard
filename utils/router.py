# utils/router.py
# Minimal helper to import a screen module and return a callable renderer.

from __future__ import annotations
import importlib
from typing import Callable

def resolve_renderer(module_name: str) -> Callable[[], None]:
    """
    Import the given module and return a callable to render the screen.
    Tries in order: render, render_<module>, render_screen, main.
    Returns a stub that raises at call-time if none found (keeps app.py thin).
    """
    mod = importlib.import_module(module_name)
    base = module_name.split(".")[-1]
    for name in ("render", f"render_{base}", "render_screen", "main"):
        fn = getattr(mod, name, None)
        if callable(fn):
            return fn

    def _missing_renderer() -> None:
        raise RuntimeError(
            f"Module '{module_name}' does not expose a callable renderer. "
            "Expected one of: render, render_<module>, render_screen, main."
        )
    return _missing_renderer
