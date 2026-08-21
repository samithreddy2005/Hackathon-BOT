"""Domain constants: the skills vocabulary, its aliases, and scoring weights.

Keeping the vocabulary here (rather than inline in the matcher) makes it easy to
extend for a new domain without touching the scoring logic.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final

__all__ = [
    "CANONICAL_SKILLS",
    "SCORE_WEIGHTS",
    "SECTION_WEIGHTS",
    "SKILL_ALIASES",
    "SKILL_SURFACE_FORMS",
    "SUPPORTED_EXTENSIONS",
    "canonical_skill",
]

#: File extensions the bot can turn into text, mapped to a coarse document kind.
SUPPORTED_EXTENSIONS: Final[Mapping[str, str]] = MappingProxyType(
    {
        ".pdf": "pdf",
        ".docx": "docx",
        ".png": "image",
        ".jpg": "image",
        ".jpeg": "image",
        ".webp": "image",
        ".bmp": "image",
        ".tiff": "image",
    }
)

#: Weights of the three scoring pillars. Must sum to 1.0 (asserted below).
SCORE_WEIGHTS: Final[Mapping[str, float]] = MappingProxyType(
    {
        "keywords": 0.40,
        "sections": 0.30,
        "formatting": 0.30,
    }
)

#: Contribution of each core resume section to the structure score, plus the
#: bonus sections that top it up (the total is capped at 100).
SECTION_WEIGHTS: Final[Mapping[str, float]] = MappingProxyType(
    {
        "experience": 30.0,
        "education": 25.0,
        "skills": 25.0,
        "summary": 10.0,
        "projects": 10.0,
    }
)

BONUS_SECTION_WEIGHTS: Final[Mapping[str, float]] = MappingProxyType(
    {
        "certifications": 5.0,
        "languages": 5.0,
    }
)

# ---------------------------------------------------------------------------
# Skills vocabulary
# ---------------------------------------------------------------------------
# ``CANONICAL_SKILLS`` holds the name we report back to the user. ``SKILL_ALIASES``
# maps every alternative spelling onto its canonical name, so "React.js", "ReactJS"
# and "react" all collapse to a single matched skill instead of three.

_CANONICAL_SKILLS: Final[tuple[str, ...]] = (
    # Programming languages
    "python",
    "java",
    "javascript",
    "typescript",
    "c++",
    "c#",
    "c",
    "go",
    "ruby",
    "swift",
    "php",
    "rust",
    "kotlin",
    "scala",
    "perl",
    "objective-c",
    "dart",
    "r",
    "matlab",
    "sql",
    "html",
    "css",
    "sass",
    "bash",
    "powershell",
    "assembly",
    # Frameworks and libraries
    "react",
    "angular",
    "vue",
    "svelte",
    "next.js",
    "nuxt",
    "django",
    "flask",
    "fastapi",
    "spring boot",
    "node.js",
    "express",
    "nestjs",
    "laravel",
    "rails",
    ".net",
    "asp.net",
    "jquery",
    "bootstrap",
    "tailwind css",
    "flutter",
    "react native",
    "electron",
    "graphql",
    "rest api",
    "grpc",
    # Data / ML
    "pytorch",
    "tensorflow",
    "keras",
    "pandas",
    "numpy",
    "scipy",
    "scikit-learn",
    "matplotlib",
    "opencv",
    "hugging face",
    "langchain",
    "spark",
    "hadoop",
    "kafka",
    "airflow",
    "dbt",
    "tableau",
    "power bi",
    "looker",
    "excel",
    # Databases
    "sqlite",
    "mysql",
    "postgresql",
    "mongodb",
    "redis",
    "oracle",
    "sql server",
    "cassandra",
    "mariadb",
    "dynamodb",
    "elasticsearch",
    "snowflake",
    "bigquery",
    # Cloud, DevOps and tooling
    "aws",
    "azure",
    "google cloud",
    "docker",
    "kubernetes",
    "jenkins",
    "git",
    "github",
    "gitlab",
    "bitbucket",
    "terraform",
    "ansible",
    "puppet",
    "chef",
    "ci/cd",
    "github actions",
    "circleci",
    "jira",
    "confluence",
    "linux",
    "unix",
    "nginx",
    "apache",
    "heroku",
    "vercel",
    "netlify",
    "prometheus",
    "grafana",
    "datadog",
    "splunk",
    "serverless",
    "microservices",
    # Practices, methodologies and disciplines
    "agile",
    "scrum",
    "kanban",
    "sdlc",
    "tdd",
    "machine learning",
    "deep learning",
    "artificial intelligence",
    "natural language processing",
    "computer vision",
    "data science",
    "data analysis",
    "data engineering",
    "business intelligence",
    "software engineering",
    "software development",
    "system design",
    "object-oriented programming",
    "functional programming",
    "design patterns",
    "distributed systems",
    "cloud architecture",
    "cybersecurity",
    "penetration testing",
    "devops",
    "site reliability engineering",
    "ui/ux",
    "user research",
    "wireframing",
    "prototyping",
    "figma",
    "adobe xd",
    "project management",
    "product management",
    "stakeholder management",
    "business analysis",
    "requirements gathering",
    "test automation",
    "quality assurance",
    "selenium",
    "cypress",
    "jest",
    "pytest",
    "junit",
    "digital marketing",
    "seo",
    "content strategy",
    "salesforce",
    "sap",
    "financial modeling",
    "budgeting",
    "forecasting",
    # Soft skills
    "leadership",
    "communication",
    "teamwork",
    "problem solving",
    "critical thinking",
    "collaboration",
    "public speaking",
    "time management",
    "negotiation",
    "adaptability",
    "mentoring",
    "customer service",
    "attention to detail",
    "conflict resolution",
    "decision making",
)

CANONICAL_SKILLS: Final[frozenset[str]] = frozenset(_CANONICAL_SKILLS)

#: alias -> canonical skill name
_ALIASES: Final[dict[str, str]] = {
    "golang": "go",
    "js": "javascript",
    "ts": "typescript",
    "csharp": "c#",
    "c sharp": "c#",
    "cpp": "c++",
    "c plus plus": "c++",
    "objective c": "objective-c",
    "react js": "react",
    "react.js": "react",
    "reactjs": "react",
    "vue js": "vue",
    "vue.js": "vue",
    "vuejs": "vue",
    "angularjs": "angular",
    "angular js": "angular",
    "nextjs": "next.js",
    "next js": "next.js",
    "node": "node.js",
    "nodejs": "node.js",
    "node js": "node.js",
    "expressjs": "express",
    "express.js": "express",
    "dotnet": ".net",
    "dot net": ".net",
    "asp net": "asp.net",
    "spring": "spring boot",
    "springboot": "spring boot",
    "ruby on rails": "rails",
    "tailwind": "tailwind css",
    "sklearn": "scikit-learn",
    "scikit learn": "scikit-learn",
    "sci-kit learn": "scikit-learn",
    "tf": "tensorflow",
    "postgres": "postgresql",
    "psql": "postgresql",
    "mssql": "sql server",
    "microsoft sql server": "sql server",
    "mongo": "mongodb",
    "elastic search": "elasticsearch",
    "amazon web services": "aws",
    "amazon aws": "aws",
    "microsoft azure": "azure",
    "gcp": "google cloud",
    "google cloud platform": "google cloud",
    "k8s": "kubernetes",
    "ci-cd": "ci/cd",
    "cicd": "ci/cd",
    "continuous integration": "ci/cd",
    "continuous delivery": "ci/cd",
    "continuous deployment": "ci/cd",
    "gh actions": "github actions",
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "nlp": "natural language processing",
    "cv": "computer vision",
    "dl": "deep learning",
    "bi": "business intelligence",
    "oop": "object-oriented programming",
    "object oriented programming": "object-oriented programming",
    "oops": "object-oriented programming",
    "ui-ux": "ui/ux",
    "ux/ui": "ui/ux",
    "ui": "ui/ux",
    "ux": "ui/ux",
    "user interface": "ui/ux",
    "user experience": "ui/ux",
    "qa": "quality assurance",
    "sre": "site reliability engineering",
    "test driven development": "tdd",
    "search engine optimization": "seo",
    "powerbi": "power bi",
    "restful api": "rest api",
    "rest apis": "rest api",
    "restful apis": "rest api",
    "apache spark": "spark",
    "apache kafka": "kafka",
    "apache airflow": "airflow",
    "huggingface": "hugging face",
    "problem-solving": "problem solving",
    "team work": "teamwork",
    "team-work": "teamwork",
    "communication skills": "communication",
    "leadership skills": "leadership",
}

SKILL_ALIASES: Final[Mapping[str, str]] = MappingProxyType(_ALIASES)

#: Every string worth searching for, longest first so that "machine learning"
#: is preferred over the bare token "learning" when both could match.
SKILL_SURFACE_FORMS: Final[tuple[str, ...]] = tuple(
    sorted(CANONICAL_SKILLS | SKILL_ALIASES.keys(), key=lambda term: (-len(term), term))
)


def canonical_skill(term: str) -> str:
    """Map a surface form onto its canonical skill name.

    Unknown terms are returned lower-cased and stripped, which lets the caller use
    this uniformly for both dictionary skills and free-text keywords.

    >>> canonical_skill("React.JS")
    'react'
    >>> canonical_skill("Kubernetes")
    'kubernetes'
    """
    normalized = term.strip().lower()
    return SKILL_ALIASES.get(normalized, normalized)


# Fail fast at import time if the weights are edited into an inconsistent state.
if abs(sum(SCORE_WEIGHTS.values()) - 1.0) > 1e-9:  # pragma: no cover - guard
    raise ValueError("SCORE_WEIGHTS must sum to 1.0")
if abs(sum(SECTION_WEIGHTS.values()) - 100.0) > 1e-9:  # pragma: no cover - guard
    raise ValueError("SECTION_WEIGHTS must sum to 100")
