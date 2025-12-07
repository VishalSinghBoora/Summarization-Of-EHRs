# app.py
import os
import io
import tempfile
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename
import PyPDF2
import docx
import google.generativeai as genai


# Paste your Gemini API key here (ONLY place to paste)
GEMINI_API_KEY = "ENTER YOUR API KEY HERE"


if not GEMINI_API_KEY or GEMINI_API_KEY == "PASTE_YOUR_KEY_HERE":
    raise RuntimeError("Paste your GEMINI API key inside app.py at GEMINI_API_KEY variable (line near top).")

genai.configure(api_key=GEMINI_API_KEY)

# Choose a model you have access to. If unsure, use "gemini-2.0-flash"
MODEL_NAME = "gemini-2.0-flash"

UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}
MAX_CHUNK_CHARS = 15000  # adjust if you use a bigger-context model

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024  # 200 MB

#file readers
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def read_txt_bytes(data: bytes):
    try:
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return data.decode("latin-1", errors="ignore")

def read_pdf_bytes(data: bytes):
    text_chunks = []
    reader = PyPDF2.PdfReader(io.BytesIO(data))
    for page in reader.pages:
        extracted = page.extract_text()
        if extracted:
            text_chunks.append(extracted)
    return "\n".join(text_chunks)

def read_docx_bytes(data: bytes):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        tmp.write(data)
        tmp.flush()
        tmp_name = tmp.name
    doc = docx.Document(tmp_name)
    os.unlink(tmp_name)
    return "\n".join([para.text for para in doc.paragraphs])

def extract_text_from_filestorage(filestorage):
    filename = secure_filename(filestorage.filename)
    ext = filename.rsplit(".", 1)[1].lower()
    data = filestorage.read()
    if ext == "pdf":
        return read_pdf_bytes(data)
    elif ext == "docx":
        return read_docx_bytes(data)
    else:
        return read_txt_bytes(data)

# -------------------------------
# Chunker
# -------------------------------
def chunk_text(text, max_chars=MAX_CHUNK_CHARS):
    text = text.strip()
    chunks = []
    while len(text) > max_chars:
        split_at = text[:max_chars].rfind(".")
        if split_at == -1 or split_at < int(max_chars * 0.6):
            split_at = max_chars
        else:
            split_at += 1
        chunks.append(text[:split_at].strip())
        text = text[split_at:].strip()
    if text:
        chunks.append(text)
    return chunks

# -------------------------------
# Gemini summarizer per chunk
# -------------------------------
def gemini_summarize_chunk(chunk, model_name=MODEL_NAME):
    prompt = f"""
You are a professional summarizer. Summarize the following text into short, factual bullet points.
If the text appears medical, organize bullets into Findings, Symptoms, Diagnosis, Treatment, Notes when relevant.
Be concise and factual. Return bullet points only.

TEXT:
{chunk}
"""
    model = genai.GenerativeModel(model_name)
    resp = model.generate_content(prompt)
    return resp.text.strip()

def summarize_full_text(text):
    chunks = chunk_text(text)
    parts = []
    for i, c in enumerate(chunks, start=1):
        summary = gemini_summarize_chunk(c)
        parts.append(f"### Summary Part {i}:\n{summary}")
    return "\n\n".join(parts)

# Routes to html and flask
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/summarize", methods=["POST"])
def summarize():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded."}), 400
    f = request.files["file"]
    if f.filename == "":
        return jsonify({"error": "No file selected."}), 400
    if not allowed_file(f.filename):
        return jsonify({"error": "Unsupported file type."}), 400

    try:
        text = extract_text_from_filestorage(f)
        if not text.strip():
            return jsonify({"error": "No text could be extracted from file."}), 400

        summary = summarize_full_text(text)
        return jsonify({"summary": summary})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/download", methods=["POST"])
def download():
    data = request.get_json()
    if not data or "summary" not in data:
        return jsonify({"error": "No summary provided"}), 400
    summary = data["summary"]
    return send_file(
        io.BytesIO(summary.encode("utf-8")),
        mimetype="text/plain",
        as_attachment=True,
        download_name="summary.txt"
    )

if __name__ == "__main__":
    app.run(debug=True, port=7860)
