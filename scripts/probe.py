"""One-off: dump live API responses so we can code against real field names.

Heroes are new and the ranked leaderboard has moved around, so rather than guess
at field names we look at what the API actually returns.

    python scripts/probe.py '#YOURTAG'
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

import _lib  # noqa: E402


def show(label, value):
    print("\n" + "=" * 70)
    print(label)
    print("=" * 70)
    print(json.dumps(value, indent=2)[:4000])


def try_get(path):
    """GET a path, printing the error instead of raising if it doesn't exist."""
    try:
        return _lib.cr_get(path)
    except Exception as error:  # noqa: BLE001 - we want to see whatever comes back
        print("  {} -> {}".format(path, error))
        return None


def main():
    if len(sys.argv) < 2:
        sys.exit("usage: python scripts/probe.py '#YOURTAG'")
    tag = _lib.encode_tag(sys.argv[1])

    # 1. What is the highest maxLevel the API reports? That fixes the constant we
    #    normalize levels against.
    cards = _lib.cr_get("/cards")
    items = cards.get("items", [])
    by_rarity = {}
    for card in items:
        by_rarity.setdefault(card.get("rarity"), set()).add(card.get("maxLevel"))
    print("maxLevel by rarity:", {k: sorted(v) for k, v in by_rarity.items()})
    print("highest maxLevel seen:", max(c.get("maxLevel", 0) for c in items))
    print("total cards:", len(items))
    print("top-level keys on /cards:", sorted(cards.keys()))
    show("A card, in full (all available fields)", items[0])

    # Any card whose fields mention a hero tells us what the hero fields are called.
    hero_cards = [c for c in items if any("hero" in k.lower() for k in c)]
    print("\ncards with hero-ish fields:", len(hero_cards))
    if hero_cards:
        show("First card with hero fields", hero_cards[0])

    evo_cards = [c for c in items if any("evolution" in k.lower() for k in c)]
    print("cards with evolution-ish fields:", len(evo_cards))
    if evo_cards:
        show("First card with evolution fields", evo_cards[0])

    # 2. What does a player look like?
    player = _lib.cr_get("/players/" + tag)
    print("\ntop-level keys on /players:", sorted(player.keys()))
    show("currentDeck", player.get("currentDeck"))
    show("currentDeckSupportCards", player.get("currentDeckSupportCards"))
    show("cards[0] from the player's collection", (player.get("cards") or [None])[0])
    print("\ncollection size:", len(player.get("cards") or []))

    owned_evos = [c for c in player.get("cards", []) if c.get("evolutionLevel")]
    print("cards the player owns an evolution for:", len(owned_evos))
    if owned_evos:
        show("An owned evolution", owned_evos[0])

    # 3. Where does the ranked leaderboard live now?
    print("\n" + "=" * 70)
    print("Leaderboard endpoints")
    print("=" * 70)

    boards = try_get("/leaderboards")
    if boards:
        show("/leaderboards", boards)
        first = (boards.get("items") or [None])[0]
        if first and first.get("id") is not None:
            board = try_get("/leaderboard/{}".format(first["id"]))
            if board is None:
                board = try_get("/leaderboards/{}".format(first["id"]))
            if board:
                items = board.get("items") or []
                print("\nentries returned:", len(items))
                show("First leaderboard entry", (items or [None])[0])

    season = try_get("/locations/global/pathoflegend/{}/rankings/players".format(
        player.get("currentPathOfLegendSeasonResult", {}).get("leagueNumber") or "2026-09"
    ))
    if season:
        show("path of legend rankings (first entry)", (season.get("items") or [None])[0])


if __name__ == "__main__":
    main()
