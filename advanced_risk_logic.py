#!/usr/bin/env python3
"""
advanced_risk_logic.py  (NEW – advanced brain for risk detection)

High-level flow (end to end):

1. Input  : A BIG block of legal text (from pipeline, web app, or Chrome extension).
2. Split  : Break it into small clauses (by lines / sentences).
3. Detect : For each clause, run your existing rule engine:
           - Uses legal vocab, templates, synonyms, generic risky phrases.
4. Score  : Convert tags into a weighted score (data_sharing, account_closure, etc.).
5. Mitigate:
           - If clause contains protective phrases like "subject to applicable law",
             reduce risk score (mitigation factor).
6. Severity:
           - Convert final score into LOW / MEDIUM / HIGH severity for each clause.
7. Explain:
           - Build a simple explanation string in plain English:
             why it’s risky + whether any protection is present.
8. Summarize:
           - Count how many clauses are risky.
           - Compute overall risky percentage.
           - Assign overall rating A/B/C/D.
           - Aggregate risk counts per risk type.
9. Output:
           - A JSON-style dict with:
               total_clauses
               risky_clauses [with severity + explanation]
               risky_percent
               overall_rating
               risk_breakdown
   This is directly used by the Flask API and Chrome extension.
"""
#Existing rule engine → tags देतो; हा script त्या tags वरून
#weighted scoring + mitigation + severity + explanation बनवून overall report JSON मध्ये देतो.
import json
import re
from typing import List, Dict, Any

from risky_phrase_detector import (
    load_vocab,
    load_templates,
    load_synonyms,
    load_generic_phrases,
    detect_risks_for_sentence,
)

# ------------------------------------------------------------
#  CONFIG: tag weights + mitigation phrases
# ------------------------------------------------------------

# How strong each risk tag is (higher = more severe)
TAG_WEIGHTS = {
    "account_closure": 4,
    "data_sharing": 3,
    "fees_charges": 2,
    "generic_risk": 1,
}

# Phrases that REDUCE risk (they show some protection / limitation)
PROTECTION_PHRASES = [
    "subject to applicable law",
    "in accordance with applicable law",
    "with your consent",
    "with prior notice",
    "upon prior written notice",
    "with reasonable notice",
    "only with your explicit consent",
]

# Multiplier applied when protection is found
MITIGATION_FACTOR = 0.7  # e.g. score 5 → 3.5


# ------------------------------------------------------------
#  Helpers: severity + explanation
# ------------------------------------------------------------
def _compute_severity(score: float) -> str:
    """
    Convert numeric score into LOW / MEDIUM / HIGH.
    """
    if score <= 2:
        return "LOW"
    elif score <= 5:
        return "MEDIUM"
    else:
        return "HIGH"


def _build_explanation(tags: List[str], mitigations: List[str]) -> str:
    """
    Human explanation in simple words based on risk tags + protection.
    """
    if not tags:
        return "No specific risky legal pattern was detected in this clause."

    pieces = []

    if "data_sharing" in tags:
        pieces.append(
            "This clause appears to allow your data to be shared with third parties, "
            "which can impact your privacy."
        )
    if "account_closure" in tags:
        pieces.append(
            "This clause gives the service the power to suspend or close your account, "
            "possibly with limited notice."
        )
    if "fees_charges" in tags:
        pieces.append(
            "This clause may add extra fees, penalties, or hidden charges to what you pay."
        )
    if "generic_risk" in tags:
        pieces.append(
            "This clause uses broad or open-ended language that can create uncertainty or extra risk."
        )

    if mitigations:
        pieces.append(
            "However, there is also some protective language that reduces the risk: "
            + "; ".join(mitigations)
            + "."
        )
    else:
        pieces.append(
            "No strong protective phrases were found, so you should read this clause carefully."
        )

    return " ".join(pieces)


# ------------------------------------------------------------
#  Lazy loading of vocab/templates/synonyms/generic phrases
# ------------------------------------------------------------
def _load_resources():
    vocab = load_vocab()
    templates = load_templates()
    variant_map = load_synonyms()
    generic_phrases = load_generic_phrases()
    return vocab, templates, variant_map, generic_phrases


_vocab = None
_templates = None
_variant_map = None
_generic_phrases = None


