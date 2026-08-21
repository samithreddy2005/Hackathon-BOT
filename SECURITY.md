# Security Policy

## Reporting a vulnerability

Please report security issues privately rather than opening a public issue. Use
GitHub's [private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
on this repository.

Include the steps to reproduce, the impact, and the affected version. Please
redact any real resume content or bot tokens from your report.

## Supported versions

| Version | Supported |
|---|---|
| 1.0.x | ✅ |
| < 1.0 | ❌ |

## Operating this bot safely

### Secrets

- The bot token is the only credential that matters: anyone holding it can read
  every message sent to your bot and impersonate it.
- Keep it in `.env`, which is git-ignored, or in your platform's secret store.
  Never commit it, never paste it into an issue, and never bake it into a Docker
  image — `.dockerignore` excludes `.env` for exactly this reason.
- If a token is ever exposed, revoke it immediately with `/revoke` in
  [@BotFather](https://t.me/BotFather) and issue a new one. Rotation is the only
  effective remedy; deleting the commit is not, because the value remains in the
  git history, in forks, and in anything that cloned the repository.

### Personal data

Resumes contain names, addresses, phone numbers, and employment history.

- Uploaded files are deleted after `UPLOAD_RETENTION_HOURS` (24 by default).
  Extracted text remains in the database so history keeps working; set
  `UPLOAD_RETENTION_HOURS=0` only if you understand that files then accumulate
  indefinitely.
- `/forgetme` gives users a self-service, immediate delete of everything stored
  about them.
- `uploads/`, `logs/`, and `database/` are git-ignored. If you have previously
  committed any of them, remember that removing the files in a later commit does
  not remove them from history.
- Set `LOG_LEVEL=INFO` or higher in production. `DEBUG` is more verbose about
  what is being processed.

### Optional LLM assistant

When `GROQ_API_KEY` is set, the user's resume and target job description are sent
to Groq to answer free-form questions. **Scoring is never sent anywhere** — it is
always local. Leave the key empty to keep the deployment fully offline; `/about`
reports which mode is active.

Documents are inserted into the prompt explicitly labelled as data, and the
system prompt instructs the model not to follow instructions found inside them.
This mitigates but does not eliminate prompt injection: treat model output as
untrusted, which is why it is HTML-escaped before being sent.

## Measures in place

| Risk | Mitigation |
|---|---|
| Path traversal via filename | `safe_display_name` strips directory components; storage paths are built from a random token inside a per-user directory |
| Oversized uploads | `MAX_UPLOAD_MB` checked before download; pixel and page caps in the parsers |
| SQL injection | All queries are parameterised; no string interpolation of user data |
| HTML/markup injection in messages | Every dynamic value is escaped; model output is escaped before conversion |
| Cross-user data access | Ownership is re-checked after every lookup by id |
| Denial of service via slow parsing | Page, pixel, and batch caps; all blocking work runs off the event loop |
| Secrets in the Docker image | `.dockerignore` excludes `.env`, keys, and local state |
| Container running as root | The image creates and runs as an unprivileged user |
