"""
Conversational FAQ Assistant for resume tips and interview preparation.
Implements a custom pure Python TF-IDF + Cosine Similarity search engine for offline query matching.
"""
import math
import logging
from collections import Counter
from telegram import Update
from telegram.ext import ContextTypes
from parser.cleaner import tokenize_and_normalize

logger = logging.getLogger(__name__)

# Expanded offline HR and recruitment FAQ dataset
FAQ_DATA = {
    "How to write a professional summary?": 
        "📝 **Professional Summary Guidelines**:\n\n"
        "1. **Keep it concise**: Limit it to 3–4 sentences.\n"
        "2. **State your value**: Mention your title, years of experience, and top accomplishments.\n"
        "3. **Align with the role**: Include target keywords from the job description.\n"
        "4. **Avoid clichés**: Highlight specific achievements (e.g., 'Led a team of 5 to increase sales by 20%') instead of using generic phrases.",
        
    "What are the most common sections in an ATS-friendly resume?":
        "📂 **Essential Resume Sections**:\n\n"
        "An ATS-compliant resume should have standard headers:\n"
        "• **Contact Information** (Name, Phone, Email, Location/LinkedIn)\n"
        "• **Professional Summary / Profile**\n"
        "• **Core Skills / Expertise**\n"
        "• **Professional Experience / Work History**\n"
        "• **Education**\n"
        "• _Optional but recommended_: **Projects**, **Certifications**, **Languages**.",
        
    "How can I improve my resume's keyword match score?":
        "🎯 **How to Improve Keyword Match**:\n\n"
        "1. **Analyze the Job Description**: Identify recurring skills, technical tools, and action verbs.\n"
        "2. **Integrate keywords naturally**: Place them inside your work experience accomplishments and skills section. Do not just list them in white font or dump them at the bottom (ATS algorithms detect this cheat).\n"
        "3. **Match acronyms**: Use both short and long forms, e.g., 'Project Management Professional (PMP)' or 'Search Engine Optimization (SEO)'.",
        
    "How do I format my work experience section?":
        "💼 **Formatting Work Experience**:\n\n"
        "1. **Reverse Chronological**: Start with your most recent job and work backwards.\n"
        "2. **Standard details**: Include Job Title, Company Name, Location, and Dates (Month/Year format).\n"
        "3. **Use Bullet Points**: 3–5 bullets per role starting with strong action verbs (e.g., *Designed, Managed, Improved*).\n"
        "4. **Quantify achievements**: Use metrics wherever possible (e.g., 'Reduced processing time by 15%', 'Managed a budget of $50k').",
        
    "Can I use tables, columns, or graphics in my resume?":
        "⚠️ **Tables and Graphics Warning**:\n\n"
        "• **Avoid Tables & Text Boxes**: Many older ATS parsers read columns horizontally across the page, which scrambles your text layout.\n"
        "• **No Graphics/Icons**: ATS cannot parse images. Avoid skill progress bars, icons, or complex charts.\n"
        "• **Keep it flat**: Use a simple single-column layout with standard margins (1 inch) and clear text formatting.",
        
    "How to answer 'Tell me about yourself' in an interview?":
        "🤝 **Interview: 'Tell me about yourself'**:\n\n"
        "Use the **Present-Past-Future** framework:\n"
        "1. **Present**: Talk about your current role, scope, and a recent big success.\n"
        "2. **Past**: Briefly explain how you got here—mention previous relevant experience or education.\n"
        "3. **Future**: Connect it to the job you are interviewing for, showing why you are the perfect fit for this specific opportunity.",
        
    "How to explain a career gap?":
        "⏱️ **Explaining Career Gaps**:\n\n"
        "• **Be honest and brief**: Address the gap clearly (e.g., caregiving, health, travel, further education, career transition) without over-explaining.\n"
        "• **Highlight productive activities**: Mention any freelance projects, certifications, courses, or volunteering you did during that time.\n"
        "• **Pivot to the present**: Refocus the conversation on why you are excited to return to work now.",
        
    "What is the STAR method for behavioral questions?":
        "⭐ **The STAR Method**:\n\n"
        "Use this structure to answer situational questions like *'Tell me about a time when...'*\n"
        "• **Situation**: Describe the context or situation you were in (1-2 sentences).\n"
        "• **Task**: Explain the challenge or target you needed to meet.\n"
        "• **Action**: Detail the specific steps **you** took to solve it.\n"
        "• **Result**: Share the outcome, quantifying the impact with numbers or positive feedback.",
        
    "How do I handle the 'What is your greatest weakness' question?":
        "💡 **Interview: 'What is your greatest weakness?'**:\n\n"
        "• **Pick a real, work-related weakness**: Don't say 'I'm a perfectionist' or 'I work too hard'. Pick something genuine but fixable (e.g., delegating, public speaking, learning a specific tool).\n"
        "• **Show the solution**: Explain the active steps you are taking to overcome it (e.g., 'I realized I was keeping too much work to myself, so I've started using task management software to delegate better').",
        
    "Tips for formatting an ATS-friendly resume":
        "📄 **ATS Formatting Guidelines**:\n\n"
        "• **Font Choice**: Use clean, standard sans-serif or serif fonts (e.g., Arial, Calibri, Garamond, Helvetica, Times New Roman).\n"
        "• **Font Size**: 10–12pt for body text; 14–16pt for headings.\n"
        "• **File Format**: Save as PDF or DOCX. Both are widely accepted, but DOCX is sometimes safer for older parsers.\n"
        "• **File Name**: Keep it professional, e.g., `FirstName_LastName_Resume.pdf`.",

    "How do I handle salary expectations and salary queries?":
        "💰 **Handling Salary Questions**:\n\n"
        "1. **Research first**: Use sites like Glassdoor or Payscale to find industry averages for your role and region.\n"
        "2. **Give a range**: Provide a range based on your research (e.g., '$75,000 - $85,000') rather than a single number.\n"
        "3. **Redirect back to fit**: Say something like, 'Based on my experience, I am looking for a salary in the range of X, but I am open to discussing this as we learn more about the role alignment.'",

    "Can you write a cover letter for me?":
        "📝 **Cover Letter Assistance**:\n\n"
        "While I cannot write a cover letter *from scratch* for you, here is the standard **ATS-friendly structure** you should use:\n\n"
        "• **Header**: Your name and contact details (matching your resume).\n"
        "• **Salutation**: Address a specific hiring manager if possible (e.g., 'Dear Hiring Team' or 'Dear [Manager Name]').\n"
        "• **Introduction (Para 1)**: State the role you're applying for and hook them with a key success.\n"
        "• **Body (Para 2)**: Detail 2 specific accomplishments that directly match their job requirements.\n"
        "• **Closing (Para 3)**: Reiterate your enthusiasm, mention attachments, and request an interview."
}

