"""
Configuration settings for the bot.
"""
import os
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

load_dotenv()

# Bot settings (required)
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Database path (relative to project root)
DATABASE_PATH = os.getenv("DATABASE_PATH", "database/ats_bot.db")

# Optional external API keys (leave empty to run fully locally)
# Example: set GROQ_API_KEY to enable optional Groq generative responses
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Logging and runtime
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
