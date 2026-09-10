"""Clash Royale API access and deck-picking logic.

The leading underscore keeps Vercel from routing this file as an endpoint.
"""

import json
import os
import time
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


def cr_get(path, attempts=4):
    """GET a Clash Royale API path (e.g. "/cards") and return the parsed JSON.

    Retries server-side failures. The proxy intermittently returns a Cloudflare
    525 (SSL handshake failed) that succeeds on the very next try, which would
    otherwise kill a 100-request refresh partway through. Client errors (404 for
    an unknown tag, 403 for a bad key) are real answers, so they're raised at once.
    """
    request = urllib.request.Request(
        BASE_URL + path,
        headers={
            "Authorization": "Bearer " + _load_key(),
            "Accept": "application/json",
            # The proxy rejects Python's default urllib User-Agent with a 403.
            "User-Agent": "cr-deck-builder",
        },
    )
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            # The API explains itself in the body; the bare status code doesn't.
            body = error.read().decode("utf-8", "replace")
            message = "{} on {}: {}".format(error.code, path, body)
            if error.code < 500 or attempt == attempts:
                raise RuntimeError(message) from None
        except urllib.error.URLError as error:
            if attempt == attempts:
                raise RuntimeError("{} on {}".format(error, path)) from None
        time.sleep(attempt)


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

# evolutionLevel is a bitmask of what a player has unlocked, not a level.
EVOLUTION = 1
HERO = 2


def normalized_level(card):
    """The level the game displays for a card, from the API's rarity-relative one.

    The API reports a maxed Legendary as level 8 and a maxed Common as level 16;
    both show as 16 in game. Without this, decks built from commons would always
    outscore everything else.
    """
    return card["level"] + (TOP_LEVEL - card["maxLevel"])


def required_bits(slot, max_evolution_level):
    """What a deck's slot demands the player have unlocked, as evolutionLevel bits.

    The API never says which cards are played as an evolution or a hero, but deck
    order gives it away: `currentDeck` comes back in the order the deck is laid
    out in game, where the first slot takes an evolution, the second a hero, and
    the third either. So the slot implies the intent, and maxEvolutionLevel says
    whether that intent is even possible for the card sitting there.

    Slots 4-8 are ordinary cards and demand nothing.
    """
    available = max_evolution_level or 0

    if slot == 0:
        # An evolution slot, unless this card has no evolution to use.
        return EVOLUTION if available & EVOLUTION else 0
    if slot == 1:
        # A hero slot, same caveat.
        return HERO if available & HERO else 0
    if slot == 2:
        # The wild slot takes either, so only a card capable of exactly one tells
        # us anything. A card with both is genuinely ambiguous — demand nothing
        # rather than guess and wrongly discard a playable deck.
        if available == EVOLUTION:
            return EVOLUTION
        if available == HERO:
            return HERO
    return 0


def collection_by_id(player):
    """Index a player's owned cards by card id.

    Cards the player has never unlocked simply aren't in the list, so a missing
    key means "doesn't own it".
    """
    return {card["id"]: card for card in player.get("cards", [])}


def deck_score(deck, collection):
    """Sum the player's levels across a deck's 8 cards.

    Returns None if the deck is unplayable for them: they're missing one of the
    cards, or they lack the evolution or hero its first three slots imply. See
    required_bits() for how those are inferred, and API_NOTES.md for why deck
    order is the only signal available.
    """
    total = 0
    for slot, card in enumerate(deck["cards"]):
        owned = collection.get(card["id"])
        if owned is None:
            return None
        needed = required_bits(slot, card.get("maxEvolutionLevel"))
        if (owned.get("evolutionLevel", 0) & needed) != needed:
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


DATA_FILE = Path(__file__).resolve().parent / "_data" / "top_decks.json"

# Opening this link on a phone with Clash Royale installed offers to copy the
# deck. Card ids are separated by semicolons.
COPY_LINK = "https://link.clashroyale.com/deck/en?deck={}"


def load_top_decks():
    """The cached top-ranked snapshot, rebuilt by scripts/refresh_top_decks.py."""
    return json.loads(DATA_FILE.read_text())


def best_deck_for_tag(tag):
    """The whole feature: a player tag in, a result ready to render out."""
    player = cr_get("/players/" + encode_tag(tag))
    collection = collection_by_id(player)
    snapshot = load_top_decks()

    result = best_deck(snapshot["decks"], collection)
    if result is None:
        return {"found": False}
    score, deck = result

    return {
        "found": True,
        "score": score,
        "max_score": MAX_SCORE,
        "player": {"name": player["name"], "tag": player["tag"]},
        "source": {"name": deck["name"], "tag": deck["tag"], "rank": deck["rank"]},
        "cards": [{
            "name": card["name"],
            "icon": card["icon"],
            "level": normalized_level(collection[card["id"]]),
        } for card in deck["cards"]],
        "copy_link": COPY_LINK.format(";".join(str(c["id"]) for c in deck["cards"])),
        "season": snapshot["season"],
        "players": snapshot["players"],
        "generated_at": snapshot["generated_at"],
    }


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        sys.exit("usage: python api/_lib.py '#YOURTAG'")
    print(json.dumps(best_deck_for_tag(sys.argv[1]), indent=2, ensure_ascii=False))
