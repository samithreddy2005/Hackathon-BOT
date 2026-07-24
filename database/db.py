"""
SQLite Database connector and operations.
"""
import sqlite3
import os
import logging
from config import DATABASE_PATH

logger = logging.getLogger(__name__)

def get_connection():
    """
    Returns a connection to the SQLite database.
    Ensures parent directories exist.
    """
    db_dir = os.path.dirname(DATABASE_PATH)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """
    Initializes the database using schema.sql.
    """
    schema_path = os.path.join(os.path.dirname(__file__), "schema.sql")
    if not os.path.exists(schema_path):
        logger.error(f"Schema file not found at {schema_path}")
        return False
        
    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema_sql = f.read()
            
        with get_connection() as conn:
            conn.executescript(schema_sql)
            conn.commit()
        logger.info("Database initialized successfully.")
        return True
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        return False

def add_user(user_id, username):
    """
    Adds a user or updates their username if they already exist.
    """
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO users (user_id, username)
                VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET username = excluded.username
                """,
                (user_id, username)
            )
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Error adding/updating user {user_id}: {e}")
        return False

def save_resume(user_id, file_path, file_type, extracted_text):
    """
    Saves a resume entry for the user.
    Returns the inserted resume_id.
    """
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO resumes (user_id, file_path, file_type, extracted_text)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, file_path, file_type, extracted_text)
            )
            conn.commit()
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"Error saving resume for user {user_id}: {e}")
        return None

def get_latest_resume(user_id):
    """
    Gets the latest resume uploaded by the user.
    """
    try:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM resumes
                WHERE user_id = ?
                ORDER BY uploaded_at DESC
                LIMIT 1
                """,
                (user_id,)
            ).fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error retrieving latest resume for user {user_id}: {e}")
        return None

def get_all_resumes(user_id):
    """
    Gets all resumes uploaded by the user ordered from newest to oldest.
    """
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT * FROM resumes
                WHERE user_id = ?
                ORDER BY uploaded_at DESC
                """,
                (user_id,)
            ).fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error retrieving resumes for user {user_id}: {e}")
        return []

def save_jd(user_id, jd_text):
    """
    Saves a job description entry for the user.
    Returns the inserted jd_id.
    """
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO job_descriptions (user_id, jd_text)
                VALUES (?, ?)
                """,
                (user_id, jd_text)
            )
            conn.commit()
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"Error saving JD for user {user_id}: {e}")
        return None

def get_latest_jd(user_id):
    """
    Gets the latest job description entered by the user.
    """
    try:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM job_descriptions
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (user_id,)
            ).fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error retrieving latest JD for user {user_id}: {e}")
        return None

def save_score(resume_id, jd_id, overall_score, keyword_score, structure_score, formatting_score, suggestions):
    """
    Saves a scoring run record.
    """
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO scores (resume_id, jd_id, overall_score, keyword_score, structure_score, formatting_score, suggestions)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (resume_id, jd_id, overall_score, keyword_score, structure_score, formatting_score, suggestions)
            )
            conn.commit()
            return cursor.lastrowid
    except Exception as e:
        logger.error(f"Error saving score for resume_id {resume_id}, jd_id {jd_id}: {e}")
        return None

def get_user_scores_history(user_id):
    """
    Fetches the history of scores for a user.
    Returns list of scores joined with resume details.
    """
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT s.*, r.file_path, r.file_type, r.uploaded_at
                FROM scores s
                JOIN resumes r ON s.resume_id = r.resume_id
                WHERE r.user_id = ?
                ORDER BY s.created_at DESC
                """,
                (user_id,)
            ).fetchall()
            return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Error retrieving scores history for user {user_id}: {e}")
        return []

def get_resume_by_id(resume_id):
    """
    Retrieves a resume record by its unique ID.
    """
    try:
        with get_connection() as conn:
            row = conn.execute("SELECT * FROM resumes WHERE resume_id = ?", (resume_id,)).fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error retrieving resume by ID {resume_id}: {e}")
        return None

def get_previous_resume(user_id, current_resume_id):
    """
    Retrieves the resume uploaded just prior to the current_resume_id.
    """
    try:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT * FROM resumes
                WHERE user_id = ? AND resume_id < ?
                ORDER BY uploaded_at DESC
                LIMIT 1
                """,
                (user_id, current_resume_id)
            ).fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error retrieving previous resume for user {user_id}: {e}")
        return None
