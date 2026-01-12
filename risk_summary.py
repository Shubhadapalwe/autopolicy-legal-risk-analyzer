import csv
from collections import Counter

# Scored clauses file from risky_phrase_detector.py
CLAUSE_SCORED_CSV = "latest_clauses_scored.csv"


def load_rows(path: str):
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def main():
    rows = load_rows(CLAUSE_SCORED_CSV)

    if not rows:
        print("===== DOCUMENT RISK SUMMARY =====")
        print("No clauses found in scored CSV.")
        print("=================================")
        return

    total = len(rows)

    risky_rows = [
        r for r in rows
        if (r.get("model_is_risky", "") or "").strip().upper() == "TRUE"
    ]
    risky_count = len(risky_rows)

    risky_pct = (risky_count / total * 100.0) if total > 0 else 0.0

    # Count risk types from model_risk_reason
    counter = Counter()
    for r in risky_rows:
        reason = (r.get("model_risk_reason", "") or "").strip()
        if not reason:
            continue
        # reasons may be comma-separated tags
        for tag in reason.split(","):
            tag = tag.strip()
            if tag:
                counter[tag] += 1

    # Print summary
    print("===== DOCUMENT RISK SUMMARY =====")
    print(f"Total clauses: {total}")
    print(f"Risky clauses (model): {risky_count}")
    print(f"Risky percentage: {risky_pct:.2f}%")
    print()
    print("Breakdown by risk type:")
    if counter:
        for tag, cnt in counter.most_common():
            print(f"  - {tag}: {cnt}")
    else:
        print("  (no risky clauses or tags found)")
    print()
    # Simple grade based on risky percentage
    if risky_pct <= 5:
        rating = "A (Low Risk)"
    elif risky_pct <= 15:
        rating = "B (Moderate Risk)"
    else:
        rating = "C (High Risk)"

    print(f"Overall risk rating: {rating}")
    print("=================================")


if __name__ == "__main__":
    main()