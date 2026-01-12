"""
BUILD_LATEST_CLAUSES.PY
=======================

High-level flow (what this script does end-to-end):

Goal:
-----
Take the *latest* cleaned text file from Final_text_extractor.py
   → break it into medium-sized "clauses"
   → save them into latest_clauses.csv
      in the format the risk engine expects.

INPUT:
------
- A file in the current folder matching:
    extracted_text_*.txt
  Example:
    extracted_text_20251221_120716.txt

  These files are created by Final_text_extractor.py.

PROCESS:
--------
1) Find the most recent extracted_text_*.txt by modification time.
2) Load its full text into memory.
3) Normalize the text:
       - Replace newlines with spaces.
4) Split into candidate clauses:
       - Split on punctuation: ".", "?", "!"
         using a regex:  (?<=[.!?])\s+
       - Strip spaces.
       - Drop very short fragments (length < 20) to avoid junk.
5) Build a list of rows:
       clause_id, text, is_risky, risky_reason
   where:
       - clause_id = running ID starting from 1
       - text      = the clause string
       - is_risky and risky_reason are left empty
         (they will be filled later by risky_phrase_detector.py)

OUTPUT:
-------
- A single CSV file in the current folder:
      latest_clauses.csv

  This file is then used as input by:
      risky_phrase_detector.py
  which adds:
      model_is_risky, model_risk_reason, model_risk_score

HOW IT FITS INTO THE BIG PROJECT:
---------------------------------
Final_text_extractor.py  →  extracted_text_*.txt
build_latest_clauses.py  →  latest_clauses.csv
risky_phrase_detector.py →  latest_clauses_scored.csv
risk_summary.py          →  summary of risk
export_risky_clauses.py  →  risky_clauses_report.csv
"""
#Final_text_extractor.py ने बनवलेला latest extracted_text_*.txt घेऊन, punctuation वर text तोडून “medium clauses”
#बनवतो आणि latest_clauses.csv तयार करतो, ज्यावर पुढे risk engine scoring करतो.
# ------------------------- IMPORTS ------------------------- #

import csv   # For writing the clauses CSV file.
import glob  # For finding files that match a pattern (extracted_text_*.txt).
import os    # For filesystem info: modification time, path operations.
import re    # For splitting text into clauses using regex.
import sys   # For exiting the script with a proper message.

# ------------------------- CONSTANTS ----------------------- #

# This is the CSV that will be created by this script.
# Later scripts (risk scoring) consume this file.
OUTPUT_CSV = "latest_clauses.csv"


# ----------------------------------------------------------- #
# 1) FIND THE LATEST extracted_text_*.txt
# ----------------------------------------------------------- #

def find_latest_extracted_text() -> str:
    """
    Look in the CURRENT DIRECTORY for files named:
        extracted_text_*.txt

    Then:
      - If none found → print error and exit.
      - If found → pick the most recently modified file
                   and return its name.

    This makes the pipeline "automatic":
      you don't have to manually type the filename each time.
    """

    # glob.glob returns a list of filenames matching the pattern.
    files = glob.glob("extracted_text_*.txt")

    # If the list is empty, there's nothing to work on.
    if not files:
        print("[ERROR] No extracted_text_*.txt files found. "
              "Run Final_text_extractor.py first.")
        sys.exit(1)

    # max(..., key=os.path.getmtime) picks the file with the
    # largest (latest) modification time.
    latest = max(files, key=os.path.getmtime)

    # Log which file we have chosen.
    print(f"[INFO] Using latest extracted text file: {latest}")

    return latest


# ----------------------------------------------------------- #
# 2) LOAD TEXT FROM A FILE
# ----------------------------------------------------------- #

def load_text(path: str) -> str:
    """
    Read the entire content of a text file into a string.

    Parameters:
      path: path to the text file.

    Returns:
      A single big string containing the file contents.
    """
    # Open the file in read mode with UTF-8 encoding.
    with open(path, "r", encoding="utf-8") as f:
        # Read all text and return it.
        return f.read()


# ----------------------------------------------------------- #
# 3) SPLIT FULL TEXT INTO CLAUSES
# ----------------------------------------------------------- #