class TFIDFSearch:
    """
    Local TF-IDF Vectorizer and Cosine Similarity search engine.
    Matches queries against the FAQ dataset without external dependencies.
    """
    def __init__(self, document_dataset):
        self.dataset = document_dataset
        self.titles = list(document_dataset.keys())
        self.corpus_size = len(self.titles)
        
        # Tokenize and normalize each document title/question
        self.tokenized_docs = [list(tokenize_and_normalize(title)) for title in self.titles]
        
        # Compute Document Frequency (DF)
        self.df = Counter()
        for doc_tokens in self.tokenized_docs:
            for token in set(doc_tokens):
                self.df[token] += 1
                
        # Compute Inverse Document Frequency (IDF)
        self.idf = {}
        for token, df_val in self.df.items():
            self.idf[token] = math.log(1.0 + (self.corpus_size / df_val))
            
        # Compute document vectors
        self.doc_vectors = []
        for doc_tokens in self.tokenized_docs:
            self.doc_vectors.append(self._vectorize(doc_tokens))
            
    def _vectorize(self, tokens):
        tf = Counter(tokens)
        total_tokens = len(tokens) if tokens else 1
        vector = {}
        for token in tokens:
            vector[token] = (tf[token] / total_tokens) * self.idf.get(token, 0.0)
        return vector
        
    def _cosine_similarity(self, vec1, vec2):
        intersect = set(vec1.keys()).intersection(set(vec2.keys()))
        if not intersect:
            return 0.0
            
        dot_product = sum(vec1[t] * vec2[t] for t in intersect)
        
        mag1 = math.sqrt(sum(v**2 for v in vec1.values()))
        mag2 = math.sqrt(sum(v**2 for v in vec2.values()))
        
        if mag1 == 0 or mag2 == 0:
            return 0.0
            
        return dot_product / (mag1 * mag2)
        
    def query(self, search_query):
        """
        Searches the FAQ documents for the closest match to the search_query.
        Returns (best_match_title, similarity_score).
        """
        query_tokens = list(tokenize_and_normalize(search_query))
        if not query_tokens:
            return None, 0.0
            
        # Vectorize query
        q_tf = Counter(query_tokens)
        q_total = len(query_tokens)
        query_vector = {}
        for token in query_tokens:
            if token in self.idf:
                query_vector[token] = (q_tf[token] / q_total) * self.idf[token]
                
        best_title = None
        best_score = 0.0
        
        for idx, doc_vector in enumerate(self.doc_vectors):
            score = self._cosine_similarity(query_vector, doc_vector)
            if score > best_score:
                best_score = score
                best_title = self.titles[idx]
                
        return best_title, best_score

# Initialize the Search Engine
search_engine = TFIDFSearch(FAQ_DATA)

def get_faq_response(user_query):
    """
    Retrieves the response to the user query using TF-IDF matching.
    """
    best_question, score = search_engine.query(user_query)
    
    # We require a threshold score to prevent matching irrelevant queries
    # Since cosine similarity can be low for short texts, 0.25 is a good baseline
    if best_question and score > 0.25:
        logger.info(f"TF-IDF matched query '{user_query}' to '{best_question}' (Score: {score:.3f})")
        return f"❓ **Question matched**: _{best_question}_\n\n{FAQ_DATA[best_question]}"
        
    # Standard fallback guide listing topics
    topics_list = "\n".join([f"• {q}" for q in list(FAQ_DATA.keys())[:5]])
    return (
        "🤖 **HR Assistant & Resume Helper**\n\n"
        "I couldn't match your question exactly. I can help answer common questions about resume formatting, ATS optimization, and interview preparation. \n\n"
        "👉 **Try asking about these topics**:\n"
        f"{topics_list}\n"
        "• _Or ask about behavioral interview tips, explaining gaps, salary queries, etc._"
    )

async def handle_faq_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Responds to general messages using the local TF-IDF search engine.
    """
    user_message = update.message.text
    response = get_faq_response(user_message)
    await update.message.reply_text(response, parse_mode="Markdown")
