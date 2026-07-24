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
            # Trigger document upload action
            await context.bot.send_chat_action(chat_id=message.chat_id, action="upload_document")
            
            file_type = ext.replace(".", "")
            tg_file = await doc.get_file()
            file_path = os.path.join(UPLOAD_DIR, f"{message.chat_id}_{doc.file_id}{ext}")
            await tg_file.download_to_drive(file_path)
            
        # Handle Photos (images sent directly)
        elif message.photo:
            status_msg = await message.reply_text("📥 Downloading resume image...")
            # Trigger document upload action
            await context.bot.send_chat_action(chat_id=message.chat_id, action="upload_document")
            
            photo = message.photo[-1]  # Get largest size
            file_type = "image"
            ext = ".jpg"
            file_name = f"photo_{photo.file_id}.jpg"
            tg_file = await photo.get_file()
            file_path = os.path.join(UPLOAD_DIR, f"{message.chat_id}_{photo.file_id}{ext}")
            await tg_file.download_to_drive(file_path)
            
        else:
            await message.reply_text("❌ No file detected. Please upload your resume.")
            return
            
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
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
        
    if not extracted_text or not extracted_text.strip():
        await status_msg.edit_text(
            "⚠️ Text extraction returned empty content.\n"
            "If this is a scanned PDF or image, ensure OCR is installed properly. "
            "Otherwise, please check your document content."
        )
        # Cleanup file if parsing failed
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
        return
        
    # 3. Save to database
    resume_id = save_resume(update.effective_user.id, file_path, file_type, extracted_text)
    
    if resume_id:
        # Update user session state
        context.user_data["state"] = "WAITING_FOR_JD"
        context.user_data["last_resume_id"] = resume_id
        
        success_msg = (
            f"✅ **Resume parsed successfully!**\n"
            f"📄 File: `{file_name}`\n"
            f"📏 Word Count: `{len(extracted_text.split())}` words\n\n"
            f"👉 **Next Step**: Please paste/send the **Job Description (JD)** text to start evaluation."
        )
        await status_msg.edit_text(success_msg, parse_mode="Markdown")
    else:
        await status_msg.edit_text("❌ Database error occurred while saving your resume. Please try again.")
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
