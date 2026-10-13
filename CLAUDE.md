# jobradar — project brief for Claude Code

## Goal
A small, local tool that collects job and PhD offers from several sources, deduplicates them,
ranks them against my profile, and exposes them to Claude through an MCP server so Claude can
triage offers and help draft applications. Public on GitHub as a portfolio piece.

Hard constraints:
- Runs on a weak laptop: i5, 8 GB RAM, no GPU. No local LLM. CPU-only embeddings are fine.
- Zero running cost: no cloud deployment, no paid API.
- No scraping of sites that forbid it (LinkedIn, Welcome to the Jungle). Those arrive as email alerts.
- MVP must be usable within one weekend (~10 h). Prefer boring, simple code over clever code.

## Architecture
```
sources/            -> fetch raw offers
  gmail_imap.py     -> reads the Gmail label "job-alerts" over IMAP (app password)
  francetravail.py  -> France Travail "Offres d'emploi v2" API (OAuth client credentials)
parsers/            -> one parser per alert sender (LinkedIn, WTTJ, APEC, Euraxess, ...)
                       turns an alert email into 1..n Offer records
store.py            -> SQLite (data/jobradar.db), dedup on normalized (title, company, url)
rank.py             -> sentence-transformers all-MiniLM-L6-v2 cosine vs profile/profile.md
                       + rule flags (see below)
mcp_server.py       -> FastMCP (official Python MCP SDK), stdio transport
cli.py              -> `jobradar fetch`, `jobradar rank`, `jobradar list`
```

## Data model (SQLite)
`offers`: id, source, kind (job|phd), title, company_or_lab, location, url, description,
posted_at, fetched_at, score (0-1), flags (JSON list), status
(new|shortlisted|applied|interview|rejected|ignored), notes, cv_variant.

## Rule flags
- `clearance`: text mentions habilitation, secret défense, nationalité française, clearance,
  EU citizenship required -> excluded from default listings (still stored).
- `language_de`: German required.
- `senior`: asks for 3+ years of experience.

## MCP tools
- `list_offers(kind=None, min_score=0.5, status="new", since_days=7, include_flagged=False)`
- `get_offer(id)` -> full record
- `set_status(id, status, note=None, cv_variant=None)`
- `stats()` -> counts by status, source and week

## Milestones (do them in order, each one tested before the next)
1. Repo skeleton, `pyproject.toml`, SQLite store + Offer dataclass, pytest set up.
2a. Gmail IMAP source: connect with `GMAIL_USER` / `GMAIL_APP_PASSWORD` from `.env`, read the
    label `job-alerts`, save each new message as raw `.eml` in `data/raw/` (track seen UIDs).
2b. One parser per sender, written against anonymized `.eml` samples in `tests/fixtures/`.
3. France Travail source (keywords and location from `config.toml`).
4. Ranking + rule flags, with unit tests on the flag rules.
5. MCP server (stdio) + README instructions to register it in Claude Code on Linux
   (`claude mcp add jobradar -- <command to start the server>`).
6. README: what it does, architecture diagram, setup, privacy notes, screenshot of a run.

## Privacy and repo hygiene
- `data/`, `.env`, `config.toml`, `profile/` are in `.gitignore`. Ship `config.example.toml`
  and `profile/profile.example.md` instead.
- Fixtures must be anonymized: no real names, emails or tracking URLs.
- Secrets only from environment variables (`.env` loaded with python-dotenv).

## Conventions
- Python 3.11+, type hints, ruff, pytest. Small modules, no framework.
- English for code, comments and README.