// content_script.js
// Runs inside each web page.
// - Returns selection / full page text
// - Highlights matched clause when popup sends HIGHLIGHT_CLAUSE

// ========== Inject CSS once ==========
(function injectAutopolicyStyle() {
  try {
    if (document.getElementById("autopolicy-highlight-style")) return;

    const style = document.createElement("style");
    style.id = "autopolicy-highlight-style";
    style.textContent = `
      .autopolicy-highlight {
        border-radius: 2px;
        padding: 2px 3px;
        cursor: pointer;
        transition: box-shadow 0.15s ease-out, background-color 0.15s ease-out;
      }

      /* only clause blocks, not whole page */
      .autopolicy-risk-low {
        background-color: rgba(255, 255, 0, 0.25);   /* soft yellow */
      }

      .autopolicy-risk-medium {
        background-color: rgba(255, 165, 0, 0.28);   /* soft orange */
      }

      .autopolicy-risk-high {
        background-color: rgba(239, 68, 68, 0.25);   /* soft red */
        box-shadow: 0 0 0 1px rgba(239, 68, 68, 0.8);
      }

      .autopolicy-highlight.autopolicy-focus-pulse {
        animation: autopolicy-pulse 1.2s ease-out 1;
      }

      @keyframes autopolicy-pulse {
        0%   { box-shadow: 0 0 0 0 rgba(255, 255, 255, 0.7); }
        100% { box-shadow: 0 0 0 7px rgba(255, 255, 255, 0); }
      }
    `;
    document.head.appendChild(style);
  } catch (e) {
    console.warn("AutoPolicy: could not inject style:", e);
  }
})();

// ========== Helpers: clear previous highlights ==========

function clearAutopolicyHighlights() {
  try {
    const els = document.querySelectorAll(".autopolicy-highlight");
    els.forEach((el) => {
      el.classList.remove(
        "autopolicy-highlight",
        "autopolicy-risk-low",
        "autopolicy-risk-medium",
        "autopolicy-risk-high",
        "autopolicy-focus-pulse"
      );
    });
  } catch (e) {
    console.warn("AutoPolicy: failed to clear highlights:", e);
  }
}

// ========== Helpers: selection & full page text ==========

function getSelectionText() {
  const sel = window.getSelection && window.getSelection();
  return sel ? sel.toString() : "";
}

function getFullPageText() {
  try {
    return document.body.innerText || "";
  } catch (e) {
    console.warn("AutoPolicy: could not read innerText:", e);
    return "";
  }
}

// ========== Helper: regex for snippet (whitespace tolerant) ==========

function escapeForRegex(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function buildSnippetRegexFromText(fullText) {
  // Collapse whitespace in the clause we got from backend
  let cleaned = fullText.replace(/\s+/g, " ").trim();
  if (!cleaned) return null;

  // Keep snippet reasonably short
  if (cleaned.length > 200) {
    cleaned = cleaned.slice(0, 200);
  }

  let escaped = escapeForRegex(cleaned);
  // Any whitespace in the clause becomes \s+ to match newlines/tabs/etc.
  escaped = escaped.replace(/\s+/g, "\\s+");

  try {
    return { regex: new RegExp(escaped, "i"), snippetLen: cleaned.length };
  } catch (e) {
    console.warn("AutoPolicy: could not build regex:", e);
    return null;
  }
}

// ========== Highlight clause: choose *smallest matching block* ==========

function highlightClauseOnPage(text, severity, doScroll) {
  if (!text || !document.body) return;

  clearAutopolicyHighlights();

  const built = buildSnippetRegexFromText(text);
  if (!built) return;
  const re = built.regex;
  const snippetLen = built.snippetLen;

  // Candidate elements that usually hold clauses
  const nodeList = document.querySelectorAll("p, li, div, span");
  const candidates = [];

  nodeList.forEach((el) => {
    const rawText = el.innerText || "";
    if (!rawText.trim()) return;

    const normalized = rawText.replace(/\s+/g, " ").trim();
    if (!normalized) return;

    const len = normalized.length;

    // Ignore gigantic containers and super-short items
    if (len < snippetLen * 0.6) return;
    if (len > snippetLen * 6) return;   // avoid whole-page containers

    if (re.test(normalized)) {
      candidates.push({ el, len });
    }
  });

  if (candidates.length === 0) {
    console.warn("AutoPolicy: no matching clause element found for snippet.");
    return;
  }

  // Choose the smallest matching element = closest to actual clause
  candidates.sort((a, b) => a.len - b.len);
  const target = candidates[0].el;

  target.classList.add("autopolicy-highlight");
  if (severity === "high") {
    target.classList.add("autopolicy-risk-high");
  } else if (severity === "medium") {
    target.classList.add("autopolicy-risk-medium");
  } else {
    target.classList.add("autopolicy-risk-low");
  }

  if (doScroll !== false) {
    target.classList.add("autopolicy-focus-pulse");
    try {
      target.scrollIntoView({ behavior: "smooth", block: "center" });
    } catch (_) {
      target.scrollIntoView();
    }
    setTimeout(() => {
      target.classList.remove("autopolicy-focus-pulse");
    }, 1400);
  }
}

// ========== Message listener from popup.js ==========

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (!message || !message.type) return;

  if (message.type === "GET_SELECTION") {
    const text = getSelectionText();
    sendResponse({ text });
    return;
  }

  if (message.type === "GET_FULL_PAGE_TEXT") {
    const text = getFullPageText();
    sendResponse({ text, url: window.location.href });
    return;
  }

  if (message.type === "HIGHLIGHT_CLAUSE") {
    const clauseText = message.text || "";
    const severity = message.severity || "low";
    const scroll = message.scroll !== false;
    highlightClauseOnPage(clauseText, severity, scroll);
    return;
  }
});