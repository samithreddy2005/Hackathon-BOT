"""
ATS Scorer Engine. Orchestrates the evaluation of a resume against a Job Description.
"""
from ats.keyword_matcher import match_keywords
from ats.section_checker import check_sections
from ats.formatting_checker import check_formatting
from ats.suggestions import generate_suggestions

def evaluate_resume(resume_text, jd_text):
    """
    Evaluates a resume against a Job Description.
    Returns:
        - dict: containing all scores, lists of matched/missing keywords, sections, and suggestions.
    """
    if not resume_text:
        return {
            "overall_score": 0.0,
            "keyword_score": 0.0,
            "structure_score": 0.0,
            "formatting_score": 0.0,
            "matched_keywords": [],
            "missing_keywords": [],
            "present_sections": [],
            "missing_sections": [],
            "formatting_issues": ["Resume text is empty or could not be read."],
            "suggestions": {
                "keywords": ["Please upload a valid resume."],
                "structure": ["Please upload a valid resume."],
                "formatting": ["Please upload a valid resume."]
            }
        }
        
    # 1. Keyword Matching (40% weight)
    kw_score, matched_kws, missing_kws = match_keywords(resume_text, jd_text)
    
    # 2. Section Completeness (30% weight)
    struct_score, present_secs, missing_secs = check_sections(resume_text)
    
    # 3. Formatting (30% weight)
    format_score, format_issues = check_formatting(resume_text)
    
    # Calculate weighted overall score
    overall = (kw_score * 0.40) + (struct_score * 0.30) + (format_score * 0.30)
    overall_score = round(overall, 1)
    
    # Generate recommendations
    suggestions = generate_suggestions(missing_kws, missing_secs, format_issues)
    
    return {
        "overall_score": overall_score,
        "keyword_score": kw_score,
        "structure_score": struct_score,
        "formatting_score": format_score,
        "matched_keywords": matched_kws,
        "missing_keywords": missing_kws,
        "present_sections": present_secs,
        "missing_sections": missing_secs,
        "formatting_issues": format_issues,
        "suggestions": suggestions
    }
