#!/usr/bin/env python3
"""
finalize_run.py
================

HIGH-LEVEL IDEA
---------------
This script **takes one legal document (PDF)** that you've just processed
through your pipeline and neatly organizes all related files into a
**single per-document folder** inside `processed/`.

INPUT (from user):
------------------
You call it like this:

    python3 finalize_run.py <pdf_file_name_or_path>

Examples:
    python3 finalize_run.py poonawala_test.pdf
    python3 finalize_run.py processed/poonawala_test/poonawala_test.pdf

It expects that:
  - Your main pipeline (`Final_text_extractor.py`, `build_latest_clauses.py`,
    `risky_phrase_detector.py`, `risk_summary.py`, `export_risky_clauses.py`)
    has already been run.
  - So the "latest" outputs exist in the current folder:
        extracted_text_*.txt (latest run)
        latest_clauses.csv
        latest_clauses_scored.csv
        risky_clauses_report.csv

STEP-BY-STEP FLOW
-----------------
1) Read the PDF name/path from the command line.
2) Call `find_pdf()`:
      - Try to locate the actual PDF file in different places:
          a) Exactly as given (absolute or relative path)
          b) processed/<basename>
          c) current directory
          d) any sub-folder under processed/
      - If found → return its absolute path.
      - If not found → show error and exit.

3) From the PDF path, derive a **document base name**:
      poonawala_test.pdf  → base name = "poonawala_test"

4) Create a **per-document folder**:
      processed/<base_name>
   Example:
      processed/poonawala_test

5) Move the original PDF into this per-document folder
   (if it's not already there).

6) Find the **latest extracted text file**:
      extracted_text_YYYYMMDD_HHMMSS.txt
   using modification time.

7) Copy all important pipeline outputs into the per-document folder:
      - extracted_text.txt           (copy of latest_extracted_text_*.txt)
      - clauses.csv                  (copy of latest_clauses.csv)
      - clauses_scored.csv           (copy of latest_clauses_scored.csv)
      - risky_clauses_report.csv     (copy of risky_clauses_report.csv)

8) Print a clean summary showing:
      - Document name
      - Folder path
      - Which files are stored there

GOAL
----
After running this script, **everything for that document** lives inside:

    processed/<document_name>/

This makes it easy to:
  - Inspect results
  - Ingest into the database (`db_ingest.py`)
  - Zip and send to your teacher as a self-contained package.
"""

# ============================================================
# 1. IMPORTS
# ============================================================

import os      # For paths, directory checks, file operations
import sys     # For reading command-line arguments and exiting
import glob    # For finding files that match patterns (e.g. extracted_text_*.txt)
import shutil  # For moving and copying files


# ============================================================
# 2. GLOBAL CONFIG
# ============================================================

# Root folder where per-document folders will live.
# Example per-document path: processed/poonawala_test
PROCESSED_ROOT = "processed"


# ============================================================
# 3. HELPER: FIND THE PDF FILE
# ============================================================

def find_pdf(pdf_name: str) -> str:
    """
    Try to find the PDF in several ways and return its ABSOLUTE PATH.

    Search strategy (in order):

    1) If the given string is already a valid file path, use it directly.

    2) Otherwise, take just the basename:
           "processed/poonawala_test/poonawala_test.pdf"
        -> basename = "poonawala_test.pdf"

       Then look for that basename in:
           a) processed/<basename>
           b) current working directory (./<basename>)

    3) If still not found, walk through all subfolders under 'processed/'
       and check if any file matches that basename.

    If found -> return absolute path.
    If not found -> print error and exit the script.
    """

    # 1) If user passed an actual path (relative or absolute) and it exists
    if os.path.isfile(pdf_name):
        full = os.path.abspath(pdf_name)  # convert to absolute path
        print(f"[INFO] Using explicit PDF path: {full}")
        return full

    # Take only the file name part (no folder path)
    basename = os.path.basename(pdf_name)

    # 2a) Check inside processed/<basename>
    candidate1 = os.path.join(PROCESSED_ROOT, basename)
    if os.path.isfile(candidate1):
        full = os.path.abspath(candidate1)
        print(f"[INFO] Found PDF in processed/: {full}")
        return full

    # 2b) Check in the current directory ./<basename>
    candidate2 = os.path.join(os.getcwd(), basename)
    if os.path.isfile(candidate2):
        full = os.path.abspath(candidate2)
        print(f"[INFO] Found PDF in current directory: {full}")
        return full

    # 3) Recursively search inside processed/ and its subfolders
    if os.path.isdir(PROCESSED_ROOT):
        # Walk through the whole tree under 'processed/'
        for root, dirs, files in os.walk(PROCESSED_ROOT):
            # If our basename is among the files in this folder
            if basename in files:
                full = os.path.abspath(os.path.join(root, basename))
                print(f"[INFO] Found PDF in subfolder: {full}")
                return full

    # If we reach here, file was not found anywhere
    print(f"[ERROR] Could not find PDF '{basename}' in '.', '{PROCESSED_ROOT}/', or its subfolders.")
    sys.exit(1)


# ============================================================
# 4. HELPER: FIND LATEST EXTRACTED TEXT FILE
# ============================================================

