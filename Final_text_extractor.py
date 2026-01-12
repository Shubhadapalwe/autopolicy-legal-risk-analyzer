"""
FINAL_TEXT_EXTRACTOR.PY
=======================

High-level story of this program (end-to-end):

INPUT (what you give):
----------------------
You can run this script in three ways:
1) No argument:
       python3 Final_text_extractor.py
   → It will treat the *current folder* (.) as input and scan it.

2) With a folder path:
       python3 Final_text_extractor.py path/to/folder
   → It will scan that folder for PDFs and images.

3) With a single file:
       python3 Final_text_extractor.py some.pdf
       python3 Final_text_extractor.py some_image.png
   → It will process only that file.

WHAT IT DOES INTERNALLY:
------------------------
For each PDF:
  1. Try to extract text directly using PyPDF2.
  2. If direct extraction fails or returns almost nothing:
        - Convert PDF pages to images.
        - Use Tesseract OCR on the images to read text.
  3. Clean the extracted text:
        - Remove headers/footers patterns (like "Page 1", "HEADER…").
        - Fix hyphenated words broken across lines.
        - Remove soft hyphens.
        - Remove duplicate lines.
  4. Save the cleaned text to:
        extracted_text_<TIMESTAMP>.txt
  5. Run spaCy NLP on that text:
        - Extract named entities (names, orgs, dates, etc.).
        - Save them into:
            entities_<TIMESTAMP>.csv
  6. Split the text into sentences and legal-like clauses:
        - Use spaCy sentence segmentation.
        - Then split each sentence into sub-clauses using legal markers
          like “provided that”, “unless”, “however”, “whereas”, “;”
        - Save this as:
            sentence_clause_segments_<TIMESTAMP>.csv
  7. Move the original PDF into:
        <folder>/processed/

For images (JPG/PNG):
  1. Collect unprocessed images from the folder.
  2. Combine them into ONE PDF: combined_document_<TIMESTAMP>.pdf
  3. Run the **same processing pipeline** on that PDF (steps 1–7 above).
  4. Move the original images into <folder>/processed/

For a folder:
  1. Find all PDFs not in "processed/".
  2. Find all images not in "processed/".
  3. Process PDFs one by one.
  4. Then, if there are images, combine them into a PDF and process.
  5. If nothing new is found, print a message and stop.

OUTPUT (what you get):
----------------------
After a successful run, you will see:
  - extracted_text_<TIMESTAMP>.txt        → full cleaned text
  - sentence_clause_segments_<TIMESTAMP>.csv → sentences + clauses
  - entities_<TIMESTAMP>.csv              → NLP entities
  - combined_document_<TIMESTAMP>.pdf     → (if images were converted)
  - Original PDFs/images moved into:
        <input_folder>/processed/

This file is the *first stage* of your AutoPolicy system:
“Take any legal PDF / screenshot → produce clean text and structure
so that later scripts can detect risky clauses.”
"""

# ------------------------- IMPORTS ------------------------- #

import os                 # For file/folder paths, checking files, making dirs.
import sys                # For reading command-line arguments (sys.argv).
import shutil             # For moving/copying files (used to move processed files).
from PIL import Image     # For opening images (JPG/PNG) and saving them as PDF.
import pytesseract        # For OCR: extracting text from images.
from pdf2image import convert_from_path  # For converting PDF pages into images.
import PyPDF2             # For reading PDFs and extracting text directly.
import re                 # For cleaning text using regular expressions.
import spacy              # For NLP: sentence splitting, entity recognition.
import pandas as pd       # For building and saving CSV tables.
from datetime import datetime  # For generating timestamp strings.
import csv                # For simple CSV writing (entity export).

# ----------------------------------------------------------- #
# NOTE: There is an older, commented-out "legal keyword" check
# kept here for reference. Right now, your pipeline processes
# any document; it does not filter only "legal" ones.
# ----------------------------------------------------------- #

