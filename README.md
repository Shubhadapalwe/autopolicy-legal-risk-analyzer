# AutoPolicy – Dynamic Legal Risk Analyzer

AutoPolicy is a **web + Chrome extension** system that helps users quickly understand how risky long legal documents are – such as Terms & Conditions, loan agreements, privacy policies, etc.

Instead of manually reading 20–30 pages, AutoPolicy:

- Extracts text from **PDFs / images (OCR)** or **live web pages**
- Splits the document into **clauses**
- Detects **risky phrases** (data sharing, account closure, fees, etc.)
- Assigns each clause a **risk severity**:
  - 🟥 **High** – red  
  - 🟧 **Medium** – orange  
  - 🟨 **Low** – yellow
- Computes an overall **document grade (A–D)**
- Highlights risky clauses directly **on the website** via Chrome extension
- Stores everything in **PostgreSQL** for later review
- Supports **Marathi / Hindi translation** for clauses (for better understanding)

AutoPolicy is a **student academic project**, not a replacement for a professional lawyer.

---

Screenshots


### A. Web app – login, signup & dashboard

[![Login page – gradient hero + login card](screenshots/01_login_page.png)](screenshots/01_login_page.png)
[![Register page – create account](screenshots/02_register_page.png)](screenshots/02_register_page.png)

[![Dashboard – empty state after login](screenshots/03_dashboard_empty.png)](screenshots/03_dashboard_empty.png)
[![Dashboard – documents table with risk grades](screenshots/04_dashboard_with_results.png)](screenshots/04_dashboard_with_results.png)

[![Upload dialog – choosing a PDF](screenshots/05_upload_choose_file.png)](screenshots/05_upload_choose_file.png)
[![Document details – donut chart + risky clauses list](screenshots/06_document_detail.png)](screenshots/06_document_detail.png)

---

### B. Chrome extension – risk analysis on live website

[![Extension popup – initial state on Flipkart Terms page](screenshots/07_extension_popup_open.png)](screenshots/07_extension_popup_open.png)

[![Extension – page text scanned and loaded](screenshots/08_extension_page_text_loaded.png)](screenshots/08_extension_page_text_loaded.png)
[![Extension – risk analysis result for full page](screenshots/09_extension_scan_result.png)](screenshots/09_extension_scan_result.png)

[![Extension – analysis result for a small selected paragraph](screenshots/10_extension_selected_text_result.png)](screenshots/10_extension_selected_text_result.png)
[![Extension – Marathi translation of selected text](screenshots/11_extension_translation_marathi.png)](screenshots/11_extension_translation_marathi.png)
[![Web page – risky clause highlighted in yellow](screenshots/12_extension_highlighted_clause.png)](screenshots/12_extension_highlighted_clause.png)



## Problem & Motivation

Most users **blindly click “I Agree”** on:

- Bank loan documents  
- E-commerce Terms of Use  
- App privacy policies  

These documents often contain:

- Data sharing clauses  
- Account termination rules  
- Hidden fees and charges  
- Broad indemnity clauses  

Reading and understanding everything is time-consuming and difficult, especially for **non-legal, non-technical** users.

**Goal of AutoPolicy:**  
Help users quickly identify **important/risky clauses**, understand the **overall risk level**, and highlight **exact sentences** that should be re-read carefully.

---

##  Key Features

### 1. Web Application (Flask + PostgreSQL)

- **User Authentication**
  - Register with email + password
  - Login / Logout, session handling
  - Passwords stored as **hashed values** (never plain text)

- **Document Upload & Storage**
  - Upload **PDF** or **image screenshots** (PNG/JPG/JPEG)
  - Each upload is linked to the logged-in user (`user_id`)
  - The system computes a **fingerprint** (hash) to detect duplicate documents

- **Risk Analysis Dashboard**
  - List of all documents for the logged-in user
  - For each document:
    - Filename
    - Total clauses
    - Number of risky clauses
    - Risk percentage
    - Overall grade (A/B/C/D)
    - Link to **detailed view**

- **Document Detail Page**
  - Summary information (filename, total clauses, risky clauses, grade)
  - **Donut chart (Chart.js)** showing risk distribution by category  
    (e.g. data_sharing, fees_charges, indemnity, account_closure, etc.)
  - Detailed list of **risky clauses**:
    - Clause number
    - Risk score
    - Risk tags (reasons)
    - Original clause text



