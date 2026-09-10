"""GET /api/best_deck?tag=%232P0LYQ -> the best deck for that player, as JSON.

Vercel routes this file by its name and calls the class named `handler`, which
must subclass BaseHTTPRequestHandler. No framework, no dependencies.
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

# Vercel doesn't guarantee this file's own directory is importable, so say so
# explicitly rather than depending on how the runtime happens to load us.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _lib  # noqa: E402


class handler(BaseHTTPRequestHandler):  # noqa: N801 - the name Vercel looks for
    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        tag = (query.get("tag") or [""])[0]

        if not tag.strip():
            self._respond(400, {"error": "Add a player tag, like ?tag=%232P0LYQ"})
            return

        try:
            self._respond(200, _lib.best_deck_for_tag(tag))
        except RuntimeError as error:
            # cr_get raises this with the API's own explanation attached.
            message = str(error)
            status = 404 if message.startswith("404") else 502
            self._respond(status, {"error": message})
        except Exception as error:  # noqa: BLE001
            # Anything else would otherwise escape as an HTML error page, which
            # the browser can't read back as JSON. Name it instead.
            self._respond(500, {"error": "{}: {}".format(
                type(error).__name__, error)})

    def _respond(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
