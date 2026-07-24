"""
Handler for the /help command.
"""
from telegram import Update
from telegram.ext import ContextTypes

async def handle_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Displays helpful usage instructions and description of the bot.
    """
    help_text = (
        "❓ **ATS Resume Analyzer Help & Guide**\n\n"
        "Here are the instructions on how to use this bot:\n\n"
        "📂 **1. Upload Resume**\n"
        "• Simply upload/send a resume document here.\n"
        "• Supported file extensions: **.pdf**, **.docx**, **.png**, **.jpg**, **.jpeg**.\n"
        "• If you upload an image, Tesseract OCR will be used to extract the text.\n\n"
        "📝 **2. Paste Job Description (JD)**\n"
        "• After uploading a resume, the bot will ask for a Job Description.\n"
        "• Paste the job description as a plain text message.\n\n"
        "📊 **3. Scoring System**\n"
        "• We evaluate the compatibility using three metrics:\n"
        "   - **Keyword Match (40%)**: Compares the skills present in the JD with your resume.\n"
        "   - **Section Completeness (30%)**: Checks for sections like Work Experience, Education, etc.\n"
        "   - **Formatting & Details (30%)**: Checks word count, contact details presence, and placeholders.\n\n"
        "💬 **4. Offline HR Assistant**\n"
        "• Type general questions related to interview prep, resume writing, or career gaps to get suggestions directly.\n\n"
        "🤖 **Commands**:\n"
        "/start - Welcome menu and buttons\n"
        "/help - Show this guide\n"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")
