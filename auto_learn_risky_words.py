#!/usr/bin/env python3
"""
auto_learn_risky_words.py
=========================

HIGH-LEVEL PURPOSE
------------------
This script auto-learns *new risky tokens* from your already-scored clauses
and updates:

  1) legal_vocab.json      -> by adding new "auto_*" token groups
  2) risk_templates.json   -> by attaching those auto-groups to templates

It uses an existing *scored CSV* where each clause already has:
  - model_is_risky (TRUE / FALSE)
  - model_risk_reason (like "data_sharing", "account_closure", "fees_charges")

Typical FLOW (end to end)
-------------------------
INPUT:
  - SCORED_CSV (e.g. clause_extracted_..._scored.csv)
  - legal_vocab.json
  - risk_templates.json

PROCESS:
  1) Read scored CSV.
  2) For every row with model_is_risky = TRUE:
       - Look at model_risk_reason (e.g. "data_sharing").
       - Tokenize the clause text.
       - Ignore short words, stopwords, and tokens already in vocab.
       - Count how often each new token appears per risk tag.
  3) For each tag (like "data_sharing"):
       - Create an auto group name: auto_data_sharing_tokens
       - Add newly discovered tokens into this group in legal_vocab.json.
  4) Attach these auto groups into risk_templates.json:
       - For each template with tag "data_sharing",
         add "auto_data_sharing_tokens" to its "objects" list.

OUTPUT:
  - Updated legal_vocab.json  (with auto_* groups)
  - Updated risk_templates.json (templates now use those auto groups)

EFFECT:
  Your risk detector becomes *smarter over time*:
  after running this script, new tokens (e.g. "brokerage", "surcharge")
  will now be recognized as risky in future documents.
"""

#Scored CSV मधून TRUE risky clauses घे → त्यातून नवीन meaningful tokens शोध → tag-wise tokens count कर → auto__tokens नावाने vocab मध्ये 
#add कर → templates मध्ये attach कर → JSON save कर.

# ============================================================
# 1. IMPORTS AND CONSTANTS
# ============================================================

import csv          # reading the scored CSV file
import json         # reading and writing JSON vocab/templates
import re           # simple regex-based tokenization
from collections import defaultdict  # nested counting structures

# ---------------- CONFIG: INPUT / OUTPUT FILE NAMES ----------------

# This CSV contains clauses that have already been scored by your
# risk engine (model_is_risky + model_risk_reason).
SCORED_CSV = "clause_extracted_text_20251112_175748_sentences_spaCy_grammar_scored.csv"

# Column names from the scored CSV
TEXT_COL = "text"                    # clause text column
MODEL_RISK_FLAG_COL = "model_is_risky"      # TRUE / FALSE
MODEL_RISK_REASON_COL = "model_risk_reason" # tag(s) like data_sharing,fees_charges,...

# JSON files used by your main risk detector
VOCAB_JSON = "legal_vocab.json"       # contains token groups (like actions, objects, etc.)
TEMPLATES_JSON = "risk_templates.json"  # contains rule templates

# -------------------------------------------------------------------
# Mapping: risk_tag -> where to attach auto-group in templates
# -------------------------------------------------------------------
# For each risk tag (like "data_sharing"), we will create a group name:
#   auto_<tag>_tokens
# and attach that group to this field in the template, usually "objects".
TAG_ATTACHMENT_TARGET = {
    "account_closure": "objects",
    "data_sharing": "objects",
    "fees_charges": "objects",
}

# -------------------------------------------------------------------
# STOPWORDS: tokens we *ignore* when auto-learning
# -------------------------------------------------------------------
# These are common words that don't carry "risky" meaning on their own.
STOPWORDS = {
    "the", "and", "for", "with", "this", "that", "from", "into", "your", "you",
    "shall", "may", "will", "any", "all", "are", "our", "such", "its", "not",
    "been", "have", "has", "hereby", "thereof", "herein", "thereby", "whereas",
    "per", "under", "been", "than", "more", "less", "only"
}

# ============================================================
# 2. BASIC TOKENIZER
# ============================================================

def tokenize(text: str):
    """
    Turn a clause into simple tokens.

    Steps:
      1) Lowercase the text.
      2) Split on any non-alphanumeric character using regex:
            [^a-zA-Z0-9]+
      3) Filter out empty strings.

    Example:
      "We may charge additional penalty fees." ->
        ["we", "may", "charge", "additional", "penalty", "fees"]
    """
    # Make everything lowercase so comparison is easier
    tokens = re.split(r"[^a-zA-Z0-9]+", text.lower())
    # Remove empty tokens
    return [t for t in tokens if t]


