-- Database schema for ATS Telegram Bot

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS resumes (
    resume_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    file_path TEXT NOT NULL,
    file_type TEXT, -- pdf, docx, image
    extracted_text TEXT,
    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS job_descriptions (
    jd_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    jd_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS scores (
    score_id INTEGER PRIMARY KEY AUTOINCREMENT,
    resume_id INTEGER,
    jd_id INTEGER,
    overall_score REAL NOT NULL,
    keyword_score REAL,
    structure_score REAL,
    formatting_score REAL,
    suggestions TEXT, -- JSON format list of suggestions
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(resume_id) REFERENCES resumes(resume_id),
    FOREIGN KEY(jd_id) REFERENCES job_descriptions(jd_id)
);

CREATE INDEX IF NOT EXISTS idx_resumes_user ON resumes(user_id);
CREATE INDEX IF NOT EXISTS idx_scores_resume ON scores(resume_id);

