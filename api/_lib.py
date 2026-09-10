"""Clash Royale API access and deck-picking logic.

The leading underscore keeps Vercel from routing this file as an endpoint.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# Our API keys are IP-locked to 45.79.218.79, the RoyaleAPI proxy, so requests go
# there rather than to api.clashroyale.com. Same paths, same responses.
BASE_URL = "https://proxy.royaleapi.dev/v1"

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_key():
    """Return the API key from the environment, falling back to .env locally.

    On Vercel the key is a real environment variable; there is no .env file.
    """
    key = os.environ.get("CR_API_KEY")
    if key:
        return key

    env_file = REPO_ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, _, value = line.partition("=")
            if name.strip() == "CR_API_KEY":
                return value.strip().strip('"').strip("'")

    raise RuntimeError(
        "No CR_API_KEY found. Locally: copy .env.example to .env and paste your "
        "key in. On Vercel: set CR_API_KEY in the project's environment variables."
    )


def cr_get(path):
    """GET a Clash Royale API path (e.g. "/cards") and return the parsed JSON."""
    request = urllib.request.Request(
        BASE_URL + path,
        headers={
            "Authorization": "Bearer " + _load_key(),
            "Accept": "application/json",
            # The proxy rejects Python's default urllib User-Agent with a 403.
            "User-Agent": "cr-deck-builder",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        # The API explains itself in the body; the bare status code doesn't.
        body = error.read().decode("utf-8", "replace")
        raise RuntimeError("{} on {}: {}".format(error.code, path, body)) from None


def encode_tag(tag):
    """Turn a player tag into the URL-encoded form the API expects.

    "#2P0LYQ", "2p0lyq" and " 2P0LYQ " all become "%232P0LYQ". The letter O is
    not a valid tag character, so treat it as the digit 0 the way the game does.
    """
    tag = tag.strip().lstrip("#").upper().replace("O", "0")
    return urllib.parse.quote("#" + tag)
