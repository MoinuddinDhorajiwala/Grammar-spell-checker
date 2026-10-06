import io
import os
import re
from collections import Counter
from pathlib import Path

import requests
from flask import Flask, jsonify, render_template, request, send_file
from PyPDF2 import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 MB request limit

SUPPORTED_EXTENSIONS = {".txt", ".pdf"}
MAX_TEXT_PER_LT_REQUEST = 18000

# For a college/demo deployment this uses LanguageTool's public HTTPS API.
# For production, set LANGUAGETOOL_URL to your own LanguageTool server.
LANGUAGETOOL_URL = os.getenv(
    "LANGUAGETOOL_URL",
    "https://api.languagetool.org/v2/check",
)

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "if", "then", "than", "so",
    "of", "to", "in", "on", "at", "for", "from", "by", "with", "about",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "is", "am", "are", "was", "were", "be", "been", "being", "have",
    "has", "had", "do", "does", "did", "will", "would", "can", "could",
    "should", "may", "might", "must", "i", "you", "he", "she", "it",
    "we", "they", "me", "him", "her", "us", "them", "my", "your", "his",
    "its", "our", "their", "this", "that", "these", "those", "not",
}

# -----------------------------
# Text extraction
# -----------------------------
def extract_txt(file_storage):
    raw = file_storage.read()
    for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("The TXT file could not be decoded.")


def extract_pdf(file_storage):
    reader = PdfReader(file_storage)
    pages = []
    for page in reader.pages:
        pages.append(page.extract_text() or "")
    return "\n\n".join(pages)


def extract_uploaded_text(file_storage):
    filename = secure_filename(file_storage.filename or "")
    suffix = Path(filename).suffix.lower()

    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError("Only TXT and PDF files are supported.")

    if suffix == ".txt":
        text = extract_txt(file_storage)
    else:
        text = extract_pdf(file_storage)

    return normalize_text(text), filename


