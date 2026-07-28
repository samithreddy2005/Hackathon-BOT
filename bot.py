"""
Main entry point for the ATS Resume Analyzer Telegram Bot.
Wires up all command handlers, callbacks, and message listeners.
"""

import sys
import logging
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

from config import BOT_TOKEN
from database.db import init_db
from handlers.start import handle_start
from handlers.help import handle_help
from handlers.upload import handle_resume_upload
from handlers.score import handle_job_description, handle_latest_score_callback
from handlers.compare import handle_compare
from handlers.history import handle_history
from handlers.conversation import handle_faq_query
from handlers.newchat import handle_newchat

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

from database.db import get_latest_resume
from handlers.conversation import search_engine, get_faq_response

def is_probably_job_description(text: str) -> bool:
    """
    Heuristic classifier to determine if input text is a Job Description or a chatbot query.
    """
    clean_text = text.strip()
    if not clean_text:
        return False
        
    # If it ends with a question mark, it's definitely a user query
    if clean_text.endswith("?"):
        return False
        
    # List of common question words at the start of a query
    question_keywords = {
        "how", "what", "why", "who", "where", "when", "can", "could", "should", "would",
        "is", "are", "do", "does", "did", "explain", "describe", "give", "suggest", "improve",
        "tell", "show", "help", "list"
    }
    words = clean_text.split()
    first_word = words[0].lower().strip(".,!?\"'") if words else ""
    
    if first_word in question_keywords:
        return False
        
    # Job descriptions are usually longer blocks of text (> 30 words)
    if len(words) > 30:
        return True
        
    return False

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Routes text messages to either the Job Description scorer or the HR FAQ assistant,
    depending on the user's state, history, and message structure.
    """
    user_id = update.effective_user.id
    user_message = update.message.text
    
    # Check if user has uploaded any resume in the system
    resume = get_latest_resume(user_id)
    
    if not resume:
        # User has no resume. Check if they pasted a JD or asked a question
        if is_probably_job_description(user_message):
            # Instruct the user to upload a resume first
            instruction_text = (
                "⚠️ **Please upload your resume first!**\n\n"
                "I cannot evaluate a Job Description without a resume to compare it against.\n\n"
                "📥 **How to start**:\n"
                "1️⃣ Send or upload your resume file first (supports **.pdf**, **.docx**, or images).\n"
                "2️⃣ Once parsed, paste or send the **Job Description** (JD) text.\n"
                "3️⃣ I will calculate your compatibility score and show improvements!"
            )
            await update.message.reply_text(instruction_text, parse_mode="Markdown")
        else:
            # Answer general questions using chatbot (Groq API/TF-IDF)
            await handle_faq_query(update, context)
        return

    # If resume exists, route based on state and heuristics
    state = context.user_data.get("state")
    if state == "WAITING_FOR_JD":
        # Actively waiting for Job Description
        await handle_job_description(update, context)
    else:
        # State is None/inactive
        if is_probably_job_description(user_message):
            # User wants to run another evaluation with a new JD
            await handle_job_description(update, context)
        else:
            # User is chatting / asking a follow-up question
            await handle_faq_query(update, context)

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Routes button click events from Inline Keyboards.
    """
    query = update.callback_query
    data = query.data
    
    if data == "btn_latest_score":
        await handle_latest_score_callback(update, context)
    elif data == "btn_compare":
        await handle_compare(update, context)
    elif data == "btn_history":
        await handle_history(update, context)
    elif data == "btn_hr_help":
        await query.answer()
        await query.message.reply_text(
            "💬 **HR Assistant & Resume Helper**\n\n"
            "Just type and send any question you have about:\n"
            "• Interview preparation (e.g., 'STAR method', 'tell me about yourself')\n"
            "• Resume formatting (e.g., 'resume template', 'can I use tables')\n"
            "• Career gap explanations\n\n"
            "I will analyze your question and give you local, expert guidance!",
            parse_mode="Markdown"
        )

async def post_init(application: Application) -> None:
    """
    Registers commands to the Telegram menu button on startup.
    """
    commands = [
        BotCommand("start", "Start the bot and open the main menu"),
        BotCommand("newchat", "Start a fresh chat conversation"),
        BotCommand("help", "View detailed instructions and help"),
        BotCommand("compare", "Compare the latest two resume uploads"),
        BotCommand("history", "View your scoring history")
    ]
    await application.bot.set_my_commands(commands)

def main() -> None:
    """
    Starts the telegram bot application.
    """
    # 1. Initialize database
    if not init_db():
        logger.critical("Could not initialize database. Exiting.")
        sys.exit(1)
        
    if not BOT_TOKEN:
        logger.critical("BOT_TOKEN is missing in the environment. Set BOT_TOKEN in .env file.")
        sys.exit(1)
        
    # 2. Build the application
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # 3. Register handlers
    # Command handlers
    application.add_handler(CommandHandler("start", handle_start))
    application.add_handler(CommandHandler("newchat", handle_newchat))
    application.add_handler(CommandHandler("help", handle_help))
    application.add_handler(CommandHandler("compare", handle_compare))
    application.add_handler(CommandHandler("history", handle_history))
    
    # Callback query handler (for buttons)
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # Document/Photo handlers (for resume uploads)
    application.add_handler(
        MessageHandler(
            filters.Document.ALL | filters.PHOTO,
            handle_resume_upload
        )
    )
    
    # General text messages (Job Description or FAQ)
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_text_message
        )
    )

    # 4. Start the Bot using polling
    logger.info("Bot started. Listening for updates...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