### 2. Chrome Extension (Manifest V3)

- **Select or Scan Text from Any Web Page**
  - **Use selected text on page** (user highlights a section)
  - **Scan whole page** (collects visible text)
  - Sends text to backend API: `/api/analyze-text`

- **Risk Summary in Popup**
  - Risk percentage
  - Overall rating: A / B / C / D
  - Risky / total clauses
  - List of risky clauses with:
    - Clause number
    - Score
    - Tags (e.g. data_sharing, fees_charges)

- **Highlight on Live Web Page**
  - When user clicks a clause in the popup:
    - The extension finds that clause text on the page
    - Scrolls to it
    - Highlights it with color based on severity:
      - 🟥 Red  → High risk
      - 🟧 Orange → Medium risk
      - 🟨 Yellow → Low risk


### 3. Risk Engine (Rule-Based NLP)

- Splits long text into **clauses** using punctuation and line breaks
- For each clause, checks for **known risky phrases**, for example:
  - Data / privacy:
    - “may share your personal data”
    - “may disclose your information”
  - Account closure:
    - “may terminate your account”
    - “may suspend your account”
  - Fees / charges:
    - “reserves the right to change its fee policy”
    - “non-refundable”
  - Indemnity:
    - “you agree to indemnify”
    - “hold us harmless”
  - Generic risk:
    - “at its sole discretion”
    - “we are not liable for”

- Assigns each clause:
  - **Tags** (e.g. `["data_sharing", "fees_charges"]`)
  - **Score** (0–3) → mapped to Low / Medium / High

- Overall document grade is derived from the **percentage of risky clauses**:

  - `risk% = (risky_clauses / total_clauses) * 100`

  - Grade:
    - **A** – risk% ≤ 1  
    - **B** – risk% ≤ 5  
    - **C** – risk% ≤ 15  
    - **D** – risk% > 15  



### 4. Clause Translation (Marathi / Hindi) – Optional

To help users who are more comfortable in **Marathi** or **Hindi**:

- Backend has an API to **translate a clause** from English → Marathi / Hindi
- Triggered from the UI (e.g. for a selected clause)
- Uses translation library (e.g. `deep_translator.GoogleTranslator`) or external service

> Translation is for **understanding**, not for official legal usage.



## System Architecture

### High-Level Blocks

1. **Web Frontend (Flask Templates + CSS)**  
   - `login.html`, `register.html`, `documents.html`, `document_detail.html`
   - Uses `styles.css` for a modern, dark-themed UI
   - Uses **Chart.js** for donut chart in document detail

2. **Backend (Flask)**
   - `app.py`
   - Routes:
     - `/register`, `/login`, `/logout`
     - `/` → redirects to `/documents` or `/login`
     - `/documents` → document list + upload
     - `/document/<id>` → detailed view
     - `/api/analyze-text` → risk analysis for raw text (extension)
     - `/api/translate-text` → optional clause translation

3. **Processing Pipeline (CLI)**
   - `Final_text_extractor.py` – extract text from PDF / images (OCR)
   - `build_latest_clauses.py` – split extracted text into clauses
   - `advanced_risk_engine.py` – compute risk for each clause
   - Outputs: `clauses_scored.csv` inside a `processed/<docname>/` folder

4. **Database Ingestion Script**
   - `db_ingest.py`
   - Reads `processed/<docname>/` folder:
     - Detects original file
     - Reads `clauses_scored.csv`
     - Counts total & risky clauses
     - Computes risk%, grade, fingerprint
     - Inserts into:
       - `documents` table (1 row)
       - `clauses` table (many rows)

5. **PostgreSQL Database**
   - `users` – authentication
   - `documents` – per document summary
   - `clauses` – per clause detailed risk

6. **Chrome Extension**
   - `manifest.json` – manifest v3
   - `popup.html` / `popup.js` – user interface for analysis
   - `content_script.js` – interacts with active web page (selection, full text, highlighting)

—

## How to run AutoPolicy

AutoPolicy can be run in two main ways:

