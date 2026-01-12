import os
import re
import subprocess
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    jsonify,
)
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# ----------------------------------------------------
# Translation (Marathi / Hindi) – for Chrome extension
# ----------------------------------------------------
try:
    from googletrans import Translator
    translator = Translator()
except ImportError:
    translator = None

# ====================================================
# Flask base config
# ====================================================

app = Flask(__name__)
app.secret_key = os.getenv("AUTOPOLICY_SECRET_KEY", "change-me-for-production")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
PROCESSED_DIR = os.path.join(BASE_DIR, "processed")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)


# ====================================================
# DB helper
# ====================================================

def get_db_connection():
    conn = psycopg2.connect(
        dbname=os.getenv("AUTOPOLICY_DB_NAME", "autopolicy"),
        user=os.getenv("AUTOPOLICY_DB_USER", "postgres"),
        password=os.getenv("AUTOPOLICY_DB_PASSWORD", ""),
        host=os.getenv("AUTOPOLICY_DB_HOST", "localhost"),
        port=os.getenv("AUTOPOLICY_DB_PORT", "5432"),
        cursor_factory=RealDictCursor,
    )
    return conn


# ====================================================
# Simple risk engine (for /api/analyze-text)
# – DOES NOT touch your CLI pipeline or DB logic
# ====================================================

CLAUSE_SPLIT_REGEX = re.compile(r"(?<=[.!?;])\s+|\n+")

# some common risky phrases with tags & base scores
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
]


def split_into_clauses(text: str):
    parts = CLAUSE_SPLIT_REGEX.split(text)
    return [p.strip() for p in parts if p and p.strip()]


def score_clause_simple(text: str):
    """
    Return (is_risky: bool, reasons: list[str], score: int)
    Simple rule-based detector for extension + quick API.
    """
    t = text.lower()
    tags = set()
    score = 0

    for phrase, phrase_tags, base_score in RISKY_PATTERNS:
        if phrase in t:
            for tg in phrase_tags:
                tags.add(tg)
            score += base_score

    # clamp score
    if score >= 5:
        score = 3
    elif score >= 3:
        score = 2
    elif score > 0:
        score = 1

    is_risky = score > 0
    return is_risky, sorted(tags), score


def overall_rating_from_percent(p: float) -> str:
    if p <= 1.0:
        return "A"
    if p <= 5.0:
        return "B"
    if p <= 15.0:
        return "C"
    return "D"


# ====================================================
# Auth helper
# ====================================================

def login_required(view_func):
    @wraps(view_func)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first.", "error")
            return redirect(url_for("login", next=request.path))
        return view_func(*args, **kwargs)
    return wrapper


# ====================================================
# Auth routes
# ====================================================

