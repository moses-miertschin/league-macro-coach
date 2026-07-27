# LeagueMacroCoach

A private, personal League of Legends macro coaching system. It retrieves ranked
match data, analyzes recurring macro mistakes, and generates personalized
improvement goals using an AI model grounded in a hand-curated knowledge base.

This is a solo, local tool — not a public service. Match data and generated
reports stay on disk and out of version control (see `.gitignore`).

## Player Profile

- Riot ID: `HelloKittler#meow`
- Region: NA
- Role: Mid
- Champion pool: Yone, Akali, Fizz, learning Syndra

## Architecture

```
Riot API ─▶ src/riot/ ─▶ data/raw_matches/, data/database/
                              │
                              ▼
                        src/analysis/
                (flags macro mistakes per game)
                              │
              knowledge/*.md ◀┤ (relevant snippets pulled by tag)
                              ▼
                          src/ai/
                (Claude generates the coaching report)
                              │
                              ▼
                reports/generated_reports/
```

**Riot API is the source of truth for match data.** The `src/` layout keeps
Riot-specific code isolated in `src/riot/` so that additional external
sources (OP.GG, U.GG, Lolalytics, patch notes, high-elo reference data) can
be added later as their own modules without touching the Riot integration or
becoming the foundation the system depends on. None of those sources are
implemented yet.

## Folder Structure

- `data/raw_matches/` — raw match JSON pulled from the Riot API.
- `data/database/` — local SQLite database file(s) once storage logic exists.
- `knowledge/fundamentals/` — general mid lane macro concepts.
- `knowledge/champions/` — champion-specific notes (Yone, Akali, Fizz, Syndra).
- `knowledge/matchups/` — matchup-specific notes.
- `knowledge/coaching_philosophy.md` — principles the AI coach follows when writing feedback.
- `reports/generated_reports/` — generated coaching reports, one per session/game.
- `src/riot/` — Riot API integration (not yet implemented).
- `src/analysis/` — heuristics that detect macro mistakes from match data (not yet implemented).
- `src/ai/` — builds prompts and calls Claude to generate reports (not yet implemented).
- `src/main.py` — CLI entrypoint; currently a placeholder.
- `.env.example` — template for required secrets/config; copy to `.env` (gitignored).
- `requirements.txt` — planned dependencies for upcoming phases.

## Status

Foundation only. No Riot API connection, no database logic, no AI calls yet.

## Next Milestone

Implement `src/riot/` enough to authenticate with the Riot API, fetch
`HelloKittler#meow`'s most recent ranked match, save the raw JSON to
`data/raw_matches/`, and print basic stats (champion, KDA, CS, result) to
the console. This validates API auth and data shape before anything else is
built on top of it.