# LEGAL_KEYWORDS = [
#     'affidavit', 'agreement', 'contract', 'court', 'deed',
#     'judgement', 'power of attorney', 'plaintiff', 'defendant',
#     'license', 'notary', 'government', 'section', 'article',
#     'witness', 'stamp', 'seal'
# ]
#
# def is_legal_document(text):
#     """
#     Simple detector:
#     - Converts text to lowercase.
#     - Checks if any word from LEGAL_KEYWORDS is present.
#     - Returns True if yes (likely legal), otherwise False.
#     """
#     lower = text.lower()
#     return any(kw in lower for kw in LEGAL_KEYWORDS)

# ----------------------------------------------------------- #
# 1) IMAGES → SINGLE PDF
# ----------------------------------------------------------- #

def images_to_pdf(image_files, output_pdf):
    """
    Purpose:
      Take a list of image file paths and combine them into
      a single multi-page PDF.

    Steps:
      1. Open each image and convert to RGB (to be safe for PDF).
      2. Save the first image as a PDF.
      3. Append the rest as extra pages.
      4. Print a small log message.

    Parameters:
      image_files: list of strings, each is a path to an image file.
      output_pdf : string, path to the PDF that will be created.
    """
    # Open each image path as a Pillow Image and convert to RGB mode.
    images = [Image.open(f).convert('RGB') for f in image_files]

    # Save the first image as a PDF and append the others as pages.
    images[0].save(output_pdf, save_all=True, append_images=images[1:])

    
    print(f'[INFO] PDF created: {output_pdf}')


# ----------------------------------------------------------- #
# 2) EXTRACT TEXT FROM PDF (DIRECT + OCR FALLBACK)
# ----------------------------------------------------------- #

def extract_text_from_pdf(pdf_file):

    #“pahilyanda direct text kadhaycha prayatna, nahi jamla tar OCR ne image madhun kadhaycha.”
    """
    Try to read text from a PDF in two stages:

    1) DIRECT MODE (no OCR):
       - Use PyPDF2.PdfReader to read each page.
       - Call page.extract_text().
       - Concatenate all non-empty page texts.

    2) OCR MODE (fallback):
       - If the direct text is empty or almost blank:
         * Convert each page to an image using pdf2image.
         * Run Tesseract OCR on each page image.
         * Concatenate the OCR text.

    Returns:
       A single big string containing all text we managed to extract
       (possibly empty if everything failed).
    """
    text = ""  # Collect all text in this variable.

    try:
        # Try to open the PDF using PyPDF2.
        reader = PyPDF2.PdfReader(pdf_file)

        # Loop over each page object.
        for page in reader.pages:
            # Extract text from the page.
            page_text = page.extract_text()

            # If we actually got some text, add it to our accumulator.
            if page_text:
                text += page_text + "\n"

        # If text is still empty or just whitespace, try OCR.
        if not text.strip():
            # Convert all pages of the PDF into Pillow Image objects.
            pages = convert_from_path(pdf_file)

            # Run OCR on each image page and append.
            for img in pages:
                text += pytesseract.image_to_string(img)

    except Exception as e:
        # If anything goes wrong (bad file, corrupt PDF, etc.), log the error.
        print(f'[ERROR] Could not extract text from {pdf_file}: {e}')

    # Return whatever text we have (empty string if totally failed).
    return text


# ----------------------------------------------------------- #
# 3) CLEAN EXTRACTED TEXT
# ----------------------------------------------------------- #

