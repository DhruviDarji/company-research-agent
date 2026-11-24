"""Service layer: cached brief building shared by the API and the CLI."""
import threading
import time

from .brief import build
from .export import to_text

CACHE_TTL = 900  # seconds: PDF/Excel downloads reuse the brief instead of re-searching
_cache = {}
_lock = threading.Lock()  # search engines are rate-limited globally, so build one brief at a time


def get_brief(qs):
    """Build (or reuse for 15 min) the brief for a query dict with keys q, hint, prefer, website, linkedin, about."""
    kw = dict(hint=qs.get("hint", ""), prefer=qs.get("prefer", "india"),
              website=qs.get("website") or None, linkedin=qs.get("linkedin") or None,
              about=qs.get("about", ""))
    key = (qs.get("q", "").lower(), tuple(sorted(kw.items(), key=lambda x: x[0])))
    with _lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < CACHE_TTL:
            return hit[1]
        B = build(qs["q"], **kw)
        _cache[key] = (time.time(), B)
        return B


def public(B):
    """JSON-safe version of the brief (drops private keys, adds a copy-paste text version)."""
    d = {k: v for k, v in B.items() if not k.startswith("_")}
    d["text"] = to_text(B)
    return d
