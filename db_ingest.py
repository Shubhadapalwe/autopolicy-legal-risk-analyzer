#!/usr/bin/env python3
"""
db_ingest.py
============

Usage (CLI examples)
--------------------
# Old style (defaults user_id = 1, no filename)
python3 db_ingest.py processed/poonawala_test

# New style (recommended – document belongs to this user_id, with real filename)
python3 db_ingest.py processed/poonawala_test 3 loan_test.pdf

This script expects ONE processed document folder like:

    processed/poonawala_test
    processed/sbi_terms_2025

Inside that folder we expect at least:
    - clauses_scored.csv  (one row per clause, with a "text" column)

We do NOT require that the original PDF / image is copied
into that processed folder.

It will:
    1) Read clauses_scored.csv.
    2) For each clause, run a simple rule-based risk engine.
    3) Count total & risky clauses.
    4) Compute risk% and grade (A/B/C/D).
    5) Insert into:
         - documents
         - clauses
"""

import sys
import os
import csv
import hashlib

import psycopg2

# ----------------- DB CONFIG ----------------- #

DB_NAME = os.getenv("AUTOPOLICY_DB_NAME", "autopolicy")
DB_USER = os.getenv("AUTOPOLICY_DB_USER", "postgres")
DB_PASSWORD = os.getenv("AUTOPOLICY_DB_PASSWORD")  # can be None
DB_HOST = os.getenv("AUTOPOLICY_DB_HOST", "localhost")
DB_PORT = int(os.getenv("AUTOPOLICY_DB_PORT", "5432"))

# Default user if none is passed on CLI (kept for backward compatibility)
DEFAULT_USER_ID = int(os.getenv("AUTOPOLICY_DEFAULT_USER_ID", "1"))

CLAUSES_FILE_NAME = "clauses_scored.csv"


# ======================================================
# Simple rule-based risk engine (same idea as app.py)
# ======================================================

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

    # loan / penalty style phrases (extra)
    ("penal interest", ["fees_charges"], 3),
    ("late payment charges", ["fees_charges"], 2),
    ("late payment fee", ["fees_charges"], 2),
    ("processing fee", ["fees_charges"], 1),
    ("we may change the interest rate", ["generic_risk"], 2),
]