def split_into_clauses(text: str):
    """
    A simple "clause splitter" built on top of punctuation.

    Strategy:
      1) Replace all newlines with spaces so the text becomes
         one long string (otherwise splitting breaks in weird ways).
      2) Use a regex to split on sentence-ending punctuation:
            (?<=[.!?])\s+
         - `(?<=...)` = keep the punctuation in the previous token.
         - `\s+`      = one or more whitespace characters.
      3) For each piece:
           - strip leading/trailing spaces
           - ignore fragments shorter than 20 characters
             (these are usually "Note:", "etc.", or broken junk)
      4) Return a list of clauses we will feed to the CSV writer.

    This is intentionally simple.
    Your main legal clause segmentation happens earlier in
    Final_text_extractor.py; here we just ensure we have
    medium-sized text units for the risk engine.
    """

    # 1) Normalize newlines so they don't break sentences awkwardly.
    normalized = text.replace("\r\n", " ").replace("\n", " ")

    # 2) Split into raw pieces using regex:
    #    - look behind for ., !, or ?,
    #    - then split on the following whitespace.
    parts = re.split(r'(?<=[.!?])\s+', normalized)

    # This list will hold cleaned clauses.
    clauses = []

    # 3) Inspect each split piece and filter by length.
    for part in parts:
        # Remove extra spaces around the fragment.
        clause = part.strip()

        # Skip very tiny fragments; they are usually not meaningful.
        if len(clause) < 20:
            continue

        # Accept this fragment as a "clause".
        clauses.append(clause)

    return clauses


# ----------------------------------------------------------- #
# 4) WRITE CLAUSES TO CSV
# ----------------------------------------------------------- #

def write_clauses_csv(clauses, path: str):
    """
    Turn a list of clause strings into a CSV file
    with a fixed schema expected by the risk detector.

    CSV columns:
      clause_id, text, is_risky, risky_reason

    - clause_id     : integer ID starting at 1.
    - text          : the clause text itself.
    - is_risky      : left empty; risk engine fills later.
    - risky_reason  : left empty; risk engine fills later.
    """

    # The header row / column names for the CSV.
    fieldnames = ["clause_id", "text", "is_risky", "risky_reason"]

    # Open the output CSV file in write mode.
    with open(path, "w", encoding="utf-8", newline="") as f:
        # Create a DictWriter that writes rows as dictionaries.
        writer = csv.DictWriter(f, fieldnames=fieldnames)

        # Write the column headers once at the top.
        writer.writeheader()

        # Loop over clauses with a 1-based index (start=1).
        for idx, clause in enumerate(clauses, start=1):
            # For each clause, build a row dictionary matching the schema.
            writer.writerow(
                {
                    "clause_id": idx,   # Unique ID per clause.
                    "text": clause,     # Clause content.
                    "is_risky": "",     # Empty for now (to be filled later).
                    "risky_reason": "", # Empty for now.
                }
            )


# ----------------------------------------------------------- #
# 5) MAIN FUNCTION (SCRIPT ENTRY)
# ----------------------------------------------------------- #

def main():
    """
    Overall flow when you run:

        python3 build_latest_clauses.py

    Steps:
      1) Find the latest extracted_text_*.txt.
      2) Load its full text.
      3) Split into clauses.
      4) Write latest_clauses.csv.
    """

    # Step 1: pick the most recently generated extracted_text_*.txt.
    latest_txt = find_latest_extracted_text()

    # Step 2: read the entire file into memory.
    print(f"[INFO] Loading text from {latest_txt}...")
    text = load_text(latest_txt)

    # Step 3: split the text into clauses.
    print("[INFO] Splitting into clauses...")
    clauses = split_into_clauses(text)
    print(f"[INFO] Got {len(clauses)} clauses.")

    # Step 4: write these clauses into latest_clauses.csv.
    print(f"[INFO] Writing clauses CSV to {OUTPUT_CSV}...")
    write_clauses_csv(clauses, OUTPUT_CSV)

    print("[DONE] Clause CSV ready.")


# Standard Python pattern: run main() only if this file
# is executed directly (not imported as a module).
if __name__ == "__main__":
    main()