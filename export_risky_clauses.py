import csv

INPUT_CSV = "latest_clauses_scored.csv"
OUTPUT_CSV = "risky_clauses_report.csv"


def load_rows(path: str):
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def main():
    fieldnames, rows = load_rows(INPUT_CSV)

    risky_rows = [
        r for r in rows
        if (r.get("model_is_risky", "") or "").strip().upper() == "TRUE"
    ]

    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(risky_rows)

    print(f"[INFO] Found {len(risky_rows)} risky clauses.")
    print(f"[DONE] Risky clauses exported to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()