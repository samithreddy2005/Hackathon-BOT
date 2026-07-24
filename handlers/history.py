"""
Handler for showing user scoring history.
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes
from database.db import get_user_scores_history

logger = logging.getLogger(__name__)

async def handle_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Retrieves and displays the scoring history for the user.
    Works for both commands and callback queries.
    """
    is_callback = update.callback_query is not None
    user_id = update.effective_user.id
    target_msg = update.callback_query.message if is_callback else update.message
    
    if is_callback:
        await update.callback_query.answer()
        
    scores = get_user_scores_history(user_id)
    if not scores:
        await target_msg.reply_text(
            "📜 **No scoring history found!**\n\n"
            "Please upload a resume first and paste a Job Description to get your first score.",
            parse_mode="Markdown"
        )
        return
        
    history_lines = [
        "📜 **YOUR ATS SCORING HISTORY**\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
    ]
    
    # Display up to last 10 scores
    for idx, record in enumerate(scores[:10], 1):
        created_at = record["created_at"].split(".")[0] # clean milliseconds if any
        score = record["overall_score"]
        file_type = record["file_type"].upper()
        
        # ASCII Progress Bar
        bar_len = int(score / 10)
        bar = "■" * bar_len + "□" * (10 - bar_len)
        
        history_lines.append(
            f"{idx}. 📅 `{created_at}`\n"
            f"   🏆 Score: **{score}/100**  |  `{bar}`\n"
            f"   📄 Format: `{file_type}`\n"
        )
        
    if len(scores) > 10:
        history_lines.append(f"_...showing latest 10 of {len(scores)} total evaluations._")
        
    await target_msg.reply_text("\n".join(history_lines), parse_mode="Markdown")