1. **Locally on a single laptop** (Flask backend + PostgreSQL + Chrome extension)  
2. **Deployed on a remote server** (Flask backend + PostgreSQL on a VM / cloud)  

The core logic (risk analysis + grading) is fully local.  
Only the **translation feature** (Marathi / Hindi) needs internet.

---

### 1. Prerequisites

#### 1.1. Software

- **Python** 3.9+  
- **PostgreSQL** 13+  
- **Google Chrome / Chromium** (to load the extension)
- Git (optional, if cloning from GitHub)

#### 1.2. Python dependencies

Install from `requirements.txt` (example):

```bash
pip install -r requirements.txt

If you don’t have a virtual environment yet (recommended):

cd /path/to/project_msc
python3 -m venv venv
source venv/bin/activate         # macOS / Linux
# .\venv\Scripts\activate        # Windows PowerShell

pip install -r requirements.txt

Typical dependencies used in this project:
	•	Flask

	•	psycopg2-binary

	•	Werkzeug

	•	googletrans==4.0.0rc1 (or similar; used for translations)

	•	Any extra libraries used in advanced_risk_engine.py

2. Database setup (PostgreSQL)

2.1. Create database
Open a terminal and run:
psql -U postgres

Inside psql:  CREATE DATABASE autopolicy;
\c autopolicy;

2.2. Create tables
Run the SQL schema file from the project (name may vary):
psql -U postgres -d autopolicy -f schema.sql
The schema defines tables like:
	•	users          – login / auth users
	•	documents      – one row per uploaded / ingested document
	•	clauses        – one row per detected clause

If your schema file is named differently (e.g. create_tables.sql), replace schema.sql accordingly.

3. Configure environment variables (optional but recommended)

The backend uses environment variables with safe defaults.
You can override them if needed:

export AUTOPOLICY_DB_NAME="autopolicy"
export AUTOPOLICY_DB_USER="postgres"
export AUTOPOLICY_DB_PASSWORD=""
export AUTOPOLICY_DB_HOST="localhost"
export AUTOPOLICY_DB_PORT="5432"

export AUTOPOLICY_SECRET_KEY=“some-long-random-string"

If you skip this step, the defaults in app.py will be:
	•	DB name: autopolicy
	•	DB user: postgres
	•	Password: empty
	•	Host: localhost
	•	Port: 5432
	•	Secret key: “change-me-for-production"

4. Running the backend locally (Flask + PostgreSQL)

From the project root (where app.py is):

cd /path/to/project_msc
source venv/bin/activate      # if using virtual env
python3 app.py

You should see something like:

 * Serving Flask app 'app'
 * Debug mode: on
 * Running on http://127.0.0.1:5000

This starts the AutoPolicy backend on:

http://127.0.0.1:5000
This address is used both by:
	•	The web app (dashboard & login pages)
	•	The Chrome extension (for /api/analyze-text and /api/translate-text)

5. Running the web app (dashboard)
	1.	Make sure Flask server is running (python3 app.py).

	2.	Open a browser and go to:

     	3.	Register a user:
	•	Click on “Create account / Register”.
	•	Fill email + password.
	•	The user is stored in the users table.

	4.	Login:

	•	Use the same email and password.
	•	After login, you will be redirected to /documents (Dashboard).

	5.	Upload + analyze a document from the dashboard:

	•	On /documents, use the Upload section:
	•	Choose file (PDF / PNG / JPG / JPEG).
	•	Click Upload & Analyze.
	•	Under the hood, for each upload, the backend:
	1.	Saves the file into uploads/.
	2.	Calls advanced_risk_engine.py to:
	•	Extract text,
	•	Split into clauses,
	•	Generate processed/<base_name>/clauses_scored.csv.
	3.	Calls db_ingest.py processed/<base_name> <current_user_id> to:
	•	Compute clause-level risk again (rule-based),
	•	Insert into documents and clauses tables.

	6.	Dashboard table:
	•	Shows one row per document:
	•	Original filename,
	•	Total clauses,
	•	Risky clauses,
	•	Risk percentage,
	•	Overall grade (A–D).

	7.Per-document detail view:
	•	Click “View” to open /document/<id>.
	•	This shows:
	•	Summary (filename, total clauses, risky %, rating),
	•	A Pie chart of risk types (e.g. data_sharing, fees_charges, generic_risk,…),
	•	Detailed list of all risky clauses with:
	•	Clause number,
	•	Risk score (1–3),
	•	Risk reason tags,
	•	Full clause text.

⸻

6. Running the Chrome extension locally

The extension expects the backend at:
http://127.0.0.1:5000

6.1. Load the extension in Chrome
	1.	Open chrome://extensions/ in Chrome.
	2.	Enable Developer mode (top-right).
	3.	Click “Load unpacked”.
	4.	Select the extension folder, for example: /path/to/project_msc/extension

which contains:
	•	manifest.json
	•	popup.html
	•	popup.js
	•	popup.css
	•	content_script.js

	5.	The AutoPolicy icon should now appear in the Chrome toolbar.

6.2. Analyze a live web page
	1.	Make sure python3 app.py is running.
	2.	Open any legal / terms-of-use page in Chrome.
	3.	Select some text (or leave it to analyze full page).
	4.	Click the AutoPolicy extension icon.
	5.	In the popup:
	•	Click “Use Selection” or “Full Page”.
	•	Click “Analyze risk”.

The extension will:
	•	Send the text to POST http://127.0.0.1:5000/api/analyze-text.
	•	Show:
	•	Total clauses,
	•	Number of risky clauses,
	•	Grade,
	•	List of risky clauses.
	•	Let you:
	•	Click on a clause to highlight it back on the page (yellow / orange / red).
	•	Request Marathi / Hindi translation for that clause.


## Project Structure (Example)

```text
project_root/
├── app.py                    # Flask web server (routes, APIs, auth)
├── db_ingest.py              # Ingest processed results into PostgreSQL
├── Final_text_extractor.py   # (Pipeline) Extract text from PDFs/images
├── build_latest_clauses.py   # (Pipeline) Create clauses from text
├── advanced_risk_engine.py   # (Pipeline) Risk scoring per clause
├── risky_phrase_detector.py  # (Optional) More detailed risk logic
├── requirements.txt          # Python dependencies
├── templates/
│   ├── index.html            # Redirect home
│   ├── login.html            # Login screen
│   ├── register.html         # Sign-up screen
│   ├── documents.html        # Dashboard + upload + table
│   └── document_detail.html  # Document detail + chart + clauses
├── static/
│   └── styles.css            # Global styling for the web app
├── extension/
│   ├── manifest.json         # Chrome manifest
│   ├── popup.html            # Popup UI
│   ├── popup.js              # Logic for API calls + list rendering
│   └── content_script.js     # Reads page text + applies highlights
└── screenshots/              # For README images (not required by code)
    ├── register.png
    ├── login.png
    ├── dashboard_documents.png
    ├── document_detail.png
    ├── extension_popup.png
    └── extension_highlight.png