def find_latest_extracted_text() -> str:
    """
    Find the MOST RECENT extracted_text_*.txt file in the current directory.

    Assumption:
      - Every time you run your pipeline, it produces a file named:
          extracted_text_YYYYMMDD_HHMMSS.txt
      - We want to pick the newest one (by modification time).

    Returns:
      Path (string) to that latest text file.

    If none exist, prints an error and exits.
    """

    # Find all files whose name starts with 'extracted_text_' and ends with '.txt'
    files = glob.glob("extracted_text_*.txt")

    # If the list is empty, nothing was generated by the pipeline
    if not files:
        print("[ERROR] No extracted_text_*.txt files found in the current directory.")
        sys.exit(1)

    # max(..., key=os.path.getmtime) gives the file with the latest modification time
    latest = max(files, key=os.path.getmtime)
    print(f"[INFO] Using latest extracted text file: {latest}")
    return latest


# ============================================================
# 5. HELPER: SAFE COPY UTILITY
# ============================================================

def safe_copy(src: str, dst: str, label: str):
    """
    Copy file from src -> dst only if src exists.

    Parameters:
      src   : source file path (where the file currently is)
      dst   : destination file path (where we want to copy it)
      label : human-friendly description (e.g. 'extracted text')

    Behavior:
      - If src does NOT exist:
            print a warning and skip (no crash).
      - If src DOES exist:
            copy it to dst and print an info message.
    """

    # If source file does not exist, warn and do nothing
    if not os.path.isfile(src):
        print(f"[WARN] {label} not found at '{src}'. Skipping.")
        return

    # shutil.copy2 copies the file and also preserves metadata (timestamps, etc.)
    shutil.copy2(src, dst)
    print(f"[INFO] Copied {label} to {dst}")


# ============================================================
# 6. MAIN FUNCTION
# ============================================================

def main():
    """
    Entry point for the script.

    Steps:
      1) Check command-line arguments and read the PDF name/path.
      2) Use find_pdf() to locate the actual PDF file.
      3) Build a per-document folder path under processed/.
      4) Move the PDF into that folder (if not already inside).
      5) Find the latest extracted_text_*.txt file.
      6) Copy all relevant outputs into the per-document folder:
           - extracted_text.txt
           - clauses.csv
           - clauses_scored.csv
           - risky_clauses_report.csv
      7) Print a friendly summary of where everything is stored.
    """

    # 1) We expect exactly ONE argument: the PDF name/path
    if len(sys.argv) != 2:
        print("Usage: python3 finalize_run.py <pdf_file_name_or_path>")
        print("Example 1: python3 finalize_run.py poonawala_test.pdf")
        print("Example 2: python3 finalize_run.py processed/poonawala_test/poonawala_test.pdf")
        sys.exit(1)

    # sys.argv[0] is the script name; sys.argv[1] is the PDF passed by user
    pdf_input_name = sys.argv[1]

    # 2) Resolve this into an actual file path
    pdf_path = find_pdf(pdf_input_name)

    # 3) Get the base name (without extension) -> used as folder name
    #    Example: "/.../poonawala_test.pdf" -> base_name = "poonawala_test"
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]

    # 4) Build per-document folder path under processed/
    #    Example: "processed/poonawala_test"
    target_dir = os.path.join(PROCESSED_ROOT, base_name)

    # Create the folder if it doesn't exist yet
    os.makedirs(target_dir, exist_ok=True)
    print(f"[INFO] Using per-document folder: {target_dir}")

    # 5) Ensure the PDF is *inside* the per-document folder
    final_pdf_path = os.path.join(target_dir, os.path.basename(pdf_path))

    # If current PDF path is different from where we want it to live, move it
    if os.path.abspath(pdf_path) != os.path.abspath(final_pdf_path):
        shutil.move(pdf_path, final_pdf_path)
        print(f"[INFO] Moved PDF to {final_pdf_path}")
    else:
        # If they are the same, PDF is already in the right place
        print("[INFO] PDF already in target folder; not moving.")

    # 6) Find latest extracted_text_*.txt from your last pipeline run
    latest_extracted = find_latest_extracted_text()

    # 7) Copy all pipeline outputs into per-document folder, with simple names
    #    so each document folder is self-contained.

    # Copy extracted text (rename to extracted_text.txt)
    safe_copy(
        latest_extracted,
        os.path.join(target_dir, "extracted_text.txt"),
        "extracted text"
    )

    # Copy clauses file
    safe_copy(
        "latest_clauses.csv",
        os.path.join(target_dir, "clauses.csv"),
        "latest_clauses.csv"
    )

    # Copy scored clauses file
    safe_copy(
        "latest_clauses_scored.csv",
        os.path.join(target_dir, "clauses_scored.csv"),
        "latest_clauses_scored.csv"
    )

    # Copy risky clauses report
    safe_copy(
        "risky_clauses_report.csv",
        os.path.join(target_dir, "risky_clauses_report.csv"),
        "risky_clauses_report.csv"
    )

    # 8) Final summary for the user
    print("\n========== FINALIZE RUN COMPLETE ==========")
    print(f"Document name      : {base_name}")
    print(f"Per-document folder: {target_dir}")
    print("Saved files (if available):")
    print("  - original PDF")
    print("  - extracted_text.txt")
    print("  - clauses.csv")
    print("  - clauses_scored.csv")
    print("  - risky_clauses_report.csv")
    print("===========================================")


# Standard Python entry point: only run main() if script is executed directly
if __name__ == "__main__":
    main()