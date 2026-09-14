# Verified API facts

Everything here was confirmed against live responses, not taken from
documentation. `scripts/verify_api.py` re-checks every claim on this page and
fails loudly if the API has changed underneath us.

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

Slot 2 is more precisely the **champion/hero slot**: heroes and champions are
interchangeable there. All 8 champion cards report `maxEvolutionLevel: 0` and
have no hero icon, and across the 223 cached decks every champion sits in slot 2
without exception (14 of 14). So a deck playing a champion demands nothing beyond
owning the champion itself, which falls out of keying the rule on what a card is
*capable* of rather than on slot position alone. A check written as "slot 2 means
hero" would wrongly reject those decks.

The ordering holds up statistically. If slots were arbitrary, capability would be
spread evenly across them; instead it is heavily concentrated in the first three,
across the 223 cached decks:

|                   | slots 1-3     | slots 4-8      |
|-------------------|---------------|----------------|
| evolution-capable | 483/669 (72%) | 289/1115 (26%) |
| hero-capable      | 241/669 (36%) | 138/1115 (12%) |

217 of 223 decks have an evolution-capable card in slot 1, and 188 of 223 have a
hero-capable card in slot 2.

Slot 3 is left unconstrained when a card can be either, which is the conservative
choice: guessing wrong there would discard a deck the player can actually field.

### Card art follows the slot

Cards carry up to three images: `medium`, `evolutionMedium` and `heroMedium`,
all present on the entries inside `currentDeck`, so no extra `/cards` request is
needed to cache them.

Which one to draw follows the same slot logic, resolved per requesting player:

| slot | art shown                                                     |
|------|---------------------------------------------------------------|
| 1    | evolution, if the card has one                                |
| 2    | hero, if the card has one (champions keep their own art)      |
| 3    | whichever form the player has unlocked; evolution if both     |
| 4-8  | plain, even if the card has an evolution the player owns      |

`played_as()` decides the form and `card_art()` picks the URL, falling back to
plain art if the expected image is missing. This is deliberately *not* the same
as `required_bits()`: the requirement stays silent on an ambiguous slot 3 card,
while the art has to commit to something, and the player's own unlocks settle it.

### About a fifth of top decks come back with only 7 cards

77 of the top 300 players' `currentDeck` arrays had 7 entries, not 8. None of
them contained a champion, against 9% of the complete decks — the missing
card is the one in the champion slot, hero-upgraded, and the API omits it because
it has no way to represent a hero.

We can't check whether a player owns a card we can't see, so those decks are
dropped during the refresh. The cached snapshot holds the 223 complete ones.

## Leaderboards

- `/leaderboards` is **not** the ranked ladder — it lists event boards (Merge
  Tactics, Touchdown, 2v2 League, Goblin Queen's Journey).
- Path of Legends rankings live at:
  `/locations/global/pathoflegend/{seasonId}/rankings/players?limit=300`
  (one request serves at least 1000; no paging needed for our depth)
  with `seasonId` formatted `YYYY-MM`.
- **Only completed seasons are published.** On 2026-09-10, `2026-09` returned
  `404 notFound` while `2026-08` returned the full board. The refresh script walks
  backwards from the current month to find the newest season that answers.
- Ranking entries contain `tag`, `name`, `expLevel`, `eloRating`, `rank`, `clan` —
  **no decks**. Each player must be fetched individually to get `currentDeck`.

## Tower troops

`currentDeckSupportCards` holds the tower troop. We ignore it entirely — not
matched, not scored.