def score_clause_simple(text: str):
    """
    Given a clause text, return:
        (is_risky: bool, reasons: list[str], score: int 1..3 or 0)

    Score is mapped as:
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

    # clamp score into 0..3
    if score >= 5:
        score = 3
    elif score >= 3:
        score = 2
    elif score > 0:
        score = 1

    is_risky = score > 0
    return is_risky, sorted(tags), score


def grade_from_percent(p: float) -> str:
    """
    Map risky% → grade A/B/C/D
    """
    if p <= 1.0:
        return "A"
    if p <= 5.0:
        return "B"
    if p <= 15.0:
        return "C"
    return "D"


# ----------------- DB HELPERS ----------------- #

def get_connection():
    params = {
        "dbname": DB_NAME,
        "user": DB_USER,
        "host": DB_HOST,
        "port": DB_PORT,
    }
    if DB_PASSWORD:
        params["password"] = DB_PASSWORD
    return psycopg2.connect(**params)


def virtual_fingerprint(folder: str, logical_filename: str, user_id: int) -> str:
    """
    Create a fingerprint even if there is no original PDF in the folder.
    We just hash (user_id + folder path + logical filename).
    """
    h = hashlib.sha256()
    key = f"user={user_id}::folder={os.path.normpath(folder)}::file={logical_filename}"
    h.update(key.encode("utf-8"))
    return h.hexdigest()


def detect_source_type_from_name(name: str) -> str:
    name = name.lower()
    if name.endswith(".pdf"):
        return "pdf"
    if name.endswith((".png", ".jpg", ".jpeg")):
        return "ocr_image"
    return "unknown"


def read_clauses_csv(clauses_path: str):
    with open(clauses_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


# ----------------- CORE LOGIC ----------------- #

def insert_document_and_clauses(folder: str, user_id: int, original_filename_cli: str | None):
    """
    Insert one document (and its clauses) for a given user_id.
    We recompute risk for each clause here.
    We DO NOT require a PDF/image in the folder.
    """

    folder_norm = os.path.normpath(folder)

    # if Flask passed a real filename, use that; otherwise fall back
    if original_filename_cli:
        original_filename = original_filename_cli
    else:
        base_name = os.path.basename(folder_norm) or "document"
        original_filename = base_name + ".pdf"

    stored_path = folder_norm
    fingerprint = virtual_fingerprint(folder_norm, original_filename, user_id)
    source_type = detect_source_type_from_name(original_filename)

    # 3) Read clauses_scored.csv
    clauses_path = os.path.join(folder_norm, CLAUSES_FILE_NAME)
    if not os.path.exists(clauses_path):
        raise RuntimeError(f"Could not find {CLAUSES_FILE_NAME} in {folder_norm}")
    clauses_rows = read_clauses_csv(clauses_path)

    # 4) Recompute risk for each clause
    total_clauses = len(clauses_rows)
    risky_clauses = 0

    for row in clauses_rows:
        text = row.get("text") or ""
        is_risky, reasons, score = score_clause_simple(text)

        row["model_is_risky"] = "TRUE" if is_risky else "FALSE"
        row["model_risk_reason"] = ", ".join(reasons) if reasons else ""
        row["model_risk_score"] = str(score if score is not None else "")

        if is_risky:
            risky_clauses += 1

    risky_percent = (risky_clauses * 100.0 / total_clauses) if total_clauses > 0 else 0.0
    overall_rating = grade_from_percent(risky_percent)

    conn = get_connection()
    conn.autocommit = False

    try:
        cur = conn.cursor()

        # 5) Insert into documents (no dedup – every upload = one row)
        cur.execute(
            """
            INSERT INTO documents
                (user_id,
                 original_filename,
                 stored_path,
                 uploaded_at,
                 processed_at,
                 total_clauses,
                 risky_clauses,
                 overall_rating,
                 source_type,
                 fingerprint)
            VALUES
                (%s, %s, %s,
                 NOW(), NOW(),
                 %s, %s,
                 %s,
                 %s, %s)
            RETURNING id
            """,
            (
                user_id,
                original_filename,
                stored_path,
                total_clauses,
                risky_clauses,
                overall_rating,
                source_type,
                fingerprint,
            ),
        )
        document_id = cur.fetchone()[0]
        print(f"[INFO] Inserted document id={document_id} for user_id={user_id}")

        # 6) Insert clauses
        for row in clauses_rows:
            clause_number_str = row.get("clause_id") or "0"
            try:
                clause_number = int(clause_number_str)
            except ValueError:
                clause_number = 0

            text = row.get("text") or ""

            model_is_risky = (row.get("model_is_risky") or "").strip().upper() == "TRUE"
            model_risk_reason = row.get("model_risk_reason") or None

            score_str = row.get("model_risk_score")
            model_risk_score = None
            if score_str not in (None, ""):
                try:
                    model_risk_score = int(float(score_str))
                except ValueError:
                    model_risk_score = None

            cur.execute(
                """
                INSERT INTO clauses
                    (document_id,
                     clause_number,
                     text,
                     model_is_risky,
                     model_risk_reason,
                     model_risk_score)
                VALUES
                    (%s, %s, %s,
                     %s, %s, %s)
                """,
                (
                    document_id,
                    clause_number,
                    text,
                    model_is_risky,
                    model_risk_reason,
                    model_risk_score,
                ),
            )

        conn.commit()
        cur.close()
        conn.close()
        print(f"[DONE] Inserted {len(clauses_rows)} clauses for document id={document_id}")
        print(f"[DONE] total_clauses={total_clauses}, risky_clauses={risky_clauses}, "
              f"risky_percent={risky_percent:.2f}, grade={overall_rating}")

    except Exception as e:
        conn.rollback()
        conn.close()
        print(f"[ERROR] db_ingest failed: {e}")
        sys.exit(1)


# ----------------- MAIN ----------------- #

def main():
    """
    CLI entrypoint.

    Arguments:
        1) processed_folder (required)
        2) user_id (optional, defaults to DEFAULT_USER_ID)
        3) original_filename (optional – recommended when called from Flask)
    """
    if len(sys.argv) < 2 or len(sys.argv) > 4:
        print("Usage:")
        print("  python3 db_ingest.py <processed_folder> [user_id] [original_filename]")
        sys.exit(1)

    folder = sys.argv[1]

    if len(sys.argv) >= 3:
        try:
            user_id = int(sys.argv[2])
        except ValueError:
            print("[ERROR] user_id must be an integer.")
            sys.exit(1)
    else:
        user_id = DEFAULT_USER_ID

    original_filename = sys.argv[3] if len(sys.argv) == 4 else None

    if not os.path.isdir(folder):
        print(f"[ERROR] {folder} is not a directory")
        sys.exit(1)

    print(f"[INFO] Ingesting folder={folder} for user_id={user_id}, filename={original_filename}")
    insert_document_and_clauses(folder, user_id, original_filename)


if __name__ == "__main__":
    main()