## What happens internally when I upload a file? (File-level view)

This section explains **only the file-level flow** when a user uploads a PDF/image from the web dashboard — which folders and files are created, and what each file contains.

We ignore the Chrome extension here and focus on:

1. Files created in the project folder (`uploads/` and `processed/`).
2. What is stored inside those files.
3. Which step of the pipeline creates them.

---

### Step 0 – Initial state

Before uploading anything, the project already has these folders:

```text
project_root/
├── app.py
├── advanced_risk_engine.py
├── db_ingest.py
├── templates/
├── static/
├── uploads/      # exists, usually empty at the start
└── processed/    # exists, contains previous runs (if any)

### Step 1 – Upload from dashboard → file saved into uploads/

Action: User logs in → opens /documents → chooses a PDF/image → clicks “Upload & Analyze”.

What Flask does in /documents (POST):
	1.	Reads the uploaded file from the HTTP request.
	2.	Sanitizes the name (using secure_filename).
	3.	Saves it into the uploads/ folder.
Example:

If the user uploads SBI_Loan.pdf, this file is created:
uploads/
└── SBI_Loan.pdf
Contents of uploads/SBI_Loan.pdf:
	•This is exactly the original file the user uploaded (PDF / PNG / JPG / JPEG).
	•No modification, just stored on disk so the pipeline can read it.

### Step 2 – Text extraction + clause splitting → files in processed/<docname>/

After saving the file, app.py runs:
python3 advanced_risk_engine.py uploads/SBI_Loan.pdf
advanced_risk_engine.py does:
	1.Detects file type (.pdf vs .png/.jpg/.jpeg).
	2.Extracts the full raw text:
	    •For PDFs: via a PDF text extractor.
	    •For images: via OCR.
	3.Splits the text into clauses using a regex like:
                       r”(?<=[.!?;])\s+|\n+"
	4.Creates a subfolder under processed/ named after the base file name (without extension).

For SBI_Loan.pdf, the folder structure becomes:
processed/
└── SBI_Loan/
    ├── SBI_Loan.pdf           # (optional) copy of the original file
    ├── extracted_text.txt     # full raw text of the document
    └── clauses_scored.csv     # one row per clause

### 2.1 processed/SBI_Loan/extracted_text.txt
	•Created by: advanced_risk_engine.py
	•Format: Plain UTF-8 text file.
	•Content: The entire document text in one file, as extracted from the PDF/image.

Example (simplified):
SBI Loan Agreement

1. You agree to repay the loan with interest...
2. The bank may change interest rates without prior notice...
3. We are not liable for...
…

Purpose:
	•Debugging / inspection: you can quickly see what text the pipeline actually “saw”.
	•Good for showing to teachers/interviewers: “This is the cleaned text we got from OCR/PDF.”

### 2.2 processed/SBI_Loan/clauses_scored.csv
•Created by: advanced_risk_engine.py
•Updated logically by: db_ingest.py (recomputes risk, but does not necessarily rewrite the file; it uses the data to write into DB).
•Format: CSV with a header row.

Example (before DB ingest):
clause_id,text,model_is_risky,model_risk_reason,model_risk_score
1,"You agree to repay the loan with interest...",FALSE,,0
2,"The bank may change interest rates without prior notice",FALSE,,0
3,"We are not liable for any indirect damages",FALSE,,0
…

Columns:
	•clause_id
	•Clause serial number starting from 1.
	•text
	•Exact text of that clause (one row = one clause).
	•model_is_risky (placeholder initially)
	•Initially might be FALSE or 0 for all rows.
	•model_risk_reason (placeholder initially)
	•Empty or very basic; real tags are recomputed later.
	•model_risk_score (placeholder initially)
	•0 for all clauses at first.

Purpose:
	•This file is the bridge between the OCR/PDF parsing world and the     
	database world.
	•It’s a clean, structured list of clauses that db_ingest.py can consume.

### Step 3 – Risk computation + DB insert (no new files, only DB rows)

After the processed folder is ready, app.py runs:
python3 db_ingest.py processed/SBI_Loan <user_id>

Example for user id 1:
python3 db_ingest.py processed/SBI_Loan 1

Inside db_ingest.py:
	1.Reads processed/SBI_Loan/clauses_scored.csv.
	2.For each clause row, recomputes risk:

                  is_risky, reasons, score = score_clause_simple(text)
using rule-based patterns like:
‘May shear your personal data’-> data_sharing
•"we are not liable for" → generic_risk
•"you agree to indemnify" → indemnity
	
3.	Counts:
	•	total_clauses
	•	risky_clauses
	•	risky_percent
	•	overall_rating (A/B/C/D)

4.	Inserts:
	•	ONE row into documents table.
	•	MANY rows into clauses table.

Important:
In this step, no extra files are created on disk. All work is:
	•	Reading extracted_text.txt / clauses_scored.csv.
	•	Writing rows into PostgreSQL.
Internally, PostgreSQL stores these rows in its data directory (heap files, 8KB pages, WAL, etc.), but from the project perspective you can treat it simply as:
	•	Metadata → documents table
	•	Detailed per-clause data → clauses table

### Step 4 – Dashboard refresh (read-only, no new files)

When the browser reloads /documents after “Pipeline completed”:
	1.	app.py reads from documents (for that user_id).
	2.	No new files are created; it just queries the DB.
	3.	The uploaded document now appears in the dashboard table with:
	•	Filename
	•	Total clauses
	•	Risky clauses
	•	Risk %
	•	Grade

Clicking “View” on any row uses the document_id to query:
	•	documents table (summary),
	•	clauses table (risky clauses),
	•	builds the pie chart and detail list.

Again, this is read-only with respect to files. No new files are added here.
——————————————————————————————————

## What happens internally when I use the Chrome extension? (Step-by-step)

This section explains **how the Chrome extension talks to the AutoPolicy backend** and what happens when a user selects text on a web page and clicks **“Analyze risk”** or **“Translate”**.

Unlike the dashboard flow, the extension:

- Does **not** create new files on disk.
- Works entirely with:
  - Browser memory (DOM, JS objects),
  - HTTP calls to the local Flask backend (`http://127.0.0.1:5000`),
  - Temporary highlights on the page.

