"""
Clean and preprocess extracted text.
"""
import re

# Standard English stop words
STOP_WORDS = {
    'a', 'about', 'above', 'after', 'again', 'against', 'all', 'am', 'an', 'and', 'any', 'are', 'arent', 'as', 'at',
    'be', 'because', 'been', 'before', 'being', 'below', 'between', 'both', 'but', 'by', 'cant', 'cannot', 'could',
    'couldnt', 'did', 'didnt', 'do', 'does', 'doesnt', 'doing', 'dont', 'down', 'during', 'each', 'few', 'for', 'from',
    'further', 'had', 'hadnt', 'has', 'hasnt', 'have', 'havent', 'having', 'he', 'hed', 'hell', 'hes', 'her', 'here',
    'heres', 'hers', 'herself', 'him', 'himself', 'his', 'how', 'hows', 'i', 'id', 'ill', 'im', 'ive', 'if', 'in',
    'into', 'is', 'isnt', 'it', 'its', 'itself', 'lets', 'me', 'more', 'most', 'mustnt', 'my', 'myself', 'no', 'nor',
    'not', 'of', 'off', 'on', 'once', 'only', 'or', 'other', 'ought', 'our', 'ours', 'ourselves', 'out', 'over', 'own',
    'same', 'shant', 'she', 'shed', 'shell', 'shes', 'should', 'shouldnt', 'so', 'some', 'such', 'than', 'that',
    'thats', 'the', 'their', 'theirs', 'them', 'themselves', 'then', 'there', 'theres', 'these', 'they', 'theyd',
    'theyll', 'theyre', 'theyve', 'this', 'those', 'through', 'to', 'too', 'under', 'until', 'up', 'very', 'was',
    'wasnt', 'we', 'wed', 'well', 'were', 'weve', 'werent', 'what', 'whats', 'when', 'whens', 'where', 'wheres',
    'which', 'while', 'who', 'whos', 'whom', 'why', 'whys', 'with', 'wont', 'would', 'wouldnt', 'you', 'youd',
    'youll', 'youre', 'youve', 'your', 'yours', 'yourself', 'yourselves'
}

def clean_text(text):
    """
    Cleans general text (removing extra whitespace, normalization, fixing weird spaces).
    """
    if not text:
        return ""
    # Normalize whitespaces (replace multiple spaces/newlines with single ones)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def tokenize_and_normalize(text):
    """
    Tokenizes text into a set of lowercased alphanumeric words, excluding stop words.
    Used for general keyword matching comparisons.
    """
    if not text:
        return set()
        
    # Lowercase and replace non-alphanumeric characters with spaces
    cleaned = re.sub(r'[^a-zA-Z0-9+#\-\s]', ' ', text.lower())
    
    # Split into tokens
    tokens = cleaned.split()
    
    # Filter out stop words and short tokens (single chars that aren't 'c', 'r', etc.)
    allowed_single_chars = {'c', 'r'}
    normalized_tokens = [
        token for token in tokens
        if token not in STOP_WORDS and (len(token) > 1 or token in allowed_single_chars)
    ]
    
    return set(normalized_tokens)

def extract_potential_keywords(text):
    """
    Extracts terms that are likely keywords/skills from the Job Description text.
    Looks for capitalized terms, common tech symbols, and words.
    """
    if not text:
        return []
    
    # Extract unique tokens, keeping order
    words = re.findall(r'[a-zA-Z0-9+#\-]+', text)
    seen = set()
    keywords = []
    
    for word in words:
        word_lower = word.lower()
        if word_lower not in STOP_WORDS and len(word_lower) > 1:
            if word_lower not in seen:
                seen.add(word_lower)
                # Keep original case for presentation if useful, but store lower
                keywords.append(word_lower)
                
    return keywords
