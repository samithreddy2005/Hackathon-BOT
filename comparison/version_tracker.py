"""
Track and compare different resume versions and evaluation runs.
"""

def compare_versions(current_eval, previous_eval):
    """
    Compares the current evaluation metrics against the previous evaluation metrics.
    Parameters:
        - current_eval (dict): current score evaluation dict
        - previous_eval (dict): previous score evaluation dict
    Returns:
        - dict: containing deltas and change summaries.
    """
    if not current_eval or not previous_eval:
        return None
        
    score_delta = round(current_eval["overall_score"] - previous_eval["overall_score"], 1)
    
    # Keyword differences
    curr_matched = set(current_eval.get("matched_keywords", []))
    prev_matched = set(previous_eval.get("matched_keywords", []))
    
    newly_matched = list(curr_matched - prev_matched)
    dropped_keywords = list(prev_matched - curr_matched)
    
    # Section differences
    curr_sections = set(current_eval.get("present_sections", []))
    prev_sections = set(previous_eval.get("present_sections", []))
    
    added_sections = list(curr_sections - prev_sections)
    removed_sections = list(prev_sections - curr_sections)
    
    # Formatting issue improvements
    curr_issues = set(current_eval.get("formatting_issues", []))
    prev_issues = set(previous_eval.get("formatting_issues", []))
    
    resolved_issues = list(prev_issues - curr_issues)
    new_issues = list(curr_issues - prev_issues)
    
    return {
        "score_delta": score_delta,
        "newly_matched_keywords": newly_matched,
        "dropped_keywords": dropped_keywords,
        "added_sections": added_sections,
        "removed_sections": removed_sections,
        "resolved_issues": resolved_issues,
        "new_issues": new_issues
    }
