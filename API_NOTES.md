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

## Evolutions

- Card definitions carry `maxEvolutionLevel` (1, 2 or 3 — evolutions now have
  multiple levels).
- A card in `currentDeck` carries `evolutionLevel` **only when it is slotted as an
  evolution**. Absent means "played normally".
- A card in the player's `cards` collection carries `evolutionLevel` when the
  player owns that evolution, at the level they own.

So "does this player have the evolution this deck needs" is:
`player_card.get("evolutionLevel", 0) >= deck_card.get("evolutionLevel", 0)`.

## Heroes — not exposed

The game has heroes, and `/cards` card definitions include an
`iconUrls.heroMedium` image. But **no player, deck, or collection field anywhere
in the API indicates hero status or hero level.**

Checked against the top 25 Path of Legends players; the complete set of keys on
every deck card and every collection card is:

    count, elixirCost, evolutionLevel, iconUrls, id, level,
    maxEvolutionLevel, maxLevel, name, rarity, starLevel

There is no `heroLevel`, no `isHero`, no `maxHeroLevel`. A hero-upgraded card is
indistinguishable from the ordinary card in API responses.

Consequence: the "skip decks where the player lacks the hero" rule cannot be
implemented yet. `deck_score()` has a marked hook where the check goes once
Supercell exposes the field.

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
