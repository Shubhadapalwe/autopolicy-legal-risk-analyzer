import subprocess
import sys
import os


def run(cmd, desc: str):
    """
    Helper to run a shell command and stop the pipeline if it fails.
    """
    print(f"\n========== {desc} ==========")
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"[ERROR] Step failed: {desc}")
        sys.exit(result.returncode)


def main():
    # 1) Extract text from all PDFs/images in the folder
    #    (Your existing OCR + PDF logic lives inside Final_text_extractor.py)
    if os.path.exists("Final_text_extractor.py"):
        run(["python3", "Final_text_extractor.py"], "1) Extract text (PDF/OCR)")
    else:
        print("[WARN] Final_text_extractor.py not found, skipping extraction step.")

    # 2) Build latest_clauses.csv from newest extracted_text_*.txt
    if os.path.exists("build_latest_clauses.py"):
        run(
            ["python3", "build_latest_clauses.py"],
            "2) Build latest_clauses.csv from newest extracted_text_*.txt",
        )
    else:
        print("[ERROR] build_latest_clauses.py not found. Cannot continue.")
        sys.exit(1)

    # 3) Run risky phrase detector on latest_clauses.csv
    if os.path.exists("risky_phrase_detector.py"):
        run(["python3", "risky_phrase_detector.py"], "3) Run risky phrase detector")
    else:
        print("[ERROR] risky_phrase_detector.py not found. Cannot continue.")
        sys.exit(1)

    # 4) Print risk summary (on latest_clauses_scored.csv)
    if os.path.exists("risk_summary.py"):
        run(["python3", "risk_summary.py"], "4) Document risk summary")
    else:
        print("[WARN] risk_summary.py not found, skipping summary step.")

    # 5) Export risky clauses report (risky_clauses_report.csv)
    if os.path.exists("export_risky_clauses.py"):
        run(
            ["python3", "export_risky_clauses.py"],
            "5) Export risky clauses report (risky_clauses_report.csv)",
        )
    else:
        print("[WARN] export_risky_clauses.py not found, skipping risky-clauses export.")

    # 6) Auto-learn new risky tokens (for future documents), if script exists
    if os.path.exists("auto_learn_risky_words.py"):
        run(
            ["python3", "auto_learn_risky_words.py"],
            "6) Auto-learn new risky tokens (optional)",
        )
    else:
        print("[WARN] auto_learn_risky_words.py not found, skipping auto-learn step.")

    print("\n========== PIPELINE COMPLETE ==========")
    print("Inputs processed from latest extracted_text_*.txt file.")
    print("Clauses file: latest_clauses.csv")
    print("Scored clauses: latest_clauses_scored.csv")
    print("Risk summary: printed above (if risk_summary.py present).")
    print("Risky clauses CSV: risky_clauses_report.csv (if export_risky_clauses.py present).")


if __name__ == "__main__":
    main()