@app.route("/register", methods=["GET", "POST"])
def register():
    """
    Create a new user:
    - POST: insert into users table
    - then redirect to /login (NOT auto login)
    """
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = (request.form.get("password") or "").strip()
        confirm = (request.form.get("confirm") or "").strip()

        if not email or not password:
            flash("Email and password are required.", "error")
            return render_template("register.html")

        if password != confirm:
            flash("Passwords do not match.", "error")
            return render_template("register.html")

        password_hash = generate_password_hash(password)

        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute(
                """
                INSERT INTO users (email, password_hash, created_at)
                VALUES (%s, %s, now())
                RETURNING id;
                """,
                (email, password_hash),
            )
            user_id = cur.fetchone()["id"]
            conn.commit()
        except psycopg2.Error:
            conn.rollback()
            flash("Could not create user (maybe email already used).", "error")
            cur.close()
            conn.close()
            return render_template("register.html")

        cur.close()
        conn.close()

        flash("Account created. Please log in.", "info")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Log in existing user:
    - check email/password against users table
    - on success, set session and redirect to /documents
    """
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = (request.form.get("password") or "").strip()

        if not email or not password:
            flash("Email and password are required.", "error")
            return render_template("login.html")

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, email, password_hash FROM users WHERE email = %s",
            (email,),
        )
        user = cur.fetchone()
        cur.close()
        conn.close()

        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid email or password.", "error")
            return render_template("login.html")

        session["user_id"] = user["id"]
        session["user_email"] = user["email"]
        flash("Logged in successfully.", "info")

        next_url = request.args.get("next") or url_for("documents")
        return redirect(next_url)

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))


# ====================================================
# Helper: find latest processed folder
# ====================================================

def find_latest_processed_folder() -> str | None:
    """
    Look inside PROCESSED_DIR and return the path of
    the most recently modified subdirectory.
    """
    latest_path = None
    latest_mtime = None

    if not os.path.isdir(PROCESSED_DIR):
        return None

    for name in os.listdir(PROCESSED_DIR):
        path = os.path.join(PROCESSED_DIR, name)
        if not os.path.isdir(path):
            continue
        mtime = os.path.getmtime(path)
        if latest_mtime is None or mtime > latest_mtime:
            latest_mtime = mtime
            latest_path = path

    return latest_path


# ====================================================
# Navigation
# ====================================================

@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("documents"))
    return redirect(url_for("login"))


# ====================================================
# Documents dashboard – list + upload / pipeline
# ====================================================

@app.route("/documents", methods=["GET", "POST"])
@login_required
def documents():
    user_id = session["user_id"]

    # ---------- file upload + pipeline ----------
    if request.method == "POST":
        upload = request.files.get("file") or request.files.get("document")
        if not upload or upload.filename == "":
            flash("Please choose a PDF or image to upload.", "error")
            return redirect(url_for("documents"))

        filename = secure_filename(upload.filename)
        if not filename:
            flash("Invalid filename.", "error")
            return redirect(url_for("documents"))

        saved_path = os.path.join(UPLOAD_DIR, filename)
        upload.save(saved_path)

        # 1) Run your existing advanced pipeline
        try:
            result = subprocess.run(
                ["python3", "advanced_risk_engine.py", saved_path],
                cwd=BASE_DIR,
                capture_output=True,
                text=True,
                check=True,
            )
            print("advanced_risk_engine.py stdout:\n", result.stdout)
            print("advanced_risk_engine.py stderr:\n", result.stderr)
        except subprocess.CalledProcessError as e:
            print("advanced_risk_engine.py failed:", e.stderr or e.stdout)
            flash(
                f"Pipeline failed: advanced_risk_engine.py returned {e.returncode}",
                "error",
            )
            return redirect(url_for("documents"))

        # 2) Find the latest processed folder that pipeline created
        latest_dir = find_latest_processed_folder()
        if latest_dir is None:
            flash(
                "Pipeline did not create any processed folder – cannot ingest.",
                "error",
            )
            return redirect(url_for("documents"))

        # Make relative path like "processed/loan_test"
        processed_folder = os.path.relpath(latest_dir, BASE_DIR)
        print("Using processed folder for ingest:", processed_folder)

        # 3) Push into DB for THIS user
        try:
            ingest = subprocess.run(
                ["python3", "db_ingest.py", processed_folder, str(user_id), filename],
                cwd=BASE_DIR,
                capture_output=True,
                text=True,
                check=True,
            )
            print("db_ingest.py stdout:\n", ingest.stdout)
            print("db_ingest.py stderr:\n", ingest.stderr)
            flash("Pipeline completed.", "info")
        except subprocess.CalledProcessError as e:
            print("db_ingest.py failed. stdout:\n", e.stdout)
            print("db_ingest.py failed. stderr:\n", e.stderr)
            error_text = (e.stderr or e.stdout or "").strip()
            flash(
                f"DB ingest failed (exit {e.returncode}): {error_text}",
                "error",
            )

        return redirect(url_for("documents"))

    # ---------- list documents ----------
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT
            id,
            original_filename,
            total_clauses,
            risky_clauses,
            uploaded_at,
            processed_at,
            overall_rating,
            CASE
                WHEN total_clauses > 0
                THEN ROUND((risky_clauses::numeric * 100.0) / total_clauses, 2)
                ELSE 0
            END AS risk_percent
        FROM documents
        WHERE user_id = %s
        ORDER BY uploaded_at, id;
        """,
        (user_id,),
    )
    docs = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("documents.html", documents=docs)


# ====================================================
# Single document detailed view
# ====================================================

