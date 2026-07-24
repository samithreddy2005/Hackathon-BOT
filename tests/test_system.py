"""
Unit tests for the ATS Telegram Bot core modules.
Tests database CRUD, cleaners, custom skills extractor, keyword matcher, and TF-IDF conversation FAQ search.
"""
import os
import sys
import math
import unittest
import json
import sqlite3

# Add workspace root to import path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set separate database path for test runs
import config
config.DATABASE_PATH = r"database/test_unittest_bot.db"

from database import db
from parser import cleaner, extractor
from ats import keyword_matcher, scorer
from comparison import version_tracker
from handlers import conversation

class TestDatabase(unittest.TestCase):
    def setUp(self):
        # Remove any pre-existing test DB
        if os.path.exists(config.DATABASE_PATH):
            os.remove(config.DATABASE_PATH)
        db.init_db()
        
    def tearDown(self):
        # Clean up database file after run
        if os.path.exists(config.DATABASE_PATH):
            os.remove(config.DATABASE_PATH)
            
    def test_user_operations(self):
        # Add user
        self.assertTrue(db.add_user(111, "TestGuy"))
        
        # Check table contents directly
        with db.get_connection() as conn:
            user = conn.execute("SELECT * FROM users WHERE user_id = 111").fetchone()
            self.assertIsNotNone(user)
            self.assertEqual(user["username"], "TestGuy")
            
        # Update user name (ON CONFLICT clause test)
        self.assertTrue(db.add_user(111, "UpdatedName"))
        with db.get_connection() as conn:
            user = conn.execute("SELECT * FROM users WHERE user_id = 111").fetchone()
            self.assertEqual(user["username"], "UpdatedName")

    def test_resume_and_jd_operations(self):
        db.add_user(111, "User")
        
        # Save resume
        res_id = db.save_resume(111, "uploads/res.pdf", "pdf", "Python developer resume text")
        self.assertIsNotNone(res_id)
        
        # Retrieve latest
        latest_res = db.get_latest_resume(111)
        self.assertEqual(latest_res["resume_id"], res_id)
        self.assertEqual(latest_res["extracted_text"], "Python developer resume text")
        
        # Save JD
        jd_id = db.save_jd(111, "Requires Python and Git")
        self.assertIsNotNone(jd_id)
        
        latest_jd = db.get_latest_jd(111)
        self.assertEqual(latest_jd["jd_id"], jd_id)
        self.assertEqual(latest_jd["jd_text"], "Requires Python and Git")
        
        # Save score
        score_id = db.save_score(res_id, jd_id, 85.5, 90.0, 80.0, 85.0, "{}")
        self.assertIsNotNone(score_id)
        
        history = db.get_user_scores_history(111)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["overall_score"], 85.5)

class TestTextCleanersAndExtractors(unittest.TestCase):
    def test_tokenize_and_normalize(self):
        text = "This is a simple TEST sentence, with c++ and python!"
        tokens = cleaner.tokenize_and_normalize(text)
        
        # Tokens should exclude stopwords (this, is, a, with, and)
        self.assertIn("simple", tokens)
        self.assertIn("test", tokens)
        self.assertIn("sentence", tokens)
        self.assertIn("c++", tokens)
        self.assertIn("python", tokens)
        self.assertNotIn("is", tokens)
        self.assertNotIn("a", tokens)
        
    def test_entity_extraction(self):
        resume_text = (
            "Jane Doe\n"
            "Email: jane.doe@testing.com\n"
            "Phone: (123) 456-7890\n\n"
            "SUMMARY\n"
            "A seasoned engineer.\n\n"
            "PROFESSIONAL EXPERIENCE\n"
            "Worked as a software engineer at Tech Corp.\n\n"
            "EDUCATION\n"
            "Bachelor of Science in CS."
        )
        
        email = extractor.extract_email(resume_text)
        phone = extractor.extract_phone(resume_text)
        sections = extractor.detect_sections(resume_text)
        
        self.assertEqual(email, "jane.doe@testing.com")
        self.assertIn("123", phone)
        self.assertTrue(sections["summary"])
        self.assertTrue(sections["experience"])
        self.assertTrue(sections["education"])
        self.assertFalse(sections["projects"]) # Not present

class TestKeywordMatcher(unittest.TestCase):
    def test_skill_boundary_detection(self):
        text = "Experienced in C++, Python, and Go development. He goes to work."
        
        # C++ should match
        self.assertTrue(keyword_matcher.is_skill_present(text.lower(), "c++"))
        # Go should match
        self.assertTrue(keyword_matcher.is_skill_present(text.lower(), "go"))
        # "go" should NOT match substring of "goes" or "development"
        # Let's check boundary matching logic
        self.assertFalse(keyword_matcher.is_skill_present("he goes to work".lower(), "go"))
        self.assertFalse(keyword_matcher.is_skill_present("negotiation skills".lower(), "go"))

    def test_match_keywords_percentage(self):
        resume_text = "Highly skilled in Python, Docker, and Kubernetes. Some education experience."
        jd_text = "Looking for a specialist in Python, Kubernetes, and C++."
        
        # Python and Kubernetes are matched. C++ is missing.
        pct, matched, missing = keyword_matcher.match_keywords(resume_text, jd_text)
        
        self.assertEqual(pct, 66.7) # 2 out of 3 skills matched
        self.assertIn("python", matched)
        self.assertIn("kubernetes", matched)
        self.assertIn("c++", missing)

class TestTFIDFSearchEngine(unittest.TestCase):
    def test_tfidf_matching(self):
        corpus = {
            "How to write a summary?": "Summary text answer.",
            "Can I use tables or graphics in my resume?": "Do not use tables or graphics.",
            "What is the STAR method?": "Situation, Task, Action, Result."
        }
        
        engine = conversation.TFIDFSearch(corpus)
        
        # Test exact query
        match_title, score = engine.query("tell me about the STAR method")
        self.assertEqual(match_title, "What is the STAR method?")
        self.assertGreater(score, 0.4)
        
        # Test fuzzy query related to tables
        match_title, score = engine.query("is it ok to use a table or images in my resume?")
        self.assertEqual(match_title, "Can I use tables or graphics in my resume?")
        self.assertGreater(score, 0.3)
        
        # Test irrelevant query
        match_title, score = engine.query("what is the weather today?")
        # Should result in a low similarity score
        self.assertTrue(match_title is None or score < 0.2)

if __name__ == "__main__":
    unittest.main()
