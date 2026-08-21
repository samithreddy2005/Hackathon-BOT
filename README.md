# ATS Resume Analyzer

A Telegram bot that scores a resume against a specific job description the way an
applicant tracking system would, and tells the candidate exactly what to change.

Scoring runs entirely locally — no resume text leaves the machine unless the
optional LLM assistant is switched on.

![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Tests](https://img.shields.io/badge/tests-357-brightgreen)
![Coverage](https://img.shields.io/badge/coverage-89%25-brightgreen)

---

## What it does

Send a resume, paste a job posting, get a report:

```
🟡 ATS Match Report
──────────────────────
68.4/100 — Fair
▰▰▰▰▰▰▰▱▱▱

🔑 Keywords (40%) — 62.5%
🏛 Sections (30%) — 80.0%
📐 Formatting (30%) — 65.0%
──────────────────────

Skills from the posting — 5/8 found
✅ python, django, postgresql, docker, aws
❌ kubernetes, terraform, ci/cd

Missing sections: summary, projects
At a glance: 412 words · email ✅ · phone ✅ · links ❌ · 1 quantified result

──────────────────────
What to fix, highest impact first

1. Work these job-description skills into your resume where you genuinely
   have them: kubernetes, terraform, ci/cd.
2. Open with a 3-4 line 'Professional Summary' naming your title, years of
   experience, and the two results you are proudest of.
3. No LinkedIn or portfolio link found. Add one — it is the first thing most
   recruiters click after the header.
```

Upload an edited version and send the same posting again, and it diffs the two:
which keywords you gained, which sections you added, which issues you fixed, and
how the score moved.

### Features

| | |
|---|---|
| **Multi-format intake** | PDF, DOCX, and images (OCR). Tables, headers, and footers are read, not silently dropped. |
| **Keyword matching** | A curated skills vocabulary with alias folding, so `React.js`, `ReactJS`, and `react` count once. Falls back to statistical keyword mining for non-technical roles. |
| **Section analysis** | Heading-aware detection that does not mistake "I have experience" for an Experience section. |
| **Formatting checks** | Length, contact details, profile links, quantified achievements, placeholder text, first-person prose. |
| **Version comparison** | Both resumes re-scored against the *same* posting, so the delta means something. |
| **Score history** | Every evaluation kept, with the trend across the window. |
| **Q&A assistant** | Offline TF-IDF knowledge base covering resumes, interviews, salary, and career gaps. Optionally upgraded to a Groq-hosted model that can read your own documents. |
| **Data control** | `/newchat` clears the session; `/forgetme` permanently deletes everything. Uploaded files auto-expire. |

---

## Quick start

Requires **Python 3.11+**.

```bash
git clone https://github.com/samithreddy/ATS-Telegram-Bot.git
cd ATS-Telegram-Bot

python -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate

pip install -e .

cp .env.example .env           # Windows: Copy-Item .env.example .env
# Put your @BotFather token in BOT_TOKEN

ats-bot
```

`python bot.py` and `python -m ats_bot` both work too.

If the token is missing or malformed, the bot exits immediately with exit code 2
and a message naming the variable to set — it does not start and then fail on the
first update.

### Optional: OCR for photographed resumes

Without Tesseract the bot works fully; it just cannot read resumes sent as
images, and says so.

```bash
sudo apt install tesseract-ocr      # Debian/Ubuntu
brew install tesseract              # macOS
```

On Windows, install from [UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki).
It is found automatically in the standard install locations; set `TESSERACT_CMD`
if you put it elsewhere.

### Optional: LLM assistant

Set `GROQ_API_KEY` in `.env` to have free-form questions answered by a language
model that can see the user's uploaded resume and target posting. Leave it empty
and the offline knowledge base answers instead. Either way the *scoring* engine
is unchanged and fully local.

---

## Docker

```bash
docker build -t ats-resume-bot .
docker run -d --name ats-bot \
  -e BOT_TOKEN="your-token" \
  -v ats-bot-data:/data \
  ats-resume-bot
```

State (database, uploads, logs) lives under `/data`, so one volume is enough. The
image runs as a non-root user and ships without a compiler.

---

## Commands

| Command | Effect |
|---|---|
| `/start` | Main menu |
| `/help` | How scoring works |
| `/compare` | Contrast your two most recent resumes |
| `/history` | Past scores and the trend |
| `/newchat` | Clear the session (keeps stored data) |
| `/forgetme` | Permanently delete all of your data |
| `/about` | Version and which optional features are active |

Plain text is routed automatically: a pasted posting is scored, a question is
answered. See `looks_like_job_description` in
[src/ats_bot/handlers/router.py](src/ats_bot/handlers/router.py) for the exact rule.

---

## How scoring works

The overall score is a weighted mean of three pillars:

| Pillar | Weight | What it measures |
|---|---|---|
| **Keywords** | 40% | Share of the posting's required skills present in the resume. Exact match first, then alias match, then phrase coverage, then a conservative fuzzy match for long words only. |
| **Sections** | 30% | Experience 30, Education 25, Skills 25, Summary 10, Projects 10. Certifications and Languages add a 5-point bonus each, capped at 100. |
| **Formatting** | 30% | Starts at 100; penalties for no email (−25), no phone (−15), no links (−5), too short (−25) or too long (−12), placeholder text (−20), no quantified results (−10), first-person prose (−5). |

Weights live in [src/ats_bot/constants.py](src/ats_bot/constants.py) and are
validated at import time. Penalties live in
[src/ats_bot/ats/formatting.py](src/ats_bot/ats/formatting.py).

A job posting with no extractable requirements scores **0** on keywords, not 100 —
an empty checklist is not a perfect match.

---

## Architecture

Layers depend only downwards:

```
handlers/   Telegram controllers — thin, no business logic
    │
services/   File intake, FAQ retrieval, LLM client
    │
ats/        Scoring engine — pure functions, no I/O
    │
parsing/    PDF / DOCX / OCR extraction and normalisation
    │
db/         SQLite persistence
    │
config      Environment-driven settings
```

The engine being pure is what makes it testable without a database or a Telegram
connection, and deterministic enough that a stored score can be reproduced
exactly. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the details and the
rationale behind the notable design decisions.

Every blocking call — SQLite, pdfplumber, Tesseract — runs through
[`run_blocking`](src/ats_bot/utils/concurrency.py) so one slow OCR never stalls
other users' conversations.

---

## Development

```bash
pip install -e ".[dev,llm]"
pre-commit install

pytest tests --doctest-modules src/ats_bot
ruff check src tests bot.py
black --check src tests bot.py
mypy
```

CI runs all of the above on Linux and Windows across Python 3.11–3.13, plus a
Docker build. See [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Configuration

Every setting is an environment variable, documented in
[.env.example](.env.example). Notable ones:

| Variable | Default | Purpose |
|---|---|---|
| `BOT_TOKEN` | — | **Required.** Token from @BotFather. |
| `DATABASE_PATH` | `database/ats_bot.db` | SQLite file. Relative paths resolve against the project root. |
| `UPLOAD_RETENTION_HOURS` | `24` | How long uploaded files are kept. Extracted text stays in the database, so history keeps working. |
| `MAX_UPLOAD_MB` | `20` | Largest accepted file. |
| `GROQ_API_KEY` | *(empty)* | Enables the LLM assistant. |
| `LOG_LEVEL` | `INFO` | `CRITICAL`–`DEBUG`. |

---

## Privacy

Resumes are personal data, and this project treats them that way:

- Scoring is local. Nothing is sent anywhere unless `GROQ_API_KEY` is set, and
  `/about` always reports which mode is active.
- Uploaded files are deleted after `UPLOAD_RETENTION_HOURS` (24 by default).
- `/forgetme` deletes a user's resumes, postings, scores, and files immediately.
- Uploads, logs, and the database are git-ignored. Do not commit them.

See [SECURITY.md](SECURITY.md) for reporting a vulnerability.

---

## License

MIT — see [LICENSE](LICENSE).

## Author

**K. Samith Reddy**
