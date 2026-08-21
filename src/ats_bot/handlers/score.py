"""Job-description scoring: the core flow of the bot."""

from __future__ import annotations

import logging

from telegram import Update

from ats_bot.ats.comparison import compare_evaluations
from ats_bot.ats.models import Evaluation
from ats_bot.ats.scorer import evaluate_resume
from ats_bot.db import repository
from ats_bot.db.models import Resume
from ats_bot.handlers.common import (
    BotContext,
    SessionKey,
    post_report_menu,
    user_id_of,
)
from ats_bot.reporting import render_comparison, render_evaluation
from ats_bot.utils.concurrency import run_blocking
from ats_bot.utils.telegram_html import bold, code, italic, safe_edit, safe_reply

__all__ = ["MIN_JD_WORDS", "handle_job_description", "handle_latest_score"]

logger = logging.getLogger(__name__)

#: A posting shorter than this cannot produce a meaningful keyword checklist.
MIN_JD_WORDS = 20

#: Cap on how many queued resumes one job description is scored against, so a user
#: who uploads a folder of files does not generate unbounded work.
MAX_BATCH = 5


async def handle_job_description(update: Update, context: BotContext) -> None:
    """Score every queued resume against the job description just received."""
    message = update.effective_message
    if message is None or not message.text:  # pragma: no cover - filtered upstream
        return

    user_id = user_id_of(update)
    jd_text = message.text.strip()

    if len(jd_text.split()) < MIN_JD_WORDS:
        await safe_reply(
            message,
            f"📝 That job description is very short, so a keyword score would be "
            f"misleading. Paste the full posting — especially the "
            f"{bold('requirements')} or {bold('qualifications')} section.",
        )
        return

    resumes = await _resumes_to_score(context, user_id)
    if not resumes:
        await safe_reply(
            message,
            f"📄 {bold('Upload a resume first')}\n\n"
            "Send me your resume as a PDF, DOCX, or image, then paste this job "
            "description again and I will score it.",
        )
        _reset_state(context)
        return

    plural = "s" if len(resumes) > 1 else ""
    status = await message.reply_text(f"⚖️ Scoring {len(resumes)} resume{plural}…")

    jd_id = await run_blocking(repository.save_jd, user_id, jd_text)

    for index, resume in enumerate(resumes):
        report = await _score_one(user_id, resume, jd_text, jd_id)
        if index == 0:
            # The first report replaces the status message so the chat stays tidy.
            await safe_edit(status, report, reply_markup=post_report_menu())
        else:
            await safe_reply(message, report)

    _finish(context, jd_id)


async def _score_one(user_id: int, resume: Resume, jd_text: str, jd_id: int) -> str:
    """Evaluate one resume, persist the result, and render its report."""
    evaluation = await run_blocking(evaluate_resume, resume.extracted_text, jd_text)

    await run_blocking(
        repository.save_score,
        resume_id=resume.resume_id,
        jd_id=jd_id,
        overall_score=evaluation.overall_score,
        keyword_score=evaluation.keywords.score,
        structure_score=evaluation.sections.score,
        formatting_score=evaluation.formatting.score,
        details_json=evaluation.to_json(),
    )

    report = render_evaluation(evaluation, resume_name=resume.display_name)

    comparison = await _compare_with_previous(user_id, resume, jd_text, evaluation)
    if comparison:
        report += "\n\n" + comparison
    return report


async def _compare_with_previous(
    user_id: int, resume: Resume, jd_text: str, evaluation: Evaluation
) -> str | None:
    """Contrast this resume with the user's previous one, if there is one.

    The previous resume is re-scored against *this* job description rather than
    reusing its stored score, which was computed against a different posting and
    would make the delta meaningless.
    """
    previous = await run_blocking(repository.get_previous_resume, user_id, resume.resume_id)
    if previous is None or not previous.extracted_text.strip():
        return None

    previous_evaluation = await run_blocking(evaluate_resume, previous.extracted_text, jd_text)
    delta = compare_evaluations(evaluation, previous_evaluation)
    if delta.unchanged:
        return None

    return render_comparison(
        delta,
        current_name=resume.display_name,
        previous_name=previous.display_name,
        current_score=evaluation.overall_score,
        previous_score=previous_evaluation.overall_score,
    )


async def _resumes_to_score(context: BotContext, user_id: int) -> list[Resume]:
    """The resumes queued in this conversation, or the latest stored one."""
    pending: list[int] = list((context.user_data or {}).get(SessionKey.PENDING_RESUME_IDS, []))

    resumes: list[Resume] = []
    for resume_id in pending[:MAX_BATCH]:
        resume = await run_blocking(repository.get_resume, resume_id)
        if resume is not None and resume.user_id == user_id:
            resumes.append(resume)

    if resumes:
        return resumes

    latest = await run_blocking(repository.get_latest_resume, user_id)
    return [latest] if latest else []


def _reset_state(context: BotContext) -> None:
    if context.user_data is not None:
        context.user_data[SessionKey.STATE] = None


def _finish(context: BotContext, jd_id: int) -> None:
    """Clear the upload queue and record the job description as the active one."""
    if context.user_data is None:  # pragma: no cover
        return
    context.user_data[SessionKey.STATE] = None
    context.user_data[SessionKey.PENDING_RESUME_IDS] = []
    context.user_data[SessionKey.ACTIVE_JD_ID] = jd_id


async def handle_latest_score(update: Update, context: BotContext) -> None:
    """Re-send the user's most recent evaluation.

    The report is rebuilt from the exact resume and job description recorded on
    that score row — not from whichever documents happen to be newest. Scoring is
    deterministic, so the number shown always matches the stored one; pairing the
    latest resume with the latest job description would not, and would print a
    different score under a past timestamp.
    """
    message = update.effective_message
    if message is None:  # pragma: no cover
        return

    user_id = user_id_of(update)
    history = await run_blocking(repository.get_score_history, user_id, limit=1)

    if not history:
        await safe_reply(
            message,
            f"📭 {bold('No scores yet')}\n\n"
            "Upload a resume and paste a job description, and your first report will "
            "appear here.",
        )
        return

    record = history[0]
    resume = await run_blocking(repository.get_resume, record.resume_id)
    job = await run_blocking(repository.get_jd, record.jd_id)

    if resume is None or job is None:
        await safe_reply(
            message,
            f"📊 {bold(f'{record.overall_score}/100')} · {code(record.created_at.split('.')[0])}\n\n"
            + italic("The documents behind this score are no longer available."),
        )
        return

    evaluation = await run_blocking(evaluate_resume, resume.extracted_text, job.jd_text)
    header = f"📅 {italic('Most recent evaluation, ' + record.created_at.split('.')[0])}\n\n"
    await safe_reply(
        message, header + render_evaluation(evaluation, resume_name=resume.display_name)
    )
