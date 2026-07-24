"""
Configuration settings for the bot.
"""
import os
# pyrefly: ignore [missing-import]
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DATABASE_PATH = os.getenv("DATABASE_PATH", "database/ats_bot.db")
