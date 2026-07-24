"""
Generate actionable improvement suggestions for the resume.
"""

def generate_suggestions(missing_keywords, missing_sections, formatting_issues):
    """
    Creates a comprehensive list of actionable tips to improve the resume score.
    Returns a dictionary of suggestions grouped by category.
    """
    suggestions = {
        "keywords": [],
        "structure": [],
        "formatting": []
    }
    
    # 1. Keywords Suggestions
    if missing_keywords:
        limit = min(8, len(missing_keywords))
        missing_sample = missing_keywords[:limit]
        suggestions["keywords"].append(
            f"Add missing keywords/skills that were in the Job Description: "
            f"**{', '.join(missing_sample)}**."
        )
        if len(missing_keywords) > limit:
            suggestions["keywords"].append(
                f"There are {len(missing_keywords) - limit} other missing skills. Review the job description carefully."
            )
    else:
        suggestions["keywords"].append("Great job! You have matched all key skills from the Job Description.")
        
    # 2. Structure Suggestions
    if missing_sections:
        for section in missing_sections:
            if section == 'experience':
                suggestions["structure"].append("Add a detailed 'Work Experience' section with accomplishments.")
            elif section == 'education':
                suggestions["structure"].append("Include an 'Education' section outlining degrees and institutions.")
            elif section == 'skills':
                suggestions["structure"].append("Create a dedicated 'Skills' section so ATS scanners can quickly index your expertise.")
            elif section == 'summary':
                suggestions["structure"].append("Write a 'Professional Summary' or 'Objective' statement at the top to highlight your value proposition.")
            elif section == 'projects':
                suggestions["structure"].append("Add a 'Projects' section to showcase practical application of your skills.")
    else:
        suggestions["structure"].append("Your resume contains all essential sections.")
        
    # 3. Formatting Suggestions
    if formatting_issues:
        for issue in formatting_issues:
            suggestions["formatting"].append(issue)
    else:
        suggestions["formatting"].append("No major formatting issues detected.")
        
    return suggestions
