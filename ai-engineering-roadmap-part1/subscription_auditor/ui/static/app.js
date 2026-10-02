const fileInput = document.getElementById("fileInput");
const dropzone = document.getElementById("dropzone");
const dropTitle = document.getElementById("dropTitle");
const dropHint = document.getElementById("dropHint");
const auditBtn = document.getElementById("auditBtn");
const uploadError = document.getElementById("uploadError");

const progressCard = document.getElementById("progressCard");
const progressFill = document.getElementById("progressFill");
const progressPct = document.getElementById("progressPct");
const stagesEl = document.getElementById("stages");

const reportCard = document.getElementById("reportCard");
const reportBody = document.getElementById("reportBody");
const downloadReport = document.getElementById("downloadReport");
const downloadReport2 = document.getElementById("downloadReport2");
const downloadCsv = document.getElementById("downloadCsv");

let selectedFile = null;

/* ---------- File selection ---------- */
function setFile(file) {
  if (!file) return;
  if (!file.name.toLowerCase().endsWith(".pdf")) {
    showError("Please choose a PDF file.");
    return;
  }
  selectedFile = file;
  hideError();
  dropzone.classList.add("has-file");
  dropTitle.textContent = file.name;
  dropHint.textContent = `${(file.size / 1024).toFixed(0)} KB · ready to audit`;
  auditBtn.disabled = false;
}

fileInput.addEventListener("change", (e) => setFile(e.target.files[0]));

["dragenter", "dragover"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  })
);
["dragleave", "drop"].forEach((evt) =>
  dropzone.addEventListener(evt, (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");
  })
);
dropzone.addEventListener("drop", (e) => {
  const file = e.dataTransfer.files[0];
  fileInput.files = e.dataTransfer.files;
  setFile(file);
});

function showError(msg) {
  uploadError.textContent = msg;
  uploadError.hidden = false;
}
function hideError() {
  uploadError.hidden = true;
}

/* ---------- Stages UI ---------- */
function renderStages(stages) {
  stagesEl.innerHTML = "";
  stages.forEach((stage, i) => {
    const li = document.createElement("li");
    li.className = "stage";
    li.dataset.index = i;
    li.innerHTML = `
      <span class="dot">${i + 1}</span>
      <span class="stage-text">
        <b>${stage.label}</b>
        <small>${stage.detail}</small>
      </span>`;
    stagesEl.appendChild(li);
  });
}

function updateStages(activeIndex) {
  [...stagesEl.children].forEach((li, i) => {
    li.classList.remove("active", "done");
    const dot = li.querySelector(".dot");
    if (i < activeIndex) {
      li.classList.add("done");
      dot.textContent = "✓";
    } else if (i === activeIndex) {
      li.classList.add("active");
      dot.innerHTML = '<span class="spinner"></span>';
    } else {
      dot.textContent = i + 1;
    }
  });
}

function setProgress(percent) {
  progressFill.style.width = `${percent}%`;
  progressPct.textContent = percent;
}

/* ---------- Run the audit ---------- */
auditBtn.addEventListener("click", async () => {
  if (!selectedFile) return;
  auditBtn.disabled = true;
  auditBtn.textContent = "Uploading…";
  hideError();

  const form = new FormData();
  form.append("file", selectedFile);

  let data;
  try {
    const res = await fetch("/api/upload", { method: "POST", body: form });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Upload failed.");
    }
    data = await res.json();
  } catch (err) {
    showError(err.message);
    auditBtn.disabled = false;
    auditBtn.textContent = "Audit my statement";
    return;
  }

  reportCard.hidden = true;
  progressCard.hidden = false;
  renderStages(data.stages);
  updateStages(0);
  setProgress(5);
  progressCard.scrollIntoView({ behavior: "smooth", block: "center" });

  const source = new EventSource(`/api/progress/${data.jobId}`);
  source.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === "progress") {
      setProgress(msg.percent);
      updateStages(msg.activeIndex);
    } else if (msg.type === "done") {
      setProgress(100);
      updateStages(data.stages.length);
      showReport(data.jobId, msg.report, msg.hasCsv);
      source.close();
    } else if (msg.type === "error") {
      showError(msg.message);
      auditBtn.disabled = false;
      auditBtn.textContent = "Audit my statement";
      source.close();
    } else if (msg.type === "end") {
      source.close();
    }
  };
  source.onerror = () => source.close();
});

/* ---------- Show the report ---------- */
function showReport(jobId, markdown, hasCsv) {
  reportBody.innerHTML = markdown
    ? marked.parse(markdown)
    : "<p>The crew finished but no report was produced.</p>";

  const reportUrl = `/api/report/${jobId}/download`;
  downloadReport.href = reportUrl;
  downloadReport2.href = reportUrl;

  if (hasCsv) {
    downloadCsv.href = `/api/transactions/${jobId}/download`;
    downloadCsv.hidden = false;
  }

  reportCard.hidden = false;
  auditBtn.disabled = false;
  auditBtn.textContent = "Audit another statement";
  reportCard.scrollIntoView({ behavior: "smooth", block: "start" });
}