def _ensure_loaded():
    """Load resources once and reuse for all calls."""
    global _vocab, _templates, _variant_map, _generic_phrases
    if _vocab is None:
        _vocab, _templates, _variant_map, _generic_phrases = _load_resources()


# ------------------------------------------------------------
#  Clause splitting
# ------------------------------------------------------------
def _split_into_clauses(text: str) -> List[str]:
    """
    Very simple splitter:
      1) If there are multiple non-empty lines, use each line as a clause.
      2) Otherwise, split on . ? ! like earlier.
    """
    if not text:
        return []

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) > 1:
        return lines

    parts = re.split(r'(?<=[.!?])\s+', text)
    return [p.strip() for p in parts if p.strip()]


# ------------------------------------------------------------
#  Single clause analysis
# ------------------------------------------------------------
def analyze_single_clause(clause_text: str, idx: int) -> Dict[str, Any]:
    """
    Analyze ONE clause:
      - get risk tags
      - calculate weighted score
      - apply mitigation
      - compute severity
      - build explanation
    """
    _ensure_loaded()

    # 1) tags from your existing engine
    tags = detect_risks_for_sentence(
        clause_text,
        _vocab,
        _templates,
        _variant_map,
        _generic_phrases,
    )

    # 2) weighted score
    base_score = 0
    for t in tags:
        base_score += TAG_WEIGHTS.get(t, 1)

    # 3) find mitigation phrases in the text
    clause_lower = clause_text.lower()
    mitigations_found = []
    for phrase in PROTECTION_PHRASES:
        if phrase in clause_lower:
            mitigations_found.append(phrase)

    # 4) apply mitigation if any
    final_score = float(base_score)
    if mitigations_found and final_score > 0:
        final_score *= MITIGATION_FACTOR

    severity = _compute_severity(final_score)
    explanation = _build_explanation(tags, mitigations_found)
    is_risky = bool(tags)

    return {
        "clause_number": idx,
        "text": clause_text,
        "tags": tags,
        "is_risky": is_risky,
        "base_score": base_score,
        "final_score": round(final_score, 2),
        "severity": severity,
        "mitigations_found": mitigations_found,
        "explanation": explanation,
    }


# ------------------------------------------------------------
#  Analyze full text block (for API / extension)
# ------------------------------------------------------------
def analyze_text_block(text: str) -> Dict[str, Any]:
    """
    Main function used by Flask API and (indirectly) by the extension.

    Input : raw text
    Output: dict with
        - total_clauses
        - risky_clauses [each has severity + explanation]
        - risky_percent
        - overall_rating (A–D)
        - risk_breakdown {tag -> count}
    """
    clauses = _split_into_clauses(text)
    total_clauses = len(clauses)

    results = []
    risk_breakdown: Dict[str, int] = {}
    risky_count = 0

    for idx, clause_text in enumerate(clauses, start=1):
        info = analyze_single_clause(clause_text, idx)
        if info["is_risky"]:
            risky_count += 1
            results.append(info)
            for t in info["tags"]:
                risk_breakdown[t] = risk_breakdown.get(t, 0) + 1

    risky_percent = (risky_count * 100.0 / total_clauses) if total_clauses else 0.0

    # same A/B/C/D scale as earlier
    if risky_percent <= 5:
        overall_rating = "A"
    elif risky_percent <= 15:
        overall_rating = "B"
    elif risky_percent <= 30:
        overall_rating = "C"
    else:
        overall_rating = "D"

    return {
        "total_clauses": total_clauses,
        "risky_clauses": [
            {
                "clause_number": r["clause_number"],
                "text": r["text"],
                "reasons": r["tags"],
                "score": r["final_score"],
                "severity": r["severity"],
                "explanation": r["explanation"],
                "mitigations_found": r["mitigations_found"],
            }
            for r in results
        ],
        "risky_percent": round(risky_percent, 2),
        "overall_rating": overall_rating,
        "risk_breakdown": risk_breakdown,
    }


# ------------------------------------------------------------
#  Quick CLI demo (optional)
# ------------------------------------------------------------
if __name__ == "__main__":
    demo_text = (
        "We may share your personal data with third parties at any time, "
        "and we may close your account without prior notice. "
        "However, any such action will be taken in accordance with applicable law."
    )
    out = analyze_text_block(demo_text)
    print(json.dumps(out, indent=2))