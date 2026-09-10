# Verified API facts

Everything here was confirmed against live responses with `scripts/probe.py`
on 2026-09-10, not taken from documentation.

## Access

- All requests go to `https://proxy.royaleapi.dev/v1` (our keys are IP-locked to
  the proxy at `45.79.218.79`).
- The proxy **403s Python's default `urllib` User-Agent**. Sending any custom
  `User-Agent` fixes it. This is the single most confusing failure mode here: the
  same request works from `curl` and fails from Python.

## Card levels

`maxLevel` varies by rarity, and `level` is relative to it:

| rarity    | maxLevel |
|-----------|----------|
| common    | 16       |
| rare      | 14       |
| epic      | 11       |
| legendary | 8        |
| champion  | 6        |

A maxed card of any rarity displays as **level 16** in game, so:

    displayed level = level + (16 - maxLevel)

That's why `TOP_LEVEL = 16` and a perfect 8-card deck scores 128.

## Evolutions and heroes: `evolutionLevel` is a bitmask, not a level

This is the least obvious thing in the whole API. `evolutionLevel` and
`maxEvolutionLevel` look like levels but are **bit flags**:

| bit | value | meaning            |
|-----|-------|--------------------|
| 1   | 1     | evolution          |
| 2   | 2     | hero               |

So `evolutionLevel` reads:

| value   | the player has unlocked  |
|---------|--------------------------|
| absent  | neither                  |
| 1       | evolution only           |
| 2       | hero only                |
| 3       | both                     |

and `maxEvolutionLevel` says which of the two **exist in the game** for that card.

Verified two independent ways:

1. Across all 123 cards in `/cards`, `maxEvolutionLevel` matches exactly which
   icons the card has, with zero exceptions:

   | maxEvolutionLevel | `evolutionMedium` | `heroMedium` | cards |
   |-------------------|-------------------|--------------|-------|
   | 0                 | no                | no           | 68    |
   | 1                 | yes               | no           | 38    |
   | 2                 | no                | yes          | 13    |
   | 3                 | yes               | yes          | 4     |

2. Across 3,670 card records from 30 top players' collections, no card ever owns
   a bit its `maxEvolutionLevel` lacks. Critically, `maxEvolutionLevel: 2`
   (hero-only cards like Giant, Balloon, Mini P.E.K.K.A) **never** appears with
   `evolutionLevel: 1` — impossible under a bitmask, routine if it were a level.

Reading it as a level is wrong in a way that silently corrupts results: a
hero-only card at `evolutionLevel: 2` would look like "evolution level 2".

### `currentDeck` reports ownership, not what's equipped

In game there are three slots (first evolution, second hero, third either), so at
most 3 cards in a deck can be special. But `currentDeck` cards carry
`evolutionLevel` values identical to the same card in the player's `cards`
collection — 155 of 155 comparisons matched, and 16 of 20 top players had 4+ deck
cards flagged, one had all 8.

So there is **no way to tell what a player actually has equipped.** The API only
ever tells us what they own.

### Deck order reveals what the API won't say

`currentDeck` comes back in the order the deck is laid out in game, confirmed by
comparing against the client. That layout is fixed: **slot 1 takes an evolution,
slot 2 takes a hero, slot 3 takes either.** So position implies intent even
though no field states it, and `maxEvolutionLevel` says whether that intent is
possible for the card in that slot:

| slot | card can be    | inferred requirement |
|------|----------------|----------------------|
| 1    | evolution      | evolution            |
| 1    | hero only      | nothing              |
| 2    | hero           | hero                 |
| 2    | evolution only | nothing              |
| 3    | evolution only | evolution            |
| 3    | hero only      | hero                 |
| 3    | both           | nothing (ambiguous)  |
| 4-8  | anything       | nothing              |

The cached snapshot preserves card order and stores `maxEvolutionLevel`, and
`required_bits()` applies the table.

The ordering holds up statistically. If slots were arbitrary, capability would be
spread evenly across them; instead it is heavily concentrated in the first three,
across the 79 cached decks:

|                   | slots 1-3    | slots 4-8    |
|-------------------|--------------|--------------|
| evolution-capable | 180/237 (76%)| 106/395 (27%)|
| hero-capable      | 78/237 (33%) | 50/395 (13%) |

78 of 79 decks have an evolution-capable card in slot 1, and 69 of 79 have a
hero-capable card in slot 2.

Slot 3 is left unconstrained when a card can be either, which is the conservative
choice: guessing wrong there would discard a deck the player can actually field.

### About a fifth of top decks come back with only 7 cards

21 of the top 100 players' `currentDeck` arrays had 7 entries, not 8. None of
those 21 contained a champion, against 9% of the complete decks — the missing
card is the one in the champion slot, hero-upgraded, and the API omits it because
it has no way to represent a hero.

We can't check whether a player owns a card we can't see, so those decks are
dropped during the refresh. The cached snapshot holds the ~79 complete ones.

## Leaderboards

- `/leaderboards` is **not** the ranked ladder — it lists event boards (Merge
  Tactics, Touchdown, 2v2 League, Goblin Queen's Journey).
- Path of Legends rankings live at:
  `/locations/global/pathoflegend/{seasonId}/rankings/players?limit=100`
  with `seasonId` formatted `YYYY-MM`.
- **Only completed seasons are published.** On 2026-09-10, `2026-09` returned
  `404 notFound` while `2026-08` returned the full board. The refresh script walks
  backwards from the current month to find the newest season that answers.
- Ranking entries contain `tag`, `name`, `expLevel`, `eloRating`, `rank`, `clan` —
  **no decks**. Each player must be fetched individually to get `currentDeck`.

## Tower troops

`currentDeckSupportCards` holds the tower troop. We ignore it entirely — not
matched, not scored.
