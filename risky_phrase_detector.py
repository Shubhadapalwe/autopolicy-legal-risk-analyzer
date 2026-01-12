# risky_phrase_detector.py
# Simple, self-contained risk detector used by:
# - advanced_risk_engine.py
# - db_ingest.py
# - (optionally) the Flask app / extension

import re
from typing import List, Tuple

# --- Clause splitting (can be reused by other scripts) ---

CLAUSE_SPLIT_REGEX = re.compile(r"(?<=[.!?;])\s+|\n+")


def split_into_clauses(text: str) -> List[str]:
    """
    Split raw text into rough 'clauses' using punctuation and newlines.
    """
    parts = CLAUSE_SPLIT_REGEX.split(text or "")
    return [p.strip() for p in parts if p and p.strip()]


# --- Rule-based risky phrase patterns ---

# phrase, [tags], base_score
RISKY_PATTERNS: List[Tuple[str, list, int]] = [
    # data sharing / privacy
    ("may share your personal data", ["data_sharing"], 3),
    ("may share your information with third parties", ["data_sharing"], 3),
    ("may disclose your personal information", ["data_sharing"], 3),
    ("may disclose your information", ["data_sharing"], 3),
    ("may share your data", ["data_sharing"], 3),
    ("may use your personal data for marketing", ["data_sharing"], 3),

    # account closure / suspension
    ("may terminate your account", ["account_closure"], 3),
    ("may suspend your account", ["account_closure"], 2),
    ("may close your account", ["account_closure"], 2),
    ("may restrict your access", ["account_closure"], 2),

    # indemnity
    ("you agree to indemnify", ["indemnity"], 3),
    ("you agree to hold us harmless", ["indemnity"], 3),

    # generic broad risk language
    ("at our sole discretion", ["generic_risk"], 2),
    ("at its sole discretion", ["generic_risk"], 2),
    ("without prior notice", ["generic_risk"], 1),
    ("without any prior notice", ["generic_risk"], 1),
    ("we are not liable for", ["generic_risk"], 2),
    ("no liability for", ["generic_risk"], 2),
    ("we are not responsible for", ["generic_risk"], 2),

    # fees / charges
    ("reserves the right to change its fee policy", ["fees_charges"], 2),
    ("introduce fees for existing services", ["fees_charges"], 2),
    ("all sales are final", ["fees_charges"], 2),
    ("non-refundable", ["fees_charges"], 2),
]


def score_sentence_simple(text: str):
    """
    Old API expected by advanced_risk_engine.py / db_ingest.py.

    Returns:
        (is_risky: bool, reasons: List[str], score: int)

        score is a small 0/1/2/3 'grade':
        - 0 = not risky
        - 1 = mildly risky
        - 2 = medium
        - 3 = high
    """
    if not text:
        return False, [], 0

    t = text.lower()
    tags = set()
    score = 0

    for phrase, phrase_tags, base_score in RISKY_PATTERNS:
        if phrase in t:
            for tg in phrase_tags:
                tags.add(tg)
            score += base_score

    # Map raw score → 0/1/2/3
    if score >= 5:
        score = 3
    elif score >= 3:
        score = 2
    elif score > 0:
        score = 1
    else:
        score = 0

    is_risky = score > 0
    return is_risky, sorted(tags), score