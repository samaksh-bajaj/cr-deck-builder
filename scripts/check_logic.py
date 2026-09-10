"""Self-check for the scoring and matching logic. No network, no API key.

    python scripts/check_logic.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "api"))

import _lib  # noqa: E402


def card(id, level, max_level):
    return {"id": id, "name": "card%d" % id, "level": level, "maxLevel": max_level}


def deck(rank, ids):
    return {"rank": rank, "name": "p%d" % rank, "tag": "#P%d" % rank,
            "cards": [{"id": i, "name": "card%d" % i} for i in ids]}


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

    print("all checks passed")


if __name__ == "__main__":
    main()
