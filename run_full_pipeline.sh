#!/usr/bin/env bash
#
# run_full_pipeline.sh
#
# Run the entire AutoPolicy PDF pipeline in one command:
#   1) Extract text + clauses for a given PDF
#   2) Build latest_clauses.csv
#   3) Run advanced risk engine (writes latest_clauses_scored.csv)
#   4) Finalize run into processed/<docname>/
#   5) Ingest into PostgreSQL
#
# Usage:
#   ./run_full_pipeline.sh test.pdf
#   ./run_full_pipeline.sh processed/poonawala_test/poonawala_test.pdf
#

set -e

if [ $# -ne 1 ]; then
  echo "Usage: $0 <pdf_file_name_or_path>"
  exit 1
fi

PDF_INPUT="$1"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "========================================"
echo "[STEP 1] Extract text + clauses from PDF"
echo "========================================"
python3 Final_text_extractor.py "$PDF_INPUT"

echo
echo "========================================"
echo "[STEP 2] Build latest_clauses.csv"
echo "========================================"
python3 build_latest_clauses.py

echo
echo "========================================"
echo "[STEP 3] Run advanced risk engine"
echo "========================================"
python3 advanced_risk_engine.py

echo
echo "========================================"
echo "[STEP 4] Finalize run into processed/<docname>/"
echo "========================================"
python3 finalize_run.py "$PDF_INPUT"

BASENAME="$(basename "$PDF_INPUT")"
DOCNAME="${BASENAME%.*}"
TARGET_FOLDER="processed/$DOCNAME"

echo
echo "========================================"
echo "[STEP 5] Ingest into PostgreSQL from $TARGET_FOLDER"
echo "========================================"
python3 db_ingest.py "$TARGET_FOLDER"

echo
echo "========== PIPELINE FINISHED =========="
echo "PDF file       : $PDF_INPUT"
echo "Document name  : $DOCNAME"
echo "Processed dir  : $TARGET_FOLDER"
echo "Check dashboard at: http://127.0.0.1:5000/documents"
echo "======================================="