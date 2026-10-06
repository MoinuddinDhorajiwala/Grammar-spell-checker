# NLP Grammar & Spell Checker

A complete Flask-based NLP mini project that:

- Checks typed text for grammar and spelling.
- Accepts `.txt` and `.pdf` files.
- Shows **Original vs Corrected** text side by side.
- Displays NLP statistics:
  - word count
  - sentence count
  - character count
  - paragraph count
  - unique words
  - average sentence length
  - lexical diversity
  - most frequent content words
- Displays grammar/spelling suggestions.
- Downloads corrected TXT and PDF files.
- Uses a responsive UI.
- Can be deployed to Vercel.

## Group

- Moinuddin Zaid Dhorajiwala — 231238
- Mohammed Aadil Kumshi — 231232
- Rohit Madhukar More — 231239

## Project Structure

```text
grammar-spell-check/
├── app.py
├── requirements.txt
├── vercel.json
├── .env.example
├── .gitignore
├── README.md
├── templates/
│   └── index.html
└── static/
    ├── app.js
    └── style.css
```

## Local setup

Use Python 3.10+.

```bash
python -m venv venv
```

Windows:

```bash
venv\Scripts\activate
```

macOS/Linux:

```bash
source venv/bin/activate
```

Install:

```bash
pip install -r requirements.txt
```

Run:

```bash
python app.py
```

Open:

```text
http://127.0.0.1:5050
```

## Vercel deployment

Vercel currently supports Flask applications directly with its Python runtime. The project intentionally keeps the Flask entry point at the root as `app.py`.

1. Push this folder to GitHub.
2. Open Vercel.
3. Import the GitHub repository.
4. Deploy.
5. No build command is required.

After deployment, test:

```text
https://YOUR-DOMAIN/health
```

You should receive a JSON response showing version `3.0`.

## LanguageTool note

The project uses the LanguageTool public HTTP API by default so that a Java LanguageTool server does not have to be bundled into a Vercel function.

The public API has documented limits, including a maximum of 20 KB per request and request-rate limits. This project chunks longer text to stay below the per-request limit, but the public service can still be rate-limited. For a serious/public production application, set `LANGUAGETOOL_URL` to your own LanguageTool server or use an appropriate LanguageTool service/account.

The public API also means submitted text is sent to LanguageTool. Make sure your project's privacy statement is appropriate for your users.

## Environment variable

Optional:

```text
LANGUAGETOOL_URL=https://api.languagetool.org/v2/check
```

For production, point it at your own LanguageTool server.

## API

### Check text

`POST /api/check-text`

```json
{
  "text": "This are a bad sentence."
}
```

### Check file

`POST /api/check-file`

Multipart field:

```text
file
```

Supported:

```text
.txt
.pdf
```

### Health

`GET /health`

### Download corrected TXT

`POST /api/download/txt`

```json
{
  "corrected_text": "Corrected text..."
}
```

### Download corrected PDF

`POST /api/download/pdf`

```json
{
  "corrected_text": "Corrected text..."
}
```

## Important PDF limitation

This project extracts text from normal/selectable PDFs. Scanned image-only PDFs need OCR and are not automatically readable by PyPDF2.

## NLP methodology

The processing pipeline is:

```text
User Text / TXT / PDF
        ↓
Text Extraction
        ↓
Text Normalization
        ↓
Tokenization
        ↓
NLP Statistics
        ↓
LanguageTool Grammar & Spell Check
        ↓
Correction Application
        ↓
Original vs Corrected Comparison
        ↓
Results + Suggestions + Downloads
```

## Future enhancements

- OCR for scanned PDFs
- DOCX support
- User authentication
- Correction history
- Custom dictionary
- Multiple language selection
- More advanced NLP visualizations
- Persistent database
