"""
Handler for the /start command.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import add_user

def get_start_keyboard():
    """
    Builds the premium main menu keyboard.
    """
    keyboard = [
        [
            InlineKeyboardButton("📊 Latest Score", callback_data="btn_latest_score"),
            InlineKeyboardButton("🔄 Compare Iterations", callback_data="btn_compare")
        ],
        [
            InlineKeyboardButton("📜 Scoring History", callback_data="btn_history"),
            InlineKeyboardButton("💬 Ask HR Assistant", callback_data="btn_hr_help")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Welcomes the user, saves their ID in the database, and presents the main menu.
    """
    user = update.effective_user
    username = user.username if user.username else user.first_name
    
    # Save user to DB
    add_user(user.id, username)
    
    welcome_text = (
        f"🤖 **Welcome {username} to the ATS Resume Analyzer Bot!**\n\n"
        "I am designed to evaluate your resume against Job Descriptions (JD) "
        "entirely locally, helping you optimize it for Applicant Tracking Systems.\n\n"
        "📥 **How to get started**:\n"
        "1️⃣ Send or upload your resume as a file (supports **PDF**, **DOCX**, or **Image** OCR).\n"
        "2️⃣ Paste the plain text **Job Description** (JD) when prompted.\n"
        "3️⃣ Receive a compatibility score, detailed breakdown, and suggestions!\n\n"
        "💡 _Interact with the menu below or type an HR/interview prep question anytime._"
    )
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=get_start_keyboard(),
        parse_mode="Markdown"
    )
