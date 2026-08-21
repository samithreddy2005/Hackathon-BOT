# Changelog

All notable changes to this project are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] — 2026-08-21

First production release. The application was restructured into an installable
`src/ats_bot` package and hardened throughout.

### Added

- `/about` reports the version and which optional features (OCR, LLM) are active.
- `/forgetme` permanently deletes a user's resumes, postings, scores, and files.
- Automatic retention: uploaded files expire after `UPLOAD_RETENTION_HOURS`
  (24 by default), swept periodically. Extracted text stays in the database, so
  history and comparison keep working.
- Application-wide error handler — an unhandled exception now produces an honest
  message to the user and a full traceback in the log, instead of silence.
- Rotating file logging under `LOG_DIR`, with noisy libraries muted.
- Profile-link, quantified-achievement, and first-person-prose checks in the
  formatting score.
- Skill alias folding: `React.js`, `ReactJS`, and `react` count as one skill.
- Requirements-section focusing — keywords are mined from the requirements block
  of a posting rather than the company blurb.
- Per-user upload directories with collision-free, sanitised filenames.
- Upload size limit (`MAX_UPLOAD_MB`) and per-format validation before download.
- `ats-bot` console entry point; `python -m ats_bot` and `python bot.py` also work.
- Test suite: 357 tests and doctests at 89% coverage, including full upload and
  scoring integration flows.
- `docs/ARCHITECTURE.md` documenting the layering and the design rationale.
- `SECURITY.md`, a `.dockerignore`, and a CI matrix across Linux/Windows and
  Python 3.11–3.13.

### Changed

- **All messages are now rendered as HTML instead of Markdown.** Telegram's
  legacy Markdown could not be escaped safely, so a filename containing `_` or a
  skill such as `.net` would make the API reject the entire message and the user
  would receive nothing.
- Long reports are split across messages instead of exceeding Telegram's
  4096-character limit and being rejected.
- The scoring engine returns frozen dataclasses rather than dictionaries.
- Section detection is heading-aware: prose such as "I have experience" no longer
  counts as an Experience section.
- Fuzzy keyword matching tightened to words of five characters or more at 88%
  similarity; the previous bounds matched unrelated short words.
- DOCX parsing now reads headers, footers, and tables, which many resume
  templates use for contact details and skills.
- Formatting penalties and section weights moved to named constants, validated at
  import time.
- Configuration is validated at start-up: a missing or malformed `BOT_TOKEN`
  exits with code 2 and a single readable line.
- The Groq client is now async with a timeout, and disables itself permanently on
  errors that cannot succeed (bad key, unknown model) rather than retrying on
  every message.
- Documents passed to the LLM are explicitly labelled as data, not instructions.
- Docker image rebuilt as a two-stage build running as a non-root user, with a
  `.dockerignore` that keeps `.env` and the local virtualenv out of the image.

### Fixed

- **Database connections were never closed.** `sqlite3.Connection` as a context
  manager commits but does not close; handles leaked and, on Windows, left file
  locks that broke cleanup.
- **A job description with no extractable requirements scored 100%** on keywords
  instead of 0 — telling users their resume perfectly matched a posting the bot
  could not read.
- **The "latest score" button recomputed a score** by pairing the newest resume
  with the newest job description, which could display a number that never
  matched the stored record it was labelled with. It now rebuilds the report from
  the exact pair recorded on that score row.
- **Blocking calls ran on the event loop.** PDF parsing, OCR, SQLite access, and
  the Groq call all stalled every other user's conversation for their duration.
  All of them now run in a worker thread.
- Unknown callback data left the Telegram button spinner running forever; every
  callback query is now acknowledged.
- `/help` listed only two of the available commands.
- Version comparison could be computed against a resume belonging to another
  user, and against a stored score from a different job description.
- The FAQ index discarded the only meaningful word in queries such as "how do I
  answer a salary question?", because recruiting boilerplate stop words were
  applied to search as well as to keyword extraction.
- Phone-number detection matched date ranges such as "2019 - 2023".
- Resumes with a `NULL` extracted text could crash revision detection.
- Password-protected PDFs and renamed `.doc` files now produce an actionable
  message instead of a generic failure.

### Removed

- `api/webhook.py` and the Vercel deployment path. The handler could not run —
  Flask was never listed as a dependency — and the serverless model conflicts
  with SQLite persistence and long-running OCR. Long polling is the supported
  deployment.
- `google-generativeai` from the dependencies; it was never imported.
- Empty placeholder modules (`utils/helpers.py`, `utils/logger.py`,
  `utils/validators.py`).
