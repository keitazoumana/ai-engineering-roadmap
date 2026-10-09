/* The audit API. Set window.API_URL in config.js (no trailing slash). */
const API = (window.API_URL || "").replace(/\/+$/, "");

const fileInput = document.getElementById("fileInput");
const dropzone = document.getElementById("dropzone");
const dropTitle = document.getElementById("dropTitle");
const dropHint = document.getElementById("dropHint");
const auditBtn = document.getElementById("auditBtn");
const uploadError = document.getElementById("uploadError");

const progressCard = document.getElementById("progressCard");
const clockLabel = document.getElementById("clockLabel");
const clockEl = document.getElementById("clock");

const reportCard = document.getElementById("reportCard");
const reportEl = document.getElementById("report");
const downloadReport = document.getElementById("downloadReport");
const downloadCsv = document.getElementById("downloadCsv");

let file = null;
let clockTimer = null;

/* ---------- File selection ---------- */
function setFile(chosen) {
  if (!chosen) return;
  if (!chosen.name.toLowerCase().endsWith(".pdf")) {
    showError("Please choose a PDF file.");
    return;
  }
  file = chosen;
  hideError();
  dropzone.classList.add("has-file");
  dropTitle.textContent = chosen.name;
  dropHint.textContent = `${(chosen.size / 1024).toFixed(0)} KB · ready to audit`;
  auditBtn.disabled = false;
}

fileInput.addEventListener("change", (e) => setFile(e.target.files[0]));

["dragenter", "dragover"].forEach((evt) => {
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });
});
["dragleave", "drop"].forEach((evt) => {
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
  });
});
dropzone.addEventListener("drop", (e) => {
  fileInput.files = e.dataTransfer.files;
  setFile(e.dataTransfer.files[0]);
});

function showError(message) {
  uploadError.textContent = message;
  uploadError.hidden = false;
}
function hideError() {
  uploadError.hidden = true;
}

/* ---------- A local clock, so the user sees the audit is still running ---------- */
function startClock() {
  const started = Date.now();
  clockEl.textContent = "0:00";
  clockTimer = setInterval(() => {
    const seconds = Math.floor((Date.now() - started) / 1000);
    const mm = Math.floor(seconds / 60);
    const ss = String(seconds % 60).padStart(2, "0");
    clockEl.textContent = `${mm}:${ss}`;
    if (seconds > 20) {
      clockLabel.textContent = "Still working. Three agents are reviewing every charge.";
    }
  }, 1000);
}
function stopClock() {
  if (clockTimer) {
    clearInterval(clockTimer);
    clockTimer = null;
  }
}

/* ---------- Turn the PDF into base64 (without the data: prefix) ---------- */
function toBase64(pdf) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(",")[1]);
    reader.onerror = () => reject(new Error("Could not read the file."));
    reader.readAsDataURL(pdf);
  });
}

/* ---------- Run the audit ---------- */
async function start() {
  if (!API) {
    showError("Set your API URL in config.js first.");
    return;
  }
  hideError();
  auditBtn.disabled = true;
  auditBtn.textContent = "Uploading…";
  reportCard.hidden = true;
  progressCard.hidden = false;
  clockLabel.textContent = "Statement sent. The agents are reading it now.";
  progressCard.scrollIntoView({ behavior: "smooth", block: "center" });

  try {
    const pdfBase64 = await toBase64(file);
    startClock();
    const reply = await fetch(`${API}/audits`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: file.name, pdf_base64: pdfBase64 }),
    });
    const body = await reply.json();
    stopClock();
    if (!reply.ok) {
      throw new Error(body.error || `The audit failed (${reply.status}).`);
    }
    done(body);
  } catch (error) {
    stopClock();
    progressCard.hidden = true;
    showError(error.message);
  } finally {
    auditBtn.disabled = false;
    auditBtn.textContent = "Audit another statement";
  }
}

auditBtn.addEventListener("click", start);

/* ---------- Show the report ---------- */
function done(body) {
  progressCard.hidden = true;

  // The report is written by a model: sanitize it before showing it.
  reportEl.innerHTML = DOMPurify.sanitize(marked.parse(body.report_markdown || ""));

  downloadReport.href = toDownload(body.report_markdown || "", "text/markdown");
  if (body.transactions_csv) {
    downloadCsv.href = toDownload(body.transactions_csv, "text/csv");
    downloadCsv.hidden = false;
  } else {
    downloadCsv.hidden = true;
  }

  reportCard.hidden = false;
  reportCard.scrollIntoView({ behavior: "smooth", block: "start" });
}

function toDownload(text, type) {
  return URL.createObjectURL(new Blob([text], { type }));
}
