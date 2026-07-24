"""
Handler for job description submission, score evaluation, and showing latest scores.
"""
import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from database.db import get_latest_resume, save_jd, save_score, get_latest_jd, get_user_scores_history
from ats.scorer import evaluate_resume

logger = logging.getLogger(__name__)

def format_evaluation_report(eval_results):
    """
    Formats the scoring evaluation output into a beautiful markdown report.
    """
    overall = eval_results["overall_score"]
    kw = eval_results["keyword_score"]
    struct = eval_results["structure_score"]
    fmt = eval_results["formatting_score"]
    
    # Visual gauge/progress indicator
    gauge_blocks = int(overall / 10)
    gauge_str = "🟩" * gauge_blocks + "⬜" * (10 - gauge_blocks)
    
    report = (
        f"📊 **ATS EVALUATION REPORT**\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"🏆 **Overall Score**: `{overall}/100`\n"
        f"{gauge_str}\n\n"
        f"**Score Details**:\n"
        f"• 🔑 Keyword Matching (40%): `{kw}%`\n"
        f"• 🏛️ Section Completeness (30%): `{struct}%`\n"
        f"• 💅 Formatting & Details (30%): `{fmt}%`\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    
    # Keywords section
    matched = eval_results["matched_keywords"]
    missing = eval_results["missing_keywords"]
    
    report += "✅ **Matched Skills/Keywords**:\n"
    if matched:
        report += f"_{', '.join(matched[:15])}_\n"
        if len(matched) > 15:
            report += f"... and {len(matched) - 15} more.\n"
    else:
        report += "_None found._\n"
        
    report += "\n❌ **Missing Key Skills/Keywords**:\n"
    if missing:
        report += f"_{', '.join(missing[:15])}_\n"
        if len(missing) > 15:
            report += f"... and {len(missing) - 15} more.\n"
    else:
        report += "_None! Excellent job._\n"
        
    report += "━━━━━━━━━━━━━━━━━━━━━\n\n💡 **Actionable Suggestions**:\n"
    
    suggs = eval_results["suggestions"]
    for cat, list_suggs in suggs.items():
        for s in list_suggs:
            if not s.startswith("Great job") and not s.startswith("No major") and not s.startswith("Your resume"):
                report += f"• {s}\n"
                
    return report

async def handle_job_description(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Processes the pasted Job Description text, runs the ATS scorer, and shows the report.
    """
    message = update.message
    jd_text = message.text
    user_id = update.effective_user.id
    
    # 1. Retrieve latest resume
    resume = get_latest_resume(user_id)
    if not resume:
        await message.reply_text(
            "❌ No resume found in your session. Please upload a resume file (.pdf, .docx, image) first!"
        )
        context.user_data["state"] = None
        return
        
    status_msg = await message.reply_text("⚖️ Analyzing compatibility against Job Description...")
    await context.bot.send_chat_action(chat_id=message.chat_id, action="typing")
    
    # 2. Save JD
    jd_id = save_jd(user_id, jd_text)
    if not jd_id:
        await status_msg.edit_text("❌ Database error occurred while saving job description.")
        return
        
    # 3. Evaluate score
    eval_results = evaluate_resume(resume["extracted_text"], jd_text)
    
    # 4. Save score to database
    # Serialize suggestions dict to JSON string for saving in DB
    suggestions_json = json.dumps(eval_results["suggestions"])
    save_score(
        resume_id=resume["resume_id"],
        jd_id=jd_id,
        overall_score=eval_results["overall_score"],
        keyword_score=eval_results["keyword_score"],
        structure_score=eval_results["structure_score"],
        formatting_score=eval_results["formatting_score"],
        suggestions=suggestions_json
    )
    
    # 5. Format and show report
    report_text = format_evaluation_report(eval_results)
    
    # Add keyboard buttons for follow-ups
    keyboard = [
        [
            InlineKeyboardButton("🔄 Compare with Previous", callback_data="btn_compare"),
            InlineKeyboardButton("📜 View History", callback_data="btn_history")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Clear WAITING_FOR_JD state
    context.user_data["state"] = None
    
    await status_msg.edit_text(report_text, reply_markup=reply_markup, parse_mode="Markdown")

async def handle_latest_score_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles button click 'Latest Score'. Retrieves and formats the last calculated score.
    """
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    scores_history = get_user_scores_history(user_id)
    
    if not scores_history:
        await query.message.reply_text(
            "📭 No scores calculated yet. Please upload a resume first, and then send a Job Description."
        )
        return
        
    # Retrieve details for the latest evaluation
    latest_score_record = scores_history[0]
    
    # Fetch details
    resume = get_latest_resume(user_id)
    jd = get_latest_jd(user_id)
    
    if not resume or not jd:
        await query.message.reply_text("❌ Could not retrieve details of the latest score.")
        return
        
    eval_results = evaluate_resume(resume["extracted_text"], jd["jd_text"])
    report_text = format_evaluation_report(eval_results)
    
    await query.message.reply_text(
        f"📅 **Latest Score (Generated: {latest_score_record['created_at']})**\n\n{report_text}",
        parse_mode="Markdown"
    )
