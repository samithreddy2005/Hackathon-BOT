"""
Configuration settings for the bot.
"""
import os
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

load_dotenv()

# Bot settings (required)
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

# Database: support local SQLite or external Postgres via DATABASE_URL
# If `DATABASE_URL` is set (e.g. postgres://...), the app should use an external DB.
DATABASE_URL = os.getenv("DATABASE_URL", "")
DATABASE_PATH = os.getenv("DATABASE_PATH", "database/ats_bot.db")

# Optional external API keys (leave empty to run fully locally)
# Example: set GROQ_API_KEY to enable optional Groq generative responses.
# Also accept GROK_API_KEY for compatibility with older environment files.
GROQ_API_KEY = os.getenv("GROQ_API_KEY", os.getenv("GROK_API_KEY", ""))

# Logging and runtime
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Deployment mode
# Set USE_WEBHOOK=true to run the bot in webhook mode (for serverless hosts like Vercel)
USE_WEBHOOK = os.getenv("USE_WEBHOOK", "false").lower() in ("1", "true", "yes")

# URL to receive Telegram webhooks (set by your hosting provider)
TELEGRAM_WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL", "")
