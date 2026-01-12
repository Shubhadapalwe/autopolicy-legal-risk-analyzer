// popup.js – click on clause => highlight + scroll to it on page

document.addEventListener("DOMContentLoaded", () => {
  const emailInput = document.getElementById("email");
  const textArea = document.getElementById("text");
  const btnUseSelection = document.getElementById("btn-use-selection");
  const btnScanPage = document.getElementById("btn-scan-page");
  const btnClear = document.getElementById("btn-clear");
  const btnAnalyze = document.getElementById("btn-analyze");
  const statusDiv = document.getElementById("status");

  const resultsSection = document.getElementById("results-section");
  const riskPercentSpan = document.getElementById("risk-percent");
  const riskRatingSpan = document.getElementById("risk-rating");
  const riskCountSpan = document.getElementById("risk-count");
  const ratingPill = document.getElementById("rating-pill");
  const riskTypesDiv = document.getElementById("risk-types");
  const clausesListDiv = document.getElementById("clauses-list");

  let lastPageUrl = "";

  // ----------------------
  // Helpers
  // ----------------------

  function saveStateToStorage() {
    chrome.storage.local.set({
      autopolicy_email: emailInput ? emailInput.value : "",
      autopolicy_text: textArea ? textArea.value : ""
    });
  }

  function highlightInPage(clauseText, severity, scroll = true) {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (!tabs || !tabs[0]) return;
      chrome.tabs.sendMessage(tabs[0].id, {
        type: "HIGHLIGHT_CLAUSE",
        text: clauseText,
        severity: severity || "low",
        scroll: scroll
      });
    });
  }

  // Decide severity from score + tags
  function getSeverity(score, tags) {
    const tagSet = new Set(Array.isArray(tags) ? tags : []);

    const HIGH_TAGS = new Set([
      "data_sharing",
      "location_tracking",
      "camera_access",
      "microphone_access",
      "account_closure",
      "indemnity",
      "generic_high"
    ]);

    for (const t of tagSet) {
      if (HIGH_TAGS.has(t)) return "high";
    }

    if (score >= 3) return "high";
    if (score === 2) return "medium";
    if (score === 1) return "low";
    return "low";
  }

  // ----------------------
  // Load saved state
  // ----------------------
  chrome.storage.local.get(["autopolicy_email", "autopolicy_text"], (data) => {
    if (emailInput && data.autopolicy_email) {
      emailInput.value = data.autopolicy_email;
    }
    if (textArea && data.autopolicy_text) {
      textArea.value = data.autopolicy_text;
    }
  });

  if (emailInput) {
    emailInput.addEventListener("change", saveStateToStorage);
  }

  // ----------------------
  // Clear
  // ----------------------
  if (btnClear) {
    btnClear.addEventListener("click", () => {
      if (textArea) textArea.value = "";
      lastPageUrl = "";
      if (resultsSection) resultsSection.style.display = "none";
      if (statusDiv) {
        statusDiv.textContent = "Cleared text.";
        statusDiv.className = "status ok";
      }
      saveStateToStorage();
    });
  }

  // ----------------------
  // Use selected text on page
  // ----------------------
  if (btnUseSelection) {
    btnUseSelection.addEventListener("click", () => {
      if (!statusDiv) return;
      statusDiv.textContent = "Reading selected text from page...";
      statusDiv.className = "status";

      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (!tabs || !tabs[0]) {
          statusDiv.textContent = "No active tab found.";
          statusDiv.className = "status err";
          return;
        }
        const tabId = tabs[0].id;

        chrome.tabs.sendMessage(tabId, { type: "GET_SELECTION" }, (response) => {
          if (chrome.runtime.lastError) {
            console.error(chrome.runtime.lastError);
            statusDiv.textContent =
              "Could not read selection. Refresh the page and try again.";
            statusDiv.className = "status err";
            return;
          }

          if (!response || !response.text) {
            statusDiv.textContent =
              "No text selected. Please select some legal text first.";
            statusDiv.className = "status err";
            return;
          }

          if (textArea) textArea.value = response.text;
          lastPageUrl = tabs[0].url || "";
          statusDiv.textContent = "Selection copied. Now click 'Analyze risk'.";
          statusDiv.className = "status ok";

          saveStateToStorage();
        });
      });
    });
  }

  // ----------------------
  // Scan whole page
  // ----------------------
  if (btnScanPage) {
    btnScanPage.addEventListener("click", () => {
      if (!statusDiv) return;
      statusDiv.textContent = "Collecting text from the entire page...";
      statusDiv.className = "status";

      chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
        if (!tabs || !tabs[0]) {
          statusDiv.textContent = "No active tab found.";
          statusDiv.className = "status err";
          return;
        }
        const tabId = tabs[0].id;

        chrome.tabs.sendMessage(
          tabId,
          { type: "GET_FULL_PAGE_TEXT" },
          (response) => {
            if (chrome.runtime.lastError) {
              console.error(chrome.runtime.lastError);
              statusDiv.textContent =
                "Could not read page text. Refresh the page and try again.";
              statusDiv.className = "status err";
              return;
            }

            if (!response || !response.text) {
              statusDiv.textContent = "Could not extract text from this page.";
              statusDiv.className = "status err";
              return;
            }

            if (textArea) textArea.value = response.text;
            lastPageUrl = response.url || tabs[0].url || "";

            statusDiv.textContent =
              "Page text copied. Now click 'Analyze risk'.";
            statusDiv.className = "status ok";

            saveStateToStorage();
          }
        );
      });
    });
  }

  // ----------------------
  // Analyze risk (call Flask backend)
  // ----------------------
  if (btnAnalyze) {
    btnAnalyze.addEventListener("click", () => {
      if (!statusDiv) return;

      const email = emailInput
        ? (emailInput.value || "").trim() || "anonymous@local"
        : "anonymous@local";
      const text = textArea ? (textArea.value || "").trim() : "";

      if (!text) {
        statusDiv.textContent = "Please paste or select some text first.";
        statusDiv.className = "status err";
        return;
      }

      statusDiv.textContent = "Contacting AutoPolicy backend...";
      statusDiv.className = "status";

      saveStateToStorage();

      fetch("http://127.0.0.1:5000/api/analyze-text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_email: email,
          text: text,
          page_url: lastPageUrl || null
        })
      })
        .then((res) => {
          if (!res.ok) {
            throw new Error("Server returned " + res.status);
          }
          return res.json();
        })
        .then((data) => {
          renderResults(data);
          statusDiv.textContent = "Analysis complete.";
          statusDiv.className = "status ok";
        })
        .catch((err) => {
          console.error("Error calling API:", err);
          statusDiv.textContent = "Error: " + err.message;
          statusDiv.className = "status err";
          if (resultsSection) resultsSection.style.display = "none";
        });
    });
  }

  // ----------------------
  // Render results (CLICK => scroll+highlight)
  // ----------------------
  function renderResults(data) {
    if (!resultsSection) return;

    const total = data.total_clauses || 0;
    const riskyClauses = Array.isArray(data.risky_clauses)
      ? data.risky_clauses
      : [];
    const risky = riskyClauses.length;
    const percent =
      typeof data.risky_percent === "number" ? data.risky_percent : 0;
    const rating = data.overall_rating || "-";
    const breakdown = data.risk_breakdown || {};

    if (riskPercentSpan) {
      riskPercentSpan.textContent = percent.toFixed(2) + "%";
    }
    if (riskRatingSpan) {
      riskRatingSpan.textContent = rating;
    }
    if (riskCountSpan) {
      riskCountSpan.textContent = `${risky} / ${total}`;
    }

    if (ratingPill) {
      ratingPill.className = "pill";
      if (rating === "A") ratingPill.classList.add("pill-rating-A");
      else if (rating === "B") ratingPill.classList.add("pill-rating-B");
      else if (rating === "C") ratingPill.classList.add("pill-rating-C");
      else if (rating === "D") ratingPill.classList.add("pill-rating-D");
    }

    // Risk type chips
    if (riskTypesDiv) {
      riskTypesDiv.innerHTML = "";
      const keys = Object.keys(breakdown);
      if (keys.length === 0) {
        riskTypesDiv.textContent = "No specific risky categories detected.";
      } else {
        keys.forEach((k) => {
          const span = document.createElement("span");
          span.textContent = `${k}: ${breakdown[k]}`;
          riskTypesDiv.appendChild(span);
        });
      }
    }

    // Risky clauses list (CLICK => jump + highlight)
    if (clausesListDiv) {
      clausesListDiv.innerHTML = "";
      if (riskyClauses.length === 0) {
        const p = document.createElement("div");
        p.textContent = "No risky clauses found.";
        clausesListDiv.appendChild(p);
      } else {
        riskyClauses.slice(0, 10).forEach((c) => {
          const div = document.createElement("div");
          div.className = "clause-item";
          div.style.cursor = "pointer";

          const title = document.createElement("div");
          title.className = "clause-tag";
          const tags = Array.isArray(c.reasons) ? c.reasons : [];
          const score = typeof c.score === "number" ? c.score : 0;
          const severity = getSeverity(score, tags);

          title.textContent = `Clause ${c.clause_number} · Score ${score} · ${tags.join(
            ", "
          )}`;

          const textDiv = document.createElement("div");
          textDiv.textContent = c.text;

          // CLICK = highlight + scroll
          div.addEventListener("click", () => {
            highlightInPage(c.text, severity, true);
          });

          div.appendChild(title);
          div.appendChild(textDiv);
          clausesListDiv.appendChild(div);
        });

        if (riskyClauses.length > 10) {
          const more = document.createElement("div");
          more.style.marginTop = "4px";
          more.style.fontSize = "10px";
          more.style.color = "#9ca3af";
          more.textContent = `+ ${
            riskyClauses.length - 10
          } more clauses not shown here.`;
          clausesListDiv.appendChild(more);
        }
      }
    }

    resultsSection.style.display = "block";
  }
});