# Architecture

## Layering

Modules depend only on layers below them. Nothing below `handlers/` imports
anything from `telegram`, except `utils/telegram_html.py`, which exists precisely
to keep Telegram's formatting rules in one place.

```
ats_bot/
├── __main__.py        Entry point: resolve settings, configure logging, run
├── app.py             Build the Application, install singletons, schedule jobs
├── config.py          Settings.from_env() — the only reader of os.environ
├── logging_config.py  Console + rotating file handlers, noisy libraries muted
├── constants.py       Skills vocabulary, aliases, scoring weights
├── errors.py          Exception hierarchy rooted at ATSBotError
├── reporting.py       Evaluation -> Telegram HTML
│
├── handlers/          Telegram controllers
│   ├── router.py      Text classification and callback dispatch
│   ├── upload.py      Download -> parse -> validate -> store
│   ├── score.py       The core scoring flow
│   ├── compare.py     /compare
│   ├── history.py     /history
│   ├── chat.py        Free-form questions (LLM, then FAQ)
│   ├── session.py     /newchat, /forgetme
│   ├── start.py       /start, /help, /about
│   ├── errors.py      Application-wide error handler
│   └── common.py      Session keys, keyboards, bot_data accessors
│
├── services/          Application services
│   ├── files.py       Validation, safe paths, retrying download, retention
│   ├── faq.py         TF-IDF index over the knowledge base
│   ├── knowledge_base.py  The offline HR answers
│   └── llm.py         Optional Groq client
│
├── ats/               Scoring engine — pure, no I/O
│   ├── scorer.py      evaluate_resume(resume, jd) -> Evaluation
│   ├── keywords.py    Skill extraction and matching
│   ├── sections.py    Structure scoring
│   ├── formatting.py  Formatting and completeness checks
│   ├── suggestions.py Prioritised recommendations
│   ├── comparison.py  Diff two evaluations
│   └── models.py      Frozen result dataclasses
│
├── parsing/           Document -> clean text
│   ├── pdf_reader.py, docx_reader.py, image_reader.py
│   ├── cleaner.py     Normalisation, tokenising, keyword candidates
│   └── extractor.py   Emails, phones, links, sections
│
├── db/                SQLite
│   ├── connection.py  Pragmas, transactions, schema bootstrap
│   ├── repository.py  Typed CRUD
│   ├── models.py      Row dataclasses
│   └── schema.sql
│
└── utils/
    ├── concurrency.py   run_blocking
    └── telegram_html.py Escaping, chunking, safe send/edit
```

## Request flow

```
Telegram update
      │
      ▼
handlers/router.py ── document/photo ──► handlers/upload.py
      │                                        │
      │                                  services/files.py  (validate, download)
      │                                        │
      │                                  parsing/           (extract text)
      │                                        │
      │                                  db/repository.py   (store)
      │
      ├── text that looks like a posting ──► handlers/score.py
      │                                        │
      │                                  ats/scorer.py      (evaluate)
      │                                        │
      │                                  ats/comparison.py  (vs previous version)
      │                                        │
      │                                  reporting.py       (render)
      │
      └── text that looks like a question ──► handlers/chat.py
                                               │
                                        services/llm.py  ──fails──► services/faq.py
```

---

## Design decisions

### HTML, not Markdown, for every message

Telegram's legacy Markdown has no escape mechanism that survives arbitrary user
content. A resume named `my_resume_final_v2.pdf` contains three underscores; a
missing skill called `.net` sits next to an asterisk in a bold run. Either
produces an unbalanced entity, and Telegram rejects the **whole message** with
`Can't parse entities` — the user sees nothing at all.

HTML has exactly three characters to escape. `utils/telegram_html.esc()` handles
them, and every dynamic value in `reporting.py` goes through it. `safe_reply`
additionally retries once as plain text if the API still objects, so a formatting
problem can never cost the user their answer.

### Blocking work never touches the event loop

`python-telegram-bot` runs handlers as coroutines on one event loop. A synchronous
`pdfplumber.open()` on a 20-page scan, or a `pytesseract` call, blocks *every*
user's conversation for its duration. Every disk, CPU, and database call therefore
goes through `utils.concurrency.run_blocking`, which hands it to a worker thread.

The Groq client is the async variant with an explicit timeout for the same reason.

### Connections are closed, not just committed

