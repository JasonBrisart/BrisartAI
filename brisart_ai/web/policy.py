"""Internet policy helpers."""

from __future__ import annotations

import threading
import urllib.parse
import urllib.robotparser

from brisart_ai import __version__
USER_AGENT = f"BrisartAI/{__version__} (+local-first research assistant; respectful crawler)"


class RobotsCache:
    def __init__(self):
        self._cache = {}
        self._lock = threading.Lock()

    def allowed(self, url: str) -> bool:
        parsed = urllib.parse.urlsplit(url)
        root = f"{parsed.scheme}://{parsed.netloc}"
        with self._lock:
            rp = self._cache.get(root)
            if rp is None:
                rp = urllib.robotparser.RobotFileParser()
                rp.set_url(root + "/robots.txt")
                try:
                    rp.read()
                except Exception:
                    pass
                self._cache[root] = rp
        try:
            return rp.can_fetch(USER_AGENT, url)
        except Exception:
            return True
