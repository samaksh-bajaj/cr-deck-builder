# Clash Royale Deck Builder

Enter a player tag, get the one deck you should play.

## How it works

"Best deck" here means *best for your card levels*, not best in the abstract:

1. Look at the decks of the top 100 Path of Legends (Ranked) players.
2. Throw out any deck containing a card you don't own, or an evolution / hero you
   haven't unlocked.
3. Of what's left, pick the deck with the highest **level score** — the sum of
   *your* levels across its 8 cards.
4. Ties go to the deck belonging to the higher-ranked player.
5. Nothing left? `No decks found`.

Levels are normalized to what the game displays, so a maxed Legendary and a maxed
Common both count as 14. Without that, decks made of commons would always win.

Tower troops are ignored entirely — not matched, not scored.

## Setup

```
cp .env.example .env
```

Then paste your Clash Royale API key into `.env`. The key's allowed IP must be
`45.79.218.79` — that's the RoyaleAPI proxy, which every request goes through.

No dependencies to install. Python standard library only, no build step.

## Refreshing the top-100 deck data

The top players' decks are cached in a committed JSON file. Nothing refreshes it
automatically — you run it when you want new data:

```
python scripts/refresh_top_decks.py
git add api/_data/top_decks.json
git commit -m "refresh top decks"
git push
```

## Layout

```
public/index.html          the entire frontend
api/best_deck.py           GET /api/best_deck?tag=... (serverless function)
api/_lib.py                API client, scoring, deck matching
api/_data/top_decks.json   the cached top-100 snapshot
scripts/                   one-off and maintenance scripts
```
