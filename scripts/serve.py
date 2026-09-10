"""Run the site locally: the static page plus the real /api/best_deck handler.

    python scripts/serve.py
    open http://localhost:8000

This dispatches to the same handler class Vercel runs, so what you see here is
what you'll get deployed. No Vercel CLI needed.
"""

import sys
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "api"))

import best_deck  # noqa: E402

PUBLIC = REPO_ROOT / "public"
PORT = 8000


class Handler(SimpleHTTPRequestHandler):
    # Borrow the deployed handler's methods outright, so this really is the same
    # code path rather than a local imitation of it.
    _serve_api = best_deck.handler.do_GET
    _respond = best_deck.handler._respond

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PUBLIC), **kwargs)

    def do_GET(self):
        if urlparse(self.path).path == "/api/best_deck":
            self._serve_api()
        else:
            super().do_GET()


if __name__ == "__main__":
    PUBLIC.mkdir(exist_ok=True)
    print("Serving {} on http://localhost:{}".format(PUBLIC, PORT))
    print("Press Ctrl+C to stop.")
    HTTPServer(("", PORT), Handler).serve_forever()
