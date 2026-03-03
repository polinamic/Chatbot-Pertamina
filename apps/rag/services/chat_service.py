from apps.rag.services.retrieval import retrieve_context
from apps.rag.models import DocumentChunk
import ollama

SIMILARITY_THRESHOLD = 0.60  # sudah dikalibrasi untuk MiniLM


def get_chunk_text(chunk_id):
    try:
        chunk = DocumentChunk.objects.get(id=chunk_id)
        return chunk.content
    except DocumentChunk.DoesNotExist:
        return ""


def is_small_talk(text: str):
    text = text.lower().strip()

    greetings = [
        "halo", "hai", "hi", "permisi",
        "selamat pagi", "selamat siang",
        "selamat sore", "terima kasih"
    ]

    if text in greetings:
        return True

    if len(text.split()) <= 2 and any(text.startswith(g) for g in greetings):
        return True

    return False


def generate_llm_response(content, strict=False):

    if strict:
        system_prompt = """
Anda adalah AI IT Support internal perusahaan.

ATURAN KETAT:
- Jawab HANYA berdasarkan konteks.
- Jangan menambahkan informasi dari luar konteks.
- Jika informasi tidak tersedia, katakan:
  "Informasi tersebut tidak tersedia dalam sistem IT Support."
- Selalu gunakan Bahasa Indonesia.
"""
    else:
        system_prompt = """
Anda adalah AI IT Support profesional.
Selalu jawab dalam Bahasa Indonesia.
Gunakan bahasa yang ramah dan jelas.
"""

    response = ollama.chat(
        model="llama3:8b",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content}
        ]
    )

    return response["message"]["content"]


def chat(question, vector_store, embedding_service):

    # ================= SMALL TALK =================
    if is_small_talk(question):
        return generate_llm_response(question)

    # ================= RETRIEVAL =================
    results = retrieve_context(
        question,
        vector_store,
        embedding_service
    )

    if not results:
        return "Pertanyaan tersebut tidak tersedia dalam sistem IT Support."

    best_match = results[0]

    # ================= SIMILARITY CHECK =================
    if best_match["score"] < SIMILARITY_THRESHOLD:
        return "Pertanyaan tersebut tidak tersedia dalam sistem IT Support."

    # ================= STRICT RAG MODE =================
    context_texts = []

    for result in results[:3]:
        chunk_text = get_chunk_text(result["document_chunk_id"])
        if chunk_text:
            context_texts.append(chunk_text)

    if not context_texts:
        return "Pertanyaan tersebut tidak tersedia dalam sistem IT Support."

    combined_context = "\n\n".join(context_texts)

    prompt = f"""
KONTEKS:
{combined_context}

PERTANYAAN:
{question}
"""

    return generate_llm_response(prompt, strict=True)