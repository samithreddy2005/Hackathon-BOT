"""
Verify formatting and contact details in the resume.
"""
from parser.extractor import extract_email, extract_phone

def check_formatting(resume_text):
    """
    Evaluates formatting constraints such as word count and contact details.
    Returns:
        - score (float): formatting score out of 100.
        - issues (list): list of formatting issues/errors.
    """
    issues = []
    score = 100.0
    
    if not resume_text:
        return 0.0, ["Resume is empty or could not be read."]
        
    # 1. Word Count Check
    words = resume_text.split()
    word_count = len(words)
    
    if word_count < 150:
        issues.append(f"Resume is very short ({word_count} words). Recommended word count is 200 - 1500 words.")
        score -= 30.0
    elif word_count > 2000:
        issues.append(f"Resume is very long ({word_count} words). Keep it concise (under 1500 words) for readability.")
        score -= 15.0
        
    # 2. Contact Details Check
    email = extract_email(resume_text)
    phone = extract_phone(resume_text)
    
    if not email:
        issues.append("Email address not found. Ensure contact details are clearly visible.")
        score -= 30.0
    if not phone:
        issues.append("Phone number not found. Ensure employers can contact you easily.")
        score -= 20.0
        
    # 3. Check for typical placeholder words
    placeholders = ["placeholder", "lorem ipsum", "insert name", "your name here", "loremipsum"]
    found_placeholders = [p for p in placeholders if p in resume_text.lower()]
    if found_placeholders:
        issues.append(f"Found placeholder text: {', '.join(found_placeholders)}.")
        score -= 15.0
        
    final_score = max(score, 0.0)
    return round(final_score, 1), issues