def clean_text(text):
    #“PDF madhun आलेla noisy text clean karun, headers/footers + broken words + duplicate lines remove करून 
    # neat text return karte.”
    """
    Clean up the raw extracted text so that later steps
    (sentence splitting, clause detection) work better.

    Cleaning steps:
      1. Remove obvious header/footer patterns (e.g. "Page 1", "HEADER…").
      2. Fix words broken across lines with a hyphen.
      3. Remove soft hyphen characters.
      4. Remove duplicate lines while preserving order.
      5. Trim leading/trailing blank spaces.
    """

    # 1) Remove simple page headers/footers using a regex pattern.
    text = re.sub(r'(Page \d+|HEADER.*|FOOTER.*)', '', text)

    # 2) Join hyphenated line breaks: turn "agree-\nment" into "agreement".
    text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)

    # 3) Remove soft hyphen characters (often appear in PDFs).
    text = re.sub(r'[\u00AD]', '', text)

    # 4) Remove duplicate lines:
    #    - Split into lines.
    #    - Make dict keys from lines (dict removes duplicates).
    #    - Join keys back into a single string.
    lines = text.splitlines()
    unique_lines = list(dict.fromkeys(lines))
    text = "\n".join(unique_lines)

    # 5) Remove leading/trailing whitespace.
    return text.strip()


# ----------------------------------------------------------- #
# 4) NLP ENTITY EXTRACTION
# ----------------------------------------------------------- #

def nlp_operations(txt_file, entity_csv_file):
    """
    Use spaCy to find named entities (like names, organizations,
    dates, money, locations) in the cleaned text.

    INPUT:
      txt_file       - path to a text file with cleaned document text.
      entity_csv_file - path to CSV where we write entities.

    OUTPUT:
      CSV with two columns:
        Entity_Text, Entity_Type
      Example:
        "HDFC Bank", ORG
        "31 December 2024", DATE
    """

    # Load the small English language model.
    # It contains tokenization, POS tags, NER, etc.
    nlp = spacy.load('en_core_web_sm')

    # Read the full cleaned text from file.
    with open(txt_file, 'r', encoding='utf-8') as f:
        text = f.read()

    # Process the text with spaCy (creates a Doc object).
    doc = nlp(text)

    # Open the output CSV file for writing.
    with open(entity_csv_file, 'w', encoding='utf-8', newline='') as csvfile:
        writer = csv.writer(csvfile)

        # Write header row.
        writer.writerow(['Entity_Text', 'Entity_Type'])

        # Write each entity as a row.
        for ent in doc.ents:
            writer.writerow([ent.text, ent.label_])

    # Log success.
    print(f"[SUCCESS] NLP entities saved to {entity_csv_file}")


# ----------------------------------------------------------- #
# 5) SPLIT A SENTENCE INTO CLAUSES
# ----------------------------------------------------------- #

#hi segment_clauses(sentence) hi function ekach sentence gheun tyala lahaan parts (clauses) madhe todte.

#ka karaycha?

#legal sentences khup long astat ani tyat multiple conditions astat.
#example:
#“You may close…; however, the bank may retain…”

#apanla asa हवे:
#	•	Clause 1: “You may close the account at any time”
#	•	Clause 2: “the bank may retain fees already charged”

#mhanun sentence todun clauses kadhle ki पुढचा risk detection / rule matching सोपा hoto.
#“Sentence madhun legal connector words ani semicolon var split karun, neat clauses chi list return karte.”

def segment_clauses(sentence):
    """
    Take a *single sentence* and break it into smaller "clauses".

    Why?
      Legal sentences are often long and contain multiple conditions.
      For example:
        "You may close the account at any time; however, the bank
         may retain fees already charged."

      We want:
        - Clause 1: "You may close the account at any time"
        - Clause 2: "the bank may retain fees already charged"

    Strategy:
      - Split on:
          * semicolon ';'
          * key legal connectors: 'provided that', 'except', 'unless',
            'however', 'whereas'
      - Remove empty pieces and trim spaces.
    """

    # List of patterns that indicate clause boundaries.
    patterns = [
        r';',
        r'\bprovided that\b',
        r'\bexcept\b',
        r'\bunless\b',
        r'\bhowever\b',
        r'\bwhereas\b',
    ]

    # Combine patterns into a single regex with OR (|).
    regex = '|'.join(patterns)

    # Split sentence using regex; strip each piece; keep only non-empty.
    clauses = [
        cl.strip()
        for cl in re.split(regex, sentence, flags=re.IGNORECASE)
        if cl.strip()
    ]

    return clauses


