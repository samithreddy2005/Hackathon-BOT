"""The offline HR knowledge base.

Answers are stored as Telegram-flavoured HTML (see
:mod:`ats_bot.utils.telegram_html`) and are sent verbatim, so any ``<``, ``>`` or
``&`` in the prose must already be escaped here.

``tags`` exist because a user rarely phrases a question the way the entry titles
it. They are indexed alongside the question text, which is what lets "can I use a
two column layout" reach the tables-and-graphics entry.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["FAQ_ENTRIES", "FaqEntry"]


@dataclass(frozen=True, slots=True)
class FaqEntry:
    """One question/answer pair in the offline knowledge base."""

    question: str
    answer: str
    tags: tuple[str, ...] = field(default=())


FAQ_ENTRIES: tuple[FaqEntry, ...] = (
    FaqEntry(
        question="How do I write a professional summary?",
        tags=("summary", "profile", "objective", "opening", "about me", "headline"),
        answer=(
            "<b>Writing a professional summary</b>\n\n"
            "• <b>Three or four sentences, no more.</b> It sits above the fold; anything "
            "longer gets skipped.\n"
            "• <b>Lead with the facts:</b> your title, years of experience, and domain.\n"
            '• <b>Name two results</b>, with numbers. "Cut onboarding time 40%" beats '
            '"results-driven professional".\n'
            '• <b>Mirror the posting.</b> If it says "platform engineer", do not call '
            'yourself a "DevOps specialist".\n'
            "• <b>Cut the adjectives.</b> Hard-working, passionate, and detail-oriented "
            "carry no information — every applicant claims them."
        ),
    ),
    FaqEntry(
        question="Which sections should an ATS-friendly resume contain?",
        tags=("sections", "structure", "layout", "order", "headings", "what to include"),
        answer=(
            "<b>Standard resume sections, in order</b>\n\n"
            "1. <b>Contact details</b> — name, phone, email, city, LinkedIn. Plain text, "
            "in the body, never in a header image.\n"
            "2. <b>Professional summary</b> — 3-4 lines.\n"
            "3. <b>Skills</b> — the block keyword scanners read first.\n"
            "4. <b>Work experience</b> — reverse chronological.\n"
            "5. <b>Education</b> — degree, institution, year.\n"
            "6. <b>Optional:</b> Projects, Certifications, Languages, Publications.\n\n"
            'Use those exact heading words. A parser looking for "Experience" will not '
            'recognise "Where I\'ve Made An Impact".'
        ),
    ),
    FaqEntry(
        question="How do I improve my keyword match score?",
        tags=("keywords", "match", "score", "ats score", "optimize", "tailoring", "skills"),
        answer=(
            "<b>Raising your keyword match</b>\n\n"
            "1. <b>Mine the posting.</b> Anything repeated, or listed under "
            '"requirements", is what the filter looks for.\n'
            '2. <b>Use their exact words.</b> A scanner matching on "Kubernetes" does '
            'not credit "container orchestration".\n'
            '3. <b>Spell out both forms</b> the first time: "Search Engine Optimization '
            '(SEO)". Different systems index different halves.\n'
            "4. <b>Put keywords inside achievement bullets</b>, not only in a list. "
            "Recruiters read the evidence; a bare list looks padded.\n"
            "5. <b>Never stuff.</b> White text and hidden keyword blocks are detected and "
            "get the application discarded.\n\n"
            "Claim only what is true — every keyword is an interview question waiting."
        ),
    ),
    FaqEntry(
        question="How should I format my work experience section?",
        tags=("work experience", "employment", "bullets", "job history", "achievements"),
        answer=(
            "<b>Formatting work experience</b>\n\n"
            "• <b>Reverse chronological</b>, most recent first.\n"
            "• <b>One header line per role:</b> Job Title — Company — Location — "
            "Mon YYYY to Mon YYYY.\n"
            "• <b>Three to five bullets</b> for recent roles, one or two for older ones.\n"
            "• <b>Open with a verb:</b> Led, Built, Migrated, Reduced, Negotiated.\n"
            "• <b>Use the pattern</b> <i>action → method → measurable result</i>: "
            '"Cut checkout latency 40% by adding a Redis read cache."\n'
            '• <b>Describe outcomes, not duties.</b> "Responsible for reporting" says '
            'nothing; "Automated weekly reporting, saving 6 hours a week" says everything.'
        ),
    ),
    FaqEntry(
        question="Can I use tables, columns, or graphics in my resume?",
        tags=(
            "tables",
            "columns",
            "graphics",
            "icons",
            "template",
            "design",
            "two column",
            "charts",
            "photo",
            "picture",
            "creative",
        ),
        answer=(
            "<b>Tables, columns, and graphics</b>\n\n"
            "• <b>Avoid multi-column layouts.</b> Many parsers read straight across the "
            "page, interleaving your two columns into nonsense.\n"
            "• <b>Avoid tables and text boxes</b> for content that matters. Cell contents "
            "are frequently dropped entirely.\n"
            "• <b>No icons, skill bars, or charts.</b> A parser sees an image and reads "
            "nothing. A five-star rating also tells a recruiter less than one project would.\n"
            "• <b>No photo</b> unless the country you are applying in expects one — in the "
            "US and UK it invites bias complaints and is routinely removed.\n"
            "• <b>Safe recipe:</b> single column, standard headings, 1 inch margins, "
            "text bullets, 10-12pt body text."
        ),
    ),
    FaqEntry(
        question="How do I answer 'Tell me about yourself'?",
        tags=("tell me about yourself", "interview", "introduction", "opening question"),
        answer=(
            '<b>"Tell me about yourself"</b>\n\n'
            "Use <b>Present → Past → Future</b>, in about 90 seconds:\n\n"
            "• <b>Present:</b> your current role, its scope, and one recent win.\n"
            "• <b>Past:</b> the two steps that got you here — only the relevant ones.\n"
            "• <b>Future:</b> why this role, at this company, is the logical next step.\n\n"
            "It is a question about fit, not biography. Skip childhood, hobbies, and your "
            "full job history, and finish by handing the conversation back."
        ),
    ),
    FaqEntry(
        question="How do I explain a career gap?",
        tags=(
            "career gap",
            "employment gap",
            "resume gap",
            "gap year",
            "unemployed",
            "out of work",
            "not working",
            "career break",
            "time off",
            "sabbatical",
            "redundancy",
            "laid off",
            "explain",
        ),
        answer=(
            "<b>Explaining a career gap</b>\n\n"
            "• <b>Name it in one sentence</b> and move on. Caregiving, health, study, "
            "redundancy, relocation — all are ordinary. Over-explaining signals shame.\n"
            "• <b>Show what you did with it:</b> a certification, freelance work, "
            "volunteering, a course.\n"
            "• <b>Put years, not months, on older roles</b> if a short gap is the only "
            "issue — but never move dates to hide one. Background checks find it.\n"
            "• <b>Pivot forward:</b> \"That's behind me, and here's why this role is what "
            'I want next."\n\n'
            "Gaps are common. Evasiveness about them is the actual red flag."
        ),
    ),
    FaqEntry(
        question="What is the STAR method?",
        tags=("star", "behavioral", "situation task action result", "tell me about a time"),
        answer=(
            "<b>The STAR method</b>\n\n"
            'The structure for any "tell me about a time when…" question:\n\n'
            "• <b>Situation</b> — the context, in one or two sentences.\n"
            "• <b>Task</b> — what you specifically had to achieve.\n"
            '• <b>Action</b> — what <i>you</i> did. Say "I", not "we"; the interviewer '
            "is assessing you, not your team.\n"
            "• <b>Result</b> — the outcome, quantified, plus what you learned.\n\n"
            "Spend most of the time on Action and Result. Prepare five stories covering "
            "conflict, failure, leadership, deadline pressure, and influence without "
            "authority — they cover most of what gets asked."
        ),
    ),
    FaqEntry(
        question="How do I answer 'What is your greatest weakness'?",
        tags=("weakness", "greatest weakness", "flaw", "interview question"),
        answer=(
            '<b>"What is your greatest weakness?"</b>\n\n'
            "• <b>Pick something real but survivable</b> — delegating, public speaking, "
            "saying no to scope creep, a tool you are still learning.\n"
            "• <b>Show the correction.</b> The answer is really about self-awareness: name "
            "the weakness, then the concrete step you took and how it is going.\n"
            '• <b>Avoid the humblebrag.</b> "I\'m a perfectionist" and "I work too hard" '
            "are heard as evasion by every interviewer alive.\n"
            "• <b>Avoid disqualifiers</b> — never name something core to the job.\n\n"
            'Example: "I used to hold onto work I should have delegated. I now assign an '
            'owner for every task at sprint planning, and my team ships more because of it."'
        ),
    ),
    FaqEntry(
        question="What formatting makes a resume ATS-friendly?",
        tags=("formatting", "font", "file format", "pdf or docx", "margins", "file name", "length"),
        answer=(
            "<b>ATS-friendly formatting</b>\n\n"
            "• <b>File type:</b> PDF is safe with modern systems; DOCX is safest with old "
            "ones. Follow the posting if it asks for one. Never send .pages or a scan.\n"
            "• <b>File name:</b> <code>Firstname_Lastname_Resume.pdf</code>.\n"
            "• <b>Font:</b> anything standard — Arial, Calibri, Helvetica, Garamond, "
            "Times New Roman. 10-12pt body, 14-16pt headings.\n"
            "• <b>Margins:</b> at least 0.7 inch. Nothing in the page header or footer.\n"
            "• <b>Bullets:</b> real bullet characters, not images or wingdings.\n"
            "• <b>Length:</b> one page under 10 years' experience, two pages above. "
            "Three only for academic CVs.\n"
            "• <b>Dates:</b> one format throughout — Mon YYYY."
        ),
    ),
    FaqEntry(
        question="How do I handle salary expectations?",
        tags=("salary", "compensation", "pay", "negotiation", "expectations", "offer"),
        answer=(
            "<b>Salary questions</b>\n\n"
            "• <b>Research first</b> — levels.fyi, Glassdoor, Payscale, and any local pay "
            "transparency data for the role, level, and city.\n"
            "• <b>Deflect early, commit late.</b> Before an offer: \"I'd rather understand "
            'the scope first — what range is budgeted for this role?"\n'
            "• <b>If pressed, give a range</b> whose bottom you would genuinely accept, "
            "and anchor it at your researched market rate or slightly above.\n"
            "• <b>Never state your current salary</b> where the law lets you decline; it "
            "anchors the offer to your past, not the role's value.\n"
            "• <b>Negotiate the package</b> — sign-on, equity, leave, and remote days all "
            "move when base salary will not."
        ),
    ),
    FaqEntry(
        question="How do I write a cover letter?",
        tags=("cover letter", "covering letter", "motivation letter", "application letter"),
        answer=(
            "<b>Cover letter structure</b>\n\n"
            "• <b>Header</b> — the same contact block as your resume.\n"
            '• <b>Address a person</b> where you can find one; "Dear Hiring Team" '
            'otherwise. Never "To Whom It May Concern".\n'
            "• <b>Opening:</b> the role, and one sentence on the single most relevant "
            'thing you have done. No "I am writing to apply for…".\n'
            "• <b>Middle:</b> two short paragraphs, each taking one requirement from the "
            "posting and giving concrete evidence you meet it.\n"
            "• <b>Close:</b> why <i>this</i> company, and a clear ask for a conversation.\n\n"
            "Half a page. It should add evidence the resume cannot carry — not restate it."
        ),
    ),
    FaqEntry(
        question="How do I follow up after applying or interviewing?",
        tags=("follow up", "thank you note", "after interview", "no response", "ghosted"),
        answer=(
            "<b>Following up</b>\n\n"
            "• <b>After an interview:</b> email within 24 hours. Three or four sentences — "
            "thank them, reference one specific thing discussed, restate your interest.\n"
            "• <b>After applying:</b> wait a week, then message the hiring manager or "
            "recruiter directly on LinkedIn. Short, specific, no pressure.\n"
            "• <b>Chase at most twice</b>, a week or two apart, then let it go.\n"
            "• <b>If they told you a date, wait for it</b> to pass before following up.\n\n"
            "Silence is usually process backlog, not rejection — but never stop applying "
            "while you wait on one company."
        ),
    ),
    FaqEntry(
        question="How long should my resume be?",
        tags=("length", "how long", "one page", "two pages", "number of pages"),
        answer=(
            "<b>Resume length</b>\n\n"
            "• <b>One page</b> — students, career changers, and anyone under roughly ten "
            "years of experience.\n"
            "• <b>Two pages</b> — ten or more years, or a role that genuinely needs the "
            "detail. Put everything that decides the interview on page one.\n"
            "• <b>Three or more</b> — academic CVs and senior research roles only.\n\n"
            "Cut by depth, not by shrinking the font: drop roles over 15 years old, trim "
            "old positions to one line, and delete anything that does not support this "
            "specific application. 8pt text to force one page fools nobody."
        ),
    ),
)
