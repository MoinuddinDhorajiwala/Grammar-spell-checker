const $ = (id) => document.getElementById(id);

let latestResult = null;
let selectedFile = null;

function setStatus(message = "", type = "") {
    const el = $("status");
    el.textContent = message;
    el.className = `status ${type}`;
}

function setLoading(button, loading, label) {
    button.disabled = loading;
    button.textContent = loading ? "Processing..." : label;
}

function renderResult(result) {
    latestResult = result;
    $("dashboard").classList.remove("hidden");

    const stats = result.original_stats || {};
    $("statWords").textContent = stats.words ?? 0;
    $("statSentences").textContent = stats.sentences ?? 0;
    $("statCharacters").textContent = stats.characters ?? 0;
    $("statCorrections").textContent = result.correction_count ?? 0;
    $("statUnique").textContent = stats.unique_words ?? 0;
    $("statAverage").textContent = stats.avg_sentence_words ?? 0;

    $("originalText").textContent = result.original_text || "";
    $("correctedText").textContent = result.corrected_text || "";
    $("fileName").textContent = result.filename || "";

    const topWords = $("topWords");
    topWords.innerHTML = "";
    (stats.top_words || []).forEach(item => {
        const chip = document.createElement("span");
        chip.className = "word-chip";
        chip.innerHTML = `${escapeHtml(item.word)} <b>${item.count}</b>`;
        topWords.appendChild(chip);
    });

    if (!topWords.children.length) {
        topWords.innerHTML = '<span class="muted">No frequent content words found.</span>';
    }

    const corrections = $("corrections");
    corrections.innerHTML = "";

    (result.corrections || []).slice(0, 30).forEach((item, index) => {
        const box = document.createElement("div");
        box.className = "correction-item";

        const replacement = item.replacements?.length
            ? `Suggestion: ${item.replacements.join(" / ")}`
            : "No replacement suggested";

        box.innerHTML = `
            <strong>${index + 1}. ${escapeHtml(item.message)}</strong>
            <small>${escapeHtml(replacement)}</small>
        `;

        corrections.appendChild(box);
    });

    if (!corrections.children.length) {
        corrections.innerHTML =
            '<div class="correction-item"><strong>No grammar or spelling issues found 🎉</strong></div>';
    }

    window.scrollTo({
        top: $("dashboard").offsetTop - 20,
        behavior: "smooth"
    });
}

async function checkText() {
    const text = $("textInput").value.trim();

    if (!text) {
        setStatus("Please enter some text first.", "error");
        return;
    }

    const button = $("checkTextBtn");
    setLoading(button, true, "Check Grammar & Spelling");
    setStatus("Checking your text...");

    try {
        const response = await fetch("/api/check-text", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text })
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "Text checking failed.");
        }

        renderResult(data);
        setStatus(
            `${data.correction_count} correction${data.correction_count === 1 ? "" : "s"} found.`,
            "success"
        );
    } catch (error) {
        setStatus(error.message, "error");
    } finally {
        setLoading(button, false, "Check Grammar & Spelling");
    }
}

async function checkFile() {
    if (!selectedFile) return;

    const button = $("checkFileBtn");
    const formData = new FormData();
    formData.append("file", selectedFile);

    setLoading(button, true, "Check File");
    setStatus(`Processing ${selectedFile.name}...`);

    try {
        const response = await fetch("/api/check-file", {
            method: "POST",
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || "File processing failed.");
        }

        renderResult(data);
        setStatus(
            `${selectedFile.name} processed successfully.`,
            "success"
        );
    } catch (error) {
        setStatus(error.message, "error");
    } finally {
        setLoading(button, false, "Check File");
    }
}

async function downloadFile(type) {
    if (!latestResult?.corrected_text) return;

    const endpoint = type === "pdf"
        ? "/api/download/pdf"
        : "/api/download/txt";

    const response = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            corrected_text: latestResult.corrected_text
        })
    });

    if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        setStatus(data.error || "Download failed.", "error");
        return;
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = type === "pdf" ? "corrected_text.pdf" : "corrected_text.txt";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
}

function handleFile(file) {
    if (!file) return;

    const extension = file.name.toLowerCase().split(".").pop();

    if (!["txt", "pdf"].includes(extension)) {
        setStatus("Please choose a TXT or PDF file.", "error");
        return;
    }

    if (file.size > 8 * 1024 * 1024) {
        setStatus("File is larger than the 8 MB limit.", "error");
        return;
    }

    selectedFile = file;
    $("selectedFile").textContent = `Selected: ${file.name}`;
    $("checkFileBtn").disabled = false;
    setStatus("");
}

function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = value ?? "";
    return div.innerHTML;
}

$("checkTextBtn").addEventListener("click", checkText);

$("clearTextBtn").addEventListener("click", () => {
    $("textInput").value = "";
    $("dashboard").classList.add("hidden");
    setStatus("");
});

$("fileInput").addEventListener("change", event => {
    handleFile(event.target.files[0]);
});

$("checkFileBtn").addEventListener("click", checkFile);
$("downloadTxtBtn").addEventListener("click", () => downloadFile("txt"));
$("downloadPdfBtn").addEventListener("click", () => downloadFile("pdf"));

const dropzone = $("dropzone");

["dragenter", "dragover"].forEach(eventName => {
    dropzone.addEventListener(eventName, event => {
        event.preventDefault();
        dropzone.classList.add("dragging");
    });
});

["dragleave", "drop"].forEach(eventName => {
    dropzone.addEventListener(eventName, event => {
        event.preventDefault();
        dropzone.classList.remove("dragging");
    });
});

dropzone.addEventListener("drop", event => {
    const file = event.dataTransfer.files[0];
    handleFile(file);
});