# ============================================================
# 3. LOADING VOCAB AND TEMPLATES
# ============================================================

def load_vocab():
    """
    Load legal_vocab.json and also compute a set of *known* tokens.

    Returns:
      vocab        : dict (original JSON structure)
      known_tokens : set of lowercase tokens already present in vocab

    Why we need known_tokens:
      When we discover new tokens, we want to skip anything that's
      already part of the existing vocab. So we build a big set of
      all words in vocab (including parts of multi-word phrases).
    """
    # Read JSON file into a Python dict
    with open(VOCAB_JSON, "r", encoding="utf-8") as f:
        raw = json.load(f)

    # Build a set of all known tokens (single words)
    known_tokens = set()

    # raw is like:
    # {
    #   "data_terms": ["personal data", "information", ...],
    #   "actions_share": ["disclose", "share", ...],
    #   ...
    # }
    for words in raw.values():
        for item in words:
            # Add the whole phrase in lowercase
            known_tokens.add(item.lower())

            # Also split multi-word phrases and add each part
            # e.g. "personal data" -> "personal", "data"
            for part in item.lower().split():
                known_tokens.add(part)

    return raw, known_tokens


def load_templates():
    """
    Load risk_templates.json and return as a Python list/dict.

    This file typically looks like:
      [
        {
          "tag": "data_sharing",
          "actions": ["share_actions", ...],
          "objects": ["data_terms", ...],
          ...
        },
        ...
      ]
    """
    with open(TEMPLATES_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


# ============================================================
# 4. DISCOVER NEW TOKENS FROM SCORED CSV
# ============================================================

def discover_new_tokens():
    """
    Core discovery step.

    Reads SCORED_CSV and builds a structure:

      tag_token_counts[tag][token] = frequency

    Logic per CSV row:
      - Only consider rows where model_is_risky == TRUE.
      - Read model_risk_reason (can contain one or multiple tags).
      - Tokenize the clause text.
      - For each token:
          * ignore if < 4 characters
          * ignore if in STOPWORDS
          * ignore if already in known_tokens
          * otherwise: count it under each associated risk tag.
    """
    # Load vocab and templates first
    vocab, known_tokens = load_vocab()
    templates = load_templates()

    # Nested dict:
    #   { "data_sharing": {"brokerage": 3, "analytics": 5, ...}, ... }
    tag_token_counts = defaultdict(lambda: defaultdict(int))

    # Open the scored CSV (output of your earlier risk engine)
    with open(SCORED_CSV, "r", encoding="utf-8") as fin:
        reader = csv.DictReader(fin)

        for row in reader:
            # 1) Only process rows that are actually marked risky
            flag = row.get(MODEL_RISK_FLAG_COL, "").strip().upper()
            if flag != "TRUE":
                continue

            # 2) Get risk reasons (e.g., "data_sharing,fees_charges")
            reasons = row.get(MODEL_RISK_REASON_COL, "")
            if not reasons:
                continue

            # Split by comma and clean each tag
            tags = [t.strip() for t in reasons.split(",") if t.strip()]
            if not tags:
                continue

            # 3) Get clause text and tokenize
            text = row.get(TEXT_COL, "") or ""
            tokens = tokenize(text)

            # 4) For every token, decide whether to consider it or skip
            for tok in tokens:
                # Ignore very short tokens (like "of", "to", "in")
                if len(tok) < 4:
                    continue

                # Ignore stopwords (common non-risky words)
                if tok in STOPWORDS:
                    continue

                # Ignore tokens already known in vocab
                if tok in known_tokens:
                    continue

                # 5) If token passes filters, count it for each risk tag
                for tag in tags:
                    tag_token_counts[tag][tok] += 1

    # Return:
    #   vocab: original vocab dict
    #   templates: original templates list
    #   tag_token_counts: new token frequencies per tag
    return vocab, templates, tag_token_counts


# ============================================================
# 5. UPDATE VOCAB + TEMPLATES WITH NEW TOKENS
# ============================================================

def update_vocab_and_templates(vocab, templates, tag_token_counts):
    """
    Update both vocab and templates using discovered tokens.

    1) For each tag (e.g. "data_sharing"):
         - Build auto_group = "auto_data_sharing_tokens".
         - Take tag_token_counts[tag] (token -> freq).
         - Sort tokens by frequency (highest first).
         - Add these tokens into vocab[auto_group] (if not already present).

    2) For each template in templates:
         - If template.tag == <tag>, attach auto_group to the
           appropriate field (usually "objects"), based on TAG_ATTACHMENT_TARGET.
    """

    # ---------- 5.1 Update vocab with auto_* token groups ----------

    for tag, tok_counts in tag_token_counts.items():
        # If no new tokens for this tag, skip
        if not tok_counts:
            continue

        # Example: tag = "data_sharing" -> auto_data_sharing_tokens
        auto_group = f"auto_{tag}_tokens"

        # Get existing words in this group (if group already exists)
        # Make them lowercase for consistent comparison.
        existing = set(w.lower() for w in vocab.get(auto_group, []))

        # Sort candidate tokens by frequency (most common first)
        sorted_tokens = sorted(tok_counts.items(), key=lambda kv: kv[1], reverse=True)

        added = []  # track which tokens we actually added

        for tok, cnt in sorted_tokens:
            # Only add if it's not already in the group
            if tok not in existing:
                existing.add(tok)
                added.append(tok)

        # If we actually added something, update vocab
        if added:
            # Store sorted list in vocab for reproducibility
            vocab[auto_group] = sorted(existing)
            print(f"[INFO] Tag '{tag}': adding {len(added)} new tokens to group '{auto_group}'")
        else:
            print(f"[INFO] Tag '{tag}': no new tokens to add")

    # ---------- 5.2 Attach auto_* groups to templates ----------

    # Build map: tag -> auto group name
    # e.g. "data_sharing" -> "auto_data_sharing_tokens"
    tag_to_auto_group = {tag: f"auto_{tag}_tokens" for tag in tag_token_counts.keys()}

    # Now loop over each template and attach the auto group if needed
    for tpl in templates:
        # Every template has something like: {"tag": "data_sharing", ...}
        tag = tpl.get("tag")
        if tag not in tag_to_auto_group:
            # This template tag didn't appear in scored CSV; skip
            continue

        auto_group = tag_to_auto_group[tag]

        # Decide which field to attach to (e.g. "objects")
        target_field = TAG_ATTACHMENT_TARGET.get(tag, "objects")

        # Ensure the target field exists and is a list
        groups_list = tpl.setdefault(target_field, [])

        # If auto_group is not already in that list, append it
        if auto_group not in groups_list:
            groups_list.append(auto_group)
            print(f"[INFO] Template for tag '{tag}': attached '{auto_group}' to '{target_field}'")

    # Return updated vocab and templates
    return vocab, templates


# ============================================================
# 6. SAVE UPDATED JSON FILES
# ============================================================

def save_vocab(vocab):
    """
    Write the updated vocab back to legal_vocab.json
    with indentation and UTF-8 encoding.
    """
    with open(VOCAB_JSON, "w", encoding="utf-8") as f:
        json.dump(vocab, f, indent=2, ensure_ascii=False)
    print(f"[DONE] Updated vocab written to {VOCAB_JSON}")


def save_templates(templates):
    """
    Write the updated templates back to risk_templates.json
    with indentation and UTF-8 encoding.
    """
    with open(TEMPLATES_JSON, "w", encoding="utf-8") as f:
        json.dump(templates, f, indent=2, ensure_ascii=False)
    print(f"[DONE] Updated templates written to {TEMPLATES_JSON}")


# ============================================================
# 7. MAIN ENTRY POINT
# ============================================================

def main():
    """
    Full script runner.

    Steps:
      1) Call discover_new_tokens() to collect new tokens.
      2) If nothing new is found, print message and exit.
      3) Otherwise, call update_vocab_and_templates().
      4) Save updated vocab + templates.
    """
    print("[INFO] Discovering new risky tokens from scored CSV...")

    vocab, templates, tag_token_counts = discover_new_tokens()

    # Check if we discovered any new tokens for any tag
    if not any(tag_token_counts.values()):
        print("[INFO] No new tokens discovered (no TRUE rows or all tokens already known).")
        return

    # Update vocab and templates in memory
    vocab, templates = update_vocab_and_templates(vocab, templates, tag_token_counts)

    # Write changes back to disk
    save_vocab(vocab)
    save_templates(templates)

    print("[INFO] Auto-learning completed. You can now re-run risky_phrase_detector.py")


# Standard "run if executed as a script"
if __name__ == "__main__":
    main()