#!/usr/bin/env python3
"""
advanced_risk_engine.py
=======================

Usage:
    python3 advanced_risk_engine.py <input_pdf_or_image_or_txt>

Given a legal document (PDF, PNG/JPG screenshot, or plain text file), this
script:

  1. Extracts text.
  2. Splits it into clauses (simple sentence-like chunks).
  3. Runs a rule-based risk engine on each clause.
  4. Writes processed/<base_name>/clauses_scored.csv with columns:
        clause_id, text, model_is_risky, model_risk_reason, model_risk_score

db_ingest.py then picks up that CSV and inserts rows into PostgreSQL.
"""

import sys
import os
import re
import csv
from pathlib import Path

# -----------------------------
# Clause splitting
# -----------------------------

# Split on ., !, ?, ; followed by whitespace OR on newlines
CLAUSE_SPLIT_REGEX = re.compile(r"(?<=[.!?;])\s+|\n+")

def split_into_clauses(text: str):
    parts = CLAUSE_SPLIT_REGEX.split(text)
    return [p.strip() for p in parts if p and p.strip()]


# -----------------------------
# Risk engine (same logic as app/db_ingest)
# -----------------------------

RISKY_PATTERNS = [
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

    # extra loan / penalty terms
    ("penal interest", ["fees_charges"], 3),
    ("late payment charges", ["fees_charges"], 2),
    ("late payment fee", ["fees_charges"], 2),
    ("processing fee", ["fees_charges"], 1),
    ("we may change the interest rate", ["generic_risk"], 2),
]

def score_clause_simple(text: str):
    """
    Given clause text, return:
        (is_risky: bool, reasons: list[str], score: int 0..3)

    Score mapping:
        0 -> not risky
        1 -> low (yellow)
        2 -> medium (orange)
        3 -> high (red)
    """
    t = (text or "").lower()
    tags = set()
    score = 0

    for phrase, phrase_tags, base_score in RISKY_PATTERNS:
        if phrase in t:
            for tg in phrase_tags:
                tags.add(tg)
            score += base_score

    # clamp into 0..3
    if score >= 5:
        score = 3
    elif score >= 3:
        score = 2
    elif score > 0:
        score = 1

    is_risky = score > 0
    return is_risky, sorted(tags), score


# -----------------------------
# Text extraction helpers
# -----------------------------

def extract_text_from_pdf(path: str) -> str:
    """
    Try pdfplumber first, then PyPDF2 as fallback.
    """
    try:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                txt = page.extract_text() or ""
                text_parts.append(txt)
        text = "\n".join(text_parts)
        if text.strip():
            return text
    except Exception as e:
        print("[INFO] pdfplumber failed or not available:", e, file=sys.stderr)

    # Fallback: PyPDF2
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(path)
        pages = []
        for page in reader.pages:
            txt = page.extract_text() or ""
            pages.append(txt)
        return "\n".join(pages)
    except Exception as e:
        print("[ERROR] Could not read PDF with PyPDF2:", e, file=sys.stderr)
        sys.exit(1)


def extract_text_from_image(path: str) -> str:
    """
    OCR an image (PNG/JPG/JPEG) using pytesseract.
    """
    try:
        from PIL import Image
        import pytesseract
    except Exception as e:
        print("[ERROR] pytesseract or Pillow not available for OCR:", e, file=sys.stderr)
        sys.exit(1)

    img = Image.open(path)
    txt = pytesseract.image_to_string(img)
    return txt or ""


def extract_text(path: str) -> str:
    """
    Dispatcher based on file extension.
    Allows .txt as a simple debugging path.
    """
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        return extract_text_from_pdf(path)
    if ext in (".png", ".jpg", ".jpeg"):
        return extract_text_from_image(path)
    # simple text file for debugging
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# -----------------------------
# Main processing
# -----------------------------

def run_pipeline(input_path: str):
    # Basic checks
    if not os.path.exists(input_path):
        print(f"[ERROR] File not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    processed_dir = os.path.join("processed", base_name)
    os.makedirs(processed_dir, exist_ok=True)

    print(f"[INFO] Reading file: {input_path}")
    text = extract_text(input_path)

    # Optional: save extracted raw text for debugging
    extracted_path = os.path.join(processed_dir, "extracted_text.txt")
    with open(extracted_path, "w", encoding="utf-8") as f:
        f.write(text or "")

    clauses = split_into_clauses(text)
    print(f"[INFO] Split into {len(clauses)} clauses")

    # Prepare CSV path
    csv_path = os.path.join(processed_dir, "clauses_scored.csv")
    fieldnames = ["clause_id", "text", "model_is_risky", "model_risk_reason", "model_risk_score"]

    risky_count = 0

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for idx, clause in enumerate(clauses, start=1):
            is_risky, reasons, score = score_clause_simple(clause)
            if is_risky:
                risky_count += 1

            writer.writerow({
                "clause_id": idx,
                "text": clause,
                "model_is_risky": "TRUE" if is_risky else "FALSE",
                "model_risk_reason": ", ".join(reasons),
                "model_risk_score": score if score is not None else "",
            })

    print(f"[DONE] Wrote {len(clauses)} clauses to {csv_path}")
    print(f"[DONE] Risky clauses: {risky_count}")


# -----------------------------
# Entry point
# -----------------------------

def main():
    if len(sys.argv) != 2:
        print("Usage: python3 advanced_risk_engine.py <input_pdf_or_image_or_txt>")
        sys.exit(1)

    input_path = sys.argv[1]
    run_pipeline(input_path)


if __name__ == "__main__":
    main()