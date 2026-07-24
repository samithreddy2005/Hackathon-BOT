"""
Extract specific entities and sections from resume text.
"""
import re

EMAIL_REGEX = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
PHONE_REGEX = r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b'

SECTION_PATTERNS = {
    'summary': re.compile(r'\b(summary|profile|about me|objective|professional summary|executive summary)\b', re.IGNORECASE),
    'experience': re.compile(r'\b(experience|employment|work history|professional experience|career history|work experience)\b', re.IGNORECASE),
    'education': re.compile(r'\b(education|academic history|qualifications|academic background|academic qualifications)\b', re.IGNORECASE),
    'skills': re.compile(r'\b(skills|technical skills|key skills|core competencies|expertise|technologies|proficiencies)\b', re.IGNORECASE),
    'projects': re.compile(r'\b(projects|personal projects|academic projects|key projects|research projects)\b', re.IGNORECASE),
    'languages': re.compile(r'\b(languages|language proficiencies)\b', re.IGNORECASE),
    'certifications': re.compile(r'\b(certifications|certificates|licenses|courses)\b', re.IGNORECASE)
}

def extract_email(text):
    """
    Finds and returns the first email address in the text.
    """
    if not text:
        return None
    match = re.search(EMAIL_REGEX, text)
    return match.group(0) if match else None

def extract_phone(text):
    """
    Finds and returns the first phone number pattern in the text.
    """
    if not text:
        return None
    match = re.search(PHONE_REGEX, text)
    return match.group(0) if match else None

def detect_sections(text):
    """
    Scans the text to find which common sections are present.
    Returns a dictionary of section names mapped to a boolean representing presence.
    """
    present_sections = {}
    if not text:
        return {section: False for section in SECTION_PATTERNS}
        
    # Split text into lines to look for headings
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    
    for section_name, pattern in SECTION_PATTERNS.items():
        found = False
        # Look in first few words of lines to detect sections
        for line in lines:
            # Check if line is short (typical header) and matches the pattern
            if len(line) < 50:
                if pattern.search(line):
                    found = True
                    break
        
        # Fallback: if not found in short lines, do a general search in text (less strict)
        if not found:
            # Match boundary words to reduce false positives
            if pattern.search(text):
                found = True
                
        present_sections[section_name] = found
        
    return present_sections
