"""
Handler for comparing different resume versions.
"""
import logging
from telegram import Update
from telegram.ext import ContextTypes
from database.db import get_all_resumes, get_latest_jd
from ats.scorer import evaluate_resume
from comparison.version_tracker import compare_versions

logger = logging.getLogger(__name__)

async def handle_compare(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles comparison of the latest two uploaded resumes against the latest job description.
    Works for both commands and callback queries.
    """
    # Identify caller (message vs callback)
    is_callback = update.callback_query is not None
    user_id = update.effective_user.id
    target_msg = update.callback_query.message if is_callback else update.message
    
    if is_callback:
        await update.callback_query.answer()
        
    # 1. Fetch resumes
    resumes = get_all_resumes(user_id)
    if len(resumes) < 2:
        await target_msg.reply_text(
            "🔄 **Version Comparison requires at least 2 resume uploads!**\n\n"
            "Currently, you have only uploaded one resume version. "
            "Please upload your updated resume file, and we will contrast the two.",
            parse_mode="Markdown"
        )
        return
        
    # 2. Fetch latest Job Description
    jd = get_latest_jd(user_id)
    if not jd:
        await target_msg.reply_text(
            "❌ **Job Description needed**:\n"
            "No Job Description was found. I need a Job Description to evaluate and compare both resumes against.\n"
            "Please upload a resume and paste a Job Description first."
        )
        return
        
    # 3. Evaluate both resumes against the latest JD
    latest_resume = resumes[0]
    previous_resume = resumes[1]
    
    await target_msg.reply_text("🔄 Comparing your latest resume iteration against the previous one...")
    
    latest_eval = evaluate_resume(latest_resume["extracted_text"], jd["jd_text"])
    previous_eval = evaluate_resume(previous_resume["extracted_text"], jd["jd_text"])
    
    # 4. Track changes
    comparison = compare_versions(latest_eval, previous_eval)
    
    if not comparison:
        await target_msg.reply_text("❌ Failed to compare resume versions.")
        return
        
    delta = comparison["score_delta"]
    score_direction = "📈 Improvement" if delta >= 0 else "📉 Decline"
    sign = "+" if delta >= 0 else ""
    
    report = (
        f"🔄 **RESUME ITERATION COMPARISON**\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 **Score Delta**: `{sign}{delta} points` ({score_direction})\n"
        f"• Previous Score: `{previous_eval['overall_score']}/100`\n"
        f"• New Score: `{latest_eval['overall_score']}/100`\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
    )
    
    # Newly Matched Skills
    added_kws = comparison["newly_matched_keywords"]
    if added_kws:
        report += "✨ **Newly Matched Skills**:\n" + "\n".join([f"• `{kw}`" for kw in added_kws]) + "\n\n"
        
    # Dropped Skills
    dropped_kws = comparison["dropped_keywords"]
    if dropped_kws:
        report += "⚠️ **Skills Removed (No longer matched)**:\n" + "\n".join([f"• `{kw}`" for kw in dropped_kws]) + "\n\n"
        
    # Added Sections
    added_secs = comparison["added_sections"]
    if added_secs:
        report += "🏛️ **Newly Added Sections**:\n" + "\n".join([f"• {sec.capitalize()}" for sec in added_secs]) + "\n\n"
        
    # Resolved formatting
    resolved = comparison["resolved_issues"]
    if resolved:
        report += "💅 **Resolved Formatting Issues**:\n" + "\n".join([f"• {issue}" for issue in resolved]) + "\n\n"
        
    # New issues
    new_issues = comparison["new_issues"]
    if new_issues:
        report += "🔴 **New Formatting Warnings**:\n" + "\n".join([f"• {issue}" for issue in new_issues]) + "\n\n"
        
    if not added_kws and not dropped_kws and not added_secs and not resolved and not new_issues:
        report += "No functional differences detected between both versions when compared to this Job Description."
        
    await target_msg.reply_text(report, parse_mode="Markdown")
