"""
Parser for PDF files using pdfplumber.
"""
import pdfplumber
import logging

logger = logging.getLogger(__name__)

def extract_text_from_pdf(file_path):
    """
    Extracts and returns the text content of a PDF file.
    """
    text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
        return text.strip()
    except Exception as e:
        logger.error(f"Error parsing PDF file {file_path}: {e}")
        return ""
