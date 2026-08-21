"""Free-form question answering.

Tries the LLM assistant first when it is configured, and falls back to the offline
FAQ index. The fallback is not an error path — it is the default deployment.
"""

from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ChatAction

from ats_bot.db import repository
from ats_bot.db.models import JobDescription, Resume
from ats_bot.errors import DatabaseError
from ats_bot.handlers.common import (
    BotContext,
    SessionKey,
    get_faq_index,
    get_llm,
    user_id_of,
)
from ats_bot.services.faq import FaqIndex
from ats_bot.services.llm import LlmUnavailable
from ats_bot.utils.concurrency import run_blocking
from ats_bot.utils.telegram_html import bold, esc, italic, markdown_to_html, safe_reply

__all__ = ["handle_question"]

logger = logging.getLogger(__name__)

#: How many example topics to offer when nothing matches.
_TOPIC_SUGGESTIONS = 5


async def handle_question(update: Update, context: BotContext) -> None:
    """Answer a general question about resumes, interviews, or the user's documents."""
    message = update.effective_message
    if message is None or not message.text:  # pragma: no cover
        return

    question = message.text.strip()
    user_id = user_id_of(update)
    index = get_faq_index(context)
    assistant = get_llm(context)

    if assistant is not None and assistant.enabled:
        if message.chat:
            await message.chat.send_action(ChatAction.TYPING)
        resume, job = await _session_documents(context, user_id)
        try:
            answer = await assistant.answer(question, resume=resume, job_description=job)
        except LlmUnavailable as exc:
            logger.debug("Assistant unavailable (%s); answering from the FAQ.", exc)
        else:
            await safe_reply(message, markdown_to_html(answer))
            return

    await safe_reply(message, _offline_answer(question, index))


def _offline_answer(question: str, index: FaqIndex) -> str:
    """Answer from the local knowledge base, or explain what can be asked."""
    match = index.search(question)

    if match is not None and match.confident:
        logger.debug("FAQ matched %r (score=%.3f)", match.entry.question, match.score)
        return f"💡 {italic(match.entry.question)}\n\n{match.entry.answer}"

    topics = "\n".join(f"• {esc(entry.question)}" for entry in index.entries[:_TOPIC_SUGGESTIONS])
    return (
        f"🤔 {bold('I am not sure what you are asking')}\n\n"
        "I can answer questions like:\n"
        f"{topics}\n\n"
        f"{bold('Or score your resume:')} upload it as a file, then paste a job "
        "description and I will tell you what to change."
    )


async def _session_documents(
    context: BotContext, user_id: int
) -> tuple[Resume | None, JobDescription | None]:
    """The resume and job description the assistant should reason about.

    Returns nothing after /newchat: the user explicitly asked for the previous
    documents to be forgotten, and silently re-attaching them would be a surprise.
    """
    user_data = context.user_data or {}
    if user_data.get(SessionKey.SESSION_CLEARED):
        return None, None

    resume: Resume | None = None
    job: JobDescription | None = None

    try:
        resume_id = user_data.get(SessionKey.LAST_RESUME_ID)
        resume = (
            await run_blocking(repository.get_resume, resume_id)
            if resume_id
            else await run_blocking(repository.get_latest_resume, user_id)
        )

        jd_id = user_data.get(SessionKey.ACTIVE_JD_ID)
        job = (
            await run_blocking(repository.get_jd, jd_id)
            if jd_id
            else await run_blocking(repository.get_latest_jd, user_id)
        )
    except DatabaseError:
        # Context is an enhancement; answering without it beats not answering.
        logger.exception("Could not load session documents for user %s", user_id)

    if resume is not None and resume.user_id != user_id:  # pragma: no cover - defensive
        resume = None
    if job is not None and job.user_id != user_id:  # pragma: no cover - defensive
        job = None

    return resume, job
