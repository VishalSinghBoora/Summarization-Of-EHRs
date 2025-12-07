// static/app.js
const form = document.getElementById("uploadForm");
const fileInput = document.getElementById("fileInput");
const status = document.getElementById("status");
const resultSection = document.getElementById("resultSection");
const summaryEl = document.getElementById("summary");
const submitBtn = document.getElementById("submitBtn");
const downloadBtn = document.getElementById("downloadBtn");

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  resultSection.classList.add("hidden");
  status.textContent = "";
  if (!fileInput.files.length) {
    status.textContent = "Please choose a file.";
    return;
  }

  submitBtn.disabled = true;
  status.textContent = "Uploading and summarizing...";

  const fd = new FormData();
  fd.append("file", fileInput.files[0]);

  try {
    const res = await fetch("/summarize", { method: "POST", body: fd });
    submitBtn.disabled = false;

    if (!res.ok) {
      const err = await res.json();
      status.textContent = "Error: " + (err.error || res.statusText);
      return;
    }

    const j = await res.json();
    const summary = j.summary || "";
    summaryEl.textContent = summary;
    resultSection.classList.remove("hidden");
    status.textContent = "Done.";
    downloadBtn.disabled = false;

    downloadBtn.onclick = async () => {
      const downloadResp = await fetch("/download", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({summary})
      });
      if (downloadResp.ok) {
        const blob = await downloadResp.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = "summary.txt";
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
      } else {
        alert("Download failed.");
      }
    };

  } catch (err) {
    submitBtn.disabled = false;
    status.textContent = "Error: " + err.message;
  }
});
