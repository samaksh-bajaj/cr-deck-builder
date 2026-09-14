"""Re-check every claim API_NOTES.md makes about the Clash Royale API.

The app rests on behaviour that isn't documented anywhere — a bitmask that looks
like a level, deck order that carries meaning, a proxy that rejects the default
User-Agent. If Supercell changes any of it, the app goes quietly wrong rather
than loudly broken. This proves the claims still hold.

    python scripts/verify_api.py            # checks not needing a player
    python scripts/verify_api.py '#YOURTAG' # also checks a real collection
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

import _lib  # noqa: E402

# How many ranked players to sample for the deck-shape checks. Every player is a
# separate request, so this trades runtime for confidence.
SAMPLE = 40

results = []


def check(claim, passed, detail=""):
    results.append(passed)
    print("  {} {}".format("PASS" if passed else "FAIL", claim))
    if detail:
        print("       {}".format(detail))


def heading(text):
    print("\n" + text)
    print("-" * len(text))


def check_card_levels(cards):
    heading("Levels are rarity-relative and normalize to 16")

    by_rarity = {}
    for card in cards:
        by_rarity.setdefault(card["rarity"], set()).add(card["maxLevel"])

    consistent = all(len(levels) == 1 for levels in by_rarity.values())
    check("every rarity has a single maxLevel", consistent,
          ", ".join("{} {}".format(r, sorted(v)) for r, v in sorted(by_rarity.items())))

    top = max(card["maxLevel"] for card in cards)
    check("the highest maxLevel is TOP_LEVEL ({})".format(_lib.TOP_LEVEL),
          top == _lib.TOP_LEVEL, "highest seen: {}".format(top))

    maxed = {_lib.normalized_level({"level": m, "maxLevel": m})
             for levels in by_rarity.values() for m in levels}
    check("a maxed card of any rarity normalizes to {}".format(_lib.TOP_LEVEL),
          maxed == {_lib.TOP_LEVEL}, "normalized values seen: {}".format(sorted(maxed)))


def check_bitmask(cards):
    heading("evolutionLevel is a bitmask: bit 1 evolution, bit 2 hero")

    wrong = []
    for card in cards:
        available = card.get("maxEvolutionLevel", 0) or 0
        icons = card.get("iconUrls", {})
        if bool(available & _lib.EVOLUTION) != ("evolutionMedium" in icons):
            wrong.append(card["name"] + " (evolution)")
        if bool(available & _lib.HERO) != ("heroMedium" in icons):
            wrong.append(card["name"] + " (hero)")

    check("maxEvolutionLevel bits match which art each card has",
          not wrong, "{} cards checked, {} mismatched {}".format(
              len(cards), len(wrong), wrong[:5] if wrong else ""))


def check_collection(tag):
    heading("A real collection never owns a form the card doesn't offer")

    player = _lib.cr_get("/players/" + _lib.encode_tag(tag))
    cards = player.get("cards", [])
    impossible = [c["name"] for c in cards
                  if (c.get("evolutionLevel", 0) & ~(c.get("maxEvolutionLevel", 0) or 0))]
    check("no card owns a bit its maxEvolutionLevel lacks",
          not impossible, "{}: {} cards, {} impossible {}".format(
              player["name"], len(cards), len(impossible), impossible[:5]))

    # A hero-only card showing evolutionLevel 1 would sink the bitmask reading.
    hero_only = [c for c in cards if (c.get("maxEvolutionLevel") or 0) == _lib.HERO]
    bad = [c["name"] for c in hero_only if c.get("evolutionLevel", 0) == _lib.EVOLUTION]
    check("no hero-only card reports evolutionLevel 1",
          not bad, "{} hero-only cards owned".format(len(hero_only)))


def check_deck_order(decks):
    heading("Deck order carries the evolution and hero slots")

    first3 = [c for d in decks for c in d["cards"][:3]]
    rest = [c for d in decks for c in d["cards"][3:]]

    def share(cards, bit):
        return sum(1 for c in cards if (c.get("maxEvolutionLevel") or 0) & bit) / len(cards)

    for name, bit in (("evolution", _lib.EVOLUTION), ("hero", _lib.HERO)):
        early, late = share(first3, bit), share(rest, bit)
        check("{}-capable cards cluster in slots 1-3".format(name), early > late * 1.5,
              "slots 1-3: {:.0%}   slots 4-8: {:.0%}".format(early, late))

    slot1 = sum(1 for d in decks
                if (d["cards"][0].get("maxEvolutionLevel") or 0) & _lib.EVOLUTION)
    check("most decks put an evolution-capable card in slot 1",
          slot1 > 0.8 * len(decks), "{}/{} decks".format(slot1, len(decks)))


def check_champion_slot(decks, cards):
    heading("Champions share slot 2 with heroes")

    rarity = {c["id"]: c["rarity"] for c in cards}
    slots = [slot for d in decks for slot, c in enumerate(d["cards"])
             if rarity.get(c["id"]) == "champion"]
    check("every champion sits in slot 2", slots and set(slots) == {1},
          "{} champions, slots seen: {}".format(
              len(slots), sorted({s + 1 for s in slots})))

    champions = [c for c in cards if c["rarity"] == "champion"]
    check("no champion has a hero form",
          all(not (c.get("maxEvolutionLevel") or 0) for c in champions),
          "{} champion cards".format(len(champions)))


def check_live_decks():
    heading("Live decks: only completed seasons, and 7-card decks exist")

    season, players = None, []
    for candidate in _recent_seasons():
        try:
            players = _lib.cr_get(
                "/locations/global/pathoflegend/{}/rankings/players?limit={}".format(
                    candidate, SAMPLE))["items"]
        except RuntimeError:
            continue
        season = candidate
        break

    check("a published Path of Legends season answers", bool(players),
          "season {}, {} players".format(season, len(players)))
    if not players:
        return

    sizes = {}
    for entry in players:
        deck = _lib.cr_get("/players/" + _lib.encode_tag(entry["tag"])).get("currentDeck") or []
        sizes[len(deck)] = sizes.get(len(deck), 0) + 1

    short = sum(count for size, count in sizes.items() if size != _lib.DECK_SIZE)
    check("some decks come back short of {} cards".format(_lib.DECK_SIZE), short > 0,
          "deck sizes across {} players: {}".format(len(players), dict(sorted(sizes.items()))))


def _recent_seasons(count=6):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    year, month = now.year, now.month
    for _ in range(count):
        yield "{:04d}-{:02d}".format(year, month)
        month -= 1
        if month == 0:
            year, month = year - 1, 12


def main():
    cards = _lib.cr_get("/cards")["items"]
    decks = _lib.load_top_decks()["decks"]

    check_card_levels(cards)
    check_bitmask(cards)
    check_deck_order(decks)
    check_champion_slot(decks, cards)
    if len(sys.argv) > 1:
        check_collection(sys.argv[1])
    check_live_decks()

    failed = results.count(False)
    print("\n{} checks, {} failed".format(len(results), failed))
    if failed:
        print("API_NOTES.md is out of date — the app's assumptions have changed.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