def normalize_text(text):
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\x00", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# -----------------------------
# NLP analysis
# -----------------------------
def analyze_text(text):
    words = re.findall(r"\b[A-Za-z]+(?:['-][A-Za-z]+)*\b", text)
    sentences = [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
    paragraphs = [p for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]

    lower_words = [word.lower() for word in words]
    content_words = [word for word in lower_words if word not in STOPWORDS]
    frequency = Counter(content_words)

    word_count = len(words)
    sentence_count = len(sentences)
    character_count = len(text)
    unique_words = len(set(lower_words))
    avg_sentence_words = round(word_count / sentence_count, 2) if sentence_count else 0
    lexical_diversity = round(unique_words / word_count, 3) if word_count else 0

    return {
        "words": word_count,
        "sentences": sentence_count,
        "characters": character_count,
        "paragraphs": len(paragraphs),
        "unique_words": unique_words,
        "avg_sentence_words": avg_sentence_words,
        "lexical_diversity": lexical_diversity,
        "top_words": [
            {"word": word, "count": count}
            for word, count in frequency.most_common(8)
        ],
    }


# -----------------------------
# LanguageTool
# -----------------------------
def split_for_language_tool(text):
    """Split long text into safe chunks for the LanguageTool public API."""
    if len(text) <= MAX_TEXT_PER_LT_REQUEST:
        return [text]

    chunks = []
    current = ""

    paragraphs = re.split(r"(\n\s*\n)", text)

    for part in paragraphs:
        if len(current) + len(part) <= MAX_TEXT_PER_LT_REQUEST:
            current += part
            continue

        if current.strip():
            chunks.append(current)
            current = ""

        # A single paragraph can itself be too long.
        while len(part) > MAX_TEXT_PER_LT_REQUEST:
            cut = part.rfind(" ", 0, MAX_TEXT_PER_LT_REQUEST)
            if cut < 1000:
                cut = MAX_TEXT_PER_LT_REQUEST
            chunks.append(part[:cut])
            part = part[cut:]

        current = part

    if current.strip():
        chunks.append(current)

    return chunks


def check_chunk(text):
    response = requests.post(
        LANGUAGETOOL_URL,
        data={
            "text": text,
            "language": "en-US",
            "enabledOnly": "false",
        },
        timeout=25,
    )
    response.raise_for_status()
    return response.json()


def correct_with_language_tool(text):
    """
    Check and correct text. Matches are returned for the UI.
    Corrections are applied from right to left so offsets remain valid.
    """
    chunks = split_for_language_tool(text)
    corrected_chunks = []
    all_matches = []

    for chunk in chunks:
        if not chunk.strip():
            corrected_chunks.append(chunk)
            continue

        try:
            data = check_chunk(chunk)
        except requests.RequestException as exc:
            raise RuntimeError(
                "LanguageTool could not be reached. "
                "Check your LANGUAGETOOL_URL or try again."
            ) from exc

        matches = data.get("matches", [])
        corrected = chunk

        for match in sorted(
            matches,
            key=lambda item: item.get("offset", 0),
            reverse=True,
        ):
            offset = match.get("offset", 0)
            length = match.get("length", 0)
            replacements = match.get("replacements") or []

            if not replacements:
                continue

            replacement = replacements[0].get("value", "")
            corrected = (
                corrected[:offset]
                + replacement
                + corrected[offset + length:]
            )

        chunk_offset = sum(len(value) for value in corrected_chunks)
        for match in matches:
            all_matches.append({
                "message": match.get("message", "Possible issue"),
                "context": match.get("context", ""),
                "offset": chunk_offset + match.get("offset", 0),
                "length": match.get("length", 0),
                "replacements": [
                    item.get("value", "")
                    for item in (match.get("replacements") or [])[:3]
                ],
                "rule": (match.get("rule") or {}).get("id", ""),
                "category": (match.get("rule") or {}).get(
                    "category", {}
                ).get("name", "Grammar"),
            })

        corrected_chunks.append(corrected)

    return "\n".join(corrected_chunks) if len(chunks) > 1 else corrected_chunks[0], all_matches


def process_text(text):
    text = normalize_text(text)

    if not text:
        raise ValueError("No text was provided.")

    original_stats = analyze_text(text)
    corrected, matches = correct_with_language_tool(text)
    corrected_stats = analyze_text(corrected)

    return {
        "original_text": text,
        "corrected_text": corrected,
        "original_stats": original_stats,
        "corrected_stats": corrected_stats,
        "corrections": matches,
        "correction_count": len(matches),
    }


# -----------------------------
# Downloads
# -----------------------------
def make_corrected_txt(text):
    return io.BytesIO(text.encode("utf-8"))


def make_corrected_pdf(text):
    output = io.BytesIO()
    doc = SimpleDocTemplate(
        output,
        pagesize=A4,
        rightMargin=45,
        leftMargin=45,
        topMargin=45,
        bottomMargin=45,
    )
    styles = getSampleStyleSheet()
    story = []

    for paragraph in re.split(r"\n\s*\n", text):
        safe = (
            paragraph.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br/>")
        )
        story.append(Paragraph(safe, styles["BodyText"]))
        story.append(Spacer(1, 10))

    doc.build(story)
    output.seek(0)
    return output


# -----------------------------
# Routes
# -----------------------------
@app.route("/")
def home():
    return render_template("index.html")


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "version": "3.0",
        "project": "NLP Grammar & Spell Checker",
        "supported_formats": ["txt", "pdf"],
    })


@app.route("/api/check-text", methods=["POST"])
def api_check_text():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "")

    if not isinstance(text, str):
        return jsonify({"error": "Text must be a string."}), 400

    try:
        return jsonify(process_text(text))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503


@app.route("/api/check-file", methods=["POST"])
def api_check_file():
    uploaded = request.files.get("file")

    if not uploaded or not uploaded.filename:
        return jsonify({"error": "Please upload a TXT or PDF file."}), 400

    try:
        text, filename = extract_uploaded_text(uploaded)

        if not text:
            return jsonify({
                "error": "No extractable text was found in this file."
            }), 422

        result = process_text(text)
        result["filename"] = filename
        return jsonify(result)

    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        app.logger.exception("File processing failed")
        return jsonify({
            "error": "The file could not be processed."
        }), 500


@app.route("/api/download/txt", methods=["POST"])
def download_txt():
    data = request.get_json(silent=True) or {}
    text = data.get("corrected_text", "")
    if not text:
        return jsonify({"error": "No corrected text supplied."}), 400

    return send_file(
        make_corrected_txt(text),
        mimetype="text/plain",
        as_attachment=True,
        download_name="corrected_text.txt",
    )


@app.route("/api/download/pdf", methods=["POST"])
def download_pdf():
    data = request.get_json(silent=True) or {}
    text = data.get("corrected_text", "")
    if not text:
        return jsonify({"error": "No corrected text supplied."}), 400

    return send_file(
        make_corrected_pdf(text),
        mimetype="application/pdf",
        as_attachment=True,
        download_name="corrected_text.pdf",
    )


@app.errorhandler(413)
def too_large(_error):
    return jsonify({
        "error": "Request too large. Maximum size is 8 MB."
    }), 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5050, debug=True)
