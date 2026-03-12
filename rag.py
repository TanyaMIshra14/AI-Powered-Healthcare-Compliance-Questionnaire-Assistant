import os
import faiss
import numpy as np
import requests
from sentence_transformers import SentenceTransformer

# Load embedding model once at startup
model = SentenceTransformer("all-MiniLM-L6-v2")

# Ollama config
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "mistral")


def _call_ollama(prompt: str) -> str:
    try:
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/generate",
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.2, "num_predict": 512}
            },
            timeout=120
        )
        resp.raise_for_status()
        return resp.json().get("response", "").strip()
    except requests.exceptions.ConnectionError:
        return (
            f"Error: Could not connect to Ollama at {OLLAMA_BASE_URL}. "
            "Make sure Ollama is running ('ollama serve') and the model is pulled "
            f"('ollama pull {OLLAMA_MODEL}')."
        )
    except requests.exceptions.Timeout:
        return "Error: Ollama request timed out. The model may still be loading — try again."
    except Exception as e:
        return f"Error calling Ollama: {str(e)}"


def chunks(text, size=500, overlap=50):
    result = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        result.append(text[start:end])
        start += size - overlap
    return result


def build_index(reference_folder):
    texts = []
    sources = []

    if not os.path.exists(reference_folder) or not os.listdir(reference_folder):
        return None, [], []

    for file in sorted(os.listdir(reference_folder)):
        file_path = os.path.join(reference_folder, file)
        if not file.endswith(".txt"):
            continue
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read().strip()
                if not content:
                    continue
                for chunk in chunks(content):
                    texts.append(chunk)
                    sources.append(file)
        except Exception:
            continue

    if not texts:
        return None, [], []

    embeddings = model.encode(texts, show_progress_bar=False)
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(np.array(embeddings, dtype=np.float32))
    return index, texts, sources


def generate_answer(question, index, texts, sources):
    if index is None or not texts:
        return {
            "answer": "Not found in references.",
            "citation": "None",
            "confidence": "0.00",
            "evidence": "No reference documents were uploaded."
        }

    question_embedding = model.encode([question], show_progress_bar=False)
    D, I = index.search(np.array(question_embedding, dtype=np.float32), k=min(5, len(texts)))

    valid_indices = [i for i in I[0] if 0 <= i < len(texts)]
    if not valid_indices:
        return {
            "answer": "Not found in references.",
            "citation": "None",
            "confidence": "0.00",
            "evidence": "No relevant content found."
        }

    retrieved_texts = [texts[i] for i in valid_indices]
    retrieved_sources = [sources[i] for i in valid_indices]
    retrieved_distances = [float(D[0][idx]) for idx in range(len(valid_indices))]

    context = "\n\n---\n\n".join(
        [f"[Source: {src}]\n{txt}" for src, txt in zip(retrieved_sources, retrieved_texts)]
    )

    prompt = f"""You are an expert answering a healthcare compliance/security questionnaire.

Use ONLY the context provided below. Do NOT use any external knowledge.
If the answer is not in the context, respond EXACTLY with: Not found in references.

Context:
{context}

Question: {question}

Answer (2-5 sentences, professional, cite specific details from context):"""

    answer = _call_ollama(prompt)

    avg_distance = sum(retrieved_distances) / len(retrieved_distances)
    confidence = round(max(0.0, min(1.0, 1 / (1 + avg_distance * 0.1))), 2)

    if "not found in references" in answer.lower() or answer.startswith("Error:"):
        confidence = 0.0

    return {
        "answer": answer,
        "citation": ", ".join(sorted(set(retrieved_sources))),
        "confidence": str(confidence),
        "evidence": retrieved_texts[0] if retrieved_texts else "N/A"
    }
