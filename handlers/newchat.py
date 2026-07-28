"""
Handler for starting a new chat session.
"""
from telegram import Update
from telegram.ext import ContextTypes

async def handle_newchat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Clears the active session context so the user can start a fresh conversation.
    """
    # Clear user data state
    context.user_data.clear()
    
    # Mark the session as cleared so we don't load previous resume/JD context
    context.user_data["session_cleared"] = True
    
    msg = (
        "🧹 **New Chat Session Started!**\n\n"
        "I have cleared the active resume and job description context from our current conversation.\n\n"
        "👉 You can now ask general questions, or **upload a new resume** to start a fresh ATS screening session."
    )
    await update.message.reply_text(msg, parse_mode="Markdown")
