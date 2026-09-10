"""Self-check for the scoring and matching logic. No network, no API key.

    python scripts/check_logic.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

import _lib  # noqa: E402


def card(id, level, max_level):
    return {"id": id, "name": "card%d" % id, "level": level, "maxLevel": max_level}


def deck(rank, ids, max_evos=None):
    max_evos = max_evos or {}
    return {"rank": rank, "name": "p%d" % rank, "tag": "#P%d" % rank,
            "cards": [{"id": i, "name": "card%d" % i,
                       "maxEvolutionLevel": max_evos.get(slot, 0)}
                      for slot, i in enumerate(ids)]}


def main():
    # A maxed card of any rarity normalizes to 16.
    assert _lib.normalized_level(card(1, 16, 16)) == 16, "maxed common"
    assert _lib.normalized_level(card(1, 8, 8)) == 16, "maxed legendary"
    assert _lib.normalized_level(card(1, 6, 6)) == 16, "maxed champion"
    assert _lib.normalized_level(card(1, 11, 11)) == 16, "maxed epic"
    # One below max is 15, whatever the rarity.
    assert _lib.normalized_level(card(1, 15, 16)) == 15, "common one off max"
    assert _lib.normalized_level(card(1, 7, 8)) == 15, "legendary one off max"

    eight = list(range(1, 9))
    maxed = {i: card(i, 16, 16) for i in eight}

    # A fully maxed collection scores the perfect 128.
    assert _lib.deck_score(deck(1, eight), maxed) == _lib.MAX_SCORE == 128

    # Missing even one card makes a deck unplayable.
    short = dict(maxed)
    del short[8]
    assert _lib.deck_score(deck(1, eight), short) is None, "missing card"

    # The highest score wins, regardless of the source player's rank.
    low = dict(maxed)
    low[1] = card(1, 10, 16)  # drags any deck using card 1 down by 6
    decks = [deck(1, eight), deck(50, list(range(2, 10)))]
    collection = dict(low)
    collection[9] = card(9, 16, 16)
    score, winner = _lib.best_deck(decks, collection)
    assert winner["rank"] == 50, "better deck should win even from a worse rank"
    assert score == 128

    # On a tie, the higher-ranked player (lower rank number) wins.
    tied = [deck(77, eight), deck(4, eight), deck(31, eight)]
    score, winner = _lib.best_deck(tied, maxed)
    assert winner["rank"] == 4, "tie should go to rank 4, got %s" % winner["rank"]

    # No playable deck at all.
    assert _lib.best_deck([deck(1, eight)], {}) is None, "empty collection"
    assert _lib.best_deck([], maxed) is None, "no decks"

    # --- what each deck slot demands -------------------------------------
    # Slot 1 is the evolution slot, but only if the card has an evolution.
    assert _lib.required_bits(0, 1) == _lib.EVOLUTION, "evo-only card in slot 1"
    assert _lib.required_bits(0, 3) == _lib.EVOLUTION, "evo+hero card in slot 1"
    assert _lib.required_bits(0, 2) == 0, "hero-only card can't be an evolution"
    assert _lib.required_bits(0, 0) == 0, "plain card demands nothing"

    # Slot 2 is the hero slot, on the same terms.
    assert _lib.required_bits(1, 2) == _lib.HERO, "hero-only card in slot 2"
    assert _lib.required_bits(1, 3) == _lib.HERO, "evo+hero card in slot 2"
    assert _lib.required_bits(1, 1) == 0, "evo-only card can't be a hero"

    # Slot 2 is really the champion/hero slot: the two are interchangeable in
    # game. A champion card has no hero form (maxEvolutionLevel 0), so it demands
    # nothing beyond owning it — the deck isn't playing a hero at all. This falls
    # out of keying on capability rather than on the slot alone, and would break
    # if the check ever assumed "slot 2 means hero".
    assert _lib.required_bits(1, 0) == 0, "a champion in slot 2 needs no hero"
    champion_deck = deck(1, eight, {1: 0})
    assert _lib.deck_score(champion_deck, maxed) == 128, "champion deck is playable"

    # Slot 3 takes either, so only an unambiguous card tells us anything.
    assert _lib.required_bits(2, 1) == _lib.EVOLUTION, "slot 3, evolution only"
    assert _lib.required_bits(2, 2) == _lib.HERO, "slot 3, hero only"
    assert _lib.required_bits(2, 3) == 0, "slot 3 with both is ambiguous"

    # Slots 4-8 are ordinary cards whatever they're capable of.
    for slot in range(3, 8):
        assert _lib.required_bits(slot, 3) == 0, "slot %d demands nothing" % (slot + 1)

    # --- decks are filtered on those demands -------------------------------
    # Slot 1 needs an evolution the player doesn't have.
    needs_evo = deck(1, eight, {0: 1})
    assert _lib.deck_score(needs_evo, maxed) is None, "no evolution unlocked"

    with_evo = dict(maxed)
    with_evo[1] = dict(maxed[1], evolutionLevel=_lib.EVOLUTION)
    assert _lib.deck_score(needs_evo, with_evo) == 128, "evolution unlocked"

    # The hero bit is not the evolution bit: owning one doesn't cover the other.
    needs_hero = deck(1, eight, {1: 2})
    with_hero = dict(maxed)
    with_hero[2] = dict(maxed[2], evolutionLevel=_lib.HERO)
    assert _lib.deck_score(needs_hero, maxed) is None, "no hero unlocked"
    assert _lib.deck_score(needs_hero, with_evo) is None, "evolution is not a hero"
    assert _lib.deck_score(needs_hero, with_hero) == 128, "hero unlocked"

    # Owning both satisfies either demand.
    both = dict(maxed)
    both[1] = dict(maxed[1], evolutionLevel=_lib.EVOLUTION | _lib.HERO)
    assert _lib.deck_score(deck(1, eight, {0: 3}), both) == 128, "owns both"

    # A hero-capable card outside the first three slots demands nothing.
    assert _lib.deck_score(deck(1, eight, {5: 3}), maxed) == 128, "slot 6 is ordinary"

    # --- which art each slot is drawn in ------------------------------------
    EVO, HERO = _lib.EVOLUTION, _lib.HERO
    both = EVO | HERO

    # Slot 1 is evolution art whenever the card has an evolution.
    assert _lib.played_as(0, 1, EVO) == EVO, "slot 1 evolution"
    assert _lib.played_as(0, 3, both) == EVO, "slot 1 prefers evolution"
    assert _lib.played_as(0, 0, 0) == 0, "slot 1 plain card stays plain"

    # Slot 2 is hero art, except champions, which have no hero form.
    assert _lib.played_as(1, 2, HERO) == HERO, "slot 2 hero"
    assert _lib.played_as(1, 0, 0) == 0, "champion in slot 2 keeps its own art"

    # Slot 3 follows what the player has unlocked, evolution first.
    assert _lib.played_as(2, 3, both) == EVO, "slot 3 with both shows evolution"
    assert _lib.played_as(2, 3, EVO) == EVO, "slot 3 evolution only"
    assert _lib.played_as(2, 3, HERO) == HERO, "slot 3 hero only"
    assert _lib.played_as(2, 3, 0) == 0, "slot 3 with neither stays plain"
    # Ownership alone isn't enough; the card must offer that form.
    assert _lib.played_as(2, 1, both) == EVO, "slot 3 card has no hero form"
    assert _lib.played_as(2, 2, both) == HERO, "slot 3 card has no evolution"

    # Slots 4-8 are always plain, whatever the player owns.
    for slot in range(3, 8):
        assert _lib.played_as(slot, 3, both) == 0, "slot %d is plain" % (slot + 1)

    # The art actually swaps, and falls back when a URL is absent.
    art = {"icon": "plain.png", "evolutionIcon": "evo.png", "heroIcon": "hero.png"}
    assert _lib.card_art(art, EVO) == "evo.png"
    assert _lib.card_art(art, HERO) == "hero.png"
    assert _lib.card_art(art, 0) == "plain.png"
    assert _lib.card_art({"icon": "plain.png"}, EVO) == "plain.png", "missing art falls back"

    print("all checks passed")


if __name__ == "__main__":
    main()
