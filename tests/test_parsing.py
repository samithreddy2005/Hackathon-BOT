"""Text normalisation, entity extraction, and document dispatch."""

from __future__ import annotations

from pathlib import Path

import pytest

from ats_bot.errors import ParsingError, UnsupportedFileTypeError
from ats_bot.parsing import document_kind, extract_text
from ats_bot.parsing.cleaner import (
    clean_text,
    extract_potential_keywords,
    focus_on_requirements,
    tokenize,
)
from ats_bot.parsing.extractor import (
    count_quantified_achievements,
    detect_sections,
    extract_email,
    extract_links,
    extract_phone,
    looks_like_resume,
)


class TestCleanText:
    def test_collapses_whitespace(self) -> None:
        assert clean_text("  a   b \t c  ") == "a b c"

    def test_normalises_ligatures_and_smart_punctuation(self) -> None:
        assert clean_text("ﬁnance – it’s “good”") == 'finance - it\'s "good"'

    def test_strips_control_characters_but_keeps_newlines(self) -> None:
        assert clean_text("a\x00b\nc") == "ab\nc"

    def test_collapses_excess_blank_lines(self) -> None:
        assert clean_text("a\n\n\n\n\nb") == "a\n\nb"

    def test_empty_input(self) -> None:
        assert clean_text("") == ""


class TestTokenize:
    def test_drops_stop_words(self) -> None:
        tokens = tokenize("The quick brown fox and the lazy dog")
        assert "quick" in tokens
        assert "the" not in tokens
        assert "and" not in tokens

    def test_preserves_technical_punctuation(self) -> None:
        tokens = tokenize("Built with C++, C#, and Node.js using CI/CD")
        assert {"c++", "c#", "node.js"} <= tokens

    def test_keeps_meaningful_single_letters(self) -> None:
        assert "r" in tokenize("Statistics in R")

    def test_empty_input(self) -> None:
        assert tokenize("") == set()


class TestKeywordCandidates:
    def test_returns_nothing_for_empty_text(self) -> None:
        assert extract_potential_keywords("") == []

    def test_respects_the_limit(self, jd_text: str) -> None:
        assert len(extract_potential_keywords(jd_text, max_keywords=5)) <= 5

    def test_repeated_phrases_outrank_single_words(self) -> None:
        text = "Stakeholder management matters. Strong stakeholder management is required."
        assert extract_potential_keywords(text, max_keywords=1) == ["stakeholder management"]

    def test_phrases_do_not_cross_sentence_boundaries(self) -> None:
        text = "Deliver reports. Reports arrive daily. Deliver reports. Reports arrive daily."
        assert "reports reports" not in extract_potential_keywords(text)

    def test_boilerplate_is_filtered_out(self, jd_text: str) -> None:
        keywords = extract_potential_keywords(jd_text)
        assert not {"requirements", "responsibilities", "candidate"} & set(keywords)


class TestFocusOnRequirements:
    def test_extracts_the_requirements_block(self) -> None:
        posting = (
            "About us\n"
            "We are a wonderful company with a wonderful culture and free snacks.\n"
            "Requirements\n"
            "Deep Python expertise, PostgreSQL tuning, and Kubernetes operations "
            "experience across large production estates are all essential here.\n"
            "Benefits\n"
            "Free snacks, a gym, and unlimited holiday for everyone on the team.\n"
        )
        focused = focus_on_requirements(posting)
        assert "Kubernetes" in focused
        assert "gym" not in focused

    def test_falls_back_to_the_whole_text(self) -> None:
        text = "A posting with no recognisable headings at all, just running prose."
        assert focus_on_requirements(text) == text


class TestEntityExtraction:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("Reach me at jane.doe@example.com today", "jane.doe@example.com"),
            ("j+tag@sub.example.co.uk", "j+tag@sub.example.co.uk"),
            ("no address here", None),
        ],
    )
    def test_email(self, text: str, expected: str | None) -> None:
        assert extract_email(text) == expected

    @pytest.mark.parametrize(
        "text",
        ["+1 (555) 123-4567", "555-123-4567", "+44 20 7946 0958", "9876543210"],
    )
    def test_phone_is_found(self, text: str) -> None:
        assert extract_phone(f"Call {text} anytime") is not None

    @pytest.mark.parametrize("text", ["Employed 2019 - 2023", "Suite 400", "no digits"])
    def test_phone_rejects_non_numbers(self, text: str) -> None:
        assert extract_phone(text) is None

    def test_links(self) -> None:
        links = extract_links("See linkedin.com/in/jane and https://github.com/jane.")
        assert links == ["linkedin.com/in/jane", "https://github.com/jane"]

    def test_quantified_achievements(self) -> None:
        text = (
            "Cut latency by 40%\n"
            "Saved $80000 annually\n"
            "Served 30000 users\n"
            "Wrote documentation\n"
        )
        assert count_quantified_achievements(text) == 3


class TestSectionDetection:
    def test_finds_standalone_headings(self, resume_text: str) -> None:
        sections = detect_sections(resume_text)
        assert sections["summary"]
        assert sections["experience"]
        assert sections["education"]
        assert sections["skills"]
        assert sections["projects"]
        assert sections["certifications"]
        assert not sections["languages"]

    def test_prose_mentions_do_not_count_as_headings(self) -> None:
        text = "I have a lot of experience shipping products and value education highly."
        sections = detect_sections(text)
        assert not sections["experience"]
        assert not sections["education"]

    def test_labelled_inline_sections_are_recognised(self) -> None:
        assert detect_sections("Skills: Python, SQL, Docker")["skills"]

    def test_empty_text(self) -> None:
        assert detect_sections("") == dict.fromkeys(detect_sections("x"), False)


class TestLooksLikeResume:
    def test_accepts_a_real_resume(self, resume_text: str) -> None:
        assert looks_like_resume(resume_text)

    def test_rejects_a_job_posting(self, jd_text: str) -> None:
        assert not looks_like_resume(jd_text)

    def test_accepts_a_headingless_resume_with_contact_details(self) -> None:
        assert looks_like_resume("Jane Doe\njane@example.com\n+1 555 123 4567\nDeveloper")

    def test_rejects_empty_text(self) -> None:
        assert not looks_like_resume("")


class TestDispatch:
    @pytest.mark.parametrize(
        "name,expected",
        [("cv.pdf", "pdf"), ("CV.PDF", "pdf"), ("a.docx", "docx"), ("scan.JPEG", "image")],
    )
    def test_document_kind(self, name: str, expected: str) -> None:
        assert document_kind(name) == expected

    @pytest.mark.parametrize("name", ["notes.txt", "old.doc", "archive.zip", "noextension"])
    def test_unsupported_types_are_rejected(self, name: str) -> None:
        with pytest.raises(UnsupportedFileTypeError):
            document_kind(name)

    def test_missing_file_raises_parsing_error(self, tmp_path: Path) -> None:
        with pytest.raises(ParsingError):
            extract_text(tmp_path / "absent.pdf")

    def test_corrupt_pdf_raises_parsing_error(self, tmp_path: Path) -> None:
        broken = tmp_path / "broken.pdf"
        broken.write_bytes(b"this is definitely not a PDF")
        with pytest.raises(ParsingError):
            extract_text(broken)

    def test_renamed_doc_file_gets_an_actionable_message(self, tmp_path: Path) -> None:
        fake = tmp_path / "renamed.docx"
        fake.write_bytes(b"\xd0\xcf\x11\xe0 legacy OLE header")
        with pytest.raises(ParsingError, match=r"not a valid .docx"):
            extract_text(fake)
