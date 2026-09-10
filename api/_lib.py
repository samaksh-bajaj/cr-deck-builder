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


# A maxed card of any rarity displays as level 16 (maxLevel is 16 for commons, 14
# rare, 11 epic, 8 legendary, 6 champion), so levels are normalized against 16
# before being compared. See API_NOTES.md.
TOP_LEVEL = 16
DECK_SIZE = 8
MAX_SCORE = TOP_LEVEL * DECK_SIZE  # 128


def normalized_level(card):
    """The level the game displays for a card, from the API's rarity-relative one.

    The API reports a maxed Legendary as level 8 and a maxed Common as level 16;
    both show as 16 in game. Without this, decks built from commons would always
    outscore everything else.
    """
    return card["level"] + (TOP_LEVEL - card["maxLevel"])


def collection_by_id(player):
    """Index a player's owned cards by card id.

    Cards the player has never unlocked simply aren't in the list, so a missing
    key means "doesn't own it".
    """
    return {card["id"]: card for card in player.get("cards", [])}


def deck_score(deck, collection):
    """Sum the player's levels across a deck's 8 cards.

    Returns None if the deck is unplayable for them, i.e. they're missing one of
    the cards. Evolutions and heroes are deliberately not checked: the API only
    reports what a player *owns*, never what they have equipped, so there's no way
    to know which evolution or hero a top player's deck actually depends on.
    See API_NOTES.md.
    """
    total = 0
    for card in deck["cards"]:
        owned = collection.get(card["id"])
        if owned is None:
            return None
        total += normalized_level(owned)
    return total


def best_deck(decks, collection):
    """Pick the highest-scoring playable deck, or None if none are playable.

    Ties go to the deck belonging to the higher-ranked player, i.e. the lower
    rank number. Returns (score, deck).
    """
    best = None
    for deck in decks:
        score = deck_score(deck, collection)
        if score is None:
            continue
        # Higher score wins; on a tie, the smaller rank number wins.
        if best is None or (score, -deck["rank"]) > (best[0], -best[1]["rank"]):
            best = (score, deck)
    return best
