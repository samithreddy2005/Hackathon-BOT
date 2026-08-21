# Contributing

Thanks for your interest in improving the ATS Resume Analyzer.

## Setup

```bash
git clone https://github.com/samithreddy/ATS-Telegram-Bot.git
cd ATS-Telegram-Bot

python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

pip install -e ".[dev,llm]"
pre-commit install

cp .env.example .env            # Windows: Copy-Item .env.example .env
```

You do not need a real bot token to run the tests — every test uses a throwaway
database and a fake Telegram client.

## Checks

Run these before opening a pull request. CI runs the same commands on Linux and
Windows across Python 3.11, 3.12, and 3.13.

```bash
pytest tests --doctest-modules src/ats_bot   # tests + doctests
ruff check src tests bot.py                  # lint
black --check src tests bot.py               # formatting
mypy                                         # types
```

`pre-commit run --all-files` runs the lint, format, and type checks in one go.

Coverage must stay at or above 80%:

```bash
pytest tests --cov=src/ats_bot --cov-report=term-missing --cov-fail-under=80
```

## Code standards

- **Type hints on everything in `src/`.** `mypy` runs with `disallow_untyped_defs`.
- **Docstrings explain *why*.** What the code does is visible; the reason a
  threshold is 88 and not 80, or why a connection is explicitly closed, is not.
- **Respect the layering.** `handlers/` may import from `services/`, `ats/`,
  `parsing/`, and `db/`. Nothing goes the other way, and nothing below
  `handlers/` imports `telegram` (except `utils/telegram_html.py`).
- **Keep `ats/` pure.** No file, network, or database access in the scoring
  engine — that is what makes it testable and its results reproducible.
- **Never block the event loop.** Any synchronous disk, CPU, or database call in
  a handler goes through `utils.concurrency.run_blocking`.
- **Escape everything user-supplied.** Messages are HTML; dynamic values go
  through `utils.telegram_html.esc` (or `bold`/`italic`/`code`, which escape for
  you). A filename with a `<` in it must not be able to break a message.
- **Read settings through `Settings`.** `config.py` is the only module that
  touches `os.environ`.

Formatting is `black` with a 100-character line length; import order is handled by
`ruff`. Do not hand-format around them.

## Tests

Every behaviour change needs a test. Bug fixes need a test that fails before the
fix — name it so the regression it guards is obvious, as in
`test_unextractable_posting_scores_zero_not_a_hundred`.

Useful fixtures live in `tests/conftest.py`:

| Fixture | Gives you |
|---|---|
| `settings` | `Settings` pointing entirely at `tmp_path` |
| `db` | An initialised, empty database |
| `resume_text` / `jd_text` | Realistic sample documents |
| `update` / `message` / `context` | Telegram doubles that record what the user would see |

Handler tests assert on `message.all_output` — the text a user actually receives,
including edits to status messages.

## Extending the skills vocabulary

Add the canonical name to `_CANONICAL_SKILLS` in `src/ats_bot/constants.py`, and
put every alternative spelling in `_ALIASES` mapping to it. Aliases matter: a
skill listed twice under different spellings inflates the denominator and skews
every score that mentions it.

## Adding a FAQ answer

Append a `FaqEntry` to `FAQ_ENTRIES` in
`src/ats_bot/services/knowledge_base.py`. Two rules:

- Answers are sent verbatim as HTML, so escape any literal `<`, `>`, or `&`.
  There is a test that checks this.
- Write generous `tags`. Users do not phrase questions the way entries title
  them, and tags are weighted three times as heavily as the answer body.

## Pull requests

1. Branch off `main`.
2. Keep the change focused; unrelated refactors belong in their own PR.
3. Add a `CHANGELOG.md` entry under `[Unreleased]` for anything user-facing.
4. Make sure CI is green.

## Reporting bugs

Open an issue with the steps to reproduce, what you expected, what happened, and
the relevant log output. **Redact your bot token and any real resume content** —
log files can contain both.