@app.route("/document/<int:doc_id>")
@login_required
def document_detail(doc_id: int):
    user_id = session["user_id"]

    conn = get_db_connection()
    cur = conn.cursor()

    # 1) fetch document row
    cur.execute(
        """
        SELECT
            id,
            user_id,
            original_filename,
            total_clauses,
            risky_clauses,
            overall_rating,
            uploaded_at,
            processed_at
        FROM documents
        WHERE id = %s AND user_id = %s
        """,
        (doc_id, user_id),
    )
    document = cur.fetchone()
    if not document:
        cur.close()
        conn.close()
        flash("Document not found for this user.", "error")
        return redirect(url_for("documents"))

    # 2) fetch risky clauses
    cur.execute(
        """
        SELECT
            clause_number,
            text,
            model_risk_reason,
            model_risk_score
        FROM clauses
        WHERE document_id = %s
          AND model_is_risky = TRUE
        ORDER BY clause_number
        """,
        (doc_id,),
    )
    risky_clauses = cur.fetchall()

    # 3) risk distribution by reason
    cur.execute(
        """
        SELECT
            COALESCE(NULLIF(model_risk_reason, ''), 'generic') AS risk_type,
            COUNT(*) AS risky_clauses
        FROM clauses
        WHERE document_id = %s
          AND model_is_risky = TRUE
        GROUP BY risk_type
        ORDER BY risky_clauses DESC;
        """,
        (doc_id,),
    )
    risk_distribution = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "document.html",
        document=document,
        risky_clauses=risky_clauses,
        risk_distribution=risk_distribution,
    )


# ====================================================
# Risk analysis API for Chrome extension
# ====================================================

@app.post("/api/analyze-text")
def api_analyze_text():
    data = request.get_json(silent=True) or {}
    raw_text = (data.get("text") or "").strip()

    if not raw_text:
        return jsonify({"ok": False, "error": "No text provided."}), 400

    clauses = split_into_clauses(raw_text)
    total = len(clauses)

    risky_clauses = []
    breakdown = {}

    for idx, clause in enumerate(clauses, start=1):
        try:
            is_risky, reasons, score = score_clause_simple(clause)
        except Exception as e:
            print("Risk engine error for clause:", e)
            is_risky, reasons, score = False, [], 0

        if not is_risky:
            continue

        reasons = reasons or []
        risky_clauses.append(
            {
                "clause_number": idx,
                "text": clause,
                "score": int(score or 0),
                "reasons": reasons,
            }
        )

        for tag in reasons:
            t = str(tag).strip()
            if not t:
                continue
            breakdown[t] = breakdown.get(t, 0) + 1

    risky = len(risky_clauses)
    risky_percent = (risky * 100.0 / total) if total > 0 else 0.0
    rating = overall_rating_from_percent(risky_percent)

    return jsonify(
        {
            "ok": True,
            "total_clauses": total,
            "risky_clauses": risky_clauses,
            "risky_percent": risky_percent,
            "overall_rating": rating,
            "risk_breakdown": breakdown,
            "risky_clauses_count": risky,
            "grade": rating,
        }
    )


# ====================================================
# Translation API for Chrome extension
# ====================================================

@app.post("/api/translate-text")
def api_translate_text():
    data = request.get_json(silent=True) or {}
    text = (data.get("text") or "").strip()
    target = (data.get("target_lang") or "hi").strip().lower()

    if not text:
        return jsonify({"ok": False, "error": "No text provided."}), 400

    if translator is None:
        return jsonify({
            "ok": False,
            "error": "Translation engine is not available on the server.",
        }), 500

    if target.startswith("mar"):
        lang_code = "mr"
    elif target.startswith("hin"):
        lang_code = "hi"
    else:
        lang_code = target

    try:
        result = translator.translate(text, dest=lang_code)
        return jsonify({
            "ok": True,
            "translated_text": result.text,
            "target_lang": lang_code,
        })
    except Exception as e:
        print("Translation error:", e)
        return jsonify({
            "ok": False,
            "error": "Translation failed on server.",
        }), 500


# ====================================================
# Main
# ====================================================

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)