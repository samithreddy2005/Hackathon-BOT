-- Schema for the ATS Resume Analyzer bot.
--
-- Written to be idempotent: init_db() executes this script on every start-up, so
-- every statement must be safe to re-run against an existing database.

CREATE TABLE IF NOT EXISTS users (
    user_id    INTEGER PRIMARY KEY,
    username   TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS resumes (
    resume_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id        INTEGER NOT NULL,
    file_path      TEXT    NOT NULL,
    file_name      TEXT    NOT NULL DEFAULT '',
    file_type      TEXT    NOT NULL DEFAULT 'unknown',  -- pdf | docx | image
    extracted_text TEXT    NOT NULL DEFAULT '',
    word_count     INTEGER NOT NULL DEFAULT 0,
    uploaded_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS job_descriptions (
    jd_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    jd_text    TEXT    NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS scores (
    score_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    resume_id        INTEGER NOT NULL,
    jd_id            INTEGER NOT NULL,
    overall_score    REAL    NOT NULL,
    keyword_score    REAL    NOT NULL DEFAULT 0,
    structure_score  REAL    NOT NULL DEFAULT 0,
    formatting_score REAL    NOT NULL DEFAULT 0,
    details          TEXT    NOT NULL DEFAULT '{}',  -- JSON snapshot of the evaluation
    created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (resume_id) REFERENCES resumes (resume_id) ON DELETE CASCADE,
    FOREIGN KEY (jd_id)     REFERENCES job_descriptions (jd_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_resumes_user       ON resumes (user_id, uploaded_at DESC);
CREATE INDEX IF NOT EXISTS idx_jd_user            ON job_descriptions (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_scores_resume      ON scores (resume_id);
CREATE INDEX IF NOT EXISTS idx_scores_created_at  ON scores (created_at DESC);