# ----------------------------------------------------------- #
# 6) FULL TEXT → SENTENCE + CLAUSE TABLE (CSV)
# ----------------------------------------------------------- #

def segment_text_to_csv(txt_file, output_csv):
    #hi segment_text_to_csv(txt_file, output_csv) hi function cleaned text gheun tyacha sentence + clause level var table tayar karte ani CSV madhe save karte.
#CSV format asa banto:
#Sentence_ID, Sentence, Clause_ID, Clause
#mhanje:
#	•	kontya sentence madhun clause ala?
#	•	sentence number kay?
#	•	clause number kay?
#	•	clause cha exact text kay?


    """
    Take the cleaned document text and build a table like this:

        Sentence_ID, Sentence, Clause_ID, Clause

    Steps:
      1. Load spaCy model.
      2. Read the full text from txt_file.
      3. Use spaCy to split the text into sentences.
      4. For each sentence, call segment_clauses() to get sub-clauses.
      5. Build a list of rows (Sentence_ID, Sentence, Clause_ID, Clause).
      6. Save it as a CSV file.
    """

    # 1) Load spaCy English model.
    nlp = spacy.load('en_core_web_sm')

    # 2) Read the entire cleaned text from file.
    with open(txt_file, 'r', encoding='utf-8') as f:
        text = f.read()

    # 3) Let spaCy process the text to produce sentences.
    doc = nlp(text)

    # Extract sentence strings, strip extra spaces.
    sentences = [sent.text.strip() for sent in doc.sents]

    # This list will hold dictionaries, one per clause.
    csv_rows = []

    # 4) For every sentence, get its clauses.
    for si, sentence in enumerate(sentences, start=1):
        # si = Sentence_ID (1-based index)
        clauses = segment_clauses(sentence)

        # 5) For each clause within this sentence, append a row.
        for ci, clause in enumerate(clauses, start=1):
            # ci = Clause_ID (1-based index)
            csv_rows.append({
                'Sentence_ID': si,
                'Sentence': sentence,
                'Clause_ID': ci,
                'Clause': clause,
            })

    # 6) Convert list of dicts into a DataFrame.
    df = pd.DataFrame(csv_rows)

    # 7) Save DataFrame to CSV (no index column).
    df.to_csv(output_csv, index=False)

    #“cleaned txt madhla text spaCy ne sentences madhe split, मग प्रत्येक sentence clauses madhe split,
    #  मग (Sentence_ID, Clause_ID) sahit table banवून CSV madhe save karte.”

    # 8) Log success.
    print(f"[SUCCESS] Sentences & clauses tabulated in {output_csv}")


# ----------------------------------------------------------- #
# 7) MOVE FILE TO "processed" FOLDER
# ----------------------------------------------------------- #

def move_to_processed(file_path, processed_folder):
    """
    Move a file into a 'processed' folder so we don't process it again.

    INPUT:
      file_path      - full path of the file we want to move.
      processed_folder - folder where the file should be moved.

    Behaviour:
      - If processed_folder does NOT exist, it will be created.
      - Then the file is moved inside it.
    """

    # If the folder does not exist, create all necessary parent dirs.
    if not os.path.exists(processed_folder):
        os.makedirs(processed_folder)

    # Build new full path in the processed folder.
    target_path = os.path.join(processed_folder, os.path.basename(file_path))

    # Move the file from original location to the new location.
    shutil.move(file_path, target_path)


# ----------------------------------------------------------- #
# 8) PROCESS A SINGLE PDF COMPLETELY
# ----------------------------------------------------------- #

