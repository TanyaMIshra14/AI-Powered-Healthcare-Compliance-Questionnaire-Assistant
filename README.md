# MediQuery AI — Healthcare Questionnaire Automation Tool

## Industry
Healthcare SaaS

## The Company
MediQuery AI is a compliance automation platform built for hospital security and operations teams. It helps healthcare organizations instantly complete vendor assessments, security reviews, and operational audits by using AI to search internal policy documents and generate accurate, cited answers. Instead of manually cross-referencing dozens of internal documents, compliance teams upload their reference materials once and let the system do the heavy lifting — cutting questionnaire turnaround from days to minutes while ensuring every answer is traceable back to an approved source.

---

## What I Built

Honestly, this started as a pretty straightforward RAG (Retrieval-Augmented Generation) pipeline, but it grew into a full end-to-end web application once I started thinking about what a real compliance team would actually need.

The core idea is simple: healthcare teams constantly receive long questionnaires from vendors, auditors, and regulators. Answering them manually means digging through policy docs, security guidelines, and internal wikis for hours. MediQuery AI automates that. You upload your questionnaire and your reference documents, click a button, and get back a full set of grounded answers with citations pointing to exactly which document the answer came from.

Here's what the system does under the hood:
- Chunks your reference documents and encodes them into vector embeddings using `sentence-transformers`
- Stores those embeddings in a FAISS index for fast similarity search
- For each question, retrieves the most relevant chunks from your documents
- Passes that context to a local Ollama model (Mistral by default) which generates a professional answer using only the provided context
- If nothing relevant is found, it honestly returns "Not found in references." rather than hallucinating an answer
- Saves everything to a SQLite database so you can come back to previous runs

---

## Features

- **User auth** — register and log in, each user's data is fully isolated
- **Upload questionnaire + references** — plain `.txt` files, one question per line
- **AI-generated answers** — grounded in your documents, never made up
- **Source citations** — every answer tells you which document it came from
- **Confidence scores** — so you know how strongly the answer is supported
- **Evidence snippets** — see the exact passage from the reference doc that was used
- **Edit answers** — review and tweak any answer before exporting
- **Regenerate individual answers** — re-run just one question without redoing everything
- **Version history** — all your past runs are saved and accessible
- **Export to Word** — downloads a clean `.docx` with all questions, answers, and citations

---

## Tech Stack

| Layer | What I used |
|---|---|
| Backend | FastAPI + SQLAlchemy (SQLite) |
| AI / LLM | Ollama running locally (Mistral by default) |
| Embeddings | `sentence-transformers` (all-MiniLM-L6-v2) |
| Vector search | FAISS |
| Export | `python-docx` |
| Frontend | Jinja2 templates + vanilla CSS |

---

## How to Run It

### 1. Prerequisites

Make sure you have these installed:
- Python 3.10 or higher
- [Ollama](https://ollama.com) — this is what runs the AI model locally on your machine

### 2. Pull the AI model

Once Ollama is installed, open a terminal and run:
```bash
ollama pull mistral
```
This downloads the Mistral model (~4GB). You only need to do this once.

### 3. Start Ollama

In a terminal, keep this running in the background:
```bash
ollama serve
```

### 4. Set up the project

Open a new terminal, go to the project folder, and run:
```bash
# Create a virtual environment
python -m venv venv

# Activate it (Windows)
venv\Scripts\activate

# Activate it (Mac/Linux)
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 5. Start the app
```bash
uvicorn main:app --reload
```

Then open your browser and go to: **http://localhost:8000**

---

## Using the App

1. **Sign up** with any email and password on the login page
2. **Go to the dashboard** — you'll see the upload panel
3. **Upload your questionnaire** — a `.txt` file with one question per line
4. **Upload your reference documents** — the `.txt` files that contain your source of truth (policy docs, security guidelines, etc.)
5. **Click Generate Answers** — grab a coffee, it usually takes 1-3 minutes depending on how many questions you have
6. **Review the results** — each answer shows the source citation, confidence score, and an evidence snippet from the original document
7. **Edit anything** that needs tweaking directly in the browser
8. **Export** — download a `.docx` file with the full completed questionnaire

---

## Assumptions I Made

- Questionnaire files are plain `.txt` with one question per line — I kept this simple intentionally since the AI logic is where the complexity lives
- Reference documents are also `.txt` — in production you'd want PDF parsing too, but this was sufficient to demonstrate the RAG pipeline
- SQLite is fine for a demo — a real deployment would use PostgreSQL
- Running locally with Ollama means no API keys, no costs, no data leaving your machine

---

## What I'd Improve With More Time

- **PDF support** for both questionnaires and reference docs — most real compliance docs are PDFs
- **Streaming answers** so you see results appear question by question instead of waiting for all of them
- **Persistent FAISS index** so reference docs don't get re-indexed on every upload
- **Better chunking** — right now it's fixed-size chunks; semantic chunking would improve retrieval quality
- **JWT-based auth** instead of a plain cookie
- **A proper job queue** (like Celery) so answer generation runs in the background and the browser doesn't have to stay open