---

### Step 0 – Extension files (what ships inside the `.crx` / unpacked extension)

Inside the extension folder, we mainly have:

```text
extension_root/
├── manifest.json          # Chrome extension configuration
├── popup.html             # Small UI that opens when user clicks the icon
├── popup.js               # Logic for buttons, API calls, UI updates
├── popup.css              # Styling for the popup
└── content_script.js      # Injected into every page the user opens

High-level roles:
	•manifest.json
	•	Tells Chrome:
	•	Which files are part of the extension,
	•	Permissions (activeTab, storage, scripting),
	•	Which script to inject into web pages (content_script.js),
	•	Which file is the popup (popup.html),
	•	Which URLs the extension is allowed to call (http://127.0.0.1:5000/*).
	•popup.html + popup.js
	•	Renders the small panel you see when clicking the extension icon.
	•Lets the user:
	•	Grab selected text or full page text.
	•	Send it to the AutoPolicy backend for risk analysis.
	•	See the list of risky clauses and overall grade.
	•	Highlight a clause back on the page.
	•	Translate a clause to Marathi or Hindi.
	•content_script.js
	•	Runs inside each web page.
	•	Can read the text that the user selected.
	•	Can modify the page (for highlight).
	•	Communicates with the popup via chrome.runtime.sendMessage.

⸻

Step 1 – Page loads → content script + highlight styles are injected

Whenever you open a new tab or navigate to a page, Chrome injects:
content_script.js
(because of the "content_scripts" section in manifest.json).

Internally, content_script.js does:
	1.Injects CSS for highlights only once per page:
	•It creates a <style> tag with classes like:
                . Autopolicy -highlights
                . autopolicy-riksy- low (Yellow)
                . autopolicy-riksy- medium (Orange)
                 . autopolicy-riksy- high (Red)

•	Each highlight has a small pulse animation to draw attention.

	2.Defines helper functions:
	•getSelectionText()
	•	Returns the text currently selected by the user on the page.
	•	getFullPageText()
	•	Returns the entire document.body.innerText as plain text.
	•	highlightClauseOnPage(text, severity, doScroll)
	•	Finds a matching snippet in the page HTML using a regex.
	•	Wraps the matching text in:
   
       <span class="autopolicy-highlight autopolicy-risk-XXX autopolicy-focus-pulse">
  ...clause text...
</span>

          •Scrolls the page so that the highlighted clause is centered.
	•Removes the pulse class after the animation.
3.Sets up a message listener:

chrome.runtime.onMessage.addListener(…)

It listens for messages from the popup:
	•	GET_SELECTION → reply with { text: selectedText }
	•	GET_FULL_PAGE_TEXT → reply with { text: fullPageText, url: window.location.href }
	•	HIGHLIGHT_CLAUSE → call highlightClauseOnPage(...)

Files created in this step:
	•	None. Everything is done in browser memory and DOM.

Step 2 – User opens the popup and grabs text

Action: User clicks the AutoPolicy extension icon in the toolbar.

This opens popup.html, which is connected to popup.js.

Inside the popup:
	1.	User chooses input source:
	•	“Use selection” → ask the content script for just the selected text.
	•	“Full page” → ask for innerText of the whole page.
	2.	popup.js sends a message to the content script:
	•	To get selection:  { "type": "GET_SELECTION" }
 		•	To get full page text: { "type": "GET_FULL_PAGE_TEXT" }
	3.content_script.js replies with the text, and popup shows it in a text area, like:  [Selected or full-page text here…]
Files created in this step:
	•	Still none. Only messages between popup and content script.

Step 3 – Risk analysis via backend API (/api/analyze-text)

Action: User clicks “Analyze risk” in the popup.

Internally, popup.js:
	1.	Reads the text from the popup’s text area.
	2.	Optionally includes user_email (for future multi-user features).
	3.	Sends an HTTP POST to the local backend:

  POST http://127.0.0.1:5000/api/analyze-text
Content-Type: application/json

{
  "text": "<selected or full-page text>",
  "user_email": "<logged-in email (optional)>",
  "page_url": "<current tab URL (optional)>"
}

Backend side: app.py → /api/analyze-text

The Flask route /api/analyze-text:
	1.	Gets the raw text from JSON.
	2.	Splits it into clauses using the regex: r”(?<=[.!?;])\s+|\n+"
	3.	For each clause, calls the rule-based risk engine:
          is_risky, reasons, score = score_clause_simple(clause_text)
    Example rules:
	•Phrases like "may share your personal data" → tag data_sharing, score 3.
	•"we are not liable for" → tag generic_risk, score 2.
         •”non-refundable", "all sales are final" → tag fees_charges, score 2.

	4.Builds:
	•	total_clauses
	•	risky_clauses list (clause number, text, tags, score)
	•	risky_percent
	•	overall_rating (A/B/C/D)
	•	risk_breakdown (tag → count)
	5.Returns a JSON response like:
{
  "ok": true,
  "total_clauses": 42,
  "risky_clauses": [
    {
      "clause_number": 5,
      "text": "We are not liable for indirect or consequential damages...",
      "score": 2,
      "reasons": ["generic_risk"]
    },
    ...
  ],
  "risky_percent": 9.52,
  "overall_rating": "C",
  "risk_breakdown": {
    "generic_risk": 3,
    "data_sharing": 1
  },
  "risky_clauses_count": 4,
  "grade": "C"
}

Important:
The extension flow does not store anything in the database during this API call.
/api/analyze-text is a stateless analysis endpoint used for quick checks.

Step 4 – Popup UI renders results + sends highlight commands

Once the popup receives the JSON:

	1.It shows a summary at the top, for example:
	•	“Total clauses: 42”
	•	“Risky clauses: 4”
	•	“Grade: C (medium risk)”

	2.It lists each risky clause with:
	•	Clause number.
	•	Short snippet of the text.
	•	Risk score / tags.

	3.For each clause row, there is a “Highlight on page” (or click action).
When the user clicks Highlight, popup.js sends a message to the content script:
{
  "type": "HIGHLIGHT_CLAUSE",
  "text": "<clause text>",
  "severity": "low" | "medium" | "high"
}

•	The severity is derived from the score:
	•	score = 1 → "low" (yellow).
	•	score = 2 → "medium" (orange).
	•	score = 3 → "high" (red).

	4.The content script receives this message and calls:

                   highlightClauseOnPage(clauseText, severity, true);
Which:
	•Locates a matching snippet in document.body.innerHTML.
	•Replaces the first match with:
<span class="autopolicy-highlight autopolicy-risk-high autopolicy-focus-pulse">
  ...text...
</span>

	•Scrolls smoothly so that the span is in the center.
	•Removes the pulse after ~1.2 seconds.

Files created in this step:
	•None. This step only updates the web page DOM temporarily.

Step 5 – On-demand translation (Marathi / Hindi)

The popup also supports per-clause translation into Marathi or Hindi.

Action: User selects a clause in the popup and chooses “Translate → Marathi/Hindi”.

Internally:
	1.popup.js sends a POST to: 

POST http://127.0.0.1:5000/api/translate-text
Content-Type: application/json

{
  "text": "<clause text>",
  "target_lang": "marathi" | "hindi" | "mr" | "hi"
}
Backend side: app.py → /api/translate-text
	1.	Maps the target_lang:
	•	"marathi" → "mr"
	•	"hindi" → "hi"
	2.	Uses googletrans.Translator:
  			translator.translate(text, dest=lang_code)

	3.	Returns:{
  "ok": true,
  "translated_text": "मराठी / हिंदी भाषेतील क्लॉज...",
  "target_lang": "mr"
}
The popup shows the translated clause right below the original English clause.

Again, no files are written to disk — it’s just API in / API out.
