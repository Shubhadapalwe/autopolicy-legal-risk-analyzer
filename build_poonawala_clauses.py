import csv
import re

# Input: extracted raw text for poonawala
INPUT_TEXT = "extracted_text_20251214_124234.txt"
# Output: clauses CSV we will feed to risk detector
OUTPUT_CSV = "poonawala_clauses.csv"


def load_text(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def split_into_clauses(text):
    # Normalize newlines to spaces
    normalized = text.replace("\r\n", " ").replace("\n", " ")

    # Split on sentence-like boundaries: ., ?, !
    # (?<=[.!?]) = split AFTER ., !, or ?
    parts = re.split(r'(?<=[.!?])\s+', normalized)

    clauses = []
    for part in parts:
        clause = part.strip()
        # skip empty or very short fragments
        if len(clause) < 20:
            continue
        clauses.append(clause)

    return clauses


def write_clauses_csv(clauses, path):
    fieldnames = ["clause_id", "text", "is_risky", "risky_reason"]

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for idx, clause in enumerate(clauses, start=1):
            writer.writerow({
                "clause_id": idx,
                "text": clause,
                "is_risky": "",
                "risky_reason": ""
            })


def main():
    print(f"[INFO] Loading text from {INPUT_TEXT}...")
    text = load_text(INPUT_TEXT)

    print("[INFO] Splitting into clauses...")
    clauses = split_into_clauses(text)
    print(f"[INFO] Got {len(clauses)} clauses.")

    print(f"[INFO] Writing clauses CSV to {OUTPUT_CSV}...")
    write_clauses_csv(clauses, OUTPUT_CSV)
    print("[DONE] Clause CSV ready.")


if __name__ == "__main__":
    main()
