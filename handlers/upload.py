"""
Handler for resume file uploads (PDF, DOCX, Images).
"""
import os
import logging
from telegram import Update
from telegram.ext import ContextTypes
from parser.pdf_parser import extract_text_from_pdf
from parser.docx_parser import extract_text_from_docx
from parser.image_parser import extract_text_from_image
from database.db import save_resume

logger = logging.getLogger(__name__)

# Ensure the uploads directory exists
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

import asyncio

async def download_file_with_retry(doc_or_photo, file_path, retries=3, delay=1.0):
    """
    Downloads a Telegram file with a retry mechanism to handle concurrency or rate limits.
    Increases read and write timeouts to prevent connection timeouts during concurrent uploads.
    """
    for attempt in range(retries):
        try:
            tg_file = await doc_or_photo.get_file(read_timeout=30.0)
            await tg_file.download_to_drive(file_path, write_timeout=30.0)
            return True
        except Exception as e:
            if attempt == retries - 1:
                raise e
            logger.warning(f"Download attempt {attempt + 1} failed for {file_path}. Retrying in {delay}s... Error: {e}")
            await asyncio.sleep(delay)
    return False

async def handle_resume_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Downloads and parses the uploaded resume document.
    """
    message = update.message
    file_path = None
    file_type = None
    file_name = ""
    
    # 1. Detect and download file
    status_msg = None
    try:
        # Handle Documents (PDF, DOCX, images sent as files)
        if message.document:
            doc = message.document
            file_name = doc.file_name
            ext = os.path.splitext(file_name)[1].lower()
            
            if ext not in [".pdf", ".docx", ".png", ".jpg", ".jpeg"]:
                await message.reply_text(
                    "❌ Unsupported file type. Please send a **.pdf**, **.docx**, or an image file.",
                    parse_mode="Markdown"
                )
                return
                
            status_msg = await message.reply_text("📥 Downloading your resume file...")
            await context.bot.send_chat_action(chat_id=message.chat_id, action="upload_document")
            
            file_type = ext.replace(".", "")
            import re
            safe_name = re.sub(r'[\\/*?:"<>|]', "", file_name)
            if not safe_name:
                safe_name = f"resume_{doc.file_id}{ext}"
            file_path = os.path.join(UPLOAD_DIR, f"{message.chat_id}_{safe_name}")
            await download_file_with_retry(doc, file_path)
            
        # Handle Photos (images sent directly)
        elif message.photo:
            status_msg = await message.reply_text("📥 Downloading resume image...")
            await context.bot.send_chat_action(chat_id=message.chat_id, action="upload_document")
            
            photo = message.photo[-1]  # Get largest size
            file_type = "image"
            ext = ".jpg"
            file_name = f"photo_{photo.file_id}.jpg"
            file_path = os.path.join(UPLOAD_DIR, f"{message.chat_id}_{photo.file_id}{ext}")
            await download_file_with_retry(photo, file_path)
            
        else:
            await message.reply_text("❌ No file detected. Please upload your resume.")
            return
            
    except Exception as e:
        logger.exception("Error downloading file")
        if status_msg:
            await status_msg.edit_text("❌ Failed to download file. Please try again.")
        else:
            await message.reply_text("❌ Failed to download file. Please try again.")
        return

    # 2. Extract Text
    await status_msg.edit_text("🔍 Extracting text and performing parser operations...")
    # Send typing indicator
    await context.bot.send_chat_action(chat_id=message.chat_id, action="typing")
    
    extracted_text = ""
    
    if file_type == "pdf":
        extracted_text = extract_text_from_pdf(file_path)
    elif file_type == "docx":
        extracted_text = extract_text_from_docx(file_path)
    elif file_type in ["png", "jpg", "jpeg", "image"]:
        extracted_text = extract_text_from_image(file_path)
        
    # 2. Verify Case C: File text extraction failed or is too short
    word_count = len(extracted_text.split())
    if word_count < 50:
        await status_msg.edit_text(
            "❌ **Resume text could not be read or is too short (Case C)**\n\n"
            f"The uploaded document contains only {word_count} words, which is insufficient for an ATS evaluation.\n"
            "Please ensure you upload a text-based PDF, DOCX file, or a high-quality resume image, and try again.",
            parse_mode="Markdown"
        )
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        return
        
    # Verify Case D: File does not look like a resume (missing essential sections)
    from parser.extractor import detect_sections
    sections = detect_sections(extracted_text)
    has_headers = sections["experience"] or sections["education"] or sections["skills"]
    if not has_headers:
        await status_msg.edit_text(
            "❌ **Document does not look like a resume (Case D)**\n\n"
            "I could not detect standard resume sections (like Work Experience, Education, or Skills) in this document.\n"
            "If you intended to send a Job Description, please upload your resume file first.",
            parse_mode="Markdown"
        )
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        return
        
    # Verify Case E: Check if it's a near-duplicate / revision of a previous resume
    from database.db import get_latest_resume
    from rapidfuzz import fuzz
    
    user_id = update.effective_user.id
    prev_resume = get_latest_resume(user_id)
    is_revision = False
    
    if prev_resume:
        similarity = fuzz.ratio(extracted_text.lower(), prev_resume["extracted_text"].lower())
        if similarity > 60.0:
            is_revision = True
            
    # 3. Save to database
    resume_id = save_resume(user_id, file_path, file_type, extracted_text)
    
    if resume_id:
        context.user_data["state"] = "WAITING_FOR_JD"
        context.user_data["last_resume_id"] = resume_id
        
        # Append resume_id to tracking list
        if "uploaded_resume_ids" not in context.user_data:
            context.user_data["uploaded_resume_ids"] = []
        context.user_data["uploaded_resume_ids"].append(resume_id)
        
        # Clean file name from underscores for Markdown safety
        clean_file_name = file_name.replace("_", " ")
        
        if is_revision:
            success_msg = (
                f"🔄 **Revision detected (Case E)!**\n"
                f"📄 File: `{clean_file_name}`\n"
                f"📏 Word Count: `{word_count}` words\n\n"
                f"Your updated resume was successfully uploaded. Please paste or send the **Job Description (JD)** text to compare scores."
            )
        else:
            success_msg = (
                f"✅ **Resume parsed successfully!**\n"
                f"📄 File: `{clean_file_name}`\n"
                f"📏 Word Count: `{word_count}` words\n\n"
                f"👉 **Next Step**: Please paste/send the **Job Description (JD)** text to start evaluation."
            )
        await status_msg.edit_text(success_msg, parse_mode="Markdown")
    else:
        await status_msg.edit_text("❌ Database error occurred while saving your resume. Please try again.")
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
