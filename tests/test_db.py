"""Persistence layer: schema, CRUD, and connection hygiene."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from ats_bot.config import Settings
from ats_bot.db import repository
from ats_bot.db.connection import init_db, transaction
from ats_bot.errors import DatabaseError


class TestInitialisation:
    def test_creates_the_database_file_and_tables(self, settings: Settings) -> None:
        init_db(settings)
        assert settings.database_path.is_file()

        with transaction(settings) as conn:
            names = {
                row["name"]
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
        assert {"users", "resumes", "job_descriptions", "scores"} <= names

    def test_is_idempotent(self, settings: Settings) -> None:
        init_db(settings)
        repository.add_user(1, "kept", settings=settings)
        init_db(settings)  # re-running must not wipe anything
        assert repository.get_user(1, settings=settings) is not None

    def test_creates_missing_parent_directories(self, tmp_path: Path) -> None:
        settings = Settings(
            bot_token="1:x",
            database_path=tmp_path / "deep" / "nested" / "bot.db",
            upload_dir=tmp_path / "u",
            log_dir=tmp_path / "l",
        )
        init_db(settings)
        assert settings.database_path.is_file()


class TestTransaction:
    def test_commits_on_success(self, db: Settings) -> None:
        with transaction(db) as conn:
            conn.execute("INSERT INTO users (user_id, username) VALUES (7, 'a')")
        assert repository.get_user(7, settings=db) is not None

    def test_rolls_back_on_error(self, db: Settings) -> None:
        with pytest.raises(RuntimeError), transaction(db) as conn:
            conn.execute("INSERT INTO users (user_id, username) VALUES (8, 'b')")
            raise RuntimeError("boom")
        assert repository.get_user(8, settings=db) is None

    def test_wraps_sqlite_errors(self, db: Settings) -> None:
        with pytest.raises(DatabaseError), transaction(db) as conn:
            conn.execute("SELECT * FROM table_that_does_not_exist")

    def test_connections_are_closed(self, db: Settings) -> None:
        """A leaked connection keeps a Windows file lock and breaks cleanup."""
        with transaction(db) as conn:
            pass
        with pytest.raises(sqlite3.ProgrammingError):
            conn.execute("SELECT 1")

    def test_foreign_keys_are_enforced(self, db: Settings) -> None:
        with transaction(db) as conn:
            enabled = conn.execute("PRAGMA foreign_keys").fetchone()[0]
        assert enabled == 1


class TestUsers:
    def test_insert_then_update_username(self, db: Settings) -> None:
        repository.add_user(1, "first", settings=db)
        repository.add_user(1, "second", settings=db)

        user = repository.get_user(1, settings=db)
        assert user is not None
        assert user.username == "second"

    def test_unknown_user_is_none(self, db: Settings) -> None:
        assert repository.get_user(999, settings=db) is None


class TestResumes:
    def test_round_trip(self, db: Settings) -> None:
        resume_id = repository.save_resume(
            1, "/tmp/cv.pdf", "cv.pdf", "pdf", "Python engineer resume", settings=db
        )
        resume = repository.get_resume(resume_id, settings=db)

        assert resume is not None
        assert resume.file_name == "cv.pdf"
        assert resume.file_type == "pdf"
        assert resume.word_count == 3
        assert resume.display_name == "cv.pdf"

    def test_creates_the_user_row_if_absent(self, db: Settings) -> None:
        """Saving must work for a user who never sent /start."""
        repository.save_resume(555, "/tmp/a.pdf", "a.pdf", "pdf", "text", settings=db)
        assert repository.get_user(555, settings=db) is not None

    def test_latest_is_the_newest(self, db: Settings) -> None:
        repository.save_resume(1, "/a", "a.pdf", "pdf", "first version", settings=db)
        second = repository.save_resume(1, "/b", "b.pdf", "pdf", "second version", settings=db)

        latest = repository.get_latest_resume(1, settings=db)
        assert latest is not None
        assert latest.resume_id == second

    def test_previous_resume_walks_back_one(self, db: Settings) -> None:
        first = repository.save_resume(1, "/a", "a.pdf", "pdf", "v1", settings=db)
        second = repository.save_resume(1, "/b", "b.pdf", "pdf", "v2", settings=db)

        previous = repository.get_previous_resume(1, second, settings=db)
        assert previous is not None
        assert previous.resume_id == first
        assert repository.get_previous_resume(1, first, settings=db) is None

    def test_resumes_are_scoped_to_their_user(self, db: Settings) -> None:
        repository.save_resume(1, "/a", "a.pdf", "pdf", "mine", settings=db)
        repository.save_resume(2, "/b", "b.pdf", "pdf", "theirs", settings=db)

        assert len(repository.get_all_resumes(1, settings=db)) == 1
        assert repository.get_latest_resume(2, settings=db).file_name == "b.pdf"  # type: ignore[union-attr]

    def test_all_resumes_respects_the_limit(self, db: Settings) -> None:
        for index in range(5):
            repository.save_resume(1, f"/{index}", f"{index}.pdf", "pdf", "t", settings=db)
        assert len(repository.get_all_resumes(1, limit=2, settings=db)) == 2

    def test_display_name_falls_back_to_the_path(self, db: Settings) -> None:
        resume_id = repository.save_resume(1, "/uploads/x/abc_cv.pdf", "", "pdf", "t", settings=db)
        resume = repository.get_resume(resume_id, settings=db)
        assert resume is not None
        assert resume.display_name == "abc_cv.pdf"


class TestJobDescriptions:
    def test_round_trip(self, db: Settings) -> None:
        jd_id = repository.save_jd(1, "We need Python", settings=db)
        job = repository.get_jd(jd_id, settings=db)
        assert job is not None
        assert job.jd_text == "We need Python"

    def test_latest_is_the_newest(self, db: Settings) -> None:
        repository.save_jd(1, "old", settings=db)
        newest = repository.save_jd(1, "new", settings=db)
        latest = repository.get_latest_jd(1, settings=db)
        assert latest is not None
        assert latest.jd_id == newest


class TestScores:
    @pytest.fixture
    def ids(self, db: Settings) -> tuple[int, int]:
        resume_id = repository.save_resume(1, "/a", "a.pdf", "pdf", "text", settings=db)
        jd_id = repository.save_jd(1, "jd text", settings=db)
        return resume_id, jd_id

    def test_history_joins_resume_metadata(self, db: Settings, ids: tuple[int, int]) -> None:
        resume_id, jd_id = ids
        repository.save_score(
            resume_id=resume_id,
            jd_id=jd_id,
            overall_score=81.5,
            keyword_score=70.0,
            structure_score=90.0,
            formatting_score=85.0,
            details_json='{"ok": true}',
            settings=db,
        )

        history = repository.get_score_history(1, settings=db)
        assert len(history) == 1
        assert history[0].overall_score == 81.5
        assert history[0].file_name == "a.pdf"
        assert history[0].details_json == '{"ok": true}'

    def test_history_is_newest_first(self, db: Settings, ids: tuple[int, int]) -> None:
        resume_id, jd_id = ids
        for score in (10.0, 20.0, 30.0):
            repository.save_score(
                resume_id=resume_id,
                jd_id=jd_id,
                overall_score=score,
                keyword_score=0,
                structure_score=0,
                formatting_score=0,
                settings=db,
            )
        history = repository.get_score_history(1, settings=db)
        assert [record.overall_score for record in history] == [30.0, 20.0, 10.0]

    def test_history_is_scoped_to_the_user(self, db: Settings, ids: tuple[int, int]) -> None:
        resume_id, jd_id = ids
        repository.save_score(
            resume_id=resume_id,
            jd_id=jd_id,
            overall_score=50.0,
            keyword_score=0,
            structure_score=0,
            formatting_score=0,
            settings=db,
        )
        assert repository.get_score_history(2, settings=db) == []

    def test_count_matches_the_rows(self, db: Settings, ids: tuple[int, int]) -> None:
        resume_id, jd_id = ids
        for _ in range(3):
            repository.save_score(
                resume_id=resume_id,
                jd_id=jd_id,
                overall_score=1.0,
                keyword_score=0,
                structure_score=0,
                formatting_score=0,
                settings=db,
            )
        assert repository.count_scores(1, settings=db) == 3
        assert repository.count_scores(2, settings=db) == 0


class TestDeletion:
    def test_removes_everything_for_one_user_only(self, db: Settings) -> None:
        resume_id = repository.save_resume(1, "/a", "a.pdf", "pdf", "mine", settings=db)
        jd_id = repository.save_jd(1, "jd", settings=db)
        repository.save_score(
            resume_id=resume_id,
            jd_id=jd_id,
            overall_score=50.0,
            keyword_score=0,
            structure_score=0,
            formatting_score=0,
            settings=db,
        )
        repository.save_resume(2, "/b", "b.pdf", "pdf", "theirs", settings=db)

        removed = repository.delete_user_data(1, settings=db)

        assert removed == 1
        assert repository.get_all_resumes(1, settings=db) == []
        assert repository.get_score_history(1, settings=db) == []
        assert repository.get_latest_jd(1, settings=db) is None
        assert repository.get_user(1, settings=db) is None
        assert len(repository.get_all_resumes(2, settings=db)) == 1
