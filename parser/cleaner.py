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

def extract_potential_keywords(text, max_keywords=20):
    """
    Extracts terms that are likely keywords/skills from the Job Description text.
    Looks for strong tokens and common multi-word phrases.
    """
    if not text:
        return []

    # Normalize the text and split into tokens
    words = re.findall(r'[A-Za-z0-9+#\-]+', text)
    normalized = [word.lower() for word in words]

    # Build candidate phrases from bigrams/trigrams first, then single tokens.
    seen = set()
    keywords = []

    def is_valid_token(token: str) -> bool:
        return token not in STOP_WORDS and len(token) > 2 and not token.isdigit()

    # Add multi-word candidates first, which are often more meaningful than isolated words.
    for n in (3, 2):
        for i in range(len(normalized) - n + 1):
            phrase_tokens = normalized[i:i + n]
            if all(is_valid_token(tok) for tok in phrase_tokens):
                phrase = " ".join(phrase_tokens)
                if phrase not in seen:
                    seen.add(phrase)
                    keywords.append(phrase)
                    if len(keywords) >= max_keywords:
                        return keywords

    # Add single-word keywords after phrase candidates.
    for token in normalized:
        if is_valid_token(token) and token not in seen:
            seen.add(token)
            keywords.append(token)
            if len(keywords) >= max_keywords:
                break

    return keywords
