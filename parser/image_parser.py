"""
Parser for resume image formats (using OCR with pytesseract).
"""
import os
import pytesseract
from PIL import Image
import logging
import pandas

logger = logging.getLogger(__name__)

# Try to find Tesseract in default paths on Windows if it's not directly in PATH
tesseract_windows_paths = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expanduser(r"~\AppData\Local\Programs\Tesseract-OCR\tesseract.exe"),
    os.path.expanduser(r"~\AppData\Local\Tesseract-OCR\tesseract.exe")
]

for path in tesseract_windows_paths:
    if os.path.exists(path):
        pytesseract.pytesseract.tesseract_cmd = path
        logger.info(f"Tesseract path configured: {path}")
        break

def extract_text_from_image(file_path):
    """
    Extracts text from image formats using pytesseract OCR.
    """
    try:
        if not os.path.exists(file_path):
            logger.error(f"Image file not found: {file_path}")
            return ""
            
        with Image.open(file_path) as img:
            # 1. Convert to grayscale
            gray = img.convert('L')
            # 2. Resize to enhance detail if the image resolution is small
            width, height = gray.size
            if width < 1500:
                gray = gray.resize((width * 2, height * 2), Image.Resampling.LANCZOS)
            # 3. Perform binarization via thresholding
            binary = gray.point(lambda p: 255 if p > 127 else 0)
            
            text = pytesseract.image_to_string(binary)
            return text.strip()
    except Exception as e:
        logger.error(f"Error executing OCR on image {file_path}: {e}")
        # Note: Often pytesseract fails if tesseract is not installed on the host system.
        # Suggest installing Tesseract in the error logs.
        logger.warning(
            "Please ensure Tesseract OCR is installed and available in PATH or at "
            "C:\\Program Files\\Tesseract-OCR\\tesseract.exe"
        )
        return ""
