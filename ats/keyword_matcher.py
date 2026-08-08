"""
Match keywords and skills between Job Description and Resume using a core skills dictionary.
"""
import re
from utils.constants import SKILLS_DICTIONARY
from parser.cleaner import tokenize_and_normalize, extract_potential_keywords
from rapidfuzz import fuzz

def is_skill_present(text, skill):
    """
    Checks if a skill is present in the text, respecting word boundaries
    (works correctly for special characters like C++, C#, .NET, CI/CD).
    """
    # Fast check
    if skill not in text:
        return False
        
    index = 0
    while True:
        index = text.find(skill, index)
        if index == -1:
            return False
            
        # Check boundary before the skill
        start_ok = True
        if index > 0:
            prev_char = text[index - 1]
            # If preceding character is alphanumeric, or a symbol like +, #, or - (which are part of skills like C++, C#, CI-CD), it's not a word boundary
            if prev_char.isalnum() or prev_char in ['+', '#', '-']:
                start_ok = False
                
        # Check boundary after the skill
        end_ok = True
        end_idx = index + len(skill)
        if end_idx < len(text):
            next_char = text[end_idx]
            if next_char.isalnum() or next_char in ['+', '#', '-']:
                end_ok = False
                
        if start_ok and end_ok:
            return True
            
        index += len(skill)

def extract_skills_from_text(text):
    """
    Extracts all skills from SKILLS_DICTIONARY that are present in the text.
    """
    if not text:
        return []
        
    text_lower = text.lower()
    found_skills = []
    
    for skill in SKILLS_DICTIONARY:
        if is_skill_present(text_lower, skill):
            found_skills.append(skill)
            
    return found_skills

def match_keywords(resume_text, jd_text):
    """
    Compares the resume text against the job description text.
    Returns:
        - match_percentage (float)
        - matched_keywords (list)
        - missing_keywords (list)
    """
    if not resume_text or not jd_text:
        return 0.0, [], []
        
    # 1. Attempt dictionary-based skill extraction from JD
    jd_skills = extract_skills_from_text(jd_text)
    
    # Fallback to statistical word extraction if JD has no standard tech/soft skills
    if not jd_skills:
        jd_skills = extract_potential_keywords(jd_text)

    if not jd_skills:
        return 100.0, [], []

    resume_text_lower = resume_text.lower()
    resume_tokens = tokenize_and_normalize(resume_text)

    matched = []
    missing = []

    for skill in jd_skills:
        # Direct match for dictionary skills or extracted phrases.
        if is_skill_present(resume_text_lower, skill):
            matched.append(skill)
            continue

        # Fuzzy fallback using normalized resume tokens for single-word tokens.
        is_fuzzy_match = False
        if " " not in skill and len(skill) > 3:
            for token in resume_tokens:
                if len(token) > 3:
                    if fuzz.ratio(token, skill) > 80.0:
                        matched.append(skill)
                        is_fuzzy_match = True
                        break

        # Fuzzy phrase matching for multi-word extracted phrases.
        if not is_fuzzy_match and " " in skill:
            phrase_tokens = skill.split()
            if all(tok in resume_tokens for tok in phrase_tokens):
                matched.append(skill)
                is_fuzzy_match = True

        if not is_fuzzy_match:
            # Attempt partial token overlap for longer keywords/phrases.
            overlap_hits = 0
            skill_parts = skill.split()
            for part in skill_parts:
                if part in resume_tokens:
                    overlap_hits += 1
            if overlap_hits >= max(1, len(skill_parts) - 1):
                matched.append(skill)
                is_fuzzy_match = True

        if not is_fuzzy_match:
            missing.append(skill)

    total_skills = len(jd_skills)
    match_count = len(matched)
    match_percentage = (match_count / total_skills) * 100.0 if total_skills > 0 else 100.0

    return round(match_percentage, 1), matched, missing
