# 🤖 ATS Resume Analyzer Telegram Bot

An intelligent **Telegram-based ATS (Applicant Tracking System) Resume Analyzer** that evaluates resumes against job descriptions, calculates ATS compatibility scores, provides actionable improvement suggestions, tracks resume iterations, and answers resume-related HR questions—all without relying on external APIs.

---

## 📌 Overview

Recruiters often use Applicant Tracking Systems (ATS) to filter resumes before they reach a hiring manager. This project simulates the core functionality of an ATS by allowing users to upload a resume, compare it against a Job Description (JD), receive a compatibility score, identify missing skills, and improve their resume through iterative feedback.

The bot is designed to run entirely within Telegram while performing all processing locally using Python.

---

## ✨ Features

### 📄 Resume Upload

* Upload resumes in **PDF**, **DOCX**, or **Image** format.
* Automatically extract and clean resume text.

### 📝 Job Description Analysis

* Accept Job Descriptions as plain text.
* Extract required skills and important keywords.

### 🎯 ATS Compatibility Scoring

* Generate an ATS score (0–100).
* Evaluate:

  * Keyword Match
  * Resume Structure
  * Section Completeness
  * Formatting Quality
  * Overall Relevance

### 📊 Detailed Score Breakdown

* Matched Keywords
* Missing Keywords
* Formatting Issues
* Section Analysis
* Improvement Opportunities

### 💡 Resume Improvement Suggestions

* Recommend missing skills.
* Suggest stronger resume sections.
* Highlight ATS-friendly improvements.

### 🔄 Resume Version Tracking

* Detect updated resume uploads.
* Compare previous and current versions.
* Show:

  * Added Skills
  * Removed Skills
  * Updated Sections
  * ATS Score Improvement

### 💬 Resume & HR Assistant

Answer questions related to:

* Resume Writing
* ATS Optimization
* Interview Preparation
* Resume Formatting
* General Recruitment & HR Queries

---

## 🏗️ System Architecture

```text
Telegram User
      │
      ▼
Telegram Bot
      │
      ▼
Resume Parser
      │
      ▼
Job Description Parser
      │
      ▼
ATS Engine
   ├── Keyword Matcher
   ├── Score Calculator
   ├── Formatting Checker
   └── Suggestion Generator
      │
      ▼
Resume Version Tracker
      │
      ▼
Telegram Response
```

---

## 📁 Project Structure

```text
ATS-Telegram-Bot/
│
├── bot.py
├── config.py
├── requirements.txt
├── README.md
├── .gitignore
├── LICENSE
│
├── ats/
│   ├── scorer.py
│   ├── formatter.py
│   ├── suggestions.py
│   └── formatting_checker.py
│
├── parser/
│   ├── pdf_parser.py
│   ├── docx_parser.py
│   ├── image_parser.py
│   └── resume_cleaner.py
│
├── handlers/
│   ├── start.py
│   ├── upload.py
│   ├── score.py
│   ├── compare.py
│   └── help.py
│
├── comparison/
│   └── version_tracker.py
│
├── database/
│   ├── db.py
│   └── schema.sql
│
├── utils/
│
├── tests/
│
├── sample_data/
│
└── docs/
```

---

## ⚙️ Tech Stack

### Backend

* Python 3.11+
* python-telegram-bot

### Document Processing

* pdfplumber
* python-docx
* pytesseract
* Pillow

### Text Processing

* RapidFuzz
* Regular Expressions

### Database

* SQLite

### Utilities

* Git
* GitHub

---

## 🚀 Getting Started

### Clone the Repository

```bash
git clone https://github.com/<your-username>/ATS-Telegram-Bot.git

cd ATS-Telegram-Bot
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Configure Environment

Create a `.env` file:

```env
BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
```

### Run the Bot

```bash
python bot.py
```

---

## 📈 ATS Evaluation Criteria

| Category             | Weight |
| -------------------- | ------ |
| Keyword Matching     | 40%    |
| Resume Sections      | 20%    |
| Formatting           | 15%    |
| Skills Relevance     | 15%    |
| Overall Completeness | 10%    |

---

## 🗺️ Development Roadmap

* [x] Project Planning
* [x] Repository Setup
* [x] README Creation
* [ ] Telegram Bot Initialization
* [ ] Resume Upload Module
* [ ] Resume Parsing
* [ ] Job Description Parser
* [ ] ATS Scoring Engine
* [ ] Formatting Checker
* [ ] Suggestions Engine
* [ ] Resume Version Comparison
* [ ] SQLite Integration
* [ ] Testing
* [ ] Documentation
* [ ] Final Release

---

## 📸 Screenshots

Screenshots and demo GIFs will be added as development progresses.

---

## 🤝 Contributing

Contributions, suggestions, and improvements are welcome. Feel free to fork the repository, open issues, or submit pull requests.

---

## 📄 License

This project is licensed under the MIT License.

---

## ⭐ Future Enhancements

* Role-specific ATS scoring
* Advanced semantic skill matching
* Recruiter dashboard
* Resume analytics
* Interview question generation
* Cover letter assistance
* Multi-language resume support

---

## 👨‍💻 Author

**K. Samith Reddy**

If you find this project useful, consider giving it a ⭐ on GitHub.
