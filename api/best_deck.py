"""GET /api/best_deck?tag=%232P0LYQ -> the best deck for that player, as JSON.

Vercel routes this file by its name and calls the class named `handler`, which
must subclass BaseHTTPRequestHandler. No framework, no dependencies.
"""

import json
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

import _lib


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

    def _respond(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