`sqlite3.Connection` used as a context manager commits or rolls back the
transaction — it does **not** close the connection. Relying on that leaks file
handles, and on Windows leaves file locks that make cleanup fail. `db/connection.py`
wraps every connection in `contextlib.closing`, and a test asserts the connection
is unusable after the block exits.

Pragmas are per-connection, not per-database, so WAL, `foreign_keys`, and
`busy_timeout` are set on every connect.

### The scoring engine is pure

`evaluate_resume(resume_text, jd_text)` performs no I/O and holds no state. Three
things follow:

- the engine is testable without a database or a network;
- a stored score can be reproduced exactly, which is what lets `/history` and the
  "latest score" button show the real number rather than a recomputed guess;
- comparison is meaningful, because both versions can be re-scored against the
  *same* posting on demand.

### An empty keyword checklist scores 0, not 100

If a posting yields no extractable requirements, the naive `matched / total`
calculation divides by zero and the obvious guard returns 100%. That tells the
user their resume is a perfect match for a document the bot could not read. The
engine returns 0 with an empty checklist, and the report explains why.

### Two stop-word lists

`STOP_WORDS` holds ordinary English and is applied everywhere text is tokenised,
including FAQ search. `JD_BOILERPLATE` holds recruiting filler — "requirements",
"candidate", "salary", "skills" — and is applied **only** to keyword extraction.

They were originally one list, which made "how do I answer a salary question?"
unanswerable: the single meaningful word in the query was being discarded before
it reached the index.

### Skills have canonical names

`React.js`, `ReactJS`, and `react` are one skill, not three. `constants.py` maps
every alias to a canonical name, so the matched and missing lists count each skill
once and the score is not inflated by spelling variants. Surface forms are scanned
longest-first, so "machine learning" wins over "learning".

### Fuzzy matching is deliberately conservative

Only single words of five characters or more are fuzzy-matched, at 88% similarity.
Loosening either bound starts matching "go" to "no" and "c" to "r", which produces
confidently wrong "you already have this skill" results — worse than a false
negative, because the user acts on it.

### Uploads expire

Resumes are personal data. Raw files are deleted after `UPLOAD_RETENTION_HOURS`
(24 by default) by a job scheduled at start-up. The extracted text stays in the
database, so history and comparison keep working after the file is gone.

### Configuration fails fast and loudly

`Settings.from_env()` validates the token's shape, the log level, and every
numeric bound before anything else starts. A bad `BOT_TOKEN` produces exit code 2
and one readable line, not a traceback from inside an HTTP library on the first
incoming message.

### The LLM is optional and never fatal

A missing package, a missing key, a timeout, or a rate limit all fall through to
the offline FAQ. Errors that will never succeed — a bad key, an unknown model —
switch the assistant off for the process rather than being retried on every
message. Documents injected as context are explicitly labelled as data, not
instructions.

---

## Data model

```sql
users(user_id PK, username, created_at)

resumes(resume_id PK, user_id FK→users, file_path, file_name, file_type,
        extracted_text, word_count, uploaded_at)

job_descriptions(jd_id PK, user_id FK→users, jd_text, created_at)

scores(score_id PK, resume_id FK→resumes, jd_id FK→job_descriptions,
       overall_score, keyword_score, structure_score, formatting_score,
       details, created_at)
```

`details` holds a JSON snapshot of the full `Evaluation`. Foreign keys cascade on
delete, which is what makes `/forgetme` a single operation.

`schema.sql` is executed on every start-up, so every statement is written to be
safe to re-run.

---

## Testing

357 tests, 89% line coverage, plus doctests on the public functions.

- **Unit** — every scoring analyzer, the parsers, the cleaners, the TF-IDF index.
- **Integration** — the full upload flow against a real `.docx`, and the full
  scoring flow against a real SQLite database.
- **Handler** — lightweight Telegram doubles in `tests/conftest.py` record what
  the user would actually see, which is what the assertions check.

Every test runs against a throwaway database and upload directory under
`tmp_path`; an autouse fixture redirects lazy `get_settings()` lookups so no test
can touch a developer's real data.

Regression guards worth knowing about:

- `test_a_newer_unscored_resume_does_not_change_the_number` — the latest-score
  report must follow the score row, not the newest files.
- `test_a_filename_with_markdown_characters_is_safe` — the exact input that
  crashed the old Markdown renderer.
- `test_unextractable_posting_scores_zero_not_a_hundred` — the divide-by-zero
  guard described above.
- `test_connections_are_closed` — the Windows file-lock leak.