def process_pdf(pdf_path, folder_path, timestamp):
    """
    Run the *full pipeline* for ONE PDF:

      1) Extract text (direct → OCR fallback).
      2) Clean text.
      3) Save cleaned text to extracted_text_<timestamp>.txt.
      4) Build sentence+clause CSV: sentence_clause_segments_<timestamp>.csv.
      5) Run NLP entity extraction → entities_<timestamp>.csv.
      6) Move the original PDF to <folder>/processed/.

    Parameters:
      pdf_path    - full path to the PDF that we want to process.
      folder_path - folder where we will save outputs.
      timestamp   - string used to make filenames unique.
    """

    # Log which PDF is being processed.
    print(f"[INFO] Processing PDF: {pdf_path}")

    # Build paths for the three main output files:
    # 1) Cleaned text file.
    txt_output = os.path.join(
        folder_path,
        f'extracted_text{("_" + timestamp) if timestamp else ""}.txt',
    )

    # 2) Entities CSV file.
    entity_output = os.path.join(
        folder_path,
        f'entities{("_" + timestamp) if timestamp else ""}.csv',
    )

    # 3) Sentence + clause CSV file.
    clause_output = os.path.join(
        folder_path,
        f'sentence_clause_segments{("_" + timestamp) if timestamp else ""}.csv',
    )

    # Extract raw text from the PDF (direct or OCR).
    text = extract_text_from_pdf(pdf_path)

    # If the text is empty or whitespace, we can't do anything useful.
    if not text.strip():
        print('[INFO] No text extracted.')
        return

    # Clean the extracted text for better downstream processing.
    text = clean_text(text)

    # Write cleaned text to the output text file.
    with open(txt_output, 'w', encoding='utf-8') as f:
        f.write(text)

    print(f'[SUCCESS] Text saved to {txt_output}')

    # Build sentence+clause CSV from the cleaned text.
    segment_text_to_csv(txt_output, clause_output)

    # Run NLP to find entities and save them.
    nlp_operations(txt_output, entity_output)

    # Move the original PDF into a "processed" subfolder.
    move_to_processed(pdf_path, os.path.join(folder_path, 'processed'))

    print(f"[INFO] Processed PDF moved to 'processed/'.")


# ----------------------------------------------------------- #
# 9) PROCESS A WHOLE FOLDER (PDFs + IMAGES)
# ----------------------------------------------------------- #

def process_folder(folder_path, use_timestamp=True):
    """
    Process all *new* PDFs and images in a folder.

    Steps:
      1) Create <folder_path>/processed if it does not exist.
      2) Find all PDFs in the folder that are NOT already in 'processed'.
      3) Find all images (.jpg/.jpeg/.png) that are NOT in 'processed'.
      4) If use_timestamp=True:
           - Create one timestamp string for this run.
      5) For each PDF:
           - Run process_pdf().
      6) If there are images:
           - Sort image paths for stable order.
           - Combine them into one PDF: combined_document_<timestamp>.pdf.
           - Run process_pdf() on that combined PDF.
           - Move all original images to 'processed'.
      7) If nothing new is found:
           - Print '[INFO] Nothing new to process in <folder_path>.'
    """

    # Define where processed items should go.
    processed_folder = os.path.join(folder_path, 'processed')

    # -------------------- FIND IMAGES -------------------- #
    # Collect image files (.jpg, .jpeg, .png) in the folder that
    # do NOT yet exist in 'processed/'.
    files = [
        os.path.join(folder_path, f)
        for f in os.listdir(folder_path)
        if f.lower().endswith(('.jpg', '.jpeg', '.png'))
        and not os.path.exists(os.path.join(processed_folder, f))
    ]

    # -------------------- FIND PDFs ---------------------- #
    # Collect PDF files in the folder that are not already in 'processed/'.
    pdf_files = [
        os.path.join(folder_path, f)
        for f in os.listdir(folder_path)
        if f.lower().endswith('.pdf')
        and not os.path.exists(os.path.join(processed_folder, f))
    ]

    # -------------------- TIMESTAMP ---------------------- #
    # If requested, generate a timestamp string to append to filenames.
    # Example: '20251221_120716'
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S') if use_timestamp else ""

    # -------------------- PROCESS PDFS ------------------- #
    # Sort to have deterministic order (alphabetical).
    for pdf_path in sorted(pdf_files):
        print(f"\n[INFO] Found PDF: {pdf_path}")
        process_pdf(pdf_path, folder_path, timestamp)

    # -------------------- PROCESS IMAGES ----------------- #
    # If we found image files, combine them into one PDF, then process.
    if files:
        # Sort image files for stable page order.
        files = sorted(files)

        # Path for the temporary combined PDF.
        pdf_output = os.path.join(
            folder_path,
            f'combined_document{("_" + timestamp) if timestamp else ""}.pdf',
        )

        # Convert the images into a multi-page PDF.
        images_to_pdf(files, pdf_output)

        # Process the newly created PDF.
        process_pdf(pdf_output, folder_path, timestamp)

        # Move each original image into 'processed/'.
        for img_path in files:
            move_to_processed(img_path, processed_folder)

        # Log how many images were moved.
        print(f"[INFO] {len(files)} images moved to '{processed_folder}'.")

    # -------------------- NOTHING NEW CASE --------------- #
    if not pdf_files and not files:
        print(f'[INFO] Nothing new to process in {folder_path}.')


