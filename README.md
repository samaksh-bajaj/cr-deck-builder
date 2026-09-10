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

## Running it locally

```
python scripts/serve.py
```

Then open http://localhost:8000. This runs the same handler Vercel runs, so
what you see locally is what you get deployed.

To check the logic without a browser:

```
python api/_lib.py '#YOURTAG'      # the whole pipeline, prints JSON
python scripts/check_logic.py      # scoring tests, no network or key needed
```

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
public/index.html             the entire frontend
api/best_deck.py              GET /api/best_deck?tag=... (serverless function)
api/_lib.py                   API client, scoring, deck matching
api/_data/top_decks.json      the cached top-100 snapshot
scripts/refresh_top_decks.py  rebuild that snapshot
scripts/serve.py              run the site locally
scripts/check_logic.py        tests for the scoring rules
scripts/probe.py              dump live API responses
API_NOTES.md                  what the API actually returns, and how we know
vercel.json                   bundles the cached data with the function
```

## Deploying to Vercel

You only do steps 1-6 once. After that, every `git push` redeploys automatically.

1. Push this repo to GitHub, if you haven't:
   create an empty repo at https://github.com/new (don't add a README,
   .gitignore or license — this repo already has files), then run the two
   commands GitHub shows you under "push an existing repository".
2. Go to https://vercel.com/signup and sign in **with GitHub**. That's what lets
   Vercel see your repositories.
3. On the dashboard click **Add New…** → **Project**.
4. Find this repo in the list and click **Import**. If it isn't listed, click
   **Adjust GitHub App Permissions** and give Vercel access to it.
5. Leave **Framework Preset** as *Other* and **Root Directory** as `./`. There's
   no build step, so don't change the build settings.
6. Expand **Environment Variables** and add one:
   - Name: `CR_API_KEY`
   - Value: your API key (the one whose allowed IP is `45.79.218.79`)
   - Leave Production, Preview and Development all ticked.

   **Don't skip this.** The deployed site fetches the requesting player's cards
   live, so without this variable every lookup returns a 500.
7. Click **Deploy**. After about a minute you get a URL like
   `your-project.vercel.app`.

### Changing the key later

Environment variable changes don't reach the live site until you redeploy:
dashboard → your project → **Deployments** → the `…` menu on the newest
deployment → **Redeploy**.

## Known limitations

Both come from the API rather than from this code; `API_NOTES.md` has the
evidence.

- **Evolutions and heroes aren't matched.** The API reports what a player *owns*,
  never what they have equipped, so there's no way to know which evolution a top
  player's deck actually needs. Only outright card ownership is checked.
- **Roughly a fifth of top decks are dropped.** They come back with 7 cards
  instead of 8, because the champion slot holds a hero the API can't represent.
  A card we can't see is a card we can't check, so those decks are excluded.
