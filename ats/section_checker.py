"""
Verify presence of standard resume sections and calculate structure score.
"""
from parser.extractor import detect_sections

# Weights for different sections in the structure evaluation (sum is 100)
SECTION_WEIGHTS = {
    'experience': 30,
    'education': 25,
    'skills': 25,
    'summary': 10,
    'projects': 10
}

def check_sections(resume_text):
    """
    Evaluates section completeness of the resume.
    Returns:
        - score (float): section completeness score out of 100.
        - present (list): list of sections found.
        - missing (list): list of essential sections missing.
    """
    sections = detect_sections(resume_text)
    
    score = 0.0
    present = []
    missing = []
    
    # Calculate score based on weights
    for section, weight in SECTION_WEIGHTS.items():
        if sections.get(section, False):
            score += weight
            present.append(section)
        else:
            missing.append(section)
            
    # Include minor sections (certifications, languages) as bonuses or general structure checks
    minor_bonus = 0.0
    if sections.get('certifications', False):
        minor_bonus += 5.0
    if sections.get('languages', False):
        minor_bonus += 5.0
        
    # Cap total section score at 100
    final_score = min(score + minor_bonus, 100.0)
    
    return round(final_score, 1), present, missing
