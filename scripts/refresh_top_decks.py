"""Rebuild the cached top-ranked deck snapshot.

Nothing refreshes this automatically. Run it when you want newer data:

    python scripts/refresh_top_decks.py
    git add api/_data/top_decks.json
    git commit -m "refresh top decks"
    git push

Takes a few minutes: the rankings response carries no decks, so every ranked
player has to be fetched individually.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

import _lib  # noqa: E402

OUTPUT = Path(_lib.REPO_ROOT) / "api" / "_data" / "top_decks.json"

# How far down the ranked ladder to look. One request covers it; the endpoint
# serves at least 1000 without paging.
TOP_PLAYERS = 300

RANKINGS = "/locations/global/pathoflegend/{{}}/rankings/players?limit={}".format(TOP_PLAYERS)


def recent_seasons(count=6):
    """Season ids ("YYYY-MM") from this month backwards."""
    now = datetime.now(timezone.utc)
    year, month = now.year, now.month
    for _ in range(count):
        yield "{:04d}-{:02d}".format(year, month)
        month -= 1
        if month == 0:
            year, month = year - 1, 12


def fetch_rankings():
    """The newest Path of Legends board that actually has data.

    Only completed seasons are published, so the current month 404s for most of
    the month and we fall back to the one before it.
    """
    for season in recent_seasons():
        try:
            players = _lib.cr_get(RANKINGS.format(season))["items"]
        except RuntimeError as error:
            print("  season {}: {}".format(season, str(error)[:60]))
            continue
        if players:
            print("  season {}: {} players".format(season, len(players)))
            return season, players
    raise SystemExit("No Path of Legends season returned any players.")


def _card(card):
    """The fields needed to match and draw one card of a deck.

    Both alternate arts are kept when they exist: which one to draw depends on
    the slot and on the requesting player's unlocks, decided at request time.
    """
    icons = card.get("iconUrls", {})
    kept = {
        "id": card["id"],
        "name": card["name"],
        "icon": icons.get("medium", ""),
        "maxEvolutionLevel": card.get("maxEvolutionLevel", 0),
    }
    if icons.get("evolutionMedium"):
        kept["evolutionIcon"] = icons["evolutionMedium"]
    if icons.get("heroMedium"):
        kept["heroIcon"] = icons["heroMedium"]
    return kept


def main():
    print("Finding the newest published season...")
    season, players = fetch_rankings()

    print("Fetching {} players' decks...".format(len(players)))
    decks = []
    incomplete = 0
    for position, entry in enumerate(players, 1):
        player = _lib.cr_get("/players/" + _lib.encode_tag(entry["tag"]))
        deck = player.get("currentDeck") or []
        if len(deck) != _lib.DECK_SIZE:
            # Around a fifth of top decks come back with 7 cards: the card in the
            # champion slot is hero-upgraded, and the API has no way to represent
            # a hero, so it omits it. We can't check ownership of a card we can't
            # see, so the deck has to go. See API_NOTES.md.
            incomplete += 1
            continue
        decks.append({
            "rank": entry["rank"],
            "name": entry["name"],
            "tag": entry["tag"],
            # Only what's needed to match and display. The top player's own card
            # levels are irrelevant: scoring always uses the requesting player's.
            # Card order is preserved and load-bearing: the first slot is an
            # evolution, the second a hero, the third either, and
            # maxEvolutionLevel says which of those a card can actually be.
            "cards": [_card(card) for card in deck],
        })
        if position % 25 == 0:
            print("  {}/{}".format(position, len(players)))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "season": season,
        # How deep the ladder went, so the page can say so without hardcoding it.
        "players": len(players),
        "decks": decks,
    }, indent=1) + "\n")
    print("\nWrote {} decks to {}".format(len(decks), OUTPUT))
    if incomplete:
        print("Dropped {} decks the API returned with only 7 cards "
              "(hero in the champion slot).".format(incomplete))


if __name__ == "__main__":
    main()