# ----------------------------------------------------------- #
# 10) MAIN ENTRY POINT
# ----------------------------------------------------------- #

def main():
    """
    Decide what to do based on command-line argument.

    Usage examples:
      1) Process current folder:
           python3 Final_text_extractor.py

      2) Process a specific folder:
           python3 Final_text_extractor.py /path/to/folder

      3) Process a single PDF:
           python3 Final_text_extractor.py some_doc.pdf

      4) Process a single image:
           python3 Final_text_extractor.py flipkart_terms.png
    """

    print("Legal Document Extraction/NLP Pipeline with PDF Check")

    # If the user passed a path as first argument, use it.
    if len(sys.argv) > 1:
        input_path = sys.argv[1]
    else:
        # Otherwise, default to the current directory.
        input_path = '.'

    # -------------------- IF INPUT IS A FILE -------------------- #
    if os.path.isfile(input_path):

        # Case 1: PDF file
        if input_path.lower().endswith('.pdf'):
            # Build a timestamp for this run.
            ts = datetime.now().strftime('%Y%m%d_%H%M%S')

            # Process this single PDF in its own folder.
            process_pdf(
                input_path,
                os.path.dirname(input_path) or '.',  # folder path
                ts,
            )

        # Case 2: Single image file
        elif input_path.lower().endswith(('.jpg', '.jpeg', '.png')):
            # Create a temporary folder to treat the image as a "batch".
            temp_folder = 'temp_processing'

            # Ensure the temp folder exists.
            if not os.path.exists(temp_folder):
                os.makedirs(temp_folder)

            # Copy the image into the temp folder (we don't want to move original).
            shutil.copy(input_path, os.path.join(temp_folder, os.path.basename(input_path)))

            # Process the temp folder (this will combine image → PDF → extract).
            process_folder(temp_folder)

            # After processing, move the original image to a 'processed' folder
            # next to its original location.
            move_to_processed(input_path, os.path.join(os.path.dirname(input_path), 'processed'))

        # Case 3: Unsupported file type
        else:
            print("[ERROR] Please provide a folder, a PDF, or an image file.")

    # -------------------- IF INPUT IS A FOLDER ------------------- #
    elif os.path.isdir(input_path):
        # Process every new PDF and image in that folder.
        process_folder(input_path)

    # -------------------- INVALID PATH --------------------------- #
    else:
        print("[ERROR] Provided path does not exist or is unusable.")

    print("\nAll folders/files processed. Results saved automatically.")


# Standard Python entry point check.
if __name__ == '__main__':
    